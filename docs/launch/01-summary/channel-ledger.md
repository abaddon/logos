# Channel ledger — the tracking table (the retro's input)

The acceptance criterion is "all posts logged in a tracking table with links".
This is that table. **It currently records one executed surface and zero posts**,
because this host holds a credential for no channel but GitHub — see
[`../03-dossiers/verification-log.md`](../03-dossiers/verification-log.md) §1 for the
commands that establish that. Rows are added, never deleted; a row whose status
changes keeps its history in the Notes column.

Column meanings:
- **Posted** — the UTC date the thing became publicly reachable, not the date it
  was drafted. Blank means nothing is public.
- **Link** — the canonical URL a stranger would land on.
- **Reach** — views/clicks/impressions where the host publishes them. GitHub
  publishes clone and view counts only to the maintainer, in a 14-day window.
- **Responses** — comments, replies, PR review comments, issue replies.
- **Inbound questions** — distinct questions from third parties, counted once
  each however many times they are asked. This is the number that decides the
  next wave's framing.
- **Attributable** — forks, PRs, challenge entries or issues traceable to the
  channel (a referrer, or the commenter saying where they came from).
- **Fill it with** — the command or page that produces the number, so the table is
  re-derivable rather than remembered.

## Executed (public, by this task)

| Channel | Posted | Link | Reach | Responses | Inbound Qs | Attributable | Fill it with |
|---|---|---|---|---|---|---|---|
| GitHub release `v0.2.1` (the installable artifact) | **not posted — publish failed** (attempted 2026-11-18 21:12Z) | <https://github.com/abaddon/logos/actions/runs/44398996372> | — | — | — | — | `gh release list --repo abaddon/logos` (today it still says `v0.2.0`) |

## Verified live, no posting action of this task's

| Channel | Posted | Link | Reach | Responses | Inbound Qs | Attributable | Fill it with |
|---|---|---|---|---|---|---|---|
| Repo metadata (10 topics, description) | pre-existing | <https://github.com/abaddon/logos> | 693 clones / 201 uniques in the 14 days to 2026-11-18; 0 views recorded | 0 | 0 | 2 forks (all-time) | `gh api repos/abaddon/logos/traffic/clones`, `.../traffic/views`, `.../logos` |
| `AGENTS.md` | pre-existing | <https://github.com/abaddon/logos/blob/main/AGENTS.md> | HTTP 200; fetch counts are not published | 0 | 0 | 0 | not measurable — state it as unmeasured rather than guessing |
| `examples/agent-gate/` (the reference demo) | 2026-11-18, merged as #47 | <https://github.com/abaddon/logos/tree/main/examples/agent-gate> | HTTP 200 | 0 | 0 | 0 | `gh api repos/abaddon/logos/traffic/popular/paths` |

## Ready — copy written, one command from posting, blocked on a named gate

| Channel | Posted | Link | Reach | Responses | Inbound Qs | Attributable | Gate |
|---|---|---|---|---|---|---|---|
| Official MCP Registry | — | (record `io.github.abaddon/logos` does not exist) | — | — | — | — | endpoint must answer `tools/list` |
| npm `logos-mcp` | — | (package does not exist) | — | — | — | — | `npm login` + endpoint |
| `awesome-remote-mcp-servers` PR | — | — | — | — | — | — | endpoint or installable package |
| mcp.so | — | — | — | — | — | — | endpoint |
| Show HN | — | — | — | — | — | — | endpoint + demo + 48h clean wave 1 |
| r/LocalLLaMA | — | — | — | — | — | — | HN + 14 days, account with history |
| Docker MCP Catalog | — | — | — | — | — | — | a host with Docker |
| Hugging Face Space | — | — | — | — | — | — | Docker + HF token |

## Deferred, with the reason (and what would un-defer it)

| Channel | Reason it is not posted | Un-defers when |
|---|---|---|
| `llms.txt` | file absent from `main` (404); owned by `t_5b93c8fe` running in parallel | that branch merges to `main` |
| PyPI | npm is the one package type needed to prove registry ownership; a second registry entry is duplicate effort | npm exists and someone wants `uvx` |
| Smithery | its docs are migrating hosted URLs back to vendor endpoints — an unowned dependency for a project with no endpoint yet | the endpoint exists and its URL is ours |
| LangChain / LlamaIndex adapters | nothing to post: any MCP server is importable once registered | the registry record exists |
| Claude Connectors Directory | needs organisation, privacy page, support address, endpoint stable ≥1 month | month 3, after waves 2–3 |
| ChatGPT apps directory | same verification class | month 3 |
| Dev Discords / Slacks | invite-gated, invisible to crawlers, no citable size; the map lists them as a relationship channel, not a launch channel | join and listen; never announce |
| Logos Agent Challenge launch | pre-launch checks 3–8 red: page unmerged, entry form unsubmitted, 0 `good first issue`, showcase missing | the challenge coordinator's §A9 list goes green |

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/launch-checklist.md
 -> The gate each READY row waits on, and the wave model that orders them
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> The exact command that turns each READY row into a Posted row
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> The measured baseline numbers (clones, downloads, stars) and how they were read
