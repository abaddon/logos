# Issue intake — operator runbook

The intake reads the open issues of `abaddon/logos` once an hour and creates one
Hermes Kanban task on the `logos` board for each issue it picks. It picks **at
most two issues per hour, oldest first**, and only issues that are
**independent**: neither mentions the other (`#N` in its title or body), and
their subsystems (docs, compiler, stdlib, tooling, examples, target — from the
title prefix or a label) are disjoint. The first run on an empty state seeds
every open issue and picks nothing, so only issues opened after that are ever
picked.

Everything below runs as root on this host.

## Where it lives

| Piece | Path |
|---|---|
| pipeline and tests | `tools/issue_intake.py`, `tests/test_issue_intake.py` |
| runner (what the schedule executes) | `/root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh` — source `tools/issue_intake_schedule.sh` |
| config, and the only secret | `/etc/logos-issue-intake/env` — `0600 root:root`; `GITHUB_TOKEN`, `LOGOS_INTAKE_REPO`/`_BOARD`/`_REPO_ROOT`/`_CODE_ROOT`/`_CODE_FALLBACK`/`_HERMES`, `HERMES_KANBAN_DB`, `PATH`. Never `cat` it. |
| state | `/root/.local/state/logos-issue-intake/state.json` (`0600`, dir `0700`), lock `state.json.lock` |
| log | `/var/log/logos-issue-intake.log` (`0640 root:adm`, daily, 14 kept) |
| failure markers | `/var/lib/logos-issue-intake/` — `consecutive_failures`, `ALERT` |
| schedule | `hermes cron` job `logos-issue-intake`, id `33a81bc1bb13`, `0 * * * *`, `--no-agent --deliver local` |
| board | `logos`, `/root/.hermes/kanban/boards/logos/kanban.db` |

`hermes cron` reads one profile's jobs, and this job lives in the
platform-engineer profile — export this in every shell you run it from, or you
read another profile's cron and see no jobs:

```sh
export HERMES_HOME=/root/.hermes/profiles/platform-engineer
```

`hermes kanban` and the log need no profile. The log's `code=` names the
checkout that ran.

## Is it healthy?

```sh
export HERMES_HOME=/root/.hermes/profiles/platform-engineer
tail -n 20 /var/log/logos-issue-intake.log
ls -l /var/lib/logos-issue-intake/     # ALERT present = 3 failures in a row
hermes cron list                       # Last run / Next run
hermes cron status                     # the gateway is what fires jobs
```

A healthy hour writes one line and stops:

```
2026-11-20T13:00:30Z RUN code=/root/ai-language-program repo=abaddon/logos board=logos rc=0 dur=1s
```

When there was something to report, the pipeline appends
`fetched=… prs=… unseen=… ready=… picked=… created=… failed=…` (with
`picks=#N`) and an `ERROR …` line per failure. Healthy: a `RUN` line every hour
at `HH:00`, `rc=0`, no `ALERT`, and `state.last_run_at` under an hour old —
silence is success. Stalled: no `RUN` for 75 minutes. If `hermes cron status`
says the gateway is down, no job fires and the pipeline is not the fault; an old
`Last run` or a past `Next run` in `hermes cron list` says the scheduler
stopped, not the poller.

## What has it picked?

`state.json` is the ledger: `issues` is keyed by issue number, and `outcome` is
`seeded` (existed at the first run, never picked), `picked` (a card exists, with
`task_id`) or `skipped` (not eligible that hour, re-tested every hour).

```sh
jq -r '.issues | to_entries[] | select(.value.outcome=="picked") | "\(.key)\t\(.value.task_id)"' \
  /root/.local/state/logos-issue-intake/state.json
jq -r '.issues[].outcome' /root/.local/state/logos-issue-intake/state.json | sort | uniq -c
jq -r '.last_run_at' /root/.local/state/logos-issue-intake/state.json
```

Empty output means nothing has been picked yet. An issue missing from `issues`
has never been seen; `--forget N` deletes an entry, and the next run with
`--include-backlog` can pick it again (the command is under **Corrupt state**).

## Run it by hand

Dry run — fetches, decides, prints, writes nothing, takes no lock:

```sh
( set -a; . /etc/logos-issue-intake/env; set +a
  code=$LOGOS_INTAKE_CODE_ROOT
  [ -f "$code/tools/issue_intake.py" ] || code=$LOGOS_INTAKE_CODE_FALLBACK
  cd "$code" && exec python3 tools/issue_intake.py --once --dry-run )
```

