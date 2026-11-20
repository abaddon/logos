# Spec — hourly GitHub issue intake for abaddon/logos

What is being built: a script that runs once an hour, reads the open issues at
`https://github.com/abaddon/logos/issues`, and creates **at most two** Hermes
Kanban tasks per run — one per picked issue — on the `logos` board, restricted
to issues that can be worked **independently of each other**. It runs
unattended, forever, with no model in the loop.

Status: implemented in `tools/issue_intake.py`. The normative detail lives in six
files under `../02-analysis/`; every ambiguous word is defined as a test in
`03-selection.md` §3.1, eight end-to-end traces are in `07-scenarios.md`, and the
13 cases in `../03-dossiers/04-selection-fixtures.json` are the test data
`tests/test_issue_intake.py` loads verbatim.

## The contract in one page

| # | Dimension | The decision |
|---|---|---|
| 1 | **Polling** | `GET /repos/abaddon/logos/issues?state=open&sort=created&direction=asc&per_page=100`, follow `rel="next"`, no `since`. Items with a `pull_request` key are dropped. Conditional request via stored `etag` (304 = quiet run). Rate limit / 5xx / timeout ⇒ exit 75, **no state write**; 401/404 ⇒ exit 65. |
| 2 | **State** | One JSON file at `~/.local/state/logos-issue-intake/state.json` (env override), versioned, keyed by issue number as a string, `outcome ∈ {picked, seeded, skipped}`, plus `backlog_cutoff`, `last_run_at`, `last_etag`, `last_run` counters. Written `tmp → fsync → os.replace → dir fsync`, **once per created task** and once at end of run. A `O_EXCL` lock (stale after 10 min) serialises runs. |
| 3 | **Selection** | `ready = new ∧ no excluded label ∧ not blocked ∧ not umbrella`; `independent(a,b) = neither cites the other ∧ disjoint subsystems`; greedy over `created_at asc` until 2 picks. Fewer than 2 independent ⇒ fewer than 2 picks. Never relax either test to reach 2. |
| 4 | **Task creation** | `hermes kanban --board logos create "[logos#<n>] <title>" --assignee <mapped> --workspace worktree:<repo>/.worktrees/gh-<n> --branch wt/gh-<n> --idempotency-key logos-issue-<n> --created-by logos-issue-intake --body-file <tmp> --json`; body = provenance header + inherited `**Done when:**` block + repository-gates paragraph + verbatim issue body (6 000-char cap). Assignee: `docs`/`documentation`/`good first issue` → `oss-contributor`, else `backend-engineer`. |
| 5 | **Idempotency** | Two independent mechanisms: state `picked` (fast path, audit trail) and `--idempotency-key logos-issue-<n>` (crash and lost-state backstop). Create failure stops the run, leaves earlier picks committed, retries next hour under the same key. |
| 6 | **Config** | 8 env-overridable constants (`REPO`, `API_BASE`, `BOARD`, `REPO_ROOT`, `STATE_PATH`, `HERMES_BIN`, `MAX_PICKS`, token **name** fixed as `GITHUB_TOKEN`) plus 9 policy constants held in code (labels, subsystem map, caps, timeouts). |
| 7 | **Scheduling** | `hermes cron create "0 * * * *" --name logos-issue-intake --no-agent --script logos-issue-intake.sh --deliver local`. Script job, not an agent job: deterministic, no tokens, silent when there is nothing to say. |

## The six decisions a reader may want to argue with

Each is argued in its file; they are collected here so the reviewer sees them
without reading 40 KB.

1. **First run is inert.** No state file ⇒ seed all 38 current issues as
   `seeded`, pick zero, log `bootstrap seeded=38 picked=0`. The backlog is
   reachable with `--include-backlog` (then two picks/hour, oldest first).
   Rationale: an unattended pipeline's first observable act must be provably
   harmless, and 11 of the 38 open issues are questions or `needs-info` records.
   (`02-state.md`, `07-scenarios.md` §8)
2. **Identity is the issue number, not `(number, updated_at)`.** An edited issue
   never produces a second card; the run logs `edited-after-pick` and refreshes
   the stored `updated_at`. Re-pick requires `--forget <n>`. (`02-state.md`)
