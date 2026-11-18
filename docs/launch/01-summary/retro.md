# Retro — what this launch actually produced, and the cadence to run it on

**The short version.** One surface went public — the installable release — and it
took a detour upstream of marketing to get there. The first tag was refused by the
release workflow's own acceptance gate, and finding out why turned up a two-day-old
defect: **no tag could have published at all** since the aarch64 target landed. The
fix (PR #48) merged, the version moved to 0.2.2, and `v0.2.2` published with the
tagless install verified end to end. Nothing else was posted, because this host
holds a credential for exactly one channel. There is therefore **no engagement data
to retro on** — and the honest thing to do with that is say so, keep the baseline,
and name the measurement that will answer the question at the first opportunity,
instead of dressing a prediction as a result.

## What was planned against what happened

| Planned (the brief) | Happened |
|---|---|
| Checklist per channel from the shortlist | Yes — 21 rows, every one EXECUTED / READY / DEFERRED with a named gate ([`../02-analysis/launch-checklist.md`](../02-analysis/launch-checklist.md)) |
| Channel-native copy, not copy-paste | Yes — four files, and the HN and Reddit posts are deliberately different arguments, not one block twice |
| Agent-readable side live and linked | **Yes, as of 22:42Z**: `AGENTS.md` (200), `llms.txt` (200), the challenge page (200, linked from the README), topics correct, and the demo runs from a cold clone. Two of those were 404 when this run started and landed with the docs task's #49 |
| Post in waves, observe 48h, adjust | Not reached. Wave 1's gate — an MCP endpoint answering `tools/list` — is unmet: no MCP server exists in the repository |
| Track per channel | Instrument built and run ([`channel-ledger.md`](channel-ledger.md)); only the baseline rows can be filled |
| Retro naming the top two channels | Not answerable from data. Prediction below, labelled as a prediction, with the rule that confirms or kills it |

## The baseline, measured (nothing here is estimated)

| Number | Value at 2026-11-18 21:20 UTC | How |
|---|---|---|
| Stars / forks / watchers | 0 / 2 / 0 | `gh api repos/abaddon/logos` |
| Open issues | 3 (0 labelled `good first issue`) | `gh issue list --state open` |
| `v0.2.0` tarball downloads, all-time | 14 | releases API, `download_count` |
| Git clones, 14 days to 2026-11-18 | 693 events / 201 unique cloners | `traffic/clones` |
| Page views recorded | 0 | `traffic/views` |

**The one datum worth reading twice:** 693 clone events and 201 distinct cloners
against 0 stars, 0 watchers and 0 recorded page views. Some of those clones are
this project's own verification runs and its CI, so the number is not clean — but
the *shape* is the channel map's central claim arriving as a measurement: on a
repository nobody has starred, machines are still fetching it. If that shape holds
once a post exists, the channel that matters is the one a machine reads, and the
retro's ranking will follow it rather than following the upvotes.

## Predicted top two, and the rule that confirms or kills it

Prediction, stated before the data exists so that it can be scored:

1. **The official MCP Registry record** (`io.github.abaddon/logos`). The mechanism:
   it is a search index that client libraries and aggregators poll, so one record
   is re-read forever, and it costs one afternoon. It is the only channel where an
   agent *executes* rather than reads.
2. **The `awesome-remote-mcp-servers` one-line PR.** The mechanism: 4,202 forks
   and every mirror and RAG index reproduce the line verbatim, so one accepted
   line gets copied by machines nobody will ever meet.

**Predicted to underperform its reputation:** Show HN. It will produce the most
*page views* of any single action and the fewest *attributable adoptions*, because
its audience is human, the artifact is Linux-only, and the half-life of a post is
hours. Its real product is two or three operators who then point their agents at
the endpoint — which is worth having, and is not the same thing as reach.

**Confirmation rule, applied at the first measurement sweep 14 days after wave 2:**
the top two are whatever has the most non-zero entries in the ledger's
*Attributable* column (forks, external PRs, challenge entries, tool calls traced to
a referrer) — **not** the most stars, views or upvotes. If HN leads on attributable
events, the prediction is wrong and the next quarter's effort moves to human
channels. Write the loss down; the map is only useful if it can be falsified.

## Recommended cadence

Four rhythms, none of which needs a credential this project does not have:

| Rhythm | What | Why this interval |
|---|---|---|
| **Per release** | The release page *is* the recurring launch: tag, notes from `CHANGELOG.md`, and it is a fresh crawled URL every time | It is the only channel that recurs without a credential, without social risk, and without a maintainer's afternoon. Releases are the cadence the project already has — make them the publishing unit |
| **Weekly, 30 min** | One ledger sweep with the commands in the checklist; answer every inbound question | Inbound questions are the input to the next wave's framing, and stale ones read as an abandoned project |
| **Monthly** | Re-resolve every registry and directory record; check the description strings against what is actually being searched | Records rot silently when a host moves a URL (Smithery is doing exactly that now), and a dead record is worse than an absent one |
| **Quarterly, at most one** | One human post — HN **or** Reddit, never both in the same quarter, never the same text | The subreddit's rules and HN's one-shot-per-title both punish frequency; a quarter is long enough for the artifact to have genuinely changed |

**Never:** re-post the same framing to the same place; post a date that the slip
rule can move; announce in a Discord; ask for stars in any copy.

## What this retro cannot tell you

Whether the copy converts. The HN body, the Reddit post, the registry description
and the list line are all written against measured facts and the map's rules, and
none of them has been read by a stranger. The first wave-1 post is also the first
test of the copy — treat the first 20 comments as the review the drafts did not
get, and revise the file in this pyramid rather than writing a fourth variant from
memory.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/01-summary/channel-ledger.md
 -> The table whose Attributable column decides the confirmation rule above
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> Every baseline number in this file, with the command and output that produced it
/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/02-analysis/ranked-shortlist.md
 -> The scores and dependencies the prediction is arguing from
