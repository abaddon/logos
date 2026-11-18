# Feasibility — every mechanism and award, checked against what exists

The program in [`../01-summary/program.md`](../01-summary/program.md) promises
fourteen things. This page takes each one and asks: *does the capability exist
today, and what is the command that proves it?* Anything that failed the check
was removed from the program rather than softened.

Everything below was run on 2026-11-18; the transcripts are in
[`../03-dossiers/verification-log.md`](../03-dossiers/verification-log.md).

---

## 1. The entry mechanism

| Mechanism | Depends on | Status | Proof |
|---|---|---|---|
| Third party can install and compile | a published release that downloads and runs | **works** | `gh release download --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS` → `sha256sum -c` OK → `./bin/logosc version` → `logos 0.2.0` → `build hello.logos -o hello && ./hello` → `hello from logos`, exit 0 |
| Entry as a GitHub issue | issues enabled, issue forms supported | **works** | `gh api repos/abaddon/logos --jq .has_issues` → `true`; `.github/ISSUE_TEMPLATE/bug.yml` is an issue *form* already in use, so `challenge-entry.yml` needs no new capability |
| Label-based counting | labels creatable | **works** | 18 labels exist; coordinator is authenticated as `abaddon` with the `repo` scope |
| Optional repo topic for entrants | uniqueness | **works, with a caveat** | `topic:logos-lang` already returns **5 unrelated repositories**; `topic:logos-agent-challenge` returns **0**. The program therefore never counts topics, and uses its own name only as an optional nicety |
| Coordinator can run an entry's command | x86_64 Linux + clang, network for `gh` | **works** | clang 14.0.0, lld 14, gcc, jq all present on the audit machine; the tarball route above was executed here |
| Gate 0 on a *fresh clone* of an entrant's repo | public repo reachable | **works** | `gh repo clone` + the entrant's command; no credential needed for public repos |

**Rejected on this evidence:** *"submissions live in GitHub Discussions."*
Discussions is **off** (`has_discussions: false`). It can be switched on — the
token carries `write:discussion` — but a discussion thread is a worse venue of
record than a labelled issue: it cannot be assigned, cannot be labelled, and the
REST search API does not index replies. The program uses issues and does not
require a settings change at all.

