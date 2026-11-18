# Distribution and agent-facing docs — index

What this work shipped, who it is for, and the command that proves each claim.
The audience is an agent that has just landed on the repository with no human in
the loop, plus the person who points one at it.

| If you want | Read |
|---|---|
| the five-command install, verified | [`../quickstart.md`](../quickstart.md) |
| the one-file index an agent reads first | [`../../llms.txt`](../../llms.txt) |
| the decisions behind the wording and the structure | [`01-summary/agent-surface.md`](01-summary/agent-surface.md) |
| the commands and their real output | [`03-dossiers/verification-log-2026-11-18.md`](03-dossiers/verification-log-2026-11-18.md) |

## What shipped

| File | What it is | Proven by |
|---|---|---|
| `llms.txt` (repository root) | the emerging `llms.txt` convention: an H1, a blockquote summary, then one line per important page — install, language, examples, contribution | every URL returns 200; the file ships in the release tarball and `tools/verify_install.sh` requires it |
| `README.md` (hero) | tagline, one-paragraph pitch, a five-command quickstart with pasted output, and links to the agent-facing docs and the Logos Agent Challenge | the quickstart block is copied from the run in the verification log |
| `docs/quickstart.md` | **the canonical quickstart**: both routes in five commands each, then a diagnostic read as JSON, a test run, the language manifest, the gates, and the traps | every command and output in it appears in the verification log, in order |
| `docs/install.md` | the consumer page: download, checksum, unpack, lookup order, environment variables, uninstall | the layout list now matches the artifact; the tarball run is in the log |
| `docs/00-index.md` | the index grew rows for `llms.txt`, the challenge and this page; two stale counts were corrected (35 → 36 diagnostic codes) | `tools/check_doc_links.sh` |
| `CHANGELOG.md` | the history now tells the truth about the tags: 0.2.1 was tagged and the release gate refused it (aarch64 sysroot in the acceptance gate, then a shipped-page link check), 0.2.2 is the published release and lists what the compiler carries since 0.2.0 | `gh release list`; `git log v0.2.1..v0.2.2` |
| `tools/dist.sh`, `tools/verify_install.sh` | `llms.txt` and the reference project's two pages ship in the tarball, and the install check requires them | `bash tools/release.sh` |
| repository topics and description | the GitHub-side metadata an agent's crawler sees before it opens a file | `gh repo view --json description,repositoryTopics` |

## What was not changed, and why

- **`AGENTS.md`** is the contributor contract and it already states what Logos
  is, the six gates, the four invariants, the regress rule, the bootstrap rule
  and the pull-request rules. The install-and-run path it lacked is now covered
  by [`../../llms.txt`](../../llms.txt) and
  [`../quickstart.md`](../quickstart.md), both linked from the README hero.
  `docs/00-index.md` still records its one stale claim (the suites' optimisation
  levels) rather than leaving it for a reader to discover.
- **The messaging kit's `v0.2.0` copy blocks** are deliberately left alone. The
  kit's section 0 said the install command was broken until the version it names
  was published; `v0.2.2` is that release, and the changelog says why 0.2.1 was
  not. Re-running the kit's blocks against `v0.2.2` is the outreach task's job,
  not this one's.
- **No JSON-LD.** GitHub serves markdown and renders no injected structured
  data, so the equivalent machine-readable surface is `llms.txt`, the repository
  topics and `logosc guide --json`.

## SOURCES

Absolute paths on the working tree
(`/root/ai-language-program/.worktrees/t_5b93c8fe`).

| Path | What it establishes |
|---|---|
| `/root/ai-language-program/.worktrees/t_5b93c8fe/llms.txt` | the index itself; its links are the 15 pages an agent needs |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/docs/quickstart.md` | the canonical walkthrough, both routes |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/docs/messaging/01-summary/positioning-kit.md` | the tagline, the elevator paragraph and the voice rules this README follows (from the sibling messaging task) |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/docs/challenge/01-summary/program.md` | the Logos Agent Challenge the README's "build something with it" section points at |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/examples/agent-gate/README.md` | the reference project the quickstart's test step runs |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/tools/dist.sh` | what the release tarball ships, and the link check it runs before writing it |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/tools/verify_install.sh` | the layout the unpacked artifact must have |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/docs/distribution/03-dossiers/verification-log-2026-11-18.md` | every command run for this page, with its output |
