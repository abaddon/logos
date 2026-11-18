# Owner actions — the channels this host cannot post to, with the exact steps

Each block below is a channel the launch is prepared for but cannot execute,
because the credential or the infrastructure does not exist on this host. Every
block states: what to do, the exact command or URL, what to observe afterwards,
and what "done" looks like. None of them takes more than an afternoon; the first
two are what actually move the needle.

Order matters. **A1 → A2 → A3 → A4** are the dependency chain the channel map
established, and posting out of order is what makes a launch bounce.

---

## A1. Stand up the MCP endpoint (the gate on everything else)

Score 8 in the map and the reason the map says "be the compiler an agent can
*call*". Nothing here is blocked on money — it is blocked on a host.

**Build the server** (Python, `modelcontextprotocol/python-sdk`, five tools):

| Tool | Signature | Behaviour |
|---|---|---|
| `check_program` | `(source, filename?)` | `logosc check` → `{ok, diagnostics[]}`; each diagnostic keeps `code`, `message`, `node_path`, `line`, `col` |
| `compile_program` | `(source, optimize?)` | `logosc build --json` → `{ok, ir, binary_sha256, diagnostics[]}` |
| `format_source` | `(source)` | `logosc fmt` to stdout, canonical form |
| `run_example` | `(name)` | one of the repo's examples → `{stdout, exit_code, leaks}` |
| `get_language_reference` | `()` | `logosc guide --json` (96 forms / 36 codes / schema_version 1) |

**Deploy** it as streamable-http. Requirements that are not optional: a Linux
container with `clang` in it (the compiler shells out to clang on every build),
a per-request timeout, and a rate limit — this executes model-authored source,
so it is a compute surface, not a read-only API. Bind the tools to a scratch
directory per call.

**Where it goes when it is up:**
```sh
mcp-publisher init                       # name it io.github.abaddon/logos
mcp-publisher login github
mcp-publisher publish                    # no human review; namespace is proved by the repo
```
Namespace ownership for `io.github.abaddon/*` is proved by a marker file in the
repository — read `modelcontextprotocol.io/registry/quickstart` at the time you
do it; the mechanics are stable but the exact marker file name has changed once
already.

**Done when:** `curl -X POST <endpoint> -H 'content-type: application/json' -d
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'` lists the five tools, and
`registry.modelcontextprotocol.io` returns the record.

**Copy for it:** [`../02-analysis/copy/mcp-surface.md`](../02-analysis/copy/mcp-surface.md).

## A2. npm: `logos-mcp`, and the awesome-list PR it unblocks

```sh
npm login                                  # the credential this host lacks
cd logos-mcp && npm publish --access public
```

The package must do one thing: be `npx logos-mcp` in a config file, talking to
the hosted endpoint. Do not ship the Linux binary inside it — the majority
audience is macOS and the package would install and then fail, which is worse
than not existing.

**Then** the list PR (needs a public installable package or a live remote — the
list's own rules refuse a repo with neither):

```sh
gh repo fork punkpeye/awesome-remote-mcp-servers --clone
# add ONE line, alphabetical within its section, in the existing format:
#   - [abaddon/logos](https://github.com/abaddon/logos) — Type-check, compile and run Logos programs; diagnostics as a code and a node path.
gh pr create --title "Add Logos (io.github.abaddon/logos) 🤖🤖🤖" --body-file /dev/stdin <<'BODY'
…paste the body from ../02-analysis/copy/awesome-list-pr.md…
BODY
```

The trailing `🤖🤖🤖` is the list's documented opt-in for agent-authored PRs and
gets it fast-tracked; put it in the **title**, exactly as its CONTRIBUTING says,
and say in the body which agent opened it and who operates the account. Remote
entries belong on the *remote* list, not the main one.

**Done when:** `gh pr view --json state,mergedAt` → `MERGED`, or a maintainer
reply that says what to change.

## A3. Show HN (one shot; needs A1 + the demo)

Post only after the endpoint answers and the demo runs. Then:

<https://news.ycombinator.com/submit> — title and body in
[`../02-analysis/copy/forum-posts.md`](../02-analysis/copy/forum-posts.md).
Rules that decide whether it survives: no marketing voice, the first command
must work on the reader's machine (x86_64 Linux — say so in the body rather than
letting them find out), and the author must be in the thread for the first three
hours answering, including the hostile questions about pre-1.0 status and the
21-function standard library.

