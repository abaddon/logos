# `src/logosc/main.logos` — the `fmt`, `resolve`, `check` and `build` verbs and the process contract

The entry point of the self-hosted compiler, `gen2`: `logos/cli.py`'s `fmt`
verb ported to Logos, plus `resolve`, which runs the W5 resolver without a
checker, `check`, which runs the W6 declaration pass over the resolved module
set, and `build`, which lowers that module and writes the LLVM IR `emit`
prints. The modules before it return values; this one is a program. It owns the
process boundary — the command line, the exit status and the two output
streams — and nothing else.

Read `lex.md`, `tree.md`, `fmt.md`, `resolve.md`, `check.md`, `lower.md` and
`emit.md` first. This file adds no language surface: it calls the modules in the
order the Python compiler does.

## The command line

```
gen2 fmt <file>
gen2 resolve <file>...
gen2 check <file>
gen2 build <file>... -o <out>
```

`(args)` returns the whole command line including the program name, as the
runtime copies it from `/proc/self/cmdline`. So the shape is:

| index | holds |
|---|---|
| `0` | the program, `gen2` |
| `1` | the verb, `fmt`, `resolve`, `check` or `build` |
| `2` … `n-3` | the files to resolve or build (one or more) |
| `2` | the file to format or check (exactly one) |
| `n-2` | `-o`, for `build` only |
| `n-1` | the path `build` writes the IR to |

`n` is `(vec-len a)`, so the files a `build` names are `a[2]` through
`a[n-3]` and the output path is the last element. `resolve` and `build` take
one file or many; `fmt` and `check` take exactly one. **No arguments, an
unknown verb, a missing file, a `build` that is not at least
`build <file> -o <out>`, or a `fmt`/`check` with an extra argument** prints the
usage to stderr and exits 2:

```
usage: gen2 <fmt|check> <file>
       gen2 resolve <file>...
       gen2 build <file>... -o <out>
```

Two arities are *not* usage errors, because they are facts about the build set
rather than about the command line: a set with no `main` and a set with two
`main`s each print one diagnostic line and exit 2 (`E0103` and `E0003`; see
"Output" below).

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

`gen2 resolve` lexes and parses one file, then runs `resolve-file` instead of
`fmt`; with several files it runs `resolve-set-of` over all of them, which
resolves the set as one unit (`resolve.md`). On success it prints nothing to
either stream and exits 0. On a resolver diagnostic it prints exactly one line
to stderr and exits 2:

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

`gen2 build` parses its first file, then runs the same steps as `check` over
the whole set it was given: `resolve-set-of` over every file, and `check-file`
over the module set the resolver built. It then requires exactly one `main`
somewhere in the set (see below), lowers the first file's module, and emits.
It writes the emitted IR — the whole text `out[0]` — to the `-o` path, prints
nothing to either stream, and exits 0. Nothing else is produced: no object
file, no binary, no `.ll` in a directory of `gen2`'s choosing. `-o` names the
file, and the parity phase in `tools/selfhost.sh` names it so the text can be
compared with Python's `build/<stem>.ll`.

Two checks belong to `build` and not to `check`:

- **One `main`, somewhere in the set.** `check-file` already refuses a second
  `main` anywhere in the module set (`E0003`, `duplicate definition 'main'`),
  because a second entry point is a second definition. A set with *no* `main`
  is refused by `check-required-main` with `E0103: no 'main' function to
  build`, located at the first root's file. Neither is a usage error: the
  command line was well formed and the source was not. The check runs after
  the checker, so a set that also has a body error reports the checker's
  refusal first, as Python's `build_program` does.
- **One root so far.** The lowering still spans one module, so a build with
  more than one root is refused with `E0103: multiple roots are not lowered
  yet` at the second root once the checker has passed. It is a temporary
  stop for the multi-module lowering, not a rule of the language; a one-root
  build is untouched.

The pipeline stops at the first failure and each failure has one shape:

| failure | code | location |
|---|---|---|
| the lexer | `E0006` | the token's `file:line:col` |
| the tree | `E0001` | the offending paren's `file:line:col` |
| the resolver | `E0002`–`E0005` | the node path, or a `file:line:col` (`main-at`) |
| the checker | its own code | the node path the checker named |
| the lowering | `E0002`, `E0102`, `E0103`, … | the node path of the form it refused |
| `emit` | `E0002` | the module's node path |

A lowering refusal is `lower-error`'s: `lo-fail-at` recorded the form's node
path, and `lower-code` renders the number (`2` → `E0002`). An `emit` refusal is
`ir-error`'s, and it carries no path at all — the IR rows name no source node —
so the diagnostic names the module (`tree-path` of the root, e.g. `m`) and uses
`E0002` for "this arena cannot be printed". `main-ir-diag` is the one place
that decides this; the port-only code is documented because Python's compiler
raises instead of printing. **Neither is a panic**: a failed emit is a line on
stderr and exit 2, and a bad `-o` path is `gen2 build: cannot write <path>`,
also exit 2.

