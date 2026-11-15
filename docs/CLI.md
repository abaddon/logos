# Driving `logosc`

`docs/LOGOS.md` teaches the language. This file teaches the tool: the verbs,
the flags, which stream carries what, the exit codes, and the two JSON
documents an agent may depend on. Everything here is a contract; if the
compiler disagrees with this page, the compiler is wrong.

Written for a consumer that never reads the source. `logosc` is a single
x86_64 Linux binary that links programs against `logos/runtime/rt.c` with
`clang`.

## Verbs

```sh
logosc <command> [flags] [arguments]
```

| Verb | What it does |
|---|---|
| `build` | compile one or more `.logos` files to a native binary |
| `check` | type-check one file; prints nothing and exits 0 on success |
| `fmt` | rewrite Logos source in canonical form, in place (`-` for stdin) |
| `guide` | print the generated manual, or its machine-readable manifest |
| `resolve` | resolve the names of one or more files |
| `show` | print one node of a file, addressed by its node path |
| `test` | compile and run the `(test ...)` nodes in a file or directory |
| `version` | print the compiler version |

Every verb accepts `-h` (or `--help`) and prints its own usage and flags to
**stdout** with exit 0:

```sh
logosc build -h      # usage: logosc build [-h] [-o OUT] [--opt O] ...
```

`logosc` with no arguments, `-h`, or `--help` prints the top-level help.
`--version` is the flag form of `logosc version`.

## Flags that apply to every verb

| Flag | Effect |
|---|---|
| `--json` | emit diagnostics as JSON on stderr (see below). It may appear before or after the verb. Human text remains the default and the exit code never changes. |
| `-h`, `--help` | print that verb's help on stdout, exit 0 |

Verb-specific flags are listed by `logosc <verb> -h`.

## Streams

| Stream | Carries |
|---|---|
| stdout | the program's own output (`show`, `guide`, `version`), help text |
| stderr | diagnostics, in text or JSON, one per failure |

`build` writes the binary to `build/<stem>` in the working directory unless
`-o OUT` names a path; `--keep-ir` keeps the generated `.ll` beside it.

## Exit codes

| Code | Meaning | Examples |
|---|---|---|
| `0` | success | a build, a clean `check`, `fmt`, `version`, `guide` |
| `2` | a source error, a usage error, or a `guide --check` mismatch | `E0100`, `unrecognized arguments`, `fmt` on a file that does not lex |
| `1` | an I/O or toolchain failure | the source file is unreadable or is a directory, the runtime is missing, `clang` failed |

There is no fourth code and no code `3`. A `test` run that reports failing
cases exits 1.

## JSON diagnostics

With `--json` on the command line, a compiler failure prints **one JSON
object per line on stderr**. Each line is a complete document, so a consumer
may parse stderr line by line or take the last line:

```sh
logosc build hello.logos --json 2>&1 >/dev/null | jq -e '.diagnostics[0].code'
logosc build hello.logos --json 2>&1 >/dev/null | jq -r '.diagnostics[0].node_path'
```

```json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100","message":"'+' needs numbers, found :str","node_path":"hello/main/2/0","file":"hello.logos","line":0,"col":0}]}
```

- `code` is stable and is listed with its meaning by `logosc guide --json`
  under `codes`.
- `node_path` is the address of the offending node; pass it to
  `logosc show FILE PATH` to print that subtree.
- `line` and `col` are 1-based, and are `0` when the failing phase does not
  track positions. The lexer and the parser always fill them in; the resolver,
  the checker and the lowerer address the node instead. This is a deliberate
  contract, not an omission: a node path survives edits that move lines.
- `severity` is always `"error"`: the compiler stops at the first failure.

The schema is published at `docs/schemas/diagnostic-v1.schema.json`.
`schema_version` is bumped only for a breaking change.

Toolchain and I/O failures (exit 1) are not diagnostics and stay on one
plain-text line beginning `logos: `; branch on the exit code for those.

## `version --json`

```sh
$ logosc version --json
{"schema_version":1,"name":"logos","version":"0.1.0"}
```

Schema: `docs/schemas/version-v1.schema.json`. The version matches the text
form (`logos 0.1.0`) and the release tag (`v0.1.0`).

## `guide --json`

The manifest of the language itself: `schema_version`, `forms`, `types`,
`operators`, `builtins`, `reserved`, `codes`, `categories`. It is a stable
contract at `schema_version` 1; a breaking change is a version bump.

## Where the compiler looks for its parts

`logosc` resolves its runtime (`rt.c`) and the standard library (`src/std`)
**from where the compiler lives, not from where you run it**:

1. `<root>/share/logos/runtime/rt.c` and `<root>/share/logos/std/<name>.logos`
   — the installed layout, where `<root>` is the parent of the `bin`
   directory holding `logosc`;
2. `<root>/logos/runtime/rt.c` and `<root>/src/std/<name>.logos` — the
   checkout layout (`build/logosc` inside a clone);
3. `logos/runtime/rt.c` and `src/std/<name>.logos` relative to the working
   directory — the legacy behaviour, kept so an old script keeps working.

So a compiled program needs no environment variable, no `cd`, and no
checkout: `cd /tmp && logosc build hello.logos` works, and `(use map)`
resolves from the installation.

Below the root, the lookup is a plain `-f` test per candidate, so the first
candidate that exists wins.

## Determinism

The same source compiled twice yields a byte-identical binary, and the same
Binary IR. `tests/test_cli.py` asserts the binary half of that on every
`make test`.

## Known limits of this contract

- `test --json` does not exist yet: `logosc test` prints `PASS id -` lines and
  a baseline verdict. Gating a pull request on it means parsing that text.
- `resolve`, `check` and `fmt` do not report line/column for their
  diagnostics; they report the node path.
- One target only: `x86_64-unknown-linux-gnu`. There is no cross-compilation
  and no Darwin or arm64 build.
