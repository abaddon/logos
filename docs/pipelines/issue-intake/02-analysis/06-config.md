# 6 — Config surface, entrypoint, and install

## 6.1 Where the code lives

One script and one test module. No package, no dependencies beyond the standard
library (`urllib.request`, `json`, `os`, `subprocess`, `re`, `argparse`).

```
tools/issue_intake.py           # the whole pipeline, ~350 lines
tests/test_issue_intake.py      # unittest; uses the fixtures in 03-dossiers/04-selection-fixtures.json
~/.hermes/scripts/logos-issue-intake.sh   # 5-line cron shim (outside the repo)
```

`tests.test_issue_intake` is added to `CONTRACT_TESTS` in the `Makefile` (one
line, next to `tests.test_docs`), so `make test` runs it. Without that line the
tests exist and never gate anything.

No third-party HTTP client: `urllib.request` is enough for one GET with headers,
and the repo has no Python dependencies today (it deliberately deleted its only
Python implementation — adding `requests` would be a supply-chain decision
nobody made).

## 6.2 The config block

Every value below is a module constant **and** an environment override, read
once at start-up. No config file, no CLI flag for values that are policy.

```python
REPO            = os.environ.get("LOGOS_INTAKE_REPO", "abaddon/logos")
API_BASE        = os.environ.get("LOGOS_INTAKE_API", "https://api.github.com")
TOKEN_ENV       = "GITHUB_TOKEN"                    # read at call time, never logged
BOARD           = os.environ.get("LOGOS_INTAKE_BOARD", "logos")
REPO_ROOT       = os.environ.get("LOGOS_INTAKE_REPO_ROOT", "/root/ai-language-program")
STATE_PATH      = os.environ.get("LOGOS_INTAKE_STATE",
                                 "~/.local/state/logos-issue-intake/state.json")
HERMES_BIN      = os.environ.get("LOGOS_INTAKE_HERMES", "hermes")

MAX_PICKS       = int(os.environ.get("LOGOS_INTAKE_MAX_PICKS", "2"))
PER_PAGE        = 100
MAX_PAGES       = 10
MAX_BODY_CHARS  = 6000
MAX_TITLE_CHARS = 120
UMBRELLA_MAX_REFS = 8
HTTP_TIMEOUT    = (10, 30)          # (connect, read)
CLI_TIMEOUT     = 60                # seconds for one `hermes kanban create`
LOCK_STALE_S    = 600

DEFAULT_ASSIGNEE = "backend-engineer"
LABEL_ASSIGNEE = {
    "docs": "oss-contributor",
    "documentation": "oss-contributor",
    "good first issue": "oss-contributor",
}
EXCLUDED_LABELS = {"question", "needs-info", "invalid", "wontfix",
                   "duplicate", "superseded", "in-progress"}
SUBSYSTEM_LABELS = {"compiler", "runtime", "docs", "documentation",
                    "target", "accessibility", "tooling"}
SUBSYSTEM_PREFIX = {                # title prefix -> subsystem
    "docs": "docs", "documentation": "docs", "manual": "docs",
    "compiler": "compiler", "language": "compiler",
    "stdlib": "stdlib", "tooling": "tooling",
    "examples": "examples", "target": "target",
}
STRUCTURAL_PHRASES = ("blocked by", "depends on", "sequenced after", "part of",
                      "sub-issue of", "subissue of", "parent:", "follow-up to",
                      "followup to", "tracking issue for")
```

`LOGOS_INTAKE_MAX_PICKS` exists for the operator who wants 1 during a busy week;
it is clamped to the range `0..5` and the clamp is logged when it bites, so a
typo cannot turn the board into a firehose.

## 6.3 The entrypoint

```sh
python3 tools/issue_intake.py --once            # one run, the cron path
python3 tools/issue_intake.py --once --dry-run  # decide and report, write nothing
python3 tools/issue_intake.py --once --include-backlog   # ignore backlog_cutoff once
python3 tools/issue_intake.py --forget 52       # drop state entry for #52, exit
```