## Functions

| function | returns | meaning |
|---|---|---|
| `main` | `:i64` | the entry point: read `argv`, dispatch, return the status |
| `main-args a` | `:i64` | check the verb and arity, then run the verb |
| `main-args-build a n` | `:i64` | check `build`'s shape: one or more files, then `-o` and the path |
| `main-paths a first count paths` | `:void` | copy `count` argv entries into a new `paths` vector |
| `main-run verb path` | `:i64` | create the six vectors, run, free them, return the status |
| `main-source verb path …` | `:i64` | read, lex, then parse or report `E0006` |
| `main-tree verb path …` | `:i64` | parse, then format, resolve or report `E0001` |
| `main-print nodes ntexts` | `:i64` | run `fmt` and return 0 |
| `main-resolved file nodes ntexts` | `:i64` | run `resolve-file` and return 0 or the diagnostic |
| `main-resolve-set a first count` | `:i64` | run `resolve-set-of` over the argv files and return 0 or the diagnostic |
| `main-resolve-diag file e` | `:i64` | print one resolver diagnostic and return 2 |
| `main-at path file line col fallback` | `:str` | the diagnostic's location: path, `file:line:col`, or `fallback` |
| `main-checked file nodes ntexts` | `:i64` | run `resolve-set` then `check-file`; free the module set |
| `main-checked-run file mods nodes ntexts` | `:i64` | run the checker over the resolver's module set |
| `main-check-diag file e` | `:i64` | print one checker diagnostic and return 2 |
| `main-build a first count out` | `:i64` | copy the files, create the arena, run the pipeline, free it, return the status |
| `main-built paths out …` | `:i64` | read, lex and parse the first root, resolve the set, check it, lower the root, emit, then write the IR |
| `main-lower-diag file e` | `:i64` | print one lowering diagnostic and return 2 |
| `main-ir-diag file nodes ntexts e` | `:i64` | print one emitter refusal at the module and return 2 |
| `main-spit path text` | `:i64` | open `path`, write `text`, close it; 0 or a diagnostic |
| `main-spit-bad path` | `:i64` | print the output-file failure line and return 2 |
| `main-diag path code line col msg` | `:i64` | print one lexer/parser diagnostic and return 2 |
| `main-nothing` | `:void` | the empty `else` branch of an early `ret` |
| `main-usage` | `:i64` | print the usage lines and return 2 |
| `main-write s` | `:void` | one `rt_write` to file descriptor 2 |

`main-write` is the only way this module reaches the output streams beyond
`print`: Logos has no stderr builtin, so the module declares the runtime's
`rt_write` as an `extern` and writes to descriptor 2. `main-spit` reuses the
same runtime form for the build's output file: `rt_create` opens the path and
returns a descriptor (`< 0` on failure), `rt_write` writes the whole string,
and `close` releases it. A `:str` is a pointer and a length, so the two-argument
`rt_write` declaration is the runtime's three-argument C function — the same
ABI coincidence `src/std/io.logos` relies on. `main` returns the status
and the emitted `main` hands it to the C entry point, so the process exits with
0 or 2; nothing calls `exit`.

## Ownership

`main` owns three things and frees all of them before it returns:

- the `(args)` vector, with `vec-free`; `main-build` and `main-resolve-set`
  also free the `paths` vector they copy the file names into;
- the four lexer vectors and the two arena vectors, also with `vec-free`, on
  every path — success, `E0006` and `E0001`;
- `check`'s two resolver tables (`all` and `mods`), with `vec-free`, on every
  path, before `check-file`'s diagnostic is printed;
- `build`'s full arena — seventy parallel vectors — with `vec-free`, on every
  path, including the ones that stop at a lexer, tree, resolver or checker
  diagnostic. `main-build` is the one function that allocates it, and its
  `main-built` callee is the one that returns through every early exit;
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
`tools/selfhost.sh` is the caller: it builds this binary, runs `fmt` over every
tracked `.logos` file, and then runs `build` over the files in
`tools/selfhost-ir.txt`, comparing each `.ll` with Python's byte for byte.

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
- **No clang, no binary.** `gen2 build` stops at the IR. PR B's contract is the
  text; invoking the linker driver is `gen2`'s next wave, and until then
  `tools/selfhost.sh` compares the text with Python's.
- **One module, one unit.** `build` resolves the whole set, so a `use` between
  its files is answered and the checker sees every module, but the lowering
  still lowers only the first root's children: the imported modules are not
  lowered into the same unit and `mqual` is always false. A multi-root build
  that passes the checker is therefore refused rather than written short. Every
  fixture in the parity list is a single module with no `use`; the corpus and
  the compiler's own source need the import closure and the multi-module
  lowering, which are the next step.
- **No diagnostic for an unreadable file.** That is `read-file`'s `R0007`, with
  its own line, not a fourth code here.
