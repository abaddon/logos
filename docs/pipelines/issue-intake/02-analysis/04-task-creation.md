# 4 — Task creation

One picked issue becomes exactly one board task, on the `logos` board, assigned
to a profile that exists. The create call is a single `hermes kanban create`
invocation per issue; the script never writes to the kanban database directly.

## 4.1 The invocation

```sh
hermes kanban --board logos create "[logos#52] docs: limits.md says a non-finite float literal prints inf; the compiler refuses it" \
  --assignee oss-contributor \
  --workspace "worktree:/root/ai-language-program/.worktrees/gh-52" \
  --branch "wt/gh-52" \
  --idempotency-key "logos-issue-52" \
  --created-by "logos-issue-intake" \
  --body-file /root/.local/state/logos-issue-intake/body-52.tmp \
  --json
```

| Flag | Value | Why exactly this |
|---|---|---|
| `--board logos` | config `BOARD`, default `logos` | the board whose `board.json` is `{"slug":"logos","project_id":"p_f033e8d1","default_workdir":"/root/ai-language-program"}` |
| title | `[logos#<num>] <issue title>` | stable, greppable, and one glance identifies provenance; the number makes the mapping to GitHub unambiguous even when two issues share a title prefix |
| `--assignee` | mapped profile, §4.4 | a task with no assignee is never dispatched |
| `--workspace worktree:<path>` + `--branch wt/gh-<num>` | explicit, deterministic | an explicit path works whether or not the running profile's `projects.db` knows the board's project; the worker creates the worktree on claim if it is missing |
| `--idempotency-key logos-issue-<num>` | one per issue, forever | the CLI returns the existing non-archived task with that key instead of creating a duplicate |
| `--created-by logos-issue-intake` | fixed string | every board row the robot made is attributable without reading titles |
| `--body-file` | temp file under the state dir | the body has newlines and lines starting with `-`; `--body` would fight shell quoting |
| `--json` | fixed | stdout is `_task_to_dict(task)`; the task id is the `"id"` key |

The invocation is the only place the pipeline touches the board, and it must run
from a host shell (cron), **not** from inside a dispatched worker: a
`delegate_task` child gets `kanban: delegate_task child contexts cannot mutate
Kanban tasks or boards` and the run would fail silently every hour. That refusal
is measured, not assumed.

`HERMES_BIN` (default `hermes`, resolved from `PATH`) is config so the script can
be tested against a shim.

Parse: `json.loads(stdout)["id"]`. Non-zero exit, empty stdout, or a body that
is not JSON ⇒ the create **failed** (see `05-failure-and-idempotency.md`); do
not guess an id and do not write `picked`.

## 4.2 Title

```
title = "[logos#" + str(num) + "] " + issue.title
if len(title) > MAX_TITLE_CHARS (120): title = title[:117] + "..."
```

The `[logos#<num>]` prefix is never truncated; truncation applies to the issue
title. Titles are the operator's only index into the board, so an overlong
GitHub title is cut rather than the provenance.

## 4.3 Body template (verbatim, field by field)

```markdown
Imported from https://github.com/abaddon/logos/issues/52 by `logos-issue-intake`.

- **Issue:** https://github.com/abaddon/logos/issues/52
- **Title:** docs: `limits.md` says a non-finite float literal prints `inf`; the compiler refuses it
- **Labels:** good first issue, docs
- **Opened by:** <login> at 2026-11-19T00:38:20Z
- **Updated on GitHub:** 2026-11-19T00:38:20Z
- **Subsystem:** docs
- **Picked by run:** 2026-11-20T12:00:01Z

## Acceptance criteria (inherited from the issue)

**Done when:** both rows state what the compiler does (a non-finite float literal
is `E0106` at check time), `grep -rn "accepted.*inf" docs/` returns nothing, and
`bash tools/check_doc_links.sh .` still reports 0 broken.

## Repository gates

This repository's definition of done is not negotiable and is not restated from
the issue: `bash tools/pr_gate.sh` must pass, every commit carries a DCO
sign-off (`git commit --signoff`), and a compiler change also rebuilds
`bootstrap/logosc` in the same pull request. Read `AGENTS.md` before starting.

## Issue body (verbatim, truncated at 6000 characters)

<issue body>
```

Rules:

