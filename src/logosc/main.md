# `src/logosc/main.logos` — the `fmt`, `resolve` and `check` verbs and the process contract

The entry point of the self-hosted compiler, `gen2`: `logos/cli.py`'s `fmt`
verb ported to Logos, plus `resolve`, which runs the W5 resolver without a
checker, and `check`, which runs the W6 declaration pass over the resolved
module set. The modules before it return values; this one is a program. It owns
the process boundary — the command line, the exit status and the two output
streams — and nothing else.

Read `lex.md`, `tree.md`, `fmt.md`, `resolve.md` and `check.md` first. This file adds no
language surface: it calls the modules in the order the Python compiler does.

## The command line

```
gen2 fmt <file>
gen2 resolve <file>
gen2 check <file>
```

`(args)` returns the whole command line including the program name, as the
runtime copies it from `/proc/self/cmdline`. So the shape is:

| index | holds |
|---|---|
| `0` | the program, `gen2` |
| `1` | the verb, `fmt`, `resolve` or `check` |
| `2` | the file to format or resolve |

`main` accepts exactly these three elements. **No arguments, an unknown verb, a
missing file argument, or any extra argument** prints one line to stderr and
exits 2:

```
usage: gen2 <fmt|resolve|check> <file>
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
<location>: <CODE>: <message>
```

`<location>` is the node path the resolver named — `m/f`, `m/test/t`, `m/0`,
`a/b`, or `b/0` for a cycle — or the source position of a diagnostic that has no
node behind it:

| location | when |
|---|---|
| the node path | the resolver refused a form it had a path for |
| `<file>:<line>:<column>` | an imported file the lexer or parser refused, so the position is that file's own |
| the file the caller named | a root file with no `(mod ...)` form |

The three cases are `LogosError.location`'s, in Python's order: a node path if
there is one, a source position if not, and nothing when neither exists. The
position is the imported file's, never the asking file's, because the diagnostic
belongs to the file that failed to parse. `main-at` is the one function that
decides this.

The codes are `E0001` (an imported file the parser refused), `E0006` (an
imported file the lexer refused), `E0002` (unknown node / malformed form),
`E0003` (duplicate definition, duplicate module), `E0004` (circular import) and
`E0005` (unknown module, or a module that declares another name). `resolve`
stops before the checker, so a file with a type error resolves and exits 0.

`gen2 check` lexes, parses and resolves the file exactly as `resolve` does,
then builds `gen2`'s own module set from the resolver's answer and runs
`check-file`. On success it prints nothing to either stream and exits 0. On a
checker diagnostic it prints one line and exits 2:

```text
<path>: <CODE>: <message>
```

`<path>` is the node path the checker named (`m/f/1/0`, `m/p/0/1`, `m/e`); it
is the source file only when the diagnostic has no node behind it, which the
declaration pass never produces. `resolve-set` is called first, so a resolver
failure still prints the resolver's line, with `E0002`-`E0005` as above; a
checker failure is `E0002`, `E0003`, `E0100`, `E0101`, `E0500`, `E0501`,
`E0700` or the `E0502` a channel element can carry. `check` reads no body, so a
file with an expression error checks and exits 0 — see `check.md` for the
exact boundary.

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
| `main-at path file line col fallback` | `:str` | the diagnostic's location: path, `file:line:col`, or `fallback` |
| `main-checked file nodes ntexts` | `:i64` | run `resolve-set` then `check-file`; free the module set |
| `main-checked-run file mods nodes ntexts` | `:i64` | run the checker over the resolver's module set |
| `main-check-diag file e` | `:i64` | print one checker diagnostic and return 2 |
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
- `check`'s two resolver tables (`all` and `mods`), with `vec-free`, on every
  path, before `check-file`'s diagnostic is printed;
- nothing else. `read-file` returns a buffer the runtime owns for the process's
  life, and `fmt` allocates nothing, so no other `free` is owed.

The error values are structs, not allocations: `lex-error`, `tree-error` and
`resolve-error` carry a `:str` message that is a literal or a slice of the
source, so reporting one costs no allocation either.

## Building it

`gen2` is one program built from the whole module set gen2 may use: every
`src/logosc/*.logos` file and the two standard modules the compiler's tables
name, `src/std/map.logos` and `src/std/str.logos`:

```sh
python3 -m logos build src/logosc/*.logos src/std/map.logos src/std/str.logos -o build/selfhost/gen2
```

Only those two stdlib files, not the whole `src/std` directory: the stdlib's
`_test` files carry `(test …)` forms and are not modules gen2 needs. Exactly one
module defines `main`; the `*_test.logos` modules in the set are compiled but
their `(test …)` bodies are not entry points, so they add no second entry. `use`
resolves against the build set, which is why `fmt <file>` needs no search path.
`tools/selfhost.sh` is the caller: it builds this binary and runs it over every
tracked `.logos` file.

## What it does not do

- **No checker.** `fmt`'s contract is layout, not acceptance; a file with a
  type error formats and exits 0. The Python `fmt` verb behaves the same way.
  `resolve` likewise stops at names: it does not type-check, but it does follow
  `use`, reading `<name>.logos` beside the asking file (see `resolve.md`).
- **No in-place rewrite.** `main` prints; it never writes the file back. The
  gate compares the stream with the file, and a caller that wants to rewrite
  redirects it.
- **No stdin.** The Python verb accepts `-`; `gen2 fmt` takes a path. The gate
  always has paths.
- **No diagnostic for an unreadable file.** That is `read-file`'s `R0007`, with
  its own line, not a fourth code here.
