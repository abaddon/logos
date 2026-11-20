# Dossier — the GitHub side, measured

Every figure here was taken from the live API on **2026-11-20** (unauthenticated,
`curl`, `api.github.com`). Nothing is quoted from memory. Re-derive any of it with
the commands shown.

## The repository

```
$ curl -s "https://api.github.com/repos/abaddon/logos/labels?per_page=100"
$ curl -s "https://api.github.com/repos/abaddon/logos/issues?state=open&sort=created&direction=asc&per_page=100"
```

- public, owner `abaddon`, default branch `main`
- open items returned by `GET /issues`: **38**, of which **0** carry a
  `pull_request` key (the repo merges fast; a reopened PR would appear here)
- `per_page=100` returned all 38 in one page: **no `link: … rel="next"` header**
  (with `per_page=10` the same query does return one, which is how the pagination
  format was confirmed)
- labels defined on the repo, 20 in total: `accessibility, bug, challenge-entry,
  challenge-findings, compiler, docs, documentation, duplicate, enhancement,
  good first issue, hard, help wanted, in-progress, invalid, needs-info,
  question, runtime, superseded, target, wontfix`

### Labels actually in use on the 38 open issues

| count | label |
|---|---|
| 16 | `docs` |
| 14 | `good first issue` |
| 12 | `compiler` |
| 9 | `needs-info` |
| 6 | `hard` |
| 6 | `help wanted` |
| 3 | `question` |
| 2 | `runtime` |
| 2 | `target` |
| 1 | `bug` |

`documentation`, `accessibility`, `in-progress`, `duplicate`, `invalid`,
`wontfix`, `superseded`, `enhancement` are defined but unused on the open set —
they exist for the pipeline's benefit (a maintainer marking an issue
`in-progress` or `duplicate` must be able to take it out of the queue with a
label, not with code).

## Response headers (verbatim)

First request of the session:

```
HTTP/2 200
etag: W/"f30b16ab17c122c91c2d37fbf6c2d13d8025217a51a626490fc7fffaecf1beaf"
link: <https://api.github.com/repositories/1449758221/issues?state=open&per_page=10&after=Y3Vyc29yOnYyOpLPAAABofLyMSjPAAAAAYKTEog%3D&page=2>; rel="next"
x-ratelimit-limit: 60
x-ratelimit-remaining: 59
x-ratelimit-used: 1
x-ratelimit-resource: core
x-ratelimit-reset: 1795178421
```

Later requests, same query with `per_page=100`:

```
HTTP/2 200
etag: W/"ae6f8ebd1c263ef1cd08aaaabb0ae18247f4303791c438149818ba837f7fa857"
x-ratelimit-limit: 60
x-ratelimit-remaining: 57
x-ratelimit-reset: 1795178305
```

Three things follow and are relied on by the spec:

1. **60 requests/hour unauthenticated.** An hourly run costs 1 (`2` with a page
   flip), so the anonymous quota is sufficient — but the reset timestamp is
   present and parseable, which is what the exit-75 path logs.
2. **A strong ETag is returned.** `If-None-Match` therefore turns the steady
   state into a `304`: one header round-trip per hour and no quota spent on a
   body. The spec stores `last_etag` in the state file for exactly this.
3. **`Link` uses an opaque `after=` cursor**, not `page=` — the spec parses the
   `rel="next"` URL verbatim rather than constructing `?page=N`.

## Timestamps that matter to the state design

`#10` and `#52`, fetched minutes apart:

```json
[{"number":10,"created_at":"2026-11-08T01:21:24Z","updated_at":"2026-11-19T08:39:35Z","labels":["target","hard"],"login":"abaddon"},
 {"number":52,"created_at":"2026-11-19T00:38:20Z","updated_at":"2026-11-19T08:39:36Z","labels":["good first issue","docs"],"login":"abaddon"}]
```

`updated_at` is 11 days later than `created_at` for `#10` and 8 hours later for
`#52` — label edits move it. This is the measured reason identity is the issue
**number** and not `(number, updated_at)`: keying on the pair would have re-picked
`#10` and `#52` on 2026-11-19 for a label change (`02-analysis/02-state.md`).

## The board the pipeline writes to

```
$ cat /root/.hermes/kanban/boards/logos/board.json
{"slug":"logos","name":"Logos","description":"","icon":"","color":"",
 "default_workdir":"/root/ai-language-program","project_id":"p_f033e8d1",
 "created_at":1794771824,"archived":false}
```

The board is project-scoped with `default_workdir = /root/ai-language-program`.
The spec still passes an explicit `--workspace worktree:<repo>/.worktrees/gh-<n>`
because a profile whose `projects.db` does not know `p_f033e8d1` would otherwise
fall back to a scratch workspace, and the deterministic path is what makes the
branch name predictable from the issue number.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/01-polling.md
 -> the endpoint/headers/pagination rules these measurements justify
docs/pipelines/issue-intake/02-analysis/02-state.md
 -> the state fields (`last_etag`, identity) these measurements produced
docs/pipelines/issue-intake/03-dossiers/02-issue-corpus-evidence.md
 -> what the 38 issue bodies look like, and the per-issue verdict table
