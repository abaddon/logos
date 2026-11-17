# `src/logosc/main.logos` — the verbs and the process contract

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
gen2 version
gen2 show <file> <path>
gen2 fmt <file|dir|->...
gen2 resolve <file>...
gen2 check <file>
gen2 build <file>... [-o <out>] [--opt <O>] [--target <triple>] [--test <name>] [--keep-ir]
gen2 test [<path>] [--only <category>] [--opt <level>]... [--target <triple>] [--update-baseline]
gen2 guide [--json|--check]
```

`patch` is deliberately absent: see "The usage block" below.

`(args)` returns the whole command line including the program name, as the
runtime copies it from `/proc/self/cmdline`. So the shape is:

| index | holds |
|---|---|
| `0` | the program |
| `1` | the verb, `version`, `show`, `fmt`, `resolve`, `check`, `build`, `test` or `guide` |
| `2` | `show`'s file, or the file to check |
| `2` … `n-1` | the paths to format, resolve or build (one or more), and `build`'s or `test`'s flags, or `test`'s one path |
| `3` | `show`'s node path (the empty word is the file itself) |

`build`'s flags may appear anywhere among its files, as Python's `argparse`
allows: `-o OUT` names the binary, `--opt O` (or `--opt=O`) names the
optimisation level and defaults to `-O2`, `--target TRIPLE` (or
`--target=TRIPLE`) names the triple the IR header and clang's `-target`
receive — it defaults to `x86_64-unknown-linux-gnu`, and
`aarch64-unknown-linux-gnu` is the other value accepted, so a third triple is a
usage error naming the value and the two the compiler can emit, rather than a
clang failure — and `--keep-ir` is accepted and changes nothing, because the IR
is always kept. A word that starts with `-` and is not one of those five is a
usage error; a file whose name starts with `-` would have to be written with a
path. A repeated `-o`, `--opt` or `--target` takes the last value, as
`argparse` does. `--target` is value-taking under `build` and under `test`; the
other verbs do not claim it, so there it is `unrecognized arguments`.

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
levels, `--opt=-O0` is one, and a run with no `--opt` is both. A second
positional argument, and any other word starting with `-`, is a usage error.
`--target TRIPLE` (or `--target=TRIPLE`) builds each case for that triple and
runs it with the matching runner: `h-execute` passes `--target` to the
`build --test` child, and for a foreign triple prefixes the run with
`qemu-aarch64-static` (or `qemu-aarch64`, whichever answers `-version`), so a
host-built case is never executed as if it were the target's. The triple
reaches `h-execute` through `h-run` and the file/test walk because
`harness.logos` has no global to hold it; the chain is one extra argument, not
a second code path.

`--update-baseline` rewrites `<root>/summary.txt`, the suite's recorded result,
and is the only way that file is ever written once Python is gone. It is
`harness.logos`'s (`h-baseline-save`); `main` only checks the root first,
because Python refuses a file, a category directory and a directory that holds
no category before it runs anything (`cli.py:186-210`). The three refusals are
one line each and exit 2, e.g.

```
logos: test: --update-baseline needs a directory, not a single file
logos: test: --update-baseline needs the suite root, not the category directory 'tests/exec'
logos: test: --update-baseline needs the suite root, a directory holding a category such as 'exec'; 'examples' is not one
```

`main-test-run` refuses one combination before any of those: a foreign triple
with `--update-baseline`. The file records no target, so an aarch64 run
rewriting it would leave the host comparison checking ARM numbers against a
host run — the next host run would then report regressions that are the
baseline's fault. It is a usage error, one line, exit 2:

```
logos: test: --update-baseline cannot be combined with --target aarch64-unknown-linux-gnu: summary.txt is the host baseline and records no target
```

The run is `harness.logos`'s (`h-run`), and this file gives it the levels and
turns its status into the process's: every case is built and run at each level,
its four clauses and its levels are compared, and the report ends with
`<passed> passed, <failed> failed, <leaks> leaked` and then the baseline line —
`baseline <root>/summary.txt: <n> regression(s)`, or `baseline: none` when the
root owns no file. Exit 1 when a case failed, when a file sat outside the known
categories, when nothing ran, or when the baseline reports a problem; 2 on the
two usage errors above. Ids, their order, the detail sentences, the summary and
the baseline's problems are Python's `tester.py` and `cli.py`.

`guide` is the generated manual (`guide.md`). With no flag it prints
`docs/LOGOS.md` to stdout; `--json` prints the manifest and a newline; `--check`
regenerates the markdown and compares it byte for byte with `docs/LOGOS.md`,
printing `guide: docs/LOGOS.md is current` and exiting 0, or a stale report on
stderr and exiting 1. Both modes are mutually exclusive, as `argparse`'s
`add_mutually_exclusive_group` makes them (`cli.py:136-146`), and anything else
is the usage error below. The two tables the manifest cannot be built without
are read from the compiler — `types.logos`'s primitive and type-form lists,
`harness.logos`'s categories — and the code, rule, form, arity, meaning and
chapter-title tables live in `guide.logos` itself.

The command line is `argparse`'s, because the tool it replaces is Python's and
a script that reads a message reads it byte for byte. `main-help`, the
`main-verb-usage` table and `main-cli-error` are those bytes: a **missing
required argument** is the sub-verb's usage line plus
`<prog> <verb>: error: the following arguments are required: …`, while an
**unknown verb** and an **unrecognized word or flag** are the top-level usage
line plus `<prog>: error: …`, because `argparse` reports them from the parent
parser (`cli.py:151-184`). All of them exit 2 and write only stderr:

```
$ gen2 show
usage: gen2 show [-h] FILE PATH
gen2 show: error: the following arguments are required: FILE, PATH

