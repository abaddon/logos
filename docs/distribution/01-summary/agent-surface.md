# The agent-facing surface — what it is and why it reads the way it does

One paragraph: Logos now has four doors an agent can come through without a
human — `llms.txt` at the repository root, the README hero, the canonical
quickstart, and the consumer contract — and every door leads to the same five
commands. This page records the decisions behind the wording so the next person
who edits a page does not undo them.

## The path an agent takes

1. **`llms.txt`** — fetched first, by convention. It carries an install block and
   one line per page. An agent that reads only this file knows the version, the
   platform, the five commands and where the language is specified.
2. **`README.md`** — the human version of the same thing: tagline, one paragraph,
   the five-command quickstart with the output pasted, then status and limits.
3. **`docs/quickstart.md`** — the canonical walkthrough. Two routes, five
   commands each, then the diagnostic loop (`check` → `--json` → `show`), a test
   run, the language manifest, and the six gates.
4. **`docs/reference/agent-contract.md`** — exit codes, JSON shapes, determinism,
   traps. The page to read before scripting against the compiler.
5. **`AGENTS.md`** — the contributor contract, for the agent that stays: six
   gates, four invariants, the regress rule, the bootstrap rule.

The first three can be read in ten minutes and cost one install. The last two
are the difference between using the compiler and changing it.

## Wording decisions

The vocabulary is the messaging kit's, not invented here. The kit is
`docs/messaging/01-summary/positioning-kit.md` (its own branch, landing
separately); the rules that bind these pages are:

| Decision | Rule it follows |
|---|---|
| Tagline is **"Code an agent can read, write, and prove."** | the kit's nine-word tagline, verbatim |
| The opening paragraph is the kit's elevator paragraph, lightly cut to 63 words | the kit's "elevator, ≤60 words" block; the cut removes the platform list the README states twice |
| **"node path"**, **"code"**, **"refuses at compile time"**, **"native Linux ELF"** — never "clear errors", "catches mistakes", "memory safe", "fast" | kit §6, voice rules and the do/don't table |
| Every capability claim carries the version | the kit's rule 6: it is pre-1.0, and a version-less claim goes stale silently |
| The limit is named in the same breath as the feature | kit §4: each objection carries its own "The limit:" sentence |
| The challenge is always **"Logos Agent Challenge"**, path `docs/challenge/01-summary/program.md` | the challenge program's own name, so the anchor and the path stay stable across outreach |
| No prizes, no dates paraphrased | the challenge program §5 and §10; the README says "no prizes but a showcase page and a co-authored commit" and states the 2026-12-01 opening |

## Structure decisions

- **Two routes, both five commands.** The tarball is what a consumer does; the
  checkout is what a contributor does. Whichever an agent picks, it reaches a
  running binary in five commands and can stop.
- **The tests come before the language reference.** An agent's second question
  after "does it run" is "how do I know it still works", and the answer is a
  `(test …)` node in the same file. `examples/agent-gate/gate.logos` is the
  worked example: 174 lines, nine cases, `9 passed, 0 failed, 0 leaked`.
- **The diagnostic is shown as data, not prose.** `check --json` is pasted as
  one line with `code` and `node_path`, then `show` is used to prove the node
  path is an address. That pair is the claim the kit ranks first.
- **`llms.txt` is hygiene, not distribution.** The channel map measured that
  11.8% of live sites publish one and 97% of existing files are never fetched
  (`evangelism/02-analysis/machine-discoverability.md`). It costs one file and it
  is what an agent crawler looks for, so it exists — but it is not counted as
  reach.
- **No JSON-LD.** GitHub renders markdown, not injected structured data, so the
  machine-readable surface is `llms.txt`, the repository topics and
  `logosc guide --json`. Writing a JSON-LD block into a page no crawler parses
  would be decoration.

## The release this depends on

The quickstart's first route downloads `v0.2.2`. How that version number came to
be is worth keeping, because it is the release gate doing its job:

- **Two tags were cut.** `v0.2.1` was tagged on `main` and its release gate
  refused it twice over: the `verify` job failed the acceptance gate because the
  runner had no aarch64 sysroot (the release workflow now installs the cross
  toolchain, #48), and the tarball build behind it would have stopped at the
  shipped-page link check — `main`'s README links
  `examples/agent-gate/README.md`, which `tools/dist.sh` did not stage. No
  release exists for that tag.
- **`v0.2.2` is that tag plus the fix.** The two reference-project pages and
  `llms.txt` ship, `tools/verify_install.sh` requires them by name, and the only
  source change is the version string in `src/logosc/main.logos` — with the
  stage-0 binary rebuilt in the same commit, as the bootstrap rule requires.
- **The changelog carries that story**, so the release notes are true rather
  than reconstructed: the 0.2.1 entry says it was tagged and never released, and
  0.2.2 lists what the compiler carries since 0.2.0.

The residual impurity: a patch number carries feature work (aarch64, the
executable-relative lookup), which the project's own semver note says belongs to
a minor. It is stated here rather than hidden; the alternative was retagging
eight files and a bootstrap binary days before a launch.

## Repository metadata

Applied with `gh repo edit abaddon/logos` and read back with `gh repo view`:

| Field | Value |
|---|---|
| description | `Logos: code an agent can read, write, and prove. A prefix-form language and a self-hosting compiler to native Linux binaries.` |
| topics | `compiler`, `programming-language`, `self-hosting`, `llvm`, `ai-agents`, `llm`, `code-generation`, `language-design` |
| homepage | left empty: there is no site to point at, and a dead homepage is worse than none |

`llms.txt` sits at the repository root, which is the only root GitHub gives a
project. There is no website serving it at a domain root, so the file is
addressed as `https://github.com/abaddon/logos/blob/main/llms.txt` from outside
the repository.

## What this page does not claim

- No adoption, speed or ecosystem claim: the kit's ledger marks all three as
  deliberate cuts, and none appear in the files this task wrote.
- No claim that an agent wrote the quickstart's outputs: they are copied from the
  transcript in [`../03-dossiers/verification-log-2026-11-18.md`](../03-dossiers/verification-log-2026-11-18.md),
  which is the run itself.
