# Agent contract — using `logosc` and changing it

Everything an agent needs to be useful in this repository, in two halves. The
file you are reading is the **consumer** contract and the index to the
contributor one; [`AGENTS.md`](../../AGENTS.md) at the repository root is the
full contributor contract (gates, invariants, bootstrap rule, PR rules) and is
authoritative for that.

| You are… | Read |
|---|---|
| an agent that wants to **write and run Logos** | [Part 1](#part-1--using-the-compiler) — this page |
| an agent that wants to **change the compiler** | [`../../AGENTS.md`](../../AGENTS.md), then [Part 2](#part-2--changing-the-compiler) for the consumer docs a change obliges you to update |
| either, and you need the documentation map | [`../00-index.md`](../00-index.md) |

The one-paragraph orientation: the language manual is
[`../LOGOS.md`](../LOGOS.md) (generated — never edit it), the CLI reference is
[`cli.md`](cli.md), the honest status is "the compiler is complete, the product
is not released" ([`../01-summary/gap-register.md`](../01-summary/gap-register.md)),
and the shortest path to a running binary is [`../quickstart.md`](../quickstart.md).

---

## Part 1 — Using the compiler

### Install, or build from a checkout

Two ways in, both supported:

- **Install** the published tarball (`docs/install.md`): unpack it and run
  `bin/logosc`. The compiler finds its runtime (`logos/runtime/rt.c` or
  `share/logos/runtime/rt.c`) and its standard library from **its own
  installation**, so it works from any working directory, with no environment
  variable and no `cd`.
- **Build from a checkout**: `./tools/logosc.sh build FILE` builds the compiler
  on first use and then behaves identically.

Do not copy `bin/logosc` out of an installation on its own: it needs the
runtime and stdlib tree beside it, because that is how it finds them.

### Five commands that work

```sh
logosc version                          # logos 0.2.1
logosc build examples/hello.logos       # build/hello.ll + build/hello
./build/hello                           # hello
logosc check FILE                       # the cheap validation call, no codegen
logosc test FILE                        # build and run its (test ...) nodes
logosc build FILE --json                # one JSON object on stderr on failure
```

### The CLI contract, in one screen

Eight verbs, all listed by `logosc -h`, and every verb accepts `-h` for its own
flags. `resolve` and `check` are the cheapest validation calls: neither links a
binary.

| Verb | Signature | Purpose |
|---|---|---|
| `version` | `version` | print the version |
| `show` | `show FILE PATH` | print one node, canonically formatted |
| `fmt` | `fmt PATH...` (file, directory, or `-`) | rewrite source in canonical form |
| `resolve` | `resolve FILE...` | names and imports only |
| `check` | `check FILE` | resolve + full checker, no codegen |
| `build` | `build FILE... [-o OUT] [--opt O] [--test NAME] [--keep-ir]` | IR + native binary |
| `test` | `test [PATH] [--only CAT] [--opt LEVEL]... [--update-baseline]` | run `(test ...)` nodes |
| `guide` | `guide [--json\|--check]` | manual, manifest, or drift check |

**Exit codes — branch on these, not on text:**

| Status | Meaning | Retry? |
|---|---|---|
| `0` | success | — |
| `2` | the **source** or the **command line** is wrong: any lexer/parser/resolver/checker/lowering diagnostic, unknown verb, bad flag, missing argument, no `main`, two `main`s | no — change the input |
| `1` | the **environment** is wrong: unreadable/missing file, `runtime not found`, clang failure, unwritable IR, `show` path miss, `test` case failure or baseline regression, stale manual | yes — after fixing the environment |

Success is silent for every verb except `version`, `show`, `guide` and `test`.
Diagnostics go to stderr only: one message line per run, plus the offending
node's own text when the diagnostic names one, indented four spaces. Flags,
streams, artefact paths and the exact shapes: [`cli.md`](cli.md).

### Machine-readable surfaces

| Surface | What you get | Stability |
|---|---|---|
| `--json` diagnostics | one JSON object per line on stderr: `schema_version`, `diagnostics[]` of `{severity, code, message, node_path, file, line, col}` | `schema_version` 1; schema at `../schemas/diagnostic-v1.schema.json` |
| `logosc version --json` | `{"schema_version":1,"name":"logos","version":"…"}` | `schema_version` 1 |
| `logosc guide --json` | one object: `schema_version`, `forms` (96), `types` (16), `operators` (17), `builtins` (2), `reserved` {`forms`,`prefixes`,`variants`}, `codes` (36), `categories` (8) | `schema_version` 1: a breaking change bumps it |
| node paths | every diagnostic names one, e.g. `t/main/2/0`; `show FILE PATH` prints that node, and a plain diagnostic prints the same text under its message | positional and stable across edits elsewhere |
| exit codes | `0` success, `2` source or usage error, `1` I/O or toolchain failure | pinned one test per row (`tests/test_cli.py::ExitCodes`) |

With `--json`, diagnostics never change the exit code and never touch stdout.
I/O and toolchain failures (exit `1`) stay one plain `logos: …` line.

Full tables: [`diagnostics.md`](diagnostics.md). When you need to know what a
code means, ask the compiler: `logosc guide --json | jq -r '.codes["E0100"]'`.

### Determinism, and how to check a build

The same source compiled twice produces **byte-identical** output, IR and
binary. Measured on this tree:

```sh
logosc build examples/hello.logos -o /tmp/h1 && cp build/hello.ll /tmp/h1.ll
logosc build examples/hello.logos -o /tmp/h2 && cp build/hello.ll /tmp/h2.ll
sha256sum /tmp/h1 /tmp/h2 /tmp/h1.ll /tmp/h2.ll
# two pairs of equal hashes
```

So a diff in a binary is a real difference, never noise. The IR is **always**
written to `build/<stem>.ll`; read it when a compiled program misbehaves — it
is the text clang actually compiled.

### Language rules that bite an agent

- No comments. A `;` is `E0001`, not a comment.
- Prefix forms only, one canonical spelling, no infix, no `for`.
- `(ref T)` is written **only in a signature**; the caller passes the binding
  itself.
- `E0107` — an unused binding is an error, not a warning.
- Names are global across the whole program: two modules cannot both declare
  `point` (gap A1).
- Vectors move; free them exactly once; `(run …)` takes ownership of its
  argument vector.
- Every statement is a form, and a non-`void` function must `ret` on every
  path.

Idioms that compile, one per feature: [`language.md`](language.md). Limits to
plan around: [`limits.md`](limits.md).

---

## Part 2 — Changing the compiler

The contributor contract — the six gates, the DCO sign-off rule, the four
invariants, the regress-case requirement, the bootstrap rebuild rule and the PR
conventions — is [`../../AGENTS.md`](../../AGENTS.md). It is authoritative; do
not duplicate it here.

What that file does not say, and this doc set adds: **a behaviour change also
makes the consumer docs stale.** Update them in the same pull request.

| Change | Page to update |
|---|---|
| a verb, flag, exit status, stream or artefact path | [`cli.md`](cli.md) |
| a diagnostic code, message shape or node path | [`diagnostics.md`](diagnostics.md) |
| a standard-library function | [`stdlib.md`](stdlib.md) and `src/std/*.md` |
| anything a consumer must know before trusting the tool | [`limits.md`](limits.md) |
| anything in the walkthrough | [`../quickstart.md`](../quickstart.md) — re-run it, do not edit its outputs by hand |
| a new doc of any kind | a row in [`../00-index.md`](../00-index.md) |

The pages in this directory are **measured**, not aspirational: every command
and every `logos` block was executed against a build of this source, and the
`logos` blocks are complete modules with their expected stdout beside them. If
you change behaviour and do not change these pages, they become the next
`doc-contradictions.md`. When you must change a `logos` block, compile and run
it before committing.

### What to trust when documents disagree

| Question | Trust |
|---|---|
| what the language accepts | [`../LOGOS.md`](../LOGOS.md) — generated, drift-gated |
| what the compiler does today | `src/logosc/*.md` module contracts and the measured pages here |
| why it is shaped this way | [`../history/build-ledger.md`](../history/build-ledger.md) |
| how to contribute | [`../../AGENTS.md`](../../AGENTS.md) |
| what v1 was supposed to be | `docs/superpowers/specs/` — **stale in four places**; read with [`../03-dossiers/doc-contradictions.md`](../03-dossiers/doc-contradictions.md) open |
| is it ready to release | [`../01-summary/gap-register.md`](../01-summary/gap-register.md) — it is not |
