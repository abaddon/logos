# Copy — the awesome-list PR (the entry that gets copied)

**DO NOT OPEN UNTIL** a remote endpoint answers (owner-actions §A1) or a package
installs. The list's rules refuse a repo with neither, and a rejected PR burns the
one free "new contributor" glance a maintainer gives a project.

**Which list:** `punkpeye/awesome-remote-mcp-servers` (3,511★, 4,202 forks — the
fork count above the star count is the tell that this is a submission queue).
Remote-only servers belong there; `awesome-mcp-servers` only once there is an
installable package. Both lists' CONTRIBUTING documents an agent lane: **append
`🤖🤖🤖` to the end of the PR title** and the merge is fast-tracked.

---

## The one line

Placed alphabetically in the section for developer/code tooling, in the list's
existing format — `- [owner/repo](https://github.com/owner/repo) — description ending with a period`:

```markdown
- [abaddon/logos](https://github.com/abaddon/logos) — Type-check, compile, format and run Logos, a compiled language where allocation, fallible calls and release are visible in the source; diagnostics are JSON with a code and a node path.
```

Legibility out of context is the whole point: every mirror, scraper and RAG index
reproduces this line with no README beside it, so it must not say "a prefix-form
language" (means nothing alone) and must not depend on the word "Logos" being
known.

## PR title

```text
Add Logos (io.github.abaddon/logos) — compile and type-check Logos programs 🤖🤖🤖
```

## PR body

```markdown
Adds `io.github.abaddon/logos`, a remote MCP server for Logos.

**What it does.** Five tools: `check_program`, `compile_program`,
`format_source`, `run_example`, `get_language_reference`. Logos is a small
compiled language aimed at code an agent writes and a human still has to trust —
allocation is a call you can see, a call that can fail declares it, release is a
call you make, and the compiler refuses the rest. Diagnostics come back as JSON
objects carrying a `code` and a `node_path`, so a caller can branch on `E0100`
instead of on English.

**Why it is remote.** The compiler emits native x86_64/arm64 Linux binaries and
shells out to `clang`; it does not run on macOS, which is where most MCP clients
are. So the compiler runs server-side and the tools are the interface.

**Endpoint:** `https://<HOST>/mcp` (streamable-http)
**Registry record:** `io.github.abaddon/logos`
**Repo:** https://github.com/abaddon/logos (MIT, pre-1.0)

**Quick proof, from a client:**
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_program","arguments":{"source":"(mod hello)\n\n(fn main :void ()\n  (let x :i64 \"no\"))"}}}
```
returns `{"ok":false,"diagnostics":[{"severity":"error","code":"E0100",
"message":"let 'x' has type :i64, found :str","node_path":"hello/main/2"}]}`.

**Disclosure.** This PR was opened by an AI agent (`<agent name>`) operating the
GitHub account `abaddon`. The project's compiler is itself mostly agent-written —
87 of 118 commits carry the identity `Logos Builder <agent@logos.local>` — which
is the reason it is shaped the way it is. Happy to make any formatting or
placement change you want.
```

Why disclose in the body as well as the title: the title marker gets the PR
fast-tracked, and the body is what a human reads before deciding whether to keep
the line. An agent that discloses is a maintainer's normal contributor; one that
does not is a spam pattern they have already learned to spot.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> §A2: the fork, publish and `gh pr create` commands, and the gate this PR waits on
/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/02-analysis/channel-map.md
 -> The list's CONTRIBUTING rules (one line, alphabetical, agent lane) as fetched on 2026-11-18