`--dry-run` fetches and decides, prints the decision table, writes **no** state,
creates **no** task, and does not even take the lock (it is read-only):

```
DRY RUN  repo=abaddon/logos open=38 unseen=3 ready=2
  pick   #52  docs     oss-contributor        [logos#52] docs: limits.md says a non-finite float literal …
  skip   #86  docs     —                      subsystem-collision with #52
  skip   #96  docs     —                      blocked by #52,#78,#82,#86,#90
  create 0 (dry run, state untouched)
```

`--once` is required; there is no daemon mode. The hourly schedule belongs to
cron, and a looping script would hold the lock forever.

## 6.4 Exit codes

| code | meaning | cron behaviour |
|---|---|---|
| 0 | ran, including clean no-ops and the lock-skip | silent unless something was created |
| 65 | unrecoverable input problem (auth, repo, corrupt state, pagination cap) | delivers the error line; a human must look |
| 75 | transient (rate limit, 5xx, create failure) | delivers the error line; the next hour retries |

## 6.5 The cron install (one time)

The poller is a script job, not an agent job: `--no-agent` runs the script on
schedule and delivers its stdout verbatim, with no model in the loop. Empty
stdout is silent, which is exactly the "nothing new" case.

The install is a script, not a hand-typed command, because there are five things
to write (env file, log rotation, failure markers, the runner copy, the job) and
four of them have a permission that matters:

```sh
bash tools/install_issue_intake_schedule.sh                  # this checkout
bash tools/install_issue_intake_schedule.sh --repo-root PATH  # another one
```

It is idempotent: it keeps an existing `GITHUB_TOKEN`, rewrites
`/etc/logos-issue-intake/env` at `0600`, installs the runner as
`$HERMES_HOME/scripts/logos-issue-intake.sh`, and edits the job in place if a job
named `logos-issue-intake` already exists, so run history survives. The job it
leaves behind is the one §6.5 always specified:

```
hermes cron create "0 * * * *" --name logos-issue-intake --no-agent \
  --script logos-issue-intake.sh --deliver local --workdir /root/ai-language-program
```

`--deliver local` keeps the run's one-line output in `hermes cron runs` instead
of messaging the operator every hour; raise it to `origin` (or a chat target) if
the operator wants the created-task lines pushed, or set `--failure-deliver` to
push only failures. `hermes cron runs --name logos-issue-intake` is then the run
history, and the state file is the ledger.

`0 * * * *` is on the hour. The gateway dispatcher ticks every 60 s, so a task
created at `HH:00:03` is claimed within a minute. Do not schedule at `*/60` in
minutes-of-hour form and do not add a minute offset — an on-the-hour run keeps
the log timestamps aligned with the operator's mental model.

`08-operations.md` is the operational chapter: what is installed, the log, the
failure ladder, overlap behaviour, and how to remove it.

Do **not** run this from a dispatched kanban worker (see `04-task-creation.md`
§4.1): the CLI refuses board mutations from a delegate child, and the failure is
invisible because the worker's stdout is its own report, not the pipeline's.

## 6.6 What is deliberately not configurable

- The endpoint shape (`state=open`, `sort=created`, `direction=asc`): the
  selection rule's FIFO depends on it.
- `--workspace`/`--branch` shape: determined by the issue number.
- State schema: versioned, not templated.
- Token environment variable **name**: `GITHUB_TOKEN` only, so a token pasted
  into a config file elsewhere is not silently picked up.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/01-polling.md
 -> the query these constants feed
docs/pipelines/issue-intake/03-dossiers/03-hermes-cli-evidence.md
 -> `hermes cron create` flags as printed by the installed CLI
docs/pipelines/issue-intake/02-analysis/07-scenarios.md
 -> the dry-run table above, worked against real issues