**Constraint accepted:** entries must run on **x86_64 Linux**. That is not a
choice — the release ships one artifact and the compiler's own limits page says
so ([`../../reference/limits.md`](../../reference/limits.md): "One artifact: an
x86_64 Linux tarball. No package manager, no container image"). A macOS entrant
cannot run Gate 0, so Track A is honest about the platform in the entry form
rather than discovering it at judging.

---

## 2. The awards

| Award | Depends on | Status | Proof / why it holds |
|---|---|---|---|
| Ledger row | a markdown table in `docs/showcase/00-index.md` | **works** | the repo already carries generated and hand-written docs tables; a new `docs/` subdirectory needs no infrastructure |
| Showcase page | the same | **works** | `docs/showcase/<slug>.md`, linked from the index; `tools/check_doc_links.sh` keeps the links honest |
| `Co-authored-by:` credit | the entrant's git identity, a commit by the coordinator | **works** | git trailer, no platform feature involved. The repository's history already carries three author identities (`Logos Builder`, `Stefano Longhi`, `Sonike`), so a fourth is not a new mechanism |
| `CHANGELOG.md` "Thanks" line | a CHANGELOG section per version | **works** | `CHANGELOG.md` carries one section per version and is the release-notes source (`docs/release.md`), so a version section is edited anyway when a Track B fix changes behaviour |
| `good first issue` pathway | the label, and issues that deserve it | **label works, backlog does not exist yet** | the label exists (`gh label list`), but **0 are open today** — the 4 that ever carried it are closed (#3, #4, #5, #14). Seeding them is a hard pre-launch check, not an assumption |
| Named in the recap | one more markdown page | **works** | same as above |

**Removed from the program:** *"a public leaderboard with live updating."* There
is no hosting and no bot to run it, so what ships is a table updated by hand every
Monday — which is what the program says, and which is honest about the fact that
it is only as live as the coordinator.

---

## 3. The incentives that are *not* offered

| Not offered | Why not | Proof |
|---|---|---|
| Cash bounty | no funding mechanism exists on this repository | `git ls-files \| grep -i -E 'funding\|sponsor'` → no match; no GitHub Sponsors page is configured |
| Swag | needs money, an address-handling policy, and per-entrant shipping | nothing in the repository or the account backs any of the three |
| Job / internship / grant | nothing can back the words | — |
| Bounty paid "later, if funded" | an unpaid promise is worse than no challenge | — |

The single amendment in the program (section 5: one cash award per track, paid
by the maintainer through a GitHub Sponsors one-time payment, declared before
`L-7`) is deliberately *one* line, because GitHub Sponsors one-time payments are
the only payout path that needs no escrow, no contract and no legal entity. Even
that path needs a Sponsors profile with a bank account, so it is conditional on
the maintainer setting that up — which is why it is an amendment rather than a
promise, and why the program ships without it.

---

## 4. Judging feasibility

| Requirement | Status | Notes |
|---|---|---|
| A rubric that one person can apply | **works** | 5 criteria × 0–2; four of the five are mechanical (Gate 0, `(test …)` node count, line count, `fmt` idempotency) |
| A reproducibility check the coordinator can actually run | **works** | one command per entry from a fresh clone; measured at ~5 minutes including clone |
| Evidence that a `(test …)` node can be counted objectively | **works** | `logosc test` exists and reports per-case results in text (`logosc test FILE`); the absence of `test --json` is a known limit, so the count is read from text output |
| Objective "canonical form" check | **works, but not with a flag** | `logosc fmt -h` shows **no `--check` flag** — it rewrites in place. The rubric therefore specifies: copy the file, run `fmt` on the copy, `diff`. Executed: `diff` empty on formatted source |
| Track B judged by "merged" only | **works** | the repository's own gate decides: `bash tools/check_dco.sh` is a step in `.github/workflows/gate.yml` and `tools/pr_gate.sh` runs the same six gates locally plus that check. Note precisely which is which — CI does **not** invoke `pr_gate.sh`; it runs the gates as separate steps, and `pr_gate.sh` calls itself the local twin |

**Rejected on this evidence:** *"score Track B on code quality."* There is no
second reviewer, and the repo's gate is already stricter than a rubric would be.
Adding one would let a coordinator's taste override a measured gate.

---

## 5. Metrics feasibility

Every metric in the program is a command against a surface that answered today:

| Metric | Surface | Today's value |
|---|---|---|
| Entries | issue label search | label does not exist yet → 0 by construction |
| Distinct operators | issue `author` field | — |
| Distinct agents | a column the coordinator fills | — |
| Merged PRs, external | `gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged"` | **32 merged**, of which **31 by `abaddon`** and **1 by `Sonike` (#12)** — so the external baseline is 1, not 0 |
| First-time landers | author sets before/after `L` | baseline 1 (Sonike) |
| Reuse | `repos/<owner>/<repo>` `forks_count`, plus issues/PRs citing the repo | 0 today |
| Defects found | issue label | 0 today |

Two honest weaknesses, stated so the recap can be read correctly:

1. **M3 (distinct agents)** is only as good as the disclosure field. It is
   self-reported and the coordinator cannot verify a model name. It is a
   *reported* number, and the program says so.
2. **M6 (reuse)** measures forks and inbound references, which undercount reuse
   by copy-paste. A copy is invisible to the API. The metric is a lower bound.

---

## 6. Timeline feasibility

| Claim | Status | Evidence |
|---|---|---|
| A release can be cut in an afternoon | **works** | `make release` builds the tarball twice, compares SHA-256, and runs 5 install checks (`docs/release.md`, recorded run on `0b6ee47`); publishing is `git tag` + `git push` and `.github/workflows/release.yml` does the rest |
| The six-gate suite a contributor must pass exists and is one command | **works, and it is slow** | `bash tools/pr_gate.sh` on 2026-11-18: six PASS lines, **1 h 08 m elapsed** on a 6-core box also running a second gate. Transcription in the verification log. An agent's loop is cheap; this gate is the expensive step, which is why Track B is a week-long track and not an afternoon one |
| Launch can slip without cascading edits | **works, with four artifacts to re-issue** | every date in the program carries its `L+n` offset, so the new dates are arithmetic; a slip re-issues the timeline table, the close date in the paste block, the close date in the form, and the two dates in the M4/M5 queries — all named in the program's slip rule |
| 45-day window is enough for several entries | **plausible, not measured** | the reference demo task built a working Logos project in one session, and the compiler's own `examples/` run 73–487 lines (`matrix` 73, `wc` 94, `json` 487). This is the one estimate in the document with no measurement behind it, and the rescue checkpoint at `L+20` exists because of that |

---

## 7. What the pre-launch checks cost

Measured or estimated on 2026-11-18, as coordinator time:

| Check | Cost |
|---|---|
| Publish `v0.2.1` or re-point three pages | 30–60 min (release rehearsal is automated; the re-point is three one-line edits) |
| Merge challenge docs + showcase skeleton + entry form + labels | 30 min |
| Seed 8 `good first issue` issues | 60–90 min — the real cost, because each needs a done condition |
| Test the entry form end to end | 10 min |
| **Total** | **under half a day**, which is why 2026-12-01 is defensible and 2026-11-20 would not be |

---

SOURCES

- `../01-summary/program.md` — the program these checks back, section by section.
- `../03-dossiers/verification-log.md` — the commands and their real output.
- `/root/ai-language-program/.worktrees/t_c0360ffd/docs/messaging/02-analysis/claim-ledger.md`
  — the claim → command → status ledger for the numbers the program quotes.
- `/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/02-analysis/machine-discoverability.md`
  — why a callable, verifiable surface matters more than a post, which is the
  assumption the reproducibility gate rests on.
