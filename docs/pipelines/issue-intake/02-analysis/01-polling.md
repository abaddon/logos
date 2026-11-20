# 1 — Polling GitHub

Normative. An implementer reads this file and writes the fetch function; nothing
here is a suggestion.

## Endpoint

```
GET https://api.github.com/repos/abaddon/logos/issues
    ?state=open&sort=created&direction=asc&per_page=100
```

| Element | Value | Why |
|---|---|---|
| `state=open` | fixed | closed issues are not work; a closed issue is also how a blocker stops blocking |
| `sort=created&direction=asc` | fixed | the FIFO order the selection rule depends on (oldest unseen first) |
| `per_page=100` | fixed (config) | 38 open issues today → one page; the cap bounds a pathological repo |
| `since` | **not used** | `since` filters on `updated_at`, so a crash between fetch and state-write would skip an issue forever. 38 items, one conditional request — correctness over payload |

Request headers:

```
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Authorization: Bearer $GITHUB_TOKEN        # only when the env var is set and non-empty
If-None-Match: <state.last_etag>           # only when the state file has one
User-Agent: logos-issue-intake/1
```

Measured against the live repo on 2026-11-20:

```
HTTP/2 200
etag: W/"f30b16ab17c122c91c2d37fbf6c2d13d8025217a51a626490fc7fffaecf1beaf"
link: <https://api.github.com/repositories/1449758221/issues?state=open&per_page=10&after=Y3Vyc29yOnYyOpLPAAABofLyMSjPAAAAAYKTEog%3D&page=2>; rel="next"
x-ratelimit-limit: 60
x-ratelimit-remaining: 59
x-ratelimit-reset: 1795178421
```

## Which items count as an issue

`GET /issues` returns pull requests too. An item is a **pull request** and is
dropped before any other test when the JSON object has a `pull_request` key
(present with any value, including `null`-shaped empty object). A dropped PR is
not logged as an issue, is not written to state, and never consumes a pick.

The 38 open items fetched on 2026-11-20 contained 0 pull requests; the filter
exists because merged PRs are common in this repo and would otherwise appear as
"new issues" the moment a pull request is reopened.

## Which issues count as "new"

An issue is **new** in this run iff all three hold:

1. `issue.state == "open"` — guaranteed by the query, asserted anyway;
2. `"pull_request" not in issue`;
3. it is not already **picked** in the state file — that is,
   `state.issues[str(number)].outcome` is absent or is not `"picked"` — and it is
   not `"seeded"` either, **unless** `--include-backlog` was passed (see
   `02-state.md`);
4. `issue.created_at > state.backlog_cutoff`, or `--include-backlog` was passed
   on the command line.

Rule 4 is the bootstrap guard: the run that creates the state file sets
`backlog_cutoff` to its own start time, so the 38 issues that already exist are
not "new". Rule 3's `seeded` clause is the sticky half of the same guard, and
the same flag waives it: `--include-backlog` is the operator's drain, so for one
run it ignores the cutoff **and** the `seeded` entries the bootstrap wrote
(operator choice, see `07-scenarios.md` §8).

`updated_at` is **not** part of the newness test. One issue number yields at
most one task, ever (see `02-state.md` §"Identity").

## Pagination

Follow `Link: <...>; rel="next"` until it is absent, hard stop after
`MAX_PAGES = 10` (1000 issues). Accumulate in fetch order; do not sort in the
client — the query already returns created-ascending and the selection rule
re-sorts by `(created_at, number)` anyway.

A `Link` header that is absent, or present with no `rel="next"`, ends the loop.
If `MAX_PAGES` is reached, the run stops with exit 65 and an error line that
names the limit; it does **not** silently truncate (a truncated page set would
make blocked-by checks wrong).

## Rate limits and transient failures

Unauthenticated `api.github.com` allows 60 requests/hour; with `GITHUB_TOKEN`
it is 5000/hour. This pipeline makes 1–2 authenticated requests per hour, so
the limit is only a hazard when the token is missing and something else on the
host is sharing the anonymous quota. Handling, in order:

| Response | Detection | Action |
|---|---|---|
| `304 Not Modified` | status | treat as "no change": `unseen = 0`, keep every state field except `last_run_at`, exit 0 |
| `200` | status | normal path |
| `403` or `429` with `X-RateLimit-Remaining: 0` | headers | log `ERROR rate-limited remaining=0 reset=<ISO8601 from x-ratelimit-reset>`, exit **75**, **no state write** |
| `403` or `429` with `Retry-After: <n>` | header | log `ERROR secondary-limit retry-after=<n>`, exit **75**, no state write |
| `5xx` | status | one immediate retry, then log `ERROR http=<status> url=<url>`, exit **75**, no state write |
| connection error / timeout | exception | one immediate retry, then exit **75**, no state write |

Exit 75 (EX_TEMPFAIL) is the contract with cron: the next hourly run retries
the whole thing. There is no in-run backoff loop — an hourly schedule is the
backoff.

Never retry a `401`/`404`: those mean a bad token or a renamed repo and will
fail identically next hour. Exit 65 with the status named.

## Timeouts

`connect = 10 s`, `read = 30 s`, total budget for the fetch phase 90 s. A hung
connection must not hold the state lock past the next tick.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/02-state.md
 -> the state file that stores `last_etag`, `backlog_cutoff` and the picked set
docs/pipelines/issue-intake/02-analysis/03-selection.md
 -> what is done with the fetched list once it is complete
docs/pipelines/issue-intake/03-dossiers/01-github-evidence.md
 -> the measured headers, the label inventory, and the 0-PR observation
