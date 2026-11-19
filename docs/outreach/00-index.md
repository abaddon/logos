# Outreach — where Logos was published, and what each place needs

This pyramid records the outward-facing work of 2026-11-18/19: what was actually
published to third-party surfaces where agents (and the people who point agents
at repositories) discover tools, what each publication returned, and what stayed
impossible **and why** — one credential per channel, named, not implied.

Read it in this order:

| If you want to… | Read | Time |
|---|---|---|
| know what is live now and what it cost | [`01-summary/published.md`](01-summary/published.md) | 5 min |
| decide where the next publication goes | [`02-analysis/channels.md`](02-analysis/channels.md) — the channel table, the two that were executed, the one that is blocked and its exact gate | 10 min |
| check a claim | [`03-dossiers/verification-log.md`](03-dossiers/verification-log.md) — every command, every output, copied from the run | 10 min |

The two facts that make the rest of it make sense:

1. **The repository was made claimable before it was made known.** The Logos
   Agent Challenge could not open on 2026-12-01 because pre-launch checks 4–8
   were red: no entry form, no showcase, no `challenge-entry` label, and 3 open
   issues with none labelled `good first issue`. Publishing a language nobody can
   contribute to is a bounce, not outreach. Those five checks are now green
   (PR [#62](https://github.com/abaddon/logos/pull/62), merged as `4980394`, issues #52–#61).
2. **The surfaces agents actually read are instruction catalogs, not forum
   posts.** A coding agent loads `*.instructions.md` files and `AGENTS.md`; it
   does not read Hacker News. The publication with the highest expected reach in
   this batch is therefore a 130-line instruction file in
   `github/awesome-copilot` (41k stars), not a post anywhere.

## What exists now

| Surface | What it is | State |
|---|---|---|
| `github/awesome-copilot` → `instructions/logos.instructions.md` | The largest agent-instruction catalog; loaded by Copilot and mirrored by other clients | PR [#6516](https://github.com/github/awesome-copilot/pull/6516) |
| `up-for-grabs.net` → `_data/projects/logos.yml` | The curated index of projects with tasks for newcomers; feeds several aggregators | PR [#6451](https://github.com/up-for-grabs/up-for-grabs.net/pull/6451) |
| `abaddon/logos` itself | `llms.txt`, `AGENTS.md`, 12 topics (incl. `good-first-issues`, `llms-txt`), `logosc guide --json`, 6 `good first issue` | live on `main` |
| The Logos Agent Challenge | Three tracks, one entry form, one ledger, dated Round 1 | repository side green; Round 1 opens 2026-12-01 |

## What does not exist, and the single missing thing

The official MCP Registry — 66,812 servers as of 2026-11-18 — is the highest-reach
agent surface there is, and it is still out of reach. Not for want of a plan: for
want of a **published package**. The registry indexes installable packages
(`npm`, `pypi`, `oci`, `nuget`, `mcpb`). This host has a GitHub token and nothing
else: `npm whoami` is `ENEEDAUTH`, there is no Docker daemon to build an OCI
image, and no PyPI token. Six channels sit behind that one artifact and are
recorded as deferred rather than claimed — see
[`02-analysis/channels.md`](02-analysis/channels.md#the-blocked-half).

SOURCES

- [`../challenge/01-summary/program.md`](../challenge/01-summary/program.md) — the
  program whose pre-launch checks this work cleared, and the rules every
  publication must not contradict.
- [`../launch/00-index.md`](../launch/00-index.md) — the earlier launch kit: the
  per-channel checklist, the copy that was written, and the owner actions it
  waits on. This pyramid is the execution record beside it.
- [`../distribution/00-index.md`](../distribution/00-index.md) — the agent-facing
  surface (`llms.txt`, topics, quickstart, `AGENTS.md` proposal) that every
  publication points at, and the verification of the release it names.
