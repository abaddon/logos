# Launch status — what is public, what is blocked, and the order to clear it

**One line:** the installable release is public and verified end to end, the
repo's agent-readable surface is live, and every remaining channel waits on one
missing artifact — an MCP endpoint — or on a credential this host does not hold.

## Public right now, verified from outside this repo

| What | URL | State |
|---|---|---|
| **Release `v0.2.2`** | <https://github.com/abaddon/logos/releases/tag/v0.2.2> | published 2026-11-18 22:42:57Z, four jobs green, `releases/latest` resolves to it |
| Tagless install | `gh release download --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS` | executed 2026-11-18 22:47Z: checksum `OK`, `./bin/logosc version` → `logos 0.2.2`, hello world compiled and ran |
| `llms.txt` | <https://github.com/abaddon/logos/blob/main/llms.txt> | HTTP 200 (landed with #49, after the 404 recorded below) |
| `AGENTS.md` | <https://github.com/abaddon/logos/blob/main/AGENTS.md> | HTTP 200 |
| Reference demo | <https://github.com/abaddon/logos/tree/main/examples/agent-gate> | cold clone: build, 8 verdict lines, `exit 5`, `9 passed, 0 failed, 0 leaked` |
| Logos Agent Challenge page | <https://github.com/abaddon/logos/blob/main/docs/challenge/01-summary/program.md> | HTTP 200, and the README links it |
| Repo metadata | <https://github.com/abaddon/logos> | 10 topics, description set; `homepage` still **null** |

## Not public, and the exact reason

| What | Why not | Un-blocks when |
|---|---|---|
| **MCP endpoint + registry record** | no MCP server exists in the repository | someone builds the five-tool server: [`../03-dossiers/owner-actions.md`](../03-dossiers/owner-actions.md) §A1 |
| **npm `logos-mcp`** | no npm credential here (`npm whoami` → `ENEEDAUTH`); the package is only honest once the endpoint exists | §A2, after §A1 |
| **Show HN, r/LocalLLaMA** | no account credential, and the sequencing rule forbids posting before an agent can call the compiler | §A3 / §A4, after wave 1 |
| **mcp.so, Smithery, both awesome lists** | all four are entries *about* the endpoint | §A1, then §A5 and the PR draft |
| **Docker catalog, HF Space** | no Docker on this host, no HF token | §A6 / §A7 |
| **Challenge round 1 itself** | pre-launch checks 4–8 still red: no `challenge-entry` label, no entry form merged, `docs/showcase/` absent, 3 open issues and **0** `good first issue` | §A9, before any copy names a date |

## The release: how it got here, because the detour is the finding

The launch's first action was an annotated tag `v0.2.1` on `main` (`546598a`), at
21:12Z, because eight files presented v0.2.1 as current and the README's own
`gh release download v0.2.1` returned `release not found`. The workflow ran the
six gates and stopped at the fourth:

```
PASS sign-off (precondition)
PASS unit tests
PASS corpus
FAIL acceptance  — FAIL aarch64-unknown-linux-gnu: no aarch64 sysroot at
                   /usr/aarch64-linux-gnu; install gcc-aarch64-linux-gnu and
                   libc6-dev-arm64-cross
PASS manual drift
PASS formatting
PASS self-hosting
5/6 gates passed, 1 failed        -> build, reproduce, publish all skipped
```

<https://github.com/abaddon/logos/actions/runs/44398996372>

**Root cause, and why it was bigger than this release:** `tools/accept.sh` section 8
builds and runs an `aarch64-unknown-linux-gnu` ELF and fails by name rather than
skipping when the cross sysroot is missing. `gate.yml` installs the cross packages
for it; `tools/toolchain.sh --install` pins clang and lld only, and all three
`release.yml` install steps called just that. **Every tag pushed since the aarch64
target landed (`9c9f63c`, PR #43, 2026-11-18 08:41Z) would have failed the same
way.** Nothing noticed, because nothing had pushed a tag since v0.2.0.

Fixed in PR [#48](https://github.com/abaddon/logos/pull/48) — gate.yml's package
list added to the release verify job, one logical change, its own gate green in
29m17s, merged as `6dab172`. The version moved to **0.2.2** in PR
[#49](https://github.com/abaddon/logos/pull/49) (the docs task), whose `CHANGELOG`
section records both tags. `v0.2.2` then published with `verify`, `build`,
`reproduce` and `publish` all green:
<https://github.com/abaddon/logos/actions/runs/44408697968>.

**Why it matters for the launch and not only for CI:** a launch post that quotes
`gh release download` would have landed on a release gate that had been red for two
days, and produced exactly the thread the messaging kit warned about — "the
install doesn't work". The kit could not have fixed that from inside a document.

## The order to clear it

1. **Build the endpoint** (§A1). Everything scored 8 in the channel map is behind
   it: the registry, npm, both awesome lists, mcp.so, the Space — and, because of
   the sequencing rule, both human posts.
2. **npm `logos-mcp` + the registry record** (§A2, then §A1's publish step), then
   the four directory entries in one sitting (§A5).
3. **Observe 48h.** Tool calls and `npx` installs, not stars. A broken tool found
   by 40 agents is a fixed bug; the same bug found by a front page is a thread.
4. **Show HN**, then **r/LocalLLaMA** fourteen days later — reproduce the drafts
   in [`../02-analysis/copy/forum-posts.md`](../02-analysis/copy/forum-posts.md),
   and revise them from the first 20 comments rather than from memory.
5. **Merge the messaging kit branch** (`wt/t_c0360ffd`) if the launch kit is to
   link it; today it is 404 on `main` and only this pyramid references it by path.
6. **Run §A9's challenge checks** before any copy names 2026-12-01.

## What was deliberately not done

- **No post was made anywhere.** One credential (GitHub) buys no HN account, no npm
  token, no subreddit history; a fabricated "posted" row would poison the only
  input the retro has.
- **The tag was pushed rather than a local `release.sh --publish`**, so the artifact
  is proved byte-identical across two runners instead of trusted from one host.
- **`llms.txt` was not written** while `t_5b93c8fe` was writing it; that branch has
  since merged and the file is live.
- **The two repository switches** (Discussions on, `homepage` set) were left alone:
  a homepage needs an endpoint or a Space to point at, and Discussions starts a
  support surface nobody has agreed to answer.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> Every command behind this page with its real output: credentials, the failed run, the published run, the install transcript
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> Steps A1–A9: the endpoint, npm, the posts, the two repo switches, the challenge checks
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/launch-checklist.md
 -> Per-channel gate and status, and the four-wave model that orders the posts
