# 2 — State and dedupe

One JSON file is the pipeline's memory. It answers two questions: *which issues
already have a board task* and *what did the last run see*. It contains no
secrets, and it is the only file the pipeline writes besides the board itself.

## Path

```
~/.local/state/logos-issue-intake/state.json      # STATE_PATH, override: LOGOS_INTAKE_STATE
```

Created with `mkdir -p` mode `0o700`; the file is written mode `0o600`. It must
**never** live inside the git worktree — a state file in the repo shows up as a
dirty tree and would be committed by the next agent.

## Shape (version 1)

```json
{
  "version": 1,
  "repo": "abaddon/logos",
  "board": "logos",
  "backlog_cutoff": "2026-11-20T12:00:00Z",
  "last_run_at": "2026-11-20T13:00:11Z",
  "last_etag": "W/\"f30b16ab17c122c91c2d37fbf6c2d13d8025217a51a626490fc7fffaecf1beaf\"",
  "last_run": {
    "fetched": 38, "prs_skipped": 0, "unseen": 0,
    "ready": 0, "picked": 0, "created": 0, "failed": 0
  },
  "issues": {
    "52": {
      "outcome": "picked",
      "first_seen_at": "2026-11-20T12:00:00Z",
      "picked_at": "2026-11-20T12:00:01Z",
      "task_id": "t_2c1a9d47",
      "github_created_at": "2026-11-19T00:38:20Z",
      "github_updated_at": "2026-11-19T00:38:20Z"
    },
    "86": {
      "outcome": "seeded",
      "first_seen_at": "2026-11-20T12:00:00Z",
      "github_created_at": "2026-11-19T08:35:06Z",
      "github_updated_at": "2026-11-20T09:02:44Z"
    },
    "96": {
      "outcome": "skipped",
      "skip_reason": "blocked",
      "first_seen_at": "2026-11-20T12:00:00Z",
      "github_created_at": "2026-11-19T08:35:42Z",
      "github_updated_at": "2026-11-19T08:35:42Z"
    }
  }
}
```

Keys of `issues` are **string** issue numbers (JSON object keys are strings;
cast, do not key by int).

### `outcome` — the only field dedupe reads

| value | meaning | sticky? |
|---|---|---|
| `picked` | a board task was created (or already existed under the same idempotency key) | **yes, forever** |
| `seeded` | existed before the bootstrap cutoff; deliberately not picked | **yes**, until a `--include-backlog` run drains it, or `--forget <n>` clears it |
| `skipped` | seen this run and not eligible | no — rewritten every run |

`skipped` is a ledger entry for the operator, not a fact about the issue. It is
overwritten by the next run, so an issue skipped today because its blocker was
open is reconsidered automatically the hour that blocker closes. If `skipped`
were sticky, the pipeline would silently stop working on a fix.

`seeded` is sticky on the default path — the hourly run never reconsiders it,
which is what makes the first run inert — but it is not a permanent veto.
`--include-backlog` waives it for that one run, and the run rewrites every
seeded entry it considered as `picked` or `skipped` with its `skip_reason`, so
the state file explains the drain instead of reporting 38 untouched seeds
(`07-scenarios.md` §8).

### `skip_reason` vocabulary

Exactly one of: `excluded-label`, `blocked`, `umbrella`, `subsystem-collision`,
`cross-reference`, `cap`. Each maps to one clause of `03-selection.md`; anything
else is a bug and must be fixed, not spelled into the file.

## Identity: number only, not (number, updated_at)

The board task identity is the **issue number**. `github_updated_at` is stored
and refreshed so an operator can see that the issue moved, and so a run can log
`edited-after-pick`, but an edit never produces a second task. Two cards for one
issue is worse than one card with a stale copy of the body: the second card's
worker re-does work the first already did, against a branch that already exists.

The spec therefore defines:

- **new** — no `picked` entry and no `seeded` entry unless `--include-backlog`
  (see `01-polling.md`);
- **edited after pick** — `state.issues[n].github_updated_at != issue.updated_at`
  and `outcome == "picked"` → append `edited-after-pick` to that run's log line
  and update the stored `github_updated_at`. No task, no state outcome change;
- **re-pick** — only by explicit operator action: `--forget <number>` deletes
  the entry, so the issue becomes new again on the next run. The old board task
  is left alone; the operator archives it if it is stale.

## Crash-safe write

Every state write is atomic and ordered:

```
1. write  <state>.tmp            (same directory, mode 0o600, json.dump + "\n")
2. flush + os.fsync(file handle)
3. os.replace(<state>.tmp, <state>)       # atomic rename on the same filesystem
4. fsync the directory handle             # make the rename durable
```

A kill at any point leaves either the old file or the new one, never a truncated
one. A `.tmp` left behind by a kill is overwritten by the next write, never read.

**When the write happens matters as much as how.** The state is committed
**once per created task**, immediately after that task's `hermes kanban create`
returns, and once more at the end of the run for `last_run_at` / `last_etag`:

```
for issue in picked:
    task_id = create_task(issue)      # idempotent, see 05
    state.issues[n].outcome = "picked"
    state.issues[n].task_id = task_id
    atomic_write(state)
atomic_write(state)                   # last_run_at, last_etag, last_run counters
```

A crash between the two picks therefore loses at most the in-flight pick, and
the in-flight pick is recovered by its idempotency key, not by the state file
(see `05-failure-and-idempotency.md`). A single write at the end of the run
would be simpler and wrong: it would orphan every task created before the crash.

## Concurrency lock

`<state>.lock` created with `O_CREAT | O_EXCL`, containing `pid=<n> started=<iso>`.
Held for the whole run, removed in a `finally`. If the lock exists and its
`started` is younger than 10 minutes, the run logs
`ERROR locked pid=<n> age=<s>` and exits **0** without fetching — a second tick
did not win, which is not an error. Older than 10 minutes: the previous run
died, and the lock is reclaimed with a logged `WARN stale-lock reclaimed`.

The lock is not decoration. Two overlapping runs would each pick one issue from
the same unseen set and never test the pair — the two tasks would be exactly the
non-independent pair this pipeline exists to prevent.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/01-polling.md
 -> what fills `last_etag` and why the fetch is open-only
docs/pipelines/issue-intake/02-analysis/03-selection.md
 -> the consumer of `outcome`, and the skip_reason each clause produces
docs/pipelines/issue-intake/02-analysis/05-failure-and-idempotency.md
 -> the create-then-write ordering, restated as a failure table