3. **"Blocked" is decided from the repo's own dependency lines.** A line matching
   `blocked by|depends on|sequenced after|part of|sub-issue of|parent:|follow-up to`
   whose `#N` is still open makes the issue not ready. Measured: the corpus writes
   exactly this way (`- **Blocked by #74 — hard** …`,
   `- **Sequenced after:** … #52, #78, #82, #86, #90`). Line scope is what keeps
   prose from tripping it. (`03-selection.md` §3.1)
4. **"Same area" is a title prefix, not a label.** `docs|documentation|manual →
   docs`, `compiler|language → compiler`, `stdlib`, `tooling`, `examples`,
   `target`; labels are only a fallback. Counts from the live corpus: docs 16,
   tooling 6, compiler 7, stdlib 3, examples 2, target 1. (`03-selection.md` §3.2)
5. **An umbrella issue is not work.** ≥8 open-issue references, or a title /
   first body line matching `tracking issue|index of|master list|umbrella`,
   makes it not ready — this is what stops `#41` and `#100` (the 37-gap index)
   from becoming cards, while `#74` (6 refs: a real design issue that lists what
   it blocks) stays pickable. (`03-selection.md` §3.1)
6. **Two picks, and silence otherwise.** Empty stdout on a no-op run; one line
   per run that acted; exit 75 on anything retryable. (`05-failure-and-idempotency.md`,
   `06-config.md` §6.4)

## Acceptance criteria for the implementation

1. `python3 tools/issue_intake.py --once --dry-run` against the live repo prints
   a decision table, exits 0, creates no task and writes no file.
2. `python3 -m unittest tests.test_issue_intake` passes and consumes
   `../../03-dossiers/04-selection-fixtures.json` verbatim; the module is listed
   in `CONTRACT_TESTS` in the `Makefile`.
3. First run (no state file) creates zero tasks and writes a state file whose
   `backlog_cutoff` equals that run's start time.
4. Reproduction of all eight traces in `07-scenarios.md` — the two real-data
   ones (`#86,#87,#90,#96,#97,#98` burst; the `#10,#52` drain) are checked
   against the issue bodies committed in `../../03-dossiers/02-issue-corpus-evidence.md`.
5. Killing the process between `hermes kanban create` and the state write leaves
   no duplicate task when the next run re-executes (proved with a `hermes` shim
   on `PATH` that fails once and records its argv).
6. A simulated `403` with `X-RateLimit-Remaining: 0` exits 75 and leaves the
   state file byte-identical.
7. `bash tools/check_doc_links.sh .` reports 0 broken and `make test` passes;
   the pull request carries a DCO sign-off and no token.
8. `grep -rn "GITHUB_TOKEN" tools/ tests/` matches only the constant holding the
   variable's **name**, never a value.

## Reading order

`02-analysis/01-polling.md` → `02-state.md` → `03-selection.md` (the core) →
`04-task-creation.md` → `05-failure-and-idempotency.md` → `06-config.md` →
`07-scenarios.md`. The dossiers under `../03-dossiers/` hold everything measured
against the live repository and the installed CLI, so any figure quoted above can
be re-derived.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/01-polling.md
 -> endpoint, headers, pagination, and the rate-limit failure table
docs/pipelines/issue-intake/02-analysis/02-state.md
 -> state schema, atomic write, lock, and the picked/seeded/skipped contract
docs/pipelines/issue-intake/02-analysis/03-selection.md
 -> testable definitions of new/ready/independent/umbrella/subsystem and the algorithm
docs/pipelines/issue-intake/02-analysis/04-task-creation.md
 -> exact CLI invocation, title/body templates, acceptance-criteria extraction, assignee map
docs/pipelines/issue-intake/02-analysis/05-failure-and-idempotency.md
 -> failure table, partial-run semantics, the never-do list
docs/pipelines/issue-intake/02-analysis/06-config.md
 -> the config block, entrypoint flags, exit codes, cron install
docs/pipelines/issue-intake/02-analysis/07-scenarios.md
 -> eight end-to-end traces including the three the brief asks for
