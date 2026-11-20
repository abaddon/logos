# Logos issue intake — spec index

An hourly pipeline that reads `https://github.com/abaddon/logos/issues` and
creates **at most two** Hermes Kanban tasks per run, one per picked issue,
restricted to issues that can be worked independently. This directory is the
specification: it is implementable as written, and every ambiguity in the brief
(`new`, `independent`) is replaced here by a test a machine evaluates.

Status: **implemented and installed.** The implementation is
`tools/issue_intake.py` plus `tests/test_issue_intake.py`, built against
`../03-dossiers/04-selection-fixtures.json`, and it is listed in
`CONTRACT_TESTS` so `make test` runs it. The hourly schedule is live on this
host — a `hermes cron` script job running
`tools/issue_intake_schedule.sh` — documented in
[`02-analysis/08-operations.md`](02-analysis/08-operations.md) and evidenced in
[`03-dossiers/05-installed-schedule.md`](03-dossiers/05-installed-schedule.md).

## Read in this order

| Layer | File | Answers |
|---|---|---|
| L1 | [`01-summary/spec.md`](01-summary/spec.md) | what is being built, the six decisions that matter, and the acceptance criteria for the implementation — one page |
| L2 | [`02-analysis/01-polling.md`](02-analysis/01-polling.md) | which endpoint, which headers, which issues count as new, pagination, rate limits |
| L2 | [`02-analysis/02-state.md`](02-analysis/02-state.md) | the state file's schema, its atomic write, the lock, and what `picked`/`seeded`/`skipped` mean |
| L2 | [`02-analysis/03-selection.md`](02-analysis/03-selection.md) | **the core**: testable definitions of `new`, `ready`, `independent`, `umbrella`, `subsystem`, and the 20-line algorithm |
| L2 | [`02-analysis/04-task-creation.md`](02-analysis/04-task-creation.md) | the exact CLI call, the title and body templates, acceptance-criteria extraction, assignee mapping |
| L2 | [`02-analysis/05-failure-and-idempotency.md`](02-analysis/05-failure-and-idempotency.md) | the failure table, partial runs, and the six things the pipeline must never do |
| L2 | [`02-analysis/06-config.md`](02-analysis/06-config.md) | the config block, entrypoint flags, exit codes, the cron install |
| L2 | [`02-analysis/07-scenarios.md`](02-analysis/07-scenarios.md) | eight end-to-end traces, including the three the brief names (0 new, 1 new, 3 new → 2 picked) |
| L2 | [`02-analysis/08-operations.md`](02-analysis/08-operations.md) | the installed hourly schedule: log, failure ladder, alert marker, overlap, manual trigger, removal |
| L3 | [`03-dossiers/01-github-evidence.md`](03-dossiers/01-github-evidence.md) | measured API headers, the label inventory, the board metadata |
| L3 | [`03-dossiers/02-issue-corpus-evidence.md`](03-dossiers/02-issue-corpus-evidence.md) | the dependency/wording conventions the rules are calibrated to, and a verdict table for all 38 open issues |
| L3 | [`03-dossiers/03-hermes-cli-evidence.md`](03-dossiers/03-hermes-cli-evidence.md) | the installed `kanban create` / `cron create` surfaces the pipeline calls |
| L3 | [`03-dossiers/04-selection-fixtures.json`](03-dossiers/04-selection-fixtures.json) | 13 machine-readable cases with expected picks — the selection function's test data |

## The four sentences that decide everything

1. **New** = open, not a pull request, no `picked`/`seeded` state entry, created
   after `backlog_cutoff` — the first run seeds the existing backlog and picks
   nothing.
2. **Ready** = new, no excluded label (`question`, `needs-info`, `invalid`,
   `wontfix`, `duplicate`, `superseded`, `in-progress`), not blocked by an open
   issue on a `Blocked by`/`Sequenced after` line, not an index/tracking issue.
3. **Independent** = neither ready issue cites the other, and their subsystems
   (`docs`/`compiler`/`stdlib`/`tooling`/`examples`/`target`) are disjoint.
4. **Two at most**, oldest first, then silence — fewer picks is a correct run.

## Numbers this spec was calibrated against (2026-11-20)

| Quantity | Value |
|---|---|
| open issues (no PRs) | 38 |
| ready under the rules | 22 |
| pickable pair from the backlog | `#10` (target) + `#52` (docs) |
| excluded by label / blocked / umbrella / over cap | 9 / 5 / 2 / 20 |
| issues using `**Done when:**` | 34 of 38 |

SOURCES (LAYER 1 NAVIGATION)
docs/pipelines/issue-intake/01-summary/spec.md
 -> the one-page contract, the six decisions, and the implementation's acceptance criteria
docs/pipelines/issue-intake/02-analysis/03-selection.md
 -> the normative definitions every other file refers back to

SOURCES (LAYER 3 NAVIGATION)
docs/pipelines/issue-intake/03-dossiers/04-selection-fixtures.json
 -> load this first when implementing: it pins the selection function's behaviour without HTTP
