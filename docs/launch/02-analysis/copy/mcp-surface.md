# Copy — the machine-readable surface: MCP registry, npm, mcp.so, Smithery

**DO NOT PUBLISH ANY OF THIS UNTIL THE ENDPOINT ANSWERS.** The registry has no
human review, which is exactly why it is easy to poison: a record describing five
tools that time out is worse than no record, because the aggregators copy it and
every copy is a dead link an agent will hit. Gate: `tools/list` returns the five
tools and a real `check_program` call returns diagnostics (see
[`../../03-dossiers/owner-actions.md`](../../03-dossiers/owner-actions.md) §A1).

The organising rule for this whole file: **the description string is the only
pitch an agent ever sees.** It is matched against what a planner searches for, so
it names the capability in those words and puts the brand after the verb. Nobody
searches for "Logos"; they search for "compile a program" and "type-check".

---

## 1. Official MCP Registry — `server.json`

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json",
  "name": "io.github.abaddon/logos",
  "title": "Logos",
  "description": "Type-check, compile, format and run Logos programs. Diagnostics come back as JSON with a code and a node path.",
  "version": "0.2.1",
  "websiteUrl": "https://github.com/abaddon/logos",
  "repository": {
    "url": "https://github.com/abaddon/logos",
    "source": "github"
  },
  "remotes": [
    { "type": "streamable-http", "url": "https://<HOST>/mcp" }
  ]
}
```

Field notes that are load-bearing rather than cosmetic:

- `description` is 131 characters and leads with the verbs. The registry displays
  it in a list next to 66,000 others; "Logos — a prefix-form language" tells a
  planner nothing it can act on.
- `version` must equal what `./bin/logosc version` prints inside the image, or
  the ownership check and the artifact disagree.
- `remotes` before `packages`: 68.2% of registry servers declare a remote and it
  is the only form that works from a client on macOS, where the binary cannot
  run.

**Tool descriptions** — these are what the calling model reads to decide whether
to use the tool at all. Write them as instructions, not as marketing:

| Tool | Description string |
|---|---|
| `check_program` | `Type-check Logos source without compiling. Returns {ok, diagnostics[]}; each diagnostic carries code, message, node_path, line, col. Use this before compile_program.` |
| `compile_program` | `Compile Logos source to LLVM IR and return the IR text plus the binary SHA-256 and any diagnostics. Logos is prefix-form: every construct is (head arg ...).` |
| `format_source` | `Rewrite Logos source in canonical form. The output is byte-stable: formatting it twice changes nothing. Use after editing to produce a reviewable diff.` |
| `run_example` | `Build and run one of the repository's example programs, returning stdout, exit code and the leak count. Use to observe the language without writing it.` |
| `get_language_reference` | `Return the whole language as JSON: 96 forms, 16 types, 17 operators, 36 diagnostic codes, schema_version 1. Use this instead of guessing syntax.` |

## 2. npm — `logos-mcp`

```text
name:        logos-mcp
description: MCP server for Logos — type-check, compile, format and run Logos
             programs; diagnostics as JSON with a code and a node path.
keywords:    mcp, model-context-protocol, logos, compiler, type-check,
             llm, agent, code-generation
bin:         logos-mcp
engines:     node >= 18
```

Two things the README of the package must say in its first ten lines, because
they are the two failures people report back:

```sh
# this is a client for the hosted endpoint; no Linux binary is bundled
npx logos-mcp            # talks to https://<HOST>/mcp, LOGOS_MCP_URL overrides
```

and, plainly: *Logos compiles to x86_64/arm64 Linux. On macOS or Windows, use the
endpoint or the container — the compiler itself does not run locally.*

That sentence existing in the package is the difference between "does not work"
and "not for this machine".

## 3. mcp.so — submission blurb

The form asks for name, URL, description and category. Category: **Developer
Tools**. Description, 198 characters:

```text
Logos is a compiled language built for code an agent writes: allocation, fallible
calls and release are visible in the source, an unhandled failure is a compile
error, and every diagnostic is a JSON object with a code and a node path.
```

Do not submit until §A1 is live; a directory page is a URL the crawlers keep and
a dead one is worse than an absent one. Log it in the ledger's `mcp.so` row when
it is approved, not when it is submitted.

## 4. Smithery and the mirrors (Glama, PulseMCP)

One description, copied — do these in one sitting, and log them as a single row.
Smithery's own docs are currently migrating hosted server URLs back to vendor
endpoints, so its reach is volatile: point the listing at **your** endpoint URL,
never at a Smithery-hosted one, or the day Smithery changes its hosting the
listing dies with it.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> A1 the endpoint build/deploy, A2 npm publish, A5 directory submissions, and the gate each copy here waits on
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/launch-checklist.md
 -> The wave each of these belongs to and what has to be true before it
