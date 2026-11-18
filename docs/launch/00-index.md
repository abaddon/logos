# Logos outreach launch — execution record and launch kit (2026-11-18)

Mission: put Logos in front of third-party AI agents on the shortlisted channels,
with copy written for each channel's own norms, and report what worked.

## Read this first

- **The status page** — what is public now, what each blocker is, and the order to
  clear them in: [`01-summary/launch-status.md`](01-summary/launch-status.md)
- **The ledger** — every channel, posted date, link, and the measurement that
  fills each row: [`01-summary/channel-ledger.md`](01-summary/channel-ledger.md)
- **The retro** — what the launch produced, the baseline it started from, the
  predicted top two channels and the rule that scores that prediction, and the
  recommended cadence: [`01-summary/retro.md`](01-summary/retro.md)
- **The checklist** — one row per channel with the exact artifact, the framing and
  length, the rules to respect, the gate in front of it, and its status:
  [`02-analysis/launch-checklist.md`](02-analysis/launch-checklist.md)
- **The copy** — paste-ready, channel-native, four files:
  [`02-analysis/copy/`](02-analysis/copy/) — [machine surfaces](02-analysis/copy/mcp-surface.md) ·
  [awesome-list PR](02-analysis/copy/awesome-list-pr.md) ·
  [Show HN + r/LocalLLaMA](02-analysis/copy/forum-posts.md) ·
  [Space + container](02-analysis/copy/space-and-container.md)

## Headline

**Nothing is posted, and one thing had to be fixed before anything could be.** The
launch was routed to this host with exactly one writable channel — GitHub — so the
release was the only publishable surface, and the attempt to publish it uncovered
the real blocker: the release workflow had been failing its acceptance gate on
every tag since the aarch64 target landed two days earlier, so `v0.2.1` could not
ship and the README's install command returned `release not found`. That is fixed
in PR [#48](https://github.com/abaddon/logos/pull/48) — a one-line toolchain
install — and the release re-runs on merge. Everything else on the shortlist needs
what this machine does not have: a server that answers `tools/list`, an npm token,
Docker, an HF token, or an HN or Reddit account. Those are handed back as
instructions rather than faked as "done", which is why the kit below is complete
and unposted.

## Pyramid map

| Layer | File | Consumer |
|---|---|---|
| L1 | [`01-summary/launch-status.md`](01-summary/launch-status.md) | whoever decides what happens next |
| L1 | [`01-summary/channel-ledger.md`](01-summary/channel-ledger.md) | whoever runs the weekly sweep |
| L1 | [`01-summary/retro.md`](01-summary/retro.md) | whoever plans the cadence |
| L2 | [`02-analysis/launch-checklist.md`](02-analysis/launch-checklist.md) | whoever executes a row |
| L2 | [`02-analysis/copy/`](02-analysis/copy/) (4 files) | whoever pastes a post |
| L3 | [`03-dossiers/verification-log.md`](03-dossiers/verification-log.md) | anyone re-checking a claim |
| L3 | [`03-dossiers/owner-actions.md`](03-dossiers/owner-actions.md) | the human with the credentials |

SOURCES (LAYER 2 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/01-summary/launch-status.md
 -> What is public, what is blocked, what to do first: the one page to read if you read one
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/01-summary/channel-ledger.md
 -> The tracking table, half-filled, with the command that fills each empty cell
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/01-summary/retro.md
 -> Baseline numbers, the two-channel prediction with its scoring rule, and the cadence
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/launch-checklist.md
 -> 21 channels: artifact, framing, rules, gate, status; the four waves and their gating
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/copy/
 -> Four channel-native drafts — registry/npm/mcp.so, awesome-list PR, HN + Reddit, Space + Docker
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> Every command run for this launch and its real output, including the failure it kept
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> The nine owner actions with exact commands, URLs and definitions of done