$ gen2 frobnicate
usage: gen2 [-h] command ...
gen2: error: argument command: invalid choice: 'frobnicate' (choose from 'build', 'test', 'fmt', 'show', 'version', 'guide')
```

**No argument at all** is not an error: it prints the help to stdout and exits
0, exactly as `argparse`'s `print_help` does when no subcommand was given
(`cli.py:156-158`). The help is the 80-column rendering, with one row per verb;
`COLUMNS` does not change it, because the text is a constant here and argparse's
wrapping is not reproduced.

`<prog>` is the base name of `argv[0]`, not a constant: installed as `logosc`
the text is Python's exactly, and run as `build/selfhost/gen2` it names the
binary that was actually run. Python hardcodes `logosc`; a copy of the binary
named `logosc` is therefore what the parity test compares, and the rename costs
nothing at the call site. `(args)` gives the whole command line, so the base
name is `main-base` of entry zero.

The verb list is Python's, minus `patch`: that verb replaces one node through
`stdin`, is used by nobody in the gate, and is a developer convenience rather
than something `logosc` keeps. `patch` is therefore **not** a verb here — it is
rejected as an unknown command (exit 2, `invalid choice: 'patch'`), and neither
the help nor the choice list names it. `resolve` and `check`, which are this
port's own verbs and have no Python counterpart, stay out of the help for the
same reason the text is Python's: the block is the replaced tool's contract, and
`resolve`/`check` are documented here instead.

A repeated `-` is the one `fmt` argument error that is not a usage error:
Python refuses it with `logos: fmt: '-' may be given at most once` and exit 2
(`cli.py:336-343`), and so does this verb, before it formats anything. A word
starting with `-` is an option rather than a path, so `fmt -x` is
`the following arguments are required: FILE` and `fmt -x a.logos` is
`unrecognized arguments: -x`, both measured.

Two arities are *not* usage errors, because they are facts about the build set
rather than about the command line: a set with no `main` and a set with two
`main`s each print one diagnostic line and exit 2 (`E0103` and `E0003`; see
"Output" below). `resolve` and `check` keep one usage line each for a wrong
arity (`main-port-verb`), since neither has an `argparse` spelling to copy.

A verb given a **path that does not exist** is not a usage error either: it is
`logos: <path>: <strerror>` with exit 1, the same line `fmt` prints, for every
verb that reads a file (`fmt`, `build`, `show`, and `test`'s own
`logos: test: <root>: no such file or directory`). `build` checks its whole set
with `path-error` before lowering anything, so a missing source is reported
before a diagnostic is raised about a half-read set; `show` uses the same check
`fmt` does. `test` skips the check and lets the harness answer, because a
missing suite root is a run failure rather than an argument error.

## `version` and `show`

`version` is one line, `logos 0.2.1`, and exit 0 — Python's
`print(f"logos {__version__}")` (`cli.py:131`, `logos/__init__.py:3`). The
string is a constant here rather than read from a package, because there is no
package left to read it from; bumping the version means changing `main-version`
and nothing else.

`show FILE PATH` prints one node: the canonical form the printer would write
for it, followed by one newline — Python's `render(node)` (`cli.py:401-418`),
which is `fmt-form` at column zero for a form and `fmt-token` for a token, plus
the newline `render` adds. The empty path is the file, and prints the whole
canonical file exactly as `fmt` would (`fmt 1`).

The path is the **node path the diagnostics print**: `mod/fn/2/1`. `tree-path`
already computes it, so `main-find-tree` asks each top-level form for its
stored path, compares, and descends through `main-find-below` by numbering each
form's children from zero. The descent has to number tokens too, because a
token holds a position and can be addressed (`m/f/0` is a return type); a token
has no stored path, which is why the walk mirrors `assign_paths` instead of
reading the field. `main-prefix` is `str.startswith(child + "/")`, including
its behaviour on an empty prefix, so `hello//main` and `/hello/main` miss the
way Python's do.