```
DRY RUN  repo=abaddon/logos not-modified unseen=0 ready=0
  create 0 (dry run, state untouched)
```

A quiet repo answers `not-modified`; otherwise the table lists `pick` and `skip`
per unseen issue, with the reason.

Real run — exactly what the schedule executes, env and log line included:

```sh
/root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
```

Exit `0` ran (including nothing new), `65` auth/repo/state, `75` rate limit,
5xx, timeout or create failure. Do not run it from a dispatched Kanban worker:
the board CLI refuses card creation there and the run exits 75.

Pause and resume; the job and its history survive:

```sh
export HERMES_HOME=/root/.hermes/profiles/platform-engineer
hermes cron pause 33a81bc1bb13
hermes cron resume 33a81bc1bb13
```

## When it breaks

**401 / expired token.** `ERROR auth/repo status=401` with
`url=https://api.github.com/…`, exit 65. A quiet repo hides it — a 304 answers
before the credential is checked — so it surfaces only when the repo next
changes. Refresh and reinstall (the installer re-reads the token from `gh`,
keeps the job id, writes `0600`, never prints the token):

```sh
export HERMES_HOME=/root/.hermes/profiles/platform-engineer
gh auth login
rm -f /etc/logos-issue-intake/env
bash tools/install_issue_intake_schedule.sh    # from the checkout named by code= in the log
```

Then dry-run and do one real run; success clears `consecutive_failures` and
`ALERT`.

**Rate limit.** `ERROR rate-limited remaining=0 reset=<ISO>` or
`ERROR secondary-limit retry-after=<s>`, exit 75. The next hourly run retries;
do nothing unless it repeats, then find who shares the token with
`gh api rate_limit --jq .rate`.

**Duplicate cards.** The pipeline cannot make them — it creates with
`--idempotency-key logos-issue-<n>`. They come from a manual create, or from
archiving a card whose state entry is gone. List and archive the extra, keeping
the card the ledger names:

```sh
hermes kanban --board logos list --json \
  | jq -r '.[] | select(.title|startswith("[logos#52]")) | "\(.id)\t\(.status)"'
hermes kanban --board logos archive <task-id>
hermes kanban --board logos archive --rm <task-id>   # permanent, after archiving
```

**Board / create failure.** `ERROR create failed issue=#N rc=1`, exit 75. The
run stops at the first failure and writes no `picked` entry. The line carries the
CLI's own first stderr line as `err=…`; with no `err=`, the CLI printed nothing
(or the create timed out), so reproduce it from a plain shell:
`hermes kanban --board logos list` (is the board reachable?) and check
that `env | grep HERMES_DELEGATED_CHILD_CONTEXT` is empty. A failed run still
saves the ETag, so the next hour answers 304 and does not retry until the repo
changes; to retry now, drop the ETag and run again:

```sh
f=/root/.local/state/logos-issue-intake/state.json
jq 'del(.last_etag)' "$f" > "$f.tmp" && chmod 600 "$f.tmp" && mv "$f.tmp" "$f"
/root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
```

**Corrupt state.** `ERROR state-corrupt path=… error=…`, exit 65 — the path is
the `state.json.corrupt-<epoch>` copy. The bad file is already renamed aside;
the next run bootstraps — seeds every open issue, picks nothing. **Deleting the
state file is safe for the board** — cards stay, and the idempotency key
prevents a second card — but you lose the ledger: which issues were picked,
their `task_id`, `backlog_cutoff` and the ETag. Issues opened since the last
good write are seeded too, so re-arm the ones you want (verified: after
`--forget 10`, the dry run picked #10):

```sh
python3 tools/issue_intake.py --forget 52
python3 tools/issue_intake.py --once --include-backlog --dry-run   # drop --dry-run to create
```

Inspect the bad copy with `jq . state.json.corrupt-<epoch>`, then delete it.

## Known limits

- **Two per hour.** `LOGOS_INTAKE_MAX_PICKS` in the env file (default 2, clamped
  0–5); the next run uses a changed value.
- **No auto-close.** Completing a Kanban task does not close the GitHub issue.
- **No PR linkage.** The card carries the issue URL, assignee and branch name;
  nothing links the card, its branch and a pull request.
- **One card per issue number.** An edited issue is not re-picked (the log gains
  `edited=#N`); `--forget N` then `--include-backlog` re-arms it.

Sources: [`03-dossiers/05-installed-schedule.md`](03-dossiers/05-installed-schedule.md)
(install), [`02-analysis/08-operations.md`](02-analysis/08-operations.md) (design).