- **Labels** render as a comma-joined list, or `(none)`.
- **Opened by / Updated on GitHub** are copied from the API object, unmodified
  ISO-8601. They are the fields that let a later reader tell whether the card is
  describing the issue's current text.
- **Picked by run** is the run's start time — the same value as `last_run_at`
  for that run — so a card can be matched to a log line.
- The **Repository gates** section is fixed text. It is present on every card
  because issue bodies in this repo assume it (`**Done when:**` bullets cite
  `bash tools/check_doc_links.sh`, `python3 -m unittest tests.test_docs`,
  `./tools/logosc.sh guide --check`), and a worker that never read `AGENTS.md`
  would otherwise run one of those and call the job done.
- The **issue body** is the raw Markdown, not a summary. Truncation happens only
  past `MAX_BODY_CHARS = 6000` characters, on a line boundary, and appends:

  ```
  …[truncated: 1234 characters omitted; read the full issue at the URL above]
  ```

  34 of the 38 open issues are under 6000 characters today, so truncation is a
  guard against one enormous issue, not a routine event.

## 4.4 Acceptance-criteria extraction

The section must contain the issue's own completion test, verbatim, because that
is the only part of a GitHub issue that survives translation into a task card.
Algorithm, in order — first match wins:

1. **`**Done when**` marker.** Find the first line matching
   `(?i)^\*\*done when` (`**Done when:**` — 34 of 38 issues — and the one
   `**Done when.**`). Take from the end of that marker to the next line
   matching `^\*\*[A-Z]`, `^## `, `^---`, or EOF. Emit the marker's own sentence
   followed by the bullets, unchanged.
2. **Task list.** Else, if the body has a contiguous run of lines matching
   `^\s*[-*] \[[ x]\]`, emit that run.
3. **`Acceptance` heading.** Else, if a line matches
   `(?i)^(#+\s*|\*\*)(acceptance|definition of done|done\b)`, emit from there to
   the next heading.
4. **Fallback.** Else emit exactly:

   ```
   No explicit definition of done in the issue. Derive it from the description
   above, state it in the first commit message, and verify it with
   `bash tools/pr_gate.sh`.
   ```

The emitted text is truncated at `MAX_BODY_CHARS` by the same rule as the body.

## 4.5 Assignee mapping

```
if "good first issue" in labels or "docs" in labels or "documentation" in labels:
    assignee = "oss-contributor"
else:
    assignee = DEFAULT_ASSIGNEE = "backend-engineer"
```

Two profiles, because this repo has exactly two shapes of work and both profiles
are installed and proven on this board:

- `backend-engineer` — compiler, runtime, stdlib, tooling work: `src/logosc/*.logos`,
  `src/std/`, `rt.h`, `tools/`. This is the profile that has landed the
  arr-set, vec-push and json work on this board.
- `oss-contributor` — docs and `good first issue` work, which in this repo is
  the outside-contributor lane: read `CONTRIBUTING.md`, one signed commit, a
  `docs/`-shaped pull request. Its own remit is exactly that lifecycle.

The map is one constant so adding a third profile is a one-line change and a
unit test, not a redesign. A label that maps to no profile falls to
`DEFAULT_ASSIGNEE`; an unknown assignee would leave the task in `ready` forever
(the dispatcher silently drops unknown assignees), which is why the mapping is a
closed table rather than a computed guess.

## 4.6 Log line

Exactly one line per run that did something; **empty stdout when nothing
happened** (the cron job is `--no-agent`, and empty stdout is silent):

```
logos-issue-intake 2026-11-20T12:00:01Z fetched=38 prs=0 unseen=2 ready=2 picked=2 created=2 failed=0 picks=#86,#52
```

Field meanings: `unseen` before eligibility, `ready` after, `picked` after the
independence filter, `created` after the board accepted them, `failed` the
difference between picked and created. `picks` lists issue numbers in pick
order. On an `edited-after-pick` event the same line ends with
`edited=#52,#61`; on a skip-only run it ends with
`skipped=#96:blocked,#67:excluded-label`.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/03-dossiers/03-hermes-cli-evidence.md
 -> the CLI help text and the source lines that fix the flag names and `"id"` in `--json`
docs/pipelines/issue-intake/02-analysis/05-failure-and-idempotency.md
 -> what a failed create means for state
docs/pipelines/issue-intake/02-analysis/06-config.md
 -> the constants named above
