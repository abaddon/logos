# `src/logosc/main.logos` — the `fmt`, `resolve`, `check` and `build` verbs and the process contract

The entry point of the self-hosted compiler, `gen2`: `logos/cli.py`'s `fmt`
verb ported to Logos — one or more paths, directories walked recursively, `-`
for standard input, rewritten in place — plus `resolve`, which runs the W5
resolver without a checker, `check`, which runs the W6 declaration pass over
the resolved module set, and `build`, which lowers that module set, writes the
LLVM IR `emit` prints, and runs clang over the text and the C runtime to
produce a native binary. The modules before it return values; this one is a program. It owns the
process boundary — the command line, the exit status and the two output
streams — and nothing else.

Read `lex.md`, `tree.md`, `fmt.md`, `resolve.md`, `check.md`, `lower.md`,
`emit.md` and `harness.md` first. This file adds no language surface: it calls
the modules in the order the Python compiler does.

## The command line

```
gen2 fmt <file|dir|->...
gen2 resolve <file>...
gen2 check <file>
gen2 build <file>... [-o <out>] [--opt <O>] [--test <name>] [--keep-ir]
gen2 test [<path>] [--only <category>] [--opt <level>]...
```

`(args)` returns the whole command line including the program name, as the
runtime copies it from `/proc/self/cmdline`. So the shape is:

| index | holds |
|---|---|
| `0` | the program, `gen2` |
| `1` | the verb, `fmt`, `resolve`, `check`, `build` or `test` |
| `2` … `n-1` | the paths to format, resolve or build (one or more), and `build`'s or `test`'s flags, or `test`'s one path |
| `2` | the file to check (exactly one) |

`build`'s flags may appear anywhere among its files, as Python's `argparse`
allows: `-o OUT` names the binary, `--opt O` (or `--opt=O`) names the
optimisation level and defaults to `-O2`, and `--keep-ir` is accepted and
changes nothing, because the IR is always kept. A word that starts with `-` and
is not one of those four is a usage error; a file whose name starts with `-`
would have to be written with a path. A repeated `-o` or `--opt` takes the last
value, as `argparse` does.