## A4. r/LocalLLaMA, two weeks after HN

Disclose authorship in the first line — the rule is explicit in the subreddit's
self-promotion policy and a post without it is removed. Post from an account with
history in the sub; a fresh account posting a project is what the rule exists to
stop. Draft in
[`../02-analysis/copy/forum-posts.md`](../02-analysis/copy/forum-posts.md).

## A5. mcp.so and the mirror directories — cheapest entries in the map

<https://mcp.so/submit> (free form; one page per server, no review). Submit only
after A1: a directory page for a server that does not answer is a dead link the
crawlers keep. Then Smithery (`npx @smithery/cli` deploy), Glama and PulseMCP —
each is a copy of the same description string, so do them in one sitting and log
them in the same row of the ledger rather than as four channels.

## A6. Docker MCP Catalog — the only way a Mac runs the real compiler

```sh
# on a host with docker:
docker build -t ghcr.io/abaddon/logos-mcp:0.2.1 .
docker push ghcr.io/abaddon/logos-mcp:0.2.1
gh repo fork docker/mcp-registry --clone
# add servers/abaddon-logos/{server.yaml,tools.json}, then open the PR
```

The image must build `logosc` from source inside the build (the release tarball's
binary is glibc-bound; building keeps the image honest about what it contains).
Submission is a PR to `docker/mcp-registry` — 3,206 forks is the tell that
everyone submits this way.

## A7. Hugging Face Space — the clickable demo

```sh
huggingface-cli login                      # token this host lacks
huggingface-cli repo create logos-playground --type space --space_sdk docker
```

The Space runs the four examples and prints the IR next to the source. This is
the link HN and Reddit traffic lands on when the visitor does not want to install
anything, which is most of them. `README.md` frontmatter and the run command are
in [`../02-analysis/copy/space-and-container.md`](../02-analysis/copy/space-and-container.md).

## A8. Two repository switches, 30 seconds, no credential needed beyond `repo`

```sh
gh api -X PATCH repos/abaddon/logos -f has_discussions=true   # Discussions is OFF today
gh api -X PATCH repos/abaddon/logos -f homepage='<the Space or endpoint URL>'
```

Discussions off means there is no place for "I built something with it" to land
outside an issue tracker; `homepage: null` means there is nowhere to send a
visitor who wants a demo. Neither is a channel on its own, but both are
prerequisites for the channels that are, and the second one cannot be set until
A1 or A7 exists to point at. **Deliberately not flipped by this run:** enabling
Discussions starts a support surface nobody has committed to answering, and a
homepage URL pointing at nothing is worse than none.

## A9. Pre-launch checks that are not mine but gate the posts

The challenge program's §9 lists eight hard checks for 2026-11-27. Two were
red before this run and one of them is now green:

| Check | State at 21:30 on 2026-11-18 | Owner |
|---|---|---|
| 2 — v0.2.1 published | **cut by this run**, tag pushed 21:12; publish depends on the release workflow | this run, verified in [`../01-summary/launch-status.md`](../01-summary/launch-status.md) |
| 3 — challenge page at a stable URL on `main` | red (`404`) — branch unmerged | merge `wt/t_1c7448cf` |
| 4 — entry issue form merged and filing | red — form written, not submitted | challenge coordinator |
| 5 — `docs/showcase/` with an empty ledger | red — does not exist on `main` | challenge coordinator |
| 6 — ≥5 `good first issue`, ≥10 open total | red — 3 open, 0 `good first issue` | file the 11 issues listed in the challenge's `assets.md` §3 |
| 7 — labels `challenge-entry`, `challenge-findings` | unknown / likely red | `gh label create` |

Do not post the launch date until checks 3–8 are green: the program's slip rule
moves `L` to 2026-12-08, 12-15 or 2027-01-05, and a date in a post that later
moves is the kind of correction that costs more than the post bought.

SOURCES (LAYER 3 — this file is a dossier; it has no deeper layer)
/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/02-analysis/ranked-shortlist.md
 -> The dependency chain A1→A2→A3 that this ordering follows, with the scores behind it
/root/ai-language-program/.worktrees/t_1c7448cf/docs/challenge/01-summary/program.md
 -> §9 pre-launch checklist and §10 the paste block, both referenced above