A path that names nothing is one line on stderr and exit 1, Python's text
character for character (`cli.py:406-412`):

```
logos: show: no node at path 'hello/main/9' in examples/hello.logos
```

The source is loaded the way `fmt` loads it — `path-error` first, then
`main-fmt-loaded`'s lex and tree passes — so an unreadable file and a file the
lexer refuses report exactly what they report for `fmt`, with the port's
`<path>:<line>:<col>: <CODE>: …` order for the latter (see "Output").

`show` does not replace anything, so it needs no `stdin` and no write: the file
is opened read-only by `read-file` and the tree it builds is freed on every
path, including the miss.

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
clang {opt} -target {target} build/<stem>.ll logos/runtime/rt.c \
    -o <out> -lpthread -lm
```

That is Python's command with Python's arguments (`driver.py:243-254`), which is
why a build of the same set produces a byte-identical executable: clang embeds
the IR file's basename and nothing else about the path, and both drivers keep
the text at `build/<stem>.ll`. `{opt}` is `-O2` unless `--opt` says otherwise,
`{target}` is `main-target-name`'s value — the last `--target` on the command
line, or `x86_64-unknown-linux-gnu` when the flag is absent, checked by
`main-target-bad` before the build starts and threaded down through
`main-build-all`, `main-built` and `main-link` so the IR header's
`target triple` and clang's `-target` cannot disagree — and both link flags are
unconditional. The build prints nothing to either stream on success and exits 0.

`{target}` is also what decides the link's shape. For
`aarch64-unknown-linux-gnu`, `main-link-cross` pushes `-static` and
`-fuse-ld=lld` onto the same argv before the inputs: the host `ld` cannot link
an ELF aarch64 (it answers `unrecognised emulation mode: aarch64linux`), and a
static binary needs no aarch64 loader when it is run under `qemu-aarch64`. The
runtime is not a separate build — `rt.c` is an input of that same clang command,
so it is compiled for `{target}` in the invocation that links it and a
host-built object can never enter a foreign ELF. The host triple pushes neither
flag, so the default command line is byte-for-byte what it was.

Two paths are created before they are used — `build/` for the IR, and the `-o`
path's directory — because a fresh checkout has no `build/` directory.
`main-mkdir` is `(mkdirs dir)`, the runtime helper that creates a path and its
missing parents and returns 0 or -1; it replaced a `mkdir -p` child process, so
a build no longer depends on a `PATH` entry and no longer pays a spawn.
`main-exists` still runs `test -f` for the runtime's presence; that probe is one
per candidate in the runtime's search order — two at most, and one in a
checkout, where the first candidate answers — and folding it into the runtime is
a separate question with a different failure line attached. Both creation and
probing ignore the status, because a directory that cannot be made fails at the
write or at clang, with the line that says so.

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
- **A runtime to link.** `main-link` asks `main-exists` for each candidate in
  `main-runtime-candidates`, `<root>/share/logos/runtime/rt.c` (installed) and
  `<root>/logos/runtime/rt.c` (checkout) first, `logos/runtime/rt.c` last; when
  none is a regular file the build stops with one `E0800` line naming the order,
  exit 1, and removes the IR it had just written, rather than handing clang a
  path that is not there.

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
| the runtime lookup | `E0800` | the file being built, then the search order |
| the link | none | `logos: clang failed: …`, exit 1 |

A lowering refusal is `lower-error`'s: `lo-fail-at` recorded the form's node
path, and `lower-code` renders the number (`2` → `E0002`). An `emit` refusal is
`ir-error`'s, and it carries no path at all — the IR rows name no source node —
so the diagnostic names the module (`tree-path` of the root, e.g. `m`) and uses
`E0002` for "this arena cannot be printed". `main-ir-diag` is the one place
that decides this; the port-only code is documented because Python's compiler
raises instead of printing. **Neither is a panic**: a failed emit is a line on
stderr and exit 2, and a bad `-o` path is `logos: cannot write <path>`, exit 1.

The IR write and the link have no source location, so they cannot use the
diagnostic shape above; they use Python's `build` shape instead, one `logos: …`
line on stderr and exit 1 (`cli.py:311-327`). The runtime lookup between them has
no source *node* either, but it has a file and a code, so it is printed the way
`E0103: no 'main' function to build` is — `<file>: E0800: …`. A clang failure
prints the command it ran
followed by clang's own stderr, which is how `BuildError` reads in Python, and
removes both artefacts — the IR and the half-written binary — so a failed build
leaves nothing behind that could be mistaken for a success.

## Functions

| function | returns | meaning |
|---|---|---|
| `main` | `:i64` | the entry point: read `argv`, dispatch, return the status |
| `main-prog a` | `:str` | the base name of `argv[0]`, what the usage block prints |
| `main-base s` | `:str` | the substring after the last `/` |
| `main-help prog` | `:i64` | print the help to stdout and return 0 |
| `main-verb-usage verb` | `:str` | the `argparse` usage tail for one verb |
| `main-verb-label verb` | `:str` | `""` for the top parser, `" show"` for a sub-parser |
| `main-cli-error prog verb msg` | `:i64` | print a usage line and an `argparse` error, return 2 |
| `main-required prog verb names` | `:i64` | the missing-positional error |
| `main-unrecognized prog rest` | `:i64` | the unrecognized-words error |
| `main-invalid prog verb` | `:i64` | the invalid-choice error and the verb list |
| `main-join-args a i n` | `:str` | join `argv[i..n)` with single spaces |
| `main-join-vec items` | `:str` | the same join over a vector |
| `main-verb a n prog` | `:i64` | dispatch on `argv[1]`, or the invalid-choice error |
| `main-args a` | `:i64` | no argument is the help; otherwise `main-verb` |
| `main-version a n prog` | `:i64` | `logos 0.2.1`, or the unrecognized words |
| `main-show a n prog` | `:i64` | `show`'s arity, then the file and its path |
| `main-show-file path target` | `:i64` | check the file, parse it, print one node or the miss |
| `main-show-nodes path nodes ntexts target` | `:i64` | address the path and print what it names |
| `main-show-one nodes ntexts id` | `:void` | print one form or one token, plus a newline |
| `main-show-form`, `main-show-token` | `:void` | the two printer calls |
| `main-show-missing path target` | `:i64` | `logos: show: no node at path …`, exit 1 |
| `main-find-tree nodes ntexts path` | `:i64` | the node id at a path, or -1 |
| `main-find-at nodes ntexts c path` | `:i64` | one top-level form: its own path, else below it |
| `main-find-below nodes ntexts base id path` | `:i64` | number a form's children and descend |
| `main-prefix p path` | `:bool` | `path` starts with `p` and then `/` |
| `main-build a n prog` | `:i64` | read `build`'s flags and files, then build or report |
| `main-bad-flag prog verb a n i` | `:i64` | the flag error at `argv[i]`: a missing value or an unknown word |
| `main-unreadable paths` | `:str` | the first path `path-error` refuses, or `""` |
| `main-arg a n i paths outs opts tnames ttargets` | `:i64` | one argv word: the next index, or -1 for a usage error |
| `main-flag-next a i into` | `:i64` | push the word after a flag and skip both |
| `main-attached-next s off i into` | `:i64` | push the value after `off` in `--opt=…`/`--target=…` |
| `main-path-next a i paths` | `:i64` | push a source path and step over it |
| `main-dest paths outs` | `:str` | `-o`'s last value, or `build/<first stem>` |
| `main-opt opts` | `:str` | `--opt`'s last value, or `-O2` |
| `main-target-name ttargets` | `:str` | `--target`'s last value, or `x86_64-unknown-linux-gnu` |
| `main-target-bad target` | `:str` | the unsupported-triple line for `target`, or `""`; x86_64 and aarch64 Linux are supported |
| `main-link-cross argv target` | `:void` | push the `-static -fuse-ld=lld` a foreign triple needs; host triple untouched |
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
| `main-test a n prog` | `:i64` | read `test`'s path and flags, then run the harness or report |
| `main-test-arg a i n path only levels flags ttargets` | `:i64` | one `test` argv word: the next index, or -1 for a usage error |
| `main-test-only value next only` | `:i64` | set `--only`'s value and skip the word |
| `main-test-level s` | `:bool` | whether a word is an `-O<digits>` level |
| `main-test-digits s i n` | `:bool` | whether `s[i..n)` is all digits |
| `main-test-opts a i n levels` | `:i64` | consume the levels after `--opt` into `levels`; -1 when there is none |
| `main-test-opt-eq s next levels` | `:i64` | push an attached `--opt=-O0`'s value and skip the word |
| `main-test-update flags next` | `:i64` | remember `--update-baseline` and skip the word |
| `main-test-path s next path flags` | `:i64` | take the one positional path; -1 on a second |
| `main-test-run path only levels flags target` | `:i64` | refuse a foreign triple with `--update-baseline`, check the baseline root, validate `--only` and the triple, call `h-run` |
| `main-test-baseline root` | `:i64` | run Python's `_baseline_argument_problem`; 0 when the root is a suite |
| `main-baseline-problem path` | `:str` | why the root cannot own a baseline, or `""` |
| `main-baseline-root-problem path` | `:str` | the directory half: a suite root, not a category or a stray |
| `main-has-category root` | `:bool` | whether `root` holds any of the eight category directories |
| `main-categories out` | `:void` | the eight category names, in `tester.CATEGORIES` order |
| `main-test-fail problem` | `:i64` | `logos: test: <problem>`, exit 2 |
| `main-test-unknown name` | `:i64` | print the unknown-category line and return 2 |
| `main-sort names` | `:void` | sort entry names byte-wise, in place |
| `main-str-less a b` | `:bool` | byte-wise `a < b` |
| `main-join dir name` | `:str` | `dir/name`, without a doubled slash |
| `main-fmt-verb a n prog` | `:i64` | `fmt`'s arity: a FILE is required, an option is not a path |
| `main-fmt-options a n counts` | `:void` | count the positionals and remember the first option |
| `main-guide a n prog` | `:i64` | `guide`'s flags, the mutually-exclusive pair, then the mode |
| `main-guide-flags a n flags extra` | `:void` | read `--json`, `--check` and everything that is neither |
| `main-guide-mutex a n` | `:str` | `argument --check: not allowed with argument --json` |
| `main-port-verb a n prog verb` | `:i64` | `resolve` and `check`, the two verbs Python has no line for |
| `main-port-arity prog verb` | `:i64` | the one usage line those two print on a wrong arity |
| `main-logos-name name` | `:bool` | whether a name ends in `.logos` |
| `main-or a b` | `:i64` | the status of two files: 1 when either failed |
| `main-resolved file nodes ntexts` | `:i64` | run `resolve-file` and return 0 or the diagnostic |
| `main-resolve-set a first count` | `:i64` | run `resolve-set-of` over the argv files and return 0 or the diagnostic |
| `main-resolve-diag file e` | `:i64` | print one resolver diagnostic and return 2 |
| `main-at path file line col fallback` | `:str` | the diagnostic's location: path, `file:line:col`, or `fallback` |
| `main-checked file nodes ntexts` | `:i64` | run `resolve-set` then `check-file`; free the module set |
| `main-checked-run file mods nodes ntexts` | `:i64` | run the checker over the resolver's module set |
| `main-check-diag file e` | `:i64` | print one checker diagnostic and return 2 |
| `main-build-all paths dest opt tname target` | `:i64` | create the arena, run the pipeline over the files, free it, return the status |
| `main-built paths dest opt …` | `:i64` | read, lex and parse the first root, resolve the set, check it, load every other module, lower the unit, emit, write `build/<stem>.ll`, link |
| `main-stem path` | `:str` | the file name without its directory and last extension |
| `main-ir-path path` | `:str` | `build/<stem>.ll`, where the IR always goes |
| `main-out-path path` | `:str` | `build/<stem>`, the default binary |
| `main-dir path` | `:str` | the directory part of `path`, or `""` when it has none |
| `main-runtime-candidates out` | `:void` | push the runtime's search order: `<root>/logos/runtime/rt.c`, then `logos/runtime/rt.c` |
| `main-runtime cands` | `:str` | the first candidate that is a regular file, or `""` |
| `main-exists path` | `:bool` | whether `path` is a regular file (`test -f`) |
| `main-mkdir dir` | `:void` | `(mkdirs dir)`, ignoring the status |
| `main-joined argv` | `:str` | the command line as one line, for the failure message |
| `main-link ll out opt dbg file target` | `:i64` | link `ll` and the runtime into `out`; 0 or the failure line |
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
binary had no package and no primitive that reported where the executable lives,
so `gen2` used to name the runtime the way it named everything else it touched:
`logos/runtime/rt.c`, relative to the working directory. That made an installed
compiler only work from inside the directory it was unpacked into. It is now
resolved from the compiler's own location (D2 of the v1 readiness audit;
`docs/superpowers/specs/2026-11-15-runtime-and-library-lookup.md`):

1. `<root>/logos/runtime/rt.c`
2. `logos/runtime/rt.c` — the working directory, last

`<root>` is `LOGOS_ROOT` when it is set and non-empty, otherwise the parent of
the directory holding `/proc/self/exe` — `<prefix>/bin/logosc` and
`<repo>/build/logosc` both name their prefix. `sys-root` in `sys.md` owns that
rule; `main-runtime-candidates` owns the order; `main-runtime` takes the first
candidate `main-exists` accepts. The working directory is last because the
repository's own gates and fixtures build with relative paths, and a build from
the root a person is standing in still works exactly as it did.

A build that finds none of them prints the order it tried, with a code and the
file being built, and removes the IR it had just written:

```
hello.logos: E0800: runtime not found; searched: /prefix/share/logos/runtime/rt.c, /prefix/logos/runtime/rt.c, logos/runtime/rt.c
```

`E0800` is the one code this change adds to the table in `guide.logos`. Before
it, this failure was `logos: runtime not found: logos/runtime/rt.c` with exit 1
and neither a code nor a location — the only refusal an agent could not classify
by reading it. The exit status stays 1: the command line was fine and the source
was fine, the installation is what is broken.

## Building it

`gen2` is one program built from the whole module set gen2 may use: every
`src/logosc/*.logos` file and the two standard modules the compiler's tables
name, `src/std/map.logos` and `src/std/str.logos`:

```sh
./tools/logosc.sh build src/logosc/*.logos src/std/map.logos src/std/str.logos -o build/selfhost/gen2
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
- **A case id outside printable ASCII.** A `BASELINE <id> <detail>` line prints
  the id percent-decoded, as Python prints it. Decoding covers bytes 32–126 and
  tab, newline and carriage return; any other byte keeps its `%XX` spelling,
  because the language cannot build a one-byte string that is not a source
  literal. The comparison itself is unaffected: both the baseline's id and the
  run's are decoded the same way before they are matched, so ids with such a
  byte still compare equal — only the printed spelling differs from Python's.
  No case id in the corpus holds one.
- **No `cwd`.** The baseline line names the file as the root argument spells it
  (`tests/summary.txt` for `test`, or `build/x/summary.txt`), which is what
  Python's `_display` prints for a relative root. Python additionally shortens
  an *absolute* root that sits under the working directory; the port cannot,
  because the language has no `getcwd` and adding one would change the runtime
  and the IR of every binary. Running with a relative root — the invocation in
  the cutover plan — is byte-identical.
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
