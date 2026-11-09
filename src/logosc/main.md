# `src/logosc/main.logos` — the `fmt` and `resolve` verbs and the process contract

The entry point of the self-hosted compiler, `gen2`: `logos/cli.py`'s `fmt`
verb ported to Logos, plus `resolve`, which runs the W5 resolver without a
checker. The modules before it return values; this one is a program. It owns
the process boundary — the command line, the exit status and the two output
streams — and nothing else.

Read `lex.md`, `tree.md`, `fmt.md` and `resolve.md` first. This file adds no
language surface: it calls the modules in the order the Python compiler does.

## The command line

```
gen2 fmt <file>
gen2 resolve <file>
```

`(args)` returns the whole command line including the program name, as the
runtime copies it from `/proc/self/cmdline`. So the shape is:

| index | holds |
|---|---|
| `0` | the program, `gen2` |
| `1` | the verb, `fmt` or `resolve` |
| `2` | the file to format or resolve |

`main` accepts exactly these three elements. **No arguments, an unknown verb, a
missing file argument, or any extra argument** prints one line to stderr and
exits 2:

```
usage: gen2 <fmt|resolve> <file>
```

The usage line is fixed, not derived from `argv[0]`: the gate runs
`build/selfhost/gen2`, and a message that echoed the path would change with the
build directory for no benefit.

## Output

On success `main` prints the canonical source of the file to stdout, byte for
byte as `fmt` prints it (`fmt.md` defines the shape), prints nothing to stderr,
and exits 0. `fmt` streams fragments straight to stdout; `main` never captures
or rebuilds them, so a long file costs no extra copy.

On a failure before the tree exists it prints exactly one diagnostic line to
stderr, prints nothing to stdout, and exits 2:

```
<file>:<line>:<column>: <CODE>: <message>
```

| failure | code | location |
|---|---|---|
| the lexer rejected the file | `E0006` | the token's one-based line and column |
| the tree rejected the file | `E0001` | the offending `(` or `)`'s one-based line and column |

The location comes first and the code second, as this entry point's contract
fixes it. `logos/diag.py` renders the code first (`E0006 file:line:col: …`
from the Python `fmt`); the two orders are deliberately not shared, because the
gate compares stdout only and no Logos consumer parses the diagnostic.

A file `read-file` cannot open or read never reaches either branch: the runtime
panics `R0007` at the `read-file` node path and exits 2, exactly as it does for
any other Logos program (`docs/manual/19-runtime-access.logos`). That line names
a node path rather than a source position, because no source position exists
yet.

`gen2 resolve` lexes and parses the file the same way, then runs
`resolve-file` instead of `fmt`. On success it prints nothing to either stream
and exits 0. On a resolver diagnostic it prints exactly one line to stderr and
exits 2:

```
<path>: <CODE>: <message>
```

`<path>` is the node path the resolver named — `m/f`, `m/test/t`, `m/0`,
`a/b` — or the source file when the diagnostic has no node behind it, which is
only a file with no `(mod ...)` form. The codes are `E0002` and `E0003` in
Task 1; Task 2 adds `E0004` and `E0005`. `resolve` stops before the checker,
so a file with a type error resolves and exits 0.

## Functions

| function | returns | meaning |
|---|---|---|
| `main` | `:i64` | the entry point: read `argv`, dispatch, return the status |
| `main-args a` | `:i64` | check the verb and arity, then run the file |
| `main-run verb path` | `:i64` | create the six vectors, run, free them, return the status |
| `main-source verb path …` | `:i64` | read, lex, then parse or report `E0006` |
| `main-tree verb path …` | `:i64` | parse, then format, resolve or report `E0001` |
| `main-print nodes ntexts` | `:i64` | run `fmt` and return 0 |
| `main-resolved file nodes ntexts` | `:i64` | run `resolve-file` and return 0 or the diagnostic |
| `main-resolve-diag file e` | `:i64` | print one resolver diagnostic and return 2 |
| `main-diag path code line col msg` | `:i64` | print one lexer/parser diagnostic and return 2 |
| `main-usage` | `:i64` | print the usage line and return 2 |
| `main-write s` | `:void` | one `rt_write` to file descriptor 2 |

`main-write` is the only way this module reaches the output streams beyond
`print`: Logos has no stderr builtin, so the module declares the runtime's
`rt_write` as an `extern` and writes to descriptor 2. `main` returns the status
and the emitted `main` hands it to the C entry point, so the process exits with
0 or 2; nothing calls `exit`.

## Ownership

`main` owns three things and frees all of them before it returns:

- the `(args)` vector, with `vec-free`;
- the four lexer vectors and the two arena vectors, also with `vec-free`, on
  every path — success, `E0006` and `E0001`;
- nothing else. `read-file` returns a buffer the runtime owns for the process's
  life, and `fmt` allocates nothing, so no other `free` is owed.

The error values are structs, not allocations: `lex-error` and `tree-error`
carry a `:str` message that is a literal or a slice of the source, so reporting
one costs no allocation either.

## Building it

`gen2` is one program built from the whole module set:

```sh
python3 -m logos build src/logosc/*.logos -o build/selfhost/gen2
```

Exactly one module defines `main`; the `*_test.logos` modules in the set are
compiled but their `(test …)` bodies are not entry points, so they add no second
entry. `use` resolves against the build set, which is why `fmt <file>` needs no
search path. `tools/selfhost.sh` is the caller: it builds this binary and runs
it over every tracked `.logos` file.

## What it does not do

- **No checker.** `fmt`'s contract is layout, not acceptance; a file with a
  type error formats and exits 0. The Python `fmt` verb behaves the same way.
  `resolve` likewise stops at names: it does not type-check, and it does not
  follow `use` (Task 2 does).
- **No in-place rewrite.** `main` prints; it never writes the file back. The
  gate compares the stream with the file, and a caller that wants to rewrite
  redirects it.
- **No stdin.** The Python verb accepts `-`; `gen2 fmt` takes a path. The gate
  always has paths.
- **No diagnostic for an unreadable file.** That is `read-file`'s `R0007`, with
  its own line, not a fourth code here.
