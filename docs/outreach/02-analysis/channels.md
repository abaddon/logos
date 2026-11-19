# Channels — the table, the reasoning, and the one gate that blocks the rest

Written after executing what could be executed on 2026-11-19. Everything here is
either done (with a URL) or blocked (with the credential that blocks it named).
Nothing is "planned".

## The rule that decided the order

A publication is worth making only if the thing it points at survives the click.
The sequence was therefore:

1. **Make the repository claimable** — labels, entry form, showcase, seeded
   issues, a named forkable example. Without this every other row sends a reader
   to a project that cannot accept their work. (Done; PR #62.)
2. **Publish where an agent loads text before it writes code** — instruction
   catalogs and `AGENTS.md`-adjacent surfaces. An agent does not browse; it is
   handed instructions. This is the only category where a publication changes
   behaviour within one session. (Done; PR #6516.)
3. **Publish where a contributor looks for a candidate repo** — curated
   newcomer-task indexes. (Done; PR #6451.)
4. **Publish where a human reads news** — HN, Reddit, X. Last, because those
   venues punish a project that is not yet growable, and because they need
   accounts this host does not have.

## The channel table

| # | Channel | Who reads it | Needs | Status |
|---|---|---|---|---|
| 1 | `github/awesome-copilot` instruction catalog | coding agents loading `*.instructions.md` | GitHub token | **PR #6516** |
| 2 | `up-for-grabs.net` project index | contributors and aggregator feeds | GitHub token | **PR #6451** |
| 3 | `abaddon/logos` surfaces (`llms.txt`, `AGENTS.md`, topics, `guide --json`) | agents pointed at the repo | nothing | **live** |
| 4 | Logos Agent Challenge (issue-labelled entries) | agents with an operator | repository preconditions | **Round 1 opens 2026-12-01** |
| 5 | Official MCP Registry | every MCP client's server search | a published package | **blocked** |
| 6 | `mcp.so`, Smithery, `punkpeye/awesome-mcp-servers`, `awesome-remote-mcp-servers` | MCP server directories | a published package | **blocked** |
| 7 | Docker MCP Catalog, Hugging Face Spaces | container/HF users | Docker Hub / HF token | **blocked** |
| 8 | npm (`logos-mcp`) | agent builders | npm token | **blocked** (`ENEEDAUTH`) |
| 9 | Show HN | humans | an HN account with history | **blocked** |
| 10 | r/LocalLLaMA | humans | a Reddit account with history | **blocked** |
| 11 | X/Twitter | agents' operators | the `xurl` CLI, absent here | **blocked** |
| 12 | Claude / ChatGPT app directories | end users of those clients | an org, a privacy page, a support address, an endpoint stable for a month | **deferred by rule** |

`llms.txt` is deliberately not in the list as a distribution channel: Ahrefs'
crawl of 11.8% of live sites found that 97% of the files that exist are never
fetched. It is hygiene — a file an agent reads if it arrives — not a way to be
found.

## The blocked half

Six rows of that table collapse to one missing artifact: **an installable MCP
server package**. The registry schema accepts `npm`, `pypi`, `oci`, `nuget` and
`mcpb`; this host can produce none of them:

- `npm whoami` → `ENEEDAUTH` (no npm token)
- no Docker or Podman daemon → no OCI image to push to `ghcr.io`, despite the
  GitHub token carrying `write:packages`
- no PyPI token, so no `uv publish`
- no public endpoint, so a *remote* server — the shape 68% of listed servers now
  use, and the only shape that works when the compiler is Linux-only — cannot be
  hosted from here regardless of packaging

That is the whole reason this batch stops where it does. The build spec exists
(owner-actions §A1 of `docs/launch/`), the tools list exists, and the copy exists;
what does not exist is a place to publish a package from.

## How to read the result

Stars are the wrong first metric for this work. The number that answers "did any
third party actually engage" is:

```sh
gh issue list --repo abaddon/logos --label challenge-entry --state all \
  --json number,author --jq '[.[] | select(.author.login != "abaddon")] | length'
```

until that is non-zero, everything above is distribution without adoption, and
it should be reported as such. The second number is merged pull requests whose
author is not `abaddon`:

```sh
gh pr list --repo abaddon/logos --state merged --json author \
  --jq '[.[] | select(.author.login != "abaddon")] | length'
```

Baseline at close of this work: **0** and **1** respectively — one external
merged pull request in the repository's whole history. A challenge that turns
that 1 into 5 has done more than a post that turns 1 star into 200.

## What the next agent should do, in order

1. When the instruction-catalog PR is reviewed, apply the same file to the next
   actively-maintained catalog rather than a stale one — check `pushed_at` before
   writing anything.
2. If a packaging credential appears, publish the MCP server and then submit
   rows 5–7 in one pass; the copy for all three is already written.
3. On 2026-11-27, run the pre-launch list in `docs/challenge/01-summary/program.md`
   §9 again. Checks 4–8 are green as of this writing; the slip rule only fires if
   they stay green on the day.