`--test NAME` builds one `(test …)` body of the file as the program's `main`
instead of the module's own: the third arity above is the only shape Python has
no `build` flag for, because the runner (`logos/driver.py`'s `run_test`) calls
the lowering directly. Three things follow from it and none is a usage error —
the required-`main` rule is not applied, the IR goes to
`build/<stem>.<name>.ll` with `/` and `\` in the name replaced by `_`, and the
link adds `-DLOGOS_DEBUG=1` first in the clang command line so the runtime's
leak report is compiled in. A repeated `--test` takes the last value. See
`lower.md`'s "Test mode" for what the lowering does with the name.

`test` is the corpus runner. `PATH` defaults to `tests` (`nargs="?"` in
`cli.py`), `--only CAT` filters by category and must name one of the eight, and
`--opt` is consumed the way `argparse` reads it after `cli._normalize_argv`:
one flag swallows every following `-O<digits>` token, so `--opt -O0 -O2` is two
levels. A second positional argument, and any other word starting with `-`, is
a usage error; `--update-baseline` is parsed and refused with exit 2 until W9.
The runner is landed through two of its seven steps (see `harness.md`): it
walks the tree, derives every case id and reads that case's directives, but it
builds and runs nothing yet, so each enumerated case prints `PASS <id> -` and
only a malformed directive prints `FAIL <id> <detail>`. Ids, their order and
the detail sentences are Python's `tester.py`.

**No arguments, an unknown verb, a missing file, a `build` with no file, a
`fmt` with no path, or a `check` with an extra argument** prints the usage to
stderr and exits 2:

```
usage: gen2 <fmt|check> <file>
       gen2 resolve <file>...
       gen2 build <file>... [-o <out>] [--opt <O>]
       gen2 test [<path>] [--only <category>] [--opt <level>]...
```

The usage line still says `<file>` for `fmt` because it is a fixed string the
gate and the tests read; the verb itself takes as many paths as the line
carries. A repeated `-` is the one argument error that is not a usage error:
Python refuses it with `logos: fmt: '-' may be given at most once` and exit 2
(`cli.py:336-343`), and so does this verb, before it formats anything.

Two arities are *not* usage errors, because they are facts about the build set
rather than about the command line: a set with no `main` and a set with two
`main`s each print one diagnostic line and exit 2 (`E0103` and `E0003`; see
"Output" below).

The usage line is fixed, not derived from `argv[0]`: the gate runs
`build/selfhost/gen2`, and a message that echoed the path would change with the
build directory for no benefit.

## Output

`fmt` rewrites each named file in place and prints nothing — Python's
`_format_path` (`cli.py:353-369`), and what makes the verb idempotent and
composable with `git`. `-` is the exception: standard input is read once,
formatted, and written to stdout, because a stream has no name to write back
to. `fmt` streams fragments straight to the open descriptor (`fmt.md`), so a
long file costs no whole-file copy and no temporary.

A path that is a directory is walked: every entry is visited in name order, a
directory entry is descended into in place and a file entry ending in
`.logos` is formatted. That is Python's `sorted(path.rglob("*.logos"))` order,
which compares path *components* rather than the whole path as a string, so
`b/x.logos` comes before `b.logos` (`b` is a prefix of `b.logos`) even though
`b.logos` sorts first byte-wise. The walk is spelled as recursion over a sorted
entry list because that is exactly the component-wise order; `main-str-less`
and `main-sort` are the byte-wise string comparison and insertion sort that
produce it. Every file is attempted even after one fails, so one broken file
does not hide the rest, and the exit status is 1 when any of them failed.

A path that cannot be read and written is Python's one line, with the C
library's own message, and exit 1 (`cli.py:355-368`):

```
logos: <path>: No such file or directory
```

`path-error` is what produces the message: `read-file` panics R0007 by design,
and a verb whose contract is a line on stderr and exit 1 cannot use it. The
check runs before the file is opened, so a file that cannot be written is not
truncated first, and a partition of the tree that fails leaves every other file
formatted.

On a failure before the tree exists it prints exactly one diagnostic line to
stderr and exits 1:

```
<file>:<line>:<column>: <CODE>: <message>
```

| failure | code | location |
|---|---|---|
| the lexer rejected the file | `E0006` | the token's one-based line and column |
| the tree rejected the file | `E0001` | the offending `(` or `)`'s one-based line and column |

The exit status is 1, as Python's `_format_path` returns 1 for a `LogosError`;
the file is left exactly as it was, because the parse finishes before the
descriptor is opened. The location comes first and the code second, as this
entry point's contract fixes it. `logos/diag.py` renders the code first
(`E0006 file:line:col: …` from the Python `fmt`); the two orders are
deliberately not shared, and the `fmt` parity test compares the file order and
the bytes, not this text.

A file `path-error` clears never reaches either branch, and a file that
changes between the check and the read — the one race this cannot close —
still panics `R0007` at the `read-file` node path and exits 2, exactly as it
does for any other Logos program
(`docs/manual/19-runtime-access.logos`).

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
somewhere in the set (see below), lowers the whole set, and emits. The emitter's
text — the whole of `out[0]` — is written to `build/<first file's stem>.ll`, and
clang turns that file plus `logos/runtime/rt.c` into a native binary at `-o`, or
at `build/<first file's stem>` when `-o` is absent:

```
clang {opt} -target x86_64-unknown-linux-gnu build/<stem>.ll logos/runtime/rt.c \
    -o <out> -lpthread -lm
```

That is Python's command with Python's arguments (`driver.py:243-254`), which is
why a build of the same set produces a byte-identical executable: clang embeds
the IR file's basename and nothing else about the path, and both drivers keep
the text at `build/<stem>.ll`. `{opt}` is `-O2` unless `--opt` says otherwise,
and both link flags are unconditional. The build prints nothing to either
stream on success and exits 0.

Two paths are created before they are used — `build/` for the IR, and the `-o`
path's directory — because a fresh checkout has no `build/` directory.
`main-mkdir` is `(mkdirs dir)`, the runtime helper that creates a path and its
missing parents and returns 0 or -1; it replaced a `mkdir -p` child process, so
a build no longer depends on a `PATH` entry and no longer pays a spawn.
`main-exists` still runs `test -f` for the runtime's presence; that probe is
one per build, and folding it into the runtime is a separate question with a
different failure line attached. Both creation and probing ignore the status,
because a directory that cannot be made fails at the write or at clang, with
the line that says so.

Nothing else is produced: no object file and no second `.ll`. `tools/selfhost.sh`
reads `build/<stem>.ll` after each `gen2 build` and compares it with the file
Python's build writes to the same path.

Two checks belong to `build` and not to `check`:

- **One `main`, somewhere in the set.** `check-file` already refuses a second
  `main` anywhere in the module set (`E0003`, `duplicate definition 'main'`),
  because a second entry point is a second definition. A set with *no* `main`
  is refused by `check-required-main` with `E0103: no 'main' function to
  build`, located at the first root's file. Neither is a usage error: the
  command line was well formed and the source was not. The check runs after the
  checker, so a set that also has a body error reports the checker's
  refusal first, as Python's `build_program` does.
- **A runtime to link.** `main-link` asks `main-exists` for
  `logos/runtime/rt.c`; when the file is absent the build stops with one
  `logos: runtime not found: logos/runtime/rt.c` line and exit 1, and removes
  the IR it had just written, rather than handing clang a path that is not
  there.

The pipeline stops at the first failure and each failure has one shape:

| failure | code | location |
|---|---|---|
| the lexer | `E0006` | the token's `file:line:col` |
| the tree | `E0001` | the offending paren's `file:line:col` |
| the resolver | `E0002`–`E0005` | the node path, or a `file:line:col` (`main-at`) |
| the checker | its own code | the node path the checker named |
| the lowering | `E0002`, `E0102`, `E0103`, … | the node path of the form it refused |
| `emit` | `E0002` | the module's node path |
| the IR write | none | `logos: cannot write <path>`, exit 1 |
| the link | none | `logos: clang failed: …`, exit 1 |

A lowering refusal is `lower-error`'s: `lo-fail-at` recorded the form's node
path, and `lower-code` renders the number (`2` → `E0002`). An `emit` refusal is
`ir-error`'s, and it carries no path at all — the IR rows name no source node —
so the diagnostic names the module (`tree-path` of the root, e.g. `m`) and uses
`E0002` for "this arena cannot be printed". `main-ir-diag` is the one place
that decides this; the port-only code is documented because Python's compiler
raises instead of printing. **Neither is a panic**: a failed emit is a line on
stderr and exit 2, and a bad `-o` path is `logos: cannot write <path>`, exit 1.

The last two stages have no source location, so they cannot use the diagnostic
shape above; they use Python's `build` shape instead, one `logos: …` line on
stderr and exit 1 (`cli.py:311-327`). A clang failure prints the command it ran
followed by clang's own stderr, which is how `BuildError` reads in Python, and
removes both artefacts — the IR and the half-written binary — so a failed build
leaves nothing behind that could be mistaken for a success.

## Functions

| function | returns | meaning |
|---|---|---|
| `main` | `:i64` | the entry point: read `argv`, dispatch, return the status |
| `main-args a` | `:i64` | check the verb and arity, then run the verb |
| `main-build a n` | `:i64` | read `build`'s flags and files, then build or print the usage |
| `main-arg a n i paths outs opts` | `:i64` | one argv word: the next index, or -1 for a usage error |
| `main-flag-next a i into` | `:i64` | push the word after a flag and skip both |
| `main-attached-next s i into` | `:i64` | push the value of `--opt=…` and skip the word |
| `main-path-next a i paths` | `:i64` | push a source path and step over it |
| `main-dest paths outs` | `:str` | `-o`'s last value, or `build/<first stem>` |
| `main-opt opts` | `:str` | `--opt`'s last value, or `-O2` |
| `main-paths a first count paths` | `:void` | copy `count` argv entries into a new `paths` vector |
| `main-run verb path` | `:i64` | create the six vectors, run, free them, return the status |
| `main-source verb path …` | `:i64` | read, lex, then parse or report `E0006` |
| `main-tree verb path …` | `:i64` | parse, then format, resolve or report `E0001` |
| `main-print nodes ntexts` | `:i64` | run `fmt` on descriptor 1 and return 0 |
| `main-fmt a first count` | `:i64` | format the argv paths, or stdin for `-`; 0, 1 or 2 |
| `main-fmt-path arg` | `:i64` | format one path: a directory by walking it, a file in place |
| `main-fmt-file path` | `:i64` | check the path, parse it, then rewrite it |
| `main-fmt-stdin` | `:i64` | read standard input, parse it and print the canonical form |
| `main-fmt-tree dir` | `:i64` | list a directory, sort it, format its `.logos` files and descend |
| `main-fmt-loaded path src …` | `:i64` | lex and parse one source, or return its diagnostic as exit 1 |
| `main-fmt-render path nodes ntexts` | `:i64` | create the file and print the canonical form into it |
| `main-fmt-write-bad path` | `:i64` | the create failure: its message, exit 1 |
| `main-fmt-diag path code line col msg` | `:i64` | print one diagnostic and return 1 |
| `main-fmt-bad path msg` | `:i64` | print `logos: <path>: <msg>` and return 1 |
| `main-fmt-twice` | `:i64` | print the repeated-`-` line and return 2 |
| `main-test a n` | `:i64` | read `test`'s path and flags, then run the harness or print the usage |
| `main-test-arg a i n path only flags` | `:i64` | one `test` argv word: the next index, or -1 for a usage error |
| `main-test-only value next only` | `:i64` | set `--only`'s value and skip the word |
| `main-test-level s` | `:bool` | whether a word is an `-O<digits>` level |
| `main-test-digits s i n` | `:bool` | whether `s[i..n)` is all digits |
| `main-test-opts a i n` | `:i64` | consume the levels after `--opt`; -1 when there is none |
| `main-test-update flags next` | `:i64` | remember `--update-baseline` and skip the word |
| `main-test-path s next path flags` | `:i64` | take the one positional path; -1 on a second |
| `main-test-run path only flags` | `:i64` | validate `--only`, refuse the baseline, call `h-run` |
| `main-test-unknown name` | `:i64` | print the unknown-category line and return 2 |
| `main-test-no-baseline` | `:i64` | print the deferred-baseline line and return 2 |
| `main-sort names` | `:void` | sort entry names byte-wise, in place |
| `main-str-less a b` | `:bool` | byte-wise `a < b` |
| `main-join dir name` | `:str` | `dir/name`, without a doubled slash |
| `main-logos-name name` | `:bool` | whether a name ends in `.logos` |
| `main-or a b` | `:i64` | the status of two files: 1 when either failed |
| `main-resolved file nodes ntexts` | `:i64` | run `resolve-file` and return 0 or the diagnostic |
| `main-resolve-set a first count` | `:i64` | run `resolve-set-of` over the argv files and return 0 or the diagnostic |
| `main-resolve-diag file e` | `:i64` | print one resolver diagnostic and return 2 |
| `main-at path file line col fallback` | `:str` | the diagnostic's location: path, `file:line:col`, or `fallback` |
| `main-checked file nodes ntexts` | `:i64` | run `resolve-set` then `check-file`; free the module set |
| `main-checked-run file mods nodes ntexts` | `:i64` | run the checker over the resolver's module set |
| `main-check-diag file e` | `:i64` | print one checker diagnostic and return 2 |
| `main-build-all paths dest opt` | `:i64` | create the arena, run the pipeline over the files, free it, return the status |
| `main-built paths dest opt …` | `:i64` | read, lex and parse the first root, resolve the set, check it, load every other module, lower the unit, emit, write `build/<stem>.ll`, link |
| `main-stem path` | `:str` | the file name without its directory and last extension |
| `main-ir-path path` | `:str` | `build/<stem>.ll`, where the IR always goes |
| `main-out-path path` | `:str` | `build/<stem>`, the default binary |
| `main-dir path` | `:str` | the directory part of `path`, or `""` when it has none |
| `main-runtime` | `:str` | `logos/runtime/rt.c`, the runtime the binary is linked with |
| `main-exists path` | `:bool` | whether `path` is a regular file (`test -f`) |
| `main-mkdir dir` | `:void` | `(mkdirs dir)`, ignoring the status |
| `main-joined argv` | `:str` | the command line as one line, for the failure message |
| `main-link ll out opt` | `:i64` | link `ll` and the runtime into `out`; 0 or the failure line |
| `main-link-bad text r ll out` | `:i64` | print clang's failure, remove both artefacts, return 1 |
| `main-link-missing ll out rt` | `:i64` | print the missing-runtime line, remove both artefacts, return 1 |
| `main-fail msg` | `:i64` | print one `logos: …` line and return 1 |
| `main-append mnod mntx starts ends nod ntx` | `:void` | append one module's nodes and texts, recording the range the two ended at |
| `main-load-module mods m mnod mntx starts ends` | `:i64` | read, lex and parse module `m` of the resolver's set into the unit, or return the first diagnostic |
| `main-lower-diag file e` | `:i64` | print one lowering diagnostic and return 2 |
| `main-ir-diag file nodes ntexts e` | `:i64` | print one emitter refusal at the module and return 2 |
| `main-spit path text` | `:i64` | open `path`, write `text`, close it; 0 or a `logos:` line |
| `main-spit-bad path` | `:i64` | print the output-file failure line and return 1 |
| `main-diag path code line col msg` | `:i64` | print one lexer/parser diagnostic and return 2 |
| `main-nothing` | `:void` | the empty `else` branch of an early `ret` |
| `main-usage` | `:i64` | print the usage lines and return 2 |
| `main-write s` | `:void` | one `fmt-emit` to file descriptor 2 |

`main-write` is the only way this module reaches the output streams beyond
`print`: Logos has no stderr builtin, so it calls `fmt-emit` with descriptor 2
(`fmt.md`). `fmt` owns the `rt_write` extern because it is the module that
prints; a second declaration of the same symbol in this module would be
`E0003: duplicate definition 'rt_write'`, and a Logos module cannot call
another module's extern through a `use` it does not have. `main-spit` reuses
the same path for the IR file: `rt_create` opens the path and returns a
descriptor (`< 0` on failure), `fmt-write` writes the whole string and returns
the byte count, and `close` releases it. A `:str` is a pointer and a length, so
the two-argument `rt_write` declaration is the runtime's three-argument C
function — the same ABI coincidence `src/std/io.logos` relies on. `unlink` is
declared the other way round: C's `unlink` reads only the pointer, and the
length the Logos `:str` passes in the second register is ignored, which is what
lets a failed build remove the two files it wrote. `main` returns the status and the emitted `main`
hands it to the C entry point, so the process exits with 0, 1 or 2; nothing
calls `exit`.

## Loading the unit

`build` lowers a **unit**, not a file. `resolve-set-of` already read every root
and everything they `use`, and left them in `mods` — one `resolve-mod` per
module, in dependency order, with the first root at slot 0. `main-built` parses
the first root into `nod`/`ntx` (the lexer, the tree and the checker all take a
single tree), then copies that module into `mnods`/`mntx` with `main-append`
and loops `main-load-module` over the rest: each one is read, lexed and parsed
into temporary vectors, appended to the unit's two vectors, and its temporary
vectors are freed. `main-append` also pushes the half-open range
`[start, end)` of the module's nodes and, as the next pair entry, of its
texts — so `mstarts`/`mends` carry one `(nodes, texts)` pair per module and
`lower-build` can refill the single-tree arena one module at a time.

Loading is not lowering: no tree walk, no resolution and no checking happens
here, and a module the resolver read twice is loaded once because `mods` names
it once. A module that fails to lex or parse is reported at its own file
(`main-diag`) before any lowering starts.

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
  diagnostic. `main-build-all` is the one function that allocates it, and its
  `main-built` callee is the one that returns through every early exit.
  `main-build` owns the three vectors the command line fills — `paths`, `outs`
  and `opts` — and frees them on the usage path as well as after the build;
- the argument vectors handed to `run` are **moved**, not freed: the form copies
  each element into a C string it keeps for the process's life, so `main-exists`
  and `main-link` pass their vectors and never free them. The `:run` handle and
  its stdout and stderr buffers are process-lifetime too, so a build that runs
  clang owes no `free` for any of it;
- the directory listing `fmt` reads is a tracked vector, freed with `vec-free`
  before `main-fmt-tree` returns; the entry *names* inside it are the runtime's
  process-lifetime buffers, like the command line's, and `vec-free` releases
  only the array that points at them (`read-dir`, `docs/LOGOS.md`);
- nothing else. `read-file` returns a buffer the runtime owns for the process's
  life, and `fmt` allocates nothing, so no other `free` is owed.

The error values are structs, not allocations: `lex-error`, `tree-error` and
`resolve-error` carry a `:str` message that is a literal or a slice of the
source, so reporting one costs no allocation either.

## Finding the runtime

Python finds `rt.c` beside its installed package (`driver.py:54-75`); a Logos
binary has no package, and no runtime primitive reports where the executable
lives, so `gen2` names the runtime the way it names everything else it touches:
`logos/runtime/rt.c`, relative to the working directory. The repository is the
unit here — `src/logosc/*.logos` on the command line, `build/` for the output,
and `logos/runtime/rt.c` for the link are all repository-relative, and every
caller is either the gate or a person at the root (`tools/selfhost.sh` starts
with `cd "$ROOT"`). A build run anywhere else says so in one line and exits 1;
it does not silently link a different runtime.

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
`tools/selfhost-ir.txt`, comparing the `build/<stem>.ll` each side writes byte
for byte.

That same command run by `gen2` itself is the fixed point this wave exists for:

```sh
build/selfhost/gen2 build src/logosc/*.logos src/std/map.logos src/std/str.logos -o build/gen3
build/gen3 build src/logosc/*.logos src/std/map.logos src/std/str.logos -o build/gen3b
cmp build/gen3 build/gen3b
```

No Python is involved in either line, and the two binaries are equal because
the second build's IR is the first build's IR, under the same name, compiled by
the same clang command. `tests/test_gen2_build.py` judges the same contract on a
one-file program, where it also compares the binary with Python's.

## What it does not do

- **No checker.** `fmt`'s contract is layout, not acceptance; a file with a
  type error formats and exits 0. The Python `fmt` verb behaves the same way.
  `resolve` likewise stops at names: it does not type-check, but it does follow
  `use`, reading `<name>.logos` beside the asking file (see `resolve.md`).
- **No `rglob` on a pattern other than `*.logos`.** The walk is the verb's,
  not a general glob: it recurses into every directory and formats the entries
  whose names end in `.logos`. Python's `Path.rglob("*.logos")` would also
  yield a *directory* named `x.logos` and then fail to read it; this verb
  descends into it and formats what is inside. No tree in the repository has
  one, and the difference is a directory named like a source file.
- **No flag parsing.** `fmt`'s arguments are all paths or `-`; a path that
  begins with `-` is read as a path, where `argparse` would call it an unknown
  flag. The verb has no flags to confuse it with.
- **No child process from `test`.** The runner is landed two steps at a time:
  discovery and the directive reader are in, and the verb stops there. It
  builds no case and starts no process, so every case it enumerates prints
  `PASS <id> -`; a case whose directive is malformed prints `FAIL <id>
  <detail>` and nothing else. `harness.md` names what the remaining steps owe —
  a child with stdin `/dev/null`, a 10 s bound with a kill, the level loop and
  its cross-level comparison, the summary line and the baseline.
- **No front-end exit-1.** A lexer, tree, resolver or checker refusal is the
  port's own diagnostic line with exit 2, where Python's `build` prints
  `error.render()` and exits 1 (`cli.py:311-327`). The link failures do follow
  Python; the four front-end statuses are part of the command-line cutover, not
  of the driver.
- **A 90-second child.** `(run)` gives the child the runtime's fixed budget
  (`rt.c`) and kills it at 124 when it runs out. W8 step 2 raised it from 30 s:
  the compiler's own unit is 18.2 MB of IR and clang at `-O2` spends 27 s on it
  here, and the 30 s budget did time out at 124 on a busy host, which the driver
  can only report as a clang failure. Ninety seconds is still a hang guard, and
  clang is the only child in the repository that approaches it.
- **No diagnostic for an unreadable file.** That is `read-file`'s `R0007`, with
  its own line, not a fourth code here.
