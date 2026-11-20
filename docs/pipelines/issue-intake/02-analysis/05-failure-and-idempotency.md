# 5 — Idempotency and failure behaviour

The pipeline runs unattended, hourly, forever. Every failure mode below is
either *recoverable by the next run with no duplicate side effect* or *loud*.
"Loud" here means non-empty stdout (delivered by cron) and a non-zero exit.

## 5.1 The invariant

> For every issue number **n**, the board holds at most one task whose
> idempotency key is `logos-issue-n`, no matter how many runs start, crash, or
> overlap.

Two mechanisms carry it, and they cover different failures:

| Mechanism | Covers | Fails when |
|---|---|---|
| state file `outcome: "picked"` | the normal path: a second run never reconsiders the issue | the state file is lost or reset |
| `--idempotency-key logos-issue-<n>` | everything else, including a lost state file, a crash between create and write, and two runs racing | the board itself is wiped, or the existing task was **archived** |

Both are cheap; neither is redundant. The state file keeps the board clean and
holds the audit trail; the key is the correctness backstop.

Note the archive hole honestly: the CLI returns an existing **non-archived**
task for a key. If an operator archives a task for issue #52 and the state entry
is also gone, #52 becomes pickable again. That is the intended semantic — an
archived task is a withdrawn one — and it is the only way to re-pick
accidentally. Recorded, not defended.

## 5.2 Failure table

| Situation | Detected by | Action | State written | Exit |
|---|---|---|---|---|
| no state file (bootstrap) | `open()` → `FileNotFoundError` | seed every fetched issue `seeded`, `backlog_cutoff = run start`, pick nothing, log `bootstrap seeded=38 picked=0` | yes | 0 |
| fetch 304 | status | update `last_run_at` only | yes | 0 |
| fetch rate-limited | 403/429 + headers | log `ERROR rate-limited …`, stop | **no** | 75 |
| fetch 5xx / timeout | status / exception | one retry, then `ERROR http=…` | **no** | 75 |
| fetch 401/404 | status | `ERROR auth/repo` | **no** | 65 |
| >`MAX_PAGES` pages | page counter | `ERROR pagination-cap` | **no** | 65 |
| state file unparsable | `json.JSONDecodeError` | rename to `state.json.corrupt-<ts>`, log `ERROR state-corrupt path=…`, stop (do **not** reseed: reseeding would silently forget every pick) | no | 65 |
| lock held, fresh | `.lock` mtime | log `ERROR locked pid=…`, stop | no | 0 |
| lock held, stale | `.lock` mtime > 10 min | log `WARN stale-lock reclaimed`, proceed | — | — |
| `hermes kanban create` non-zero / no JSON / no `"id"` | subprocess result | log `ERROR create failed issue=#n rc=<rc>`, **stop the run** (do not attempt the second pick) | for the picks already created | 75 |
| create timed out (60 s) | subprocess timeout | as above — the key makes the retry safe even if the task was actually created | as above | 75 |
| task existed under the same key | JSON `"id"` returned | treat as success, store the returned id, do not count it as `created` (`created` counts new rows; log `existing=#n`) | yes | 0 |

Stopping after the first create failure is deliberate. A run that fails to talk
to the board once will usually fail twice, and two half-created attempts leave
the operator with a log that is harder to read than one honest failure.

## 5.3 What "partial run" means, precisely

There is no transaction across the two picks. The contract is per-issue:

- pick 1 created and state written, pick 2 failed ⇒ next run sees #1 as `picked`
  (skips it), sees #2 as unseen (retries with the same key), and may pick a new
  #3 alongside #2 if the pair is independent. The board never gets a duplicate;
  it can briefly hold one task whose sibling arrived an hour late.
- crash after `create` returned, before the state write ⇒ next run treats the
  issue as unseen, calls create with the same key, gets the same task id back,
  and writes it. `existing=#n` in the log is the only trace, which is why that
  counter exists.
- crash mid-write of the state file ⇒ the temp file is ignored and the previous
  file is intact (`02-state.md` §"Crash-safe write").

## 5.4 What the pipeline must never do

- Never advance `backlog_cutoff` after bootstrap. It is written once and is the
  only thing standing between a lost state file and 38 cards in one hour.
- Never create a task before the fetch completes and the pair test has run on
  the whole candidate set.
- Never write `picked` for an issue whose create did not return an id.
- Never retry a create with a *different* key. One issue, one key, forever.
- Never print the token, the full API response, or an issue body on a failure
  path (exit-75 lines carry status codes and URLs, nothing else).
- Never create a task for an issue that is not `ready` because "the board looks
  empty this hour".

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/02-state.md
 -> atomic write, the picked/skipped distinction, and the lock
docs/pipelines/issue-intake/03-dossiers/03-hermes-cli-evidence.md
 -> the source lines proving `idempotency_key` returns an existing non-archived task
docs/pipelines/issue-intake/02-analysis/07-scenarios.md
 -> scenarios 6 and 7 walk the two partial-run cases
