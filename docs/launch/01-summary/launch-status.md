# Launch status — what is public, what is blocked, and the order to clear it

**One line:** the launch kit is complete and the installable artifact is the only
surface this host could publish; a defect in the release pipeline — found by
trying to publish it — is the thing standing between the project and a working
install command.

## Public right now

| What | URL | State |
|---|---|---|
| Repo, metadata and topics | <https://github.com/abaddon/logos> | 10 topics, description set, `homepage` **null** |
| `AGENTS.md` | <https://github.com/abaddon/logos/blob/main/AGENTS.md> | HTTP 200 |
| Reference demo | <https://github.com/abaddon/logos/tree/main/examples/agent-gate> | verified from a cold clone: build, 8 verdict lines, `exit 5`, 9 tests, `0 leaked` |
| Latest installable release | <https://github.com/abaddon/logos/releases/tag/v0.2.0> | **v0.2.0** — the older packaging |

## Not public, and the exact reason

| What | Why not | Un-blocks when |
|---|---|---|
| **Release `v0.2.1`** | the release workflow failed its acceptance gate at 21:38 (see below); the tag exists, the release does not | PR #48 merges, then the tag is moved to the fixed commit and the workflow re-runs |
| **MCP endpoint + registry record** | no MCP server exists in the repository | someone builds the five-tool server ([`../03-dossiers/owner-actions.md`](../03-dossiers/owner-actions.md) §A1) |
| **npm `logos-mcp`** | no npm credential on this host (`npm whoami` → `ENEEDAUTH`), and the package is only honest once the endpoint exists | §A2, after §A1 |
| **`llms.txt`** | 404 on `main`; the file is being written by `t_5b93c8fe` in parallel | that branch merges |
| **Challenge page** | 404 on `main`; `wt/t_1c7448cf` is unmerged | that branch merges (and the README must not link it before it does) |
| **Show HN, r/LocalLLaMA** | no account credential here, and the sequencing rule forbids posting before an agent can call the compiler | §A3 / §A4, after waves 1–2 |

## The release: attempt 1 failed, and the reason is worth keeping

Pushed `v0.2.1` as an annotated tag on `main` (`546598a`) at 21:12Z. The workflow
ran the six gates and stopped at the fourth:

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

**Root cause, and why it is bigger than this release:** `tools/accept.sh` section 8
builds and runs an `aarch64-unknown-linux-gnu` ELF and deliberately fails by name
rather than skipping when the cross sysroot is missing. `gate.yml` installs
`gcc-aarch64-linux-gnu libc6-dev-arm64-cross qemu-user-static` for it.
`tools/toolchain.sh --install` pins clang and lld only — and all three
`release.yml` install steps called just that. **Every tag pushed since the aarch64
target landed (`9c9f63c`, PR #43, 2026-11-18 08:41Z) would have failed the same
way.** Nothing noticed because nothing had pushed a tag since v0.2.0.

So the honest version of "publish v0.2.1", which the challenge program lists as
pre-launch check 2, is not one command: it is a one-line CI fix, a gate run, a
merge, and a re-tag. That fix is PR #48
(<https://github.com/abaddon/logos/pull/48>), open at the time this page was
written, with the failing run linked from its body.

**This is the most valuable thing the launch found.** A launch post that quotes
`gh release download` and lands on a release gate that has been red for two days
would have produced a thread full of "the install doesn't work", which is exactly
the failure the messaging kit warned about in its section 0 and could not fix from
inside a document.

## The order to clear it

1. **Merge PR #48** once its `gate` check is green.
2. **Move the tag** to the merge commit and let the workflow publish —
   `git tag -d v0.2.1 && git push --delete origin v0.2.1`, then re-tag on the new
   `main` tip. Safe because no release was ever created from the old tag; verify
   with `gh release view v0.2.1` → `release not found` before deleting.
3. **Verify the tagless install** from a machine that is not this one:
   `gh release download --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS && sha256sum -c SHA256SUMS && tar -xzf logos-*-x86_64-linux.tar.gz && cd logos-*-x86_64-linux && ./bin/logosc version`.
   That is challenge pre-launch check 1, and it should print `logos 0.2.1`.
4. **Build the endpoint** (§A1). Everything scored 8 in the channel map is behind
   it: registry, npm, both lists, the Space, and — because of the sequencing rule —
   both human posts.
5. **Merge the challenge branch** before anything links it, then run §A9's checks
   3–8 before any copy names a date.

## What was deliberately not done

- **No post was made anywhere.** One credential (GitHub) does not buy an HN
  account, an npm token or a subreddit history, and fabricating a "posted" row in
  the ledger would poison the retro's only input.
- **The tag was pushed rather than a local `release.sh --publish`.** The workflow
  proves byte-identity across two runners; a local publish would have shipped an
  artifact this host alone had checked.
- **`llms.txt` was not written** while `t_5b93c8fe` was writing it; I commented the
  404 window on that card instead.
- **The sibling branches were not merged.** Each merge runs the full gate and is
  the coordinator's call, not a side effect of a launch task.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> Every command behind this page with its real output, including the failed release run
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> Steps A1–A9: the endpoint, npm, the posts, the two repo switches, and the pre-launch checks
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/launch-checklist.md
 -> Per-channel gate and status, and the four-wave model that orders the posts
