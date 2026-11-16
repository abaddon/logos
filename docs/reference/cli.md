# `logosc` CLI reference

Everything the compiler's command line does: eight verbs, their flags, their
streams, their exit codes, the files they write, and the exact shape of every
diagnostic. Written for an agent that has `logosc` and nothing else.

**Status of this page.** Every command below was executed against the compiler
built from this tree, and the outputs are copied from the run. The command line
is implemented in `src/logosc/main.logos`; its design rationale is
`src/logosc/main.md`; this page is the consumer contract for it. If the two
disagree, the measured output on this page and the source are right and
`main.md` is stale — say so in an issue.

- Language: [`../LOGOS.md`](../LOGOS.md) (generated, drift-gated).
- Error codes: [`diagnostics.md`](diagnostics.md).
- Standard library: [`stdlib.md`](stdlib.md).
- Known limits: [`limits.md`](limits.md).
- Verified end-to-end walkthrough: [`../quickstart.md`](../quickstart.md).

---

## Surface at a glance

| Verb | Signature | Purpose | Exit codes |
|---|---|---|---|
| `version` | `version` | print the version | `0` |
| `show` | `show FILE PATH` | print one node, canonically formatted | `0` `1` `2` |
| `fmt` | `fmt PATH...` (file, directory, or `-`) | rewrite source in canonical form | `0` `1` `2` |
| `resolve` | `resolve FILE...` | parse and resolve names; no type check | `0` `1` `2` |
| `check` | `check FILE` | resolve, then the full checker; no codegen | `0` `1` `2` |
| `build` | `build FILE... [-o OUT] [--opt O] [--test NAME] [--keep-ir]` | lower, emit IR, link a native binary | `0` `1` `2` |
| `test` | `test [PATH] [--only CAT] [--opt LEVEL]... [--update-baseline]` | build and run every `(test ...)` node | `0` `1` `2` |
| `guide` | `guide [--json\|--check]` | print the manual, its manifest, or check it is current | `0` `1` `2` |

All eight are listed by `logosc -h`, and every verb accepts `-h` for its own
flags. `resolve` and `check` are the cheapest validation calls available —
neither links a binary — so an agent should prefer them over `build` when it
only needs to know whether the source is well formed.

## The help text, as shipped

`logosc` with no arguments, or with `-h` / `--help`, prints this to **stdout**
and exits **0**:

```text
usage: logosc [-h] [--version] [--json] command ...

Compiler for Logos, a prefix-form language for AI readers.

positional arguments:
  command
    build     compile Logos source files to a native binary
    check     type-check one file and print nothing on success
    fmt       rewrite Logos source in canonical form
    guide     print the generated Logos manual or its manifest
    resolve   resolve the names of one or more files
    show      print one node of a Logos file
    test      compile and run the (test ...) nodes in a file
    version   print the compiler version

options:
  -h, --help     show this help message and exit
  --version      print the compiler version and exit
  --json         emit diagnostics and reports as JSON

Every verb accepts -h for its own flags, and --json anywhere on the
command line. Exit codes: 0 success, 2 source or usage error, 1 I/O or
toolchain failure.
```

Every verb has its own help, on stdout, exit 0 — this is the flag discovery
surface, and each block below is a copy of it:

```sh
logosc build -h     # usage: logosc build [-h] [-o OUT] [--opt O] [--keep-ir] FILE [FILE ...]
logosc test -h      # usage: logosc test [-h] [--only CAT] [--opt O] [--update-baseline] [PATH]
logosc fmt -h       # usage: logosc fmt [-h] FILE [FILE ...]
logosc show -h      # usage: logosc show [-h] FILE PATH
logosc version -h   # usage: logosc version [-h] [--json]
logosc guide -h     # usage: logosc guide [-h] [--json | --check]
logosc resolve -h   # usage: logosc resolve [-h] FILE [FILE ...]
logosc check -h     # usage: logosc check [-h] FILE
```

`--version` is the flag form of `logosc version`; both print the same line.
`tests/test_cli.py::Help` pins every one of these blocks, so a verb that gains
a flag without a help line fails the gate.

## Global behaviour

**Program name.** Every usage line and `logos: …` message uses the base name
of `argv[0]`, so a binary installed as `logosc` prints `logosc`, and
`build/logosc` prints `logosc` too. This page shows the installed spelling.

**Streams.** Success is silent for every verb except `version`, `show`,
`guide` and `test`, which print their product to **stdout**. Every diagnostic
and every usage error goes to **stderr**, one classified line, and stdout stays
empty so `| jq` and `>` are safe.

**`--json`.** On any command line, `--json` changes *diagnostics* and the two
versioned documents, never the exit code and never stdout. A failing verb then
writes one JSON object per line to stderr:

```json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100","message":"'+' needs numbers, found :str","node_path":"bad/main/2/0/0","file":"bad.logos","line":0,"col":0}]}
```

`code` is stable and appears in `logosc guide --json` under `codes`;
`node_path` can be fed back to `logosc show FILE PATH`; `line`/`col` are 1-based
when the failing phase tracks positions (lexer, parser) and `0` when it does not
(resolver, checker, lowering) — the node path is the durable address. Severity
is always `"error"`: the compiler stops at the first failure. I/O and toolchain
failures (exit `1`) are not diagnostics and stay one plain `logos: …` line.
The schema is published at [`../schemas/diagnostic-v1.schema.json`](../schemas/diagnostic-v1.schema.json).

**Exit codes.** Three statuses, with one deliberate overload:

| Status | Meaning | Examples |
|---|---|---|
| `0` | success | build, check, resolve, fmt, guide, version, a green `test` run |
| `2` | **the source or the command line is wrong.** Fix the code or the invocation and retry. | lexer / parser / resolver / checker / lowering / emit diagnostic; unknown verb; bad flag; missing required argument; unknown `--only` category; `--update-baseline` pointed at a file, a category directory or a non-suite directory; no `main` in the set; two `main`s |
| `1` | **the environment is wrong.** Fix the machine, the paths or the checkout. | file cannot be read or written; `logos/runtime/rt.c` not found; clang failed; IR cannot be written; `show` path names nothing; `fmt` could not parse the file; a `test` run with a failing case, a leaked case count above baseline, a skipped `.logos` file outside the categories, or a baseline regression; `guide --check` when the manual is stale |

The two meanings of `2` are a deliberate choice inherited from `argparse`
(`2` = usage error) and from the port (a front-end failure is `2` rather than
the Python driver's `1`, so a caller can tell "my source is wrong" from "my
machine is wrong" without reading text). If you need to distinguish a source
error from a usage error, note that usage errors always print a `usage:` line
first and source errors never do.

**Retry policy an agent can encode.** `0` → continue. `2` → do not retry the
same input; read the diagnostic, change the source or the command. `1` → retry
after fixing the environment (path, cwd, runtime, clang); retrying the same
command unchanged cannot succeed.

**Nothing is silent on failure.** There is no partial success and no warning
channel. Every verb either exits 0 with its product, or exits non-zero with one
line that names what broke.

---

## `version`

```sh
logosc version
# logos <version>        (stdout, exit 0)

logosc version --json
# {"schema_version":1,"name":"logos","version":"<version>"}
```

`--version` on its own is the flag form and prints the same line. The version
is a string constant in the compiler (`main-semver`), not read from a package,
and it is the version a release tag is named after (`v<version>`): the release
pipeline refuses a tag that disagrees with it. Schema:
[`../schemas/version-v1.schema.json`](../schemas/version-v1.schema.json).

## `show`

```sh
logosc show FILE PATH
```

Prints one node of a Logos file, formatted exactly as `fmt` would format it,
followed by one newline, to stdout, exit 0.

`PATH` is the same **node path** the diagnostics print: `mod/fn/2/1`. It is
positional and stable — a sibling edit elsewhere in the file does not renumber
it. The points worth knowing:

| `PATH` | Prints |
|---|---|
| `hello/main` | the `main` definition |
| `hello/main/2` | the third child of `main` (`0` is the name, `1` the return type) |
| the empty string `""` | the whole file, canonical — identical to `fmt` output |
| a token's index, e.g. `hello/main/0` | that token alone |

Get the paths from a diagnostic (they are printed with every error), from
`guide --json` (forms and arities), or by bisecting with `show`.

```sh
logosc show examples/hello.logos hello/main
# (fn main :void ()
#   (println "hello"))
```

A path that names nothing is one line on stderr and exit **1**:

```sh
logosc show examples/hello.logos hello/main/9
# logos: show: no node at path 'hello/main/9' in examples/hello.logos
```

`show` never writes. To edit a node, rewrite the file yourself and run `fmt`;
`logosc patch` is not implemented (gap A2).

## `fmt`

```sh
logosc fmt PATH...        # one or more files or directories, rewritten in place
logosc fmt -              # read stdin once, write canonical source to stdout
```

Silent on success, exit 0. The rewrite is **idempotent**: `fmt` twice is `fmt`
once, so a formatting diff is always a real change.

- A **directory** is walked recursively in name order; every entry whose name
  ends in `.logos` is formatted. Every file is attempted even after one fails;
  the exit status is 1 if any of them failed. Non-`.logos` files are ignored.
- `-` means standard input; read once, formatted, written to stdout, so a
  stream that has no name can still be canonicalised. `-` may be given at most
  once (`logos: fmt: '-' may be given at most once`, exit 2).
- A file that cannot be read or written is `logos: <path>: No such file or
  directory` (the C library's own message), exit **1**. The file is not
  truncated before the check.
- A file the lexer or parser refuses is `<path>:<line>:<col>: E0006: …` or
  `E0001: …` on stderr, exit **1**, and the file is left **exactly as it was**.
  Note the position-first shape, which is this verb's alone (the diagnostic
  table explains why).
- `fmt` does **not** type-check. A file with a type error formats and exits 0.
  Formatting is layout, not acceptance.

```sh
printf '(mod  x)\n' | logosc fmt -
# (mod x)
```

Make this a habit: run `fmt` on `git diff --name-only … -- '*.logos'` before
committing, because canonical output is what the formatting gate compares.

## `resolve`

```sh
logosc resolve FILE...
```

Lexes and parses the files, runs the resolver over the whole set as one unit,
and prints **nothing** on success (exit 0). It stops before the checker, so a
file with a type error resolves and exits 0 — `(fn f :nope () …)` resolves;
the checker refuses the type.

Use it to answer "do my module names, imports and definitions line up" without
paying for codegen.

On a resolver diagnostic it prints **one** line to stderr, exit **2**:

```text
<location>: <CODE>: <message>
```

`<location>` is the node path the resolver named (`m/f`, `m/test/t`, `m/0`,
`a/b`), or `file:line:col` for a diagnostic with no node behind it (an imported
file the lexer or parser refused — the position is *that file's*), or the file
the caller named (a root file with no `(mod ...)` form).

Codes it can emit: `E0001`, `E0002`, `E0003`, `E0004`, `E0005`, `E0006`.

```sh
logosc resolve examples/hello.logos
# (nothing, exit 0)
```

## `check`

```sh
logosc check FILE
```

Parses the file, resolves it and everything it imports, and runs the **full
checker** — declarations and function bodies, `(test …)` bodies included. It
stops before lowering: no IR, no clang, no link, and no required-`main` rule.
It prints nothing on success, exit 0.

This is the cheap validation call to make between edits. It catches everything
`build` would reject in the source, and costs a fraction of a build:

| Source | `check` | `build` |
|---|---|---|
| `(println (+ 1 "x"))` in a body | `m/main/2/0: E0100: '+' needs numbers, found :str`, exit 2 | the same line, exit 2 |
| a use after move | `m/main/5/0: E0300: use after move of 'v'`, exit 2 | the same line, exit 2 |
| `(let x :i64 1)` never read | `m/f/2: E0107: unused binding 'x'`, exit 2 | the same line, exit 2 |
| a type error inside `(test bad …)` | reported, exit 2 | reported, exit 2 |
| a file with **no** `main` | exit 0 — `main` is `build`'s rule | `/tmp/nm.logos: E0103: no 'main' function to build`, exit 2 |
| a program that leaks | exit 0 — leaks are runtime facts | exit 0; the leak shows when it runs |

Note two things an agent gets wrong here: **`E0107 unused binding` is an
error**, not a warning, so a debugging build that leaves a binding unused fails
to compile; and `check` cannot see anything that only appears at run time
(leaks, panics, output).

On a checker diagnostic: `<node-path>: <CODE>: <message>` on stderr, exit 2.

## `build`

```sh
logosc build FILE... [-o OUT] [--opt LEVEL] [--test NAME] [--keep-ir]
```

Parses the first file, resolves and checks the whole set as one program,
requires exactly one `main` in that set, lowers it, writes LLVM IR, and runs
clang to produce a native binary. Silent on success, exit 0.

### Arguments and flags

| Flag | Meaning |
|---|---|
| `FILE...` | one or more `.logos` sources; the set is compiled as one program |
| `-o OUT` | write the binary to `OUT` (default `build/<stem>` of the **first** file). A repeated `-o` takes the last value |
| `--opt LEVEL` (`--opt=LEVEL`) | clang optimisation level, default `-O2`. A repeated flag takes the last value |
| `--test NAME` | build one `(test NAME …)` body as the program's `main`, for debugging a single case. Skips the required-`main` rule, writes IR to `build/<stem>.<name>.ll` (`/` and `\` replaced by `_`), and links with `-DLOGOS_DEBUG=1` so the runtime's leak report is compiled in |
| `--keep-ir` | accepted and **changes nothing** — the IR is always kept. It exists for compatibility with the deleted Python tool; ignore it |

Flags may appear anywhere among the files. A word starting with `-` that is not
one of those four is a usage error (exit 2). A file whose name starts with `-`
must be written with a path (`./-weird.logos`).

### What it writes

| Artefact | Path |
|---|---|
| LLVM IR | `build/<stem>.ll` — **always**, whether or not the build succeeds, and whether or not `-o` is given |
| binary | `-o`'s path, or `build/<stem>` |

`build/` is created when missing, **relative to the working directory**. Two
consequences: run `build` from the project that owns the output, and never run
two builds of same-named files from one directory concurrently — both write
`build/<stem>.ll`.

The IR is the artefact to read when a program misbehaves and a source-level
explanation is not enough. It is the same text clang compiled, so it is a
direct answer to "what did the compiler actually emit".

The clang invocation is fixed:

```sh
clang <opt> -target x86_64-unknown-linux-gnu build/<stem>.ll logos/runtime/rt.c \
    -o <out> -lpthread -lm
```

`logos/runtime/rt.c` is resolved **relative to the working directory**, so
`build` resolves the runtime from the compiler's own location, not from the
working directory, so it works from anywhere — see *Environment and working
directory* below. It fails with `logos: runtime not found: …`, exit 1, only
when the installation is incomplete.

### Build failures, by stage

The pipeline stops at the first failure. Each stage has one shape:

| Failure | Shape | Exit |
|---|---|---|
| lexer | `<file>:<line>:<col>: E0006: <message>` | 2 |
| parser | `<file>:<line>:<col>: E0001: <message>` | 2 |
| resolver | `<file>:<line>:<col>` or `<node-path>: E0002`–`E0005: <message>` | 2 |
| checker | `<node-path>: <CODE>: <message>` | 2 |
| lowering | `<node-path>: <CODE>: <message>` | 2 |
| emit | `<module-path>: E0002: <message>` | 2 |
| no `main` / two `main`s | `<file>: E0103: no 'main' function to build` / `<path>: E0003: duplicate definition 'main'` | 2 |
| a file is missing | `logos: <path>: No such file or directory` | 1 |
| IR cannot be written | `logos: cannot write <path>` | 1 |
| runtime not found | `logos: runtime not found: logos/runtime/rt.c` | 1 |
| clang failed | `logos: clang failed: <command>` + clang's own stderr | 1 |

A failed link removes both artefacts, so a failed build never leaves something
that could be mistaken for a success.

### Worked example

```sh
$ logosc build examples/hello.logos
$ echo $?
0
$ ls build/hello build/hello.ll
build/hello  build/hello.ll
$ ./build/hello
hello
```

A source error, whole interaction:

```sh
$ printf '(mod t)\n\n(fn main :void ()\n  (println (+ 1 "x")))\n' > t.logos
$ logosc build t.logos
t/main/2/0: E0100: '+' needs numbers, found :str
$ echo $?
2
```

Read that line as: module `t`, function `main`, the third child (`0` is the
name), the first child of that — the `+` form. `E0100` is `type mismatch`;
[`diagnostics.md`](diagnostics.md) has the full table.

### Running the result

There is no `run` verb (gap E6). Two steps, and the exit status is the
program's own:

```sh
logosc build examples/hello.logos -o /tmp/hello && /tmp/hello
```

## `test`

```sh
logosc test [PATH] [--only CATEGORY] [--opt LEVEL]... [--update-baseline]
```

Builds and runs the `(test …)` nodes of a corpus and reports one line per case
on stdout. This is the verb that proves a Logos program works; for a single
file, it is the fastest end-to-end check there is.

| Argument | Meaning |
|---|---|
| `PATH` | the suite root — a directory holding category directories — or **one file**, which is run as its own `exec` case. Default `tests` |
| `--only CATEGORY` | run one category. One of `parse`, `type`, `exec`, `mem`, `thread`, `generics`, `regress`, `diff` — anything else is `logos: test: unknown test category '<name>'`, exit 2 |
| `--opt LEVEL` | an optimisation level: `--opt -O0`, `--opt -O2`, `--opt=-O0`. One flag swallows every following `-O<digits>` token, so `--opt -O0 -O2` is two levels. **No `--opt` means both `-O0` and `-O2`** |
| `--update-baseline` | after the run, rewrite `<root>/summary.txt` with this run's result |

### What a run prints

One line per case, then the skipped files, then a summary. Measured, three
separate runs:

```text
$ logosc test tests --only regress | tail -3
PASS regress/vec-place-copy -
33 passed, 0 failed, 0 leaked
baseline tests/summary.txt: 0 regression(s)
```

```text
$ logosc test /tmp/suite        # one case whose (out …) declares "3\n"
FAIL exec/failing/wrong -O0: stdout: expected '3\n', got '2\n'; -O2: stdout: expected '3\n', got '2\n'
0 passed, 1 failed, 0 leaked
baseline: none
$ echo $?
1
```

```text
$ logosc test /tmp/suite2       # a stray .logos file outside every category
PASS exec/ok/ok -
SKIP /tmp/suite2/stray.logos
1 passed, 0 failed, 0 leaked
logos: test: 1 file(s) outside the known categories were skipped
$ echo $?
1
```

- `PASS <case-id> -` — the trailing detail is `-` unless the case declares one.
  The case id is the path under the suite root, without `.logos`, plus the
  test's name: `exec/dirs/dirs` is `tests/exec/dirs.logos`, test `dirs`.
  A single file given instead of a root is labelled `exec/<stem>/<test>`.
- `FAIL <case-id> <level>: <detail>; <level>: <detail>` — one clause per level
  that disagreed, so a `-O0`-only difference is visible as such. A case that
  fails to compile reports `build failed: <diagnostic>` instead.
- `SKIP <path>` — a `.logos` file that sits outside every known category. It is
  not silently ignored: the run fails and says so on stderr.
- `<p> passed, <f> failed, <l> leaked` — the totals.
- `baseline <root>/summary.txt: <n> regression(s)` or `baseline: none`.

Exit **1** when any case failed, when a file was skipped, when nothing ran, or
when the baseline reports a problem. Exit **2** on the usage errors only.

### The directives a case declares

A case is a `(test NAME (expect ...) body...)` node. The `(expect …)` clause
declares what the run must observe; the run compares **all** of it, at every
level, and then compares the levels with each other.

| Clause | Meaning |
|---|---|
| `(out "…")` | exact stdout |
| `(err-contains "…")` | stderr must contain this non-empty substring |
| `(code N)` | process exit status |
| `(leaks N)` | allocations the leak tracker reports (or `(expect-leak N)` in the legacy spelling; declaring both is an error) |

Negative cases declare `(expect-error E0101)` at **module level** (or a sibling
`name.expect` file holding the code), and the run asserts that the compiler
refuses the file with that code.

Malformed directives are their own errors with fixed sentences — "test has no
(expect ...) directive", "duplicate directive '(code ...)'", "expect-error
needs a code like E0101, found 'nope'" — because the harness prints the first
problem it finds, verbatim.

### The baseline

`tests/summary.txt` is the recorded result: a `LEAKS <total>` line, an
`OPTS -O0 -O2` line naming the levels it ran, then one line per case. On a run
**without** `--update-baseline`:

- a case that passed in the baseline and fails now is a **regression** and the
  run exits 1;
- a leak total higher than the baseline recorded at the same levels also exits
  1;
- a baseline with no `OPTS` line cannot be compared and is refused outright
  rather than leaving the leak total ungated.

`--update-baseline` merges when `--only` is given: it rewrites the cases that
category ran, drops the ones it no longer contains, and keeps the rest. It
refuses three shapes, each exit 2:

```text
logos: test: --update-baseline needs a directory, not a single file
logos: test: --update-baseline needs the suite root, not the category directory 'tests/exec'
logos: test: --update-baseline needs the suite root, a directory holding a category such as 'exec'; 'examples' is not one
```

Regenerate the baseline only when you add a case or change one deliberately;
never to hide a failure. Review `git diff tests/summary.txt` and say why in the
pull request.

## `guide`

```sh
logosc guide            # the generated manual to stdout
logosc guide --json     # the machine-readable manifest
logosc guide --check    # is docs/LOGOS.md current?
```

`--json` and `--check` are mutually exclusive; anything else is a usage error
(exit 2).

| Mode | stdout | stderr | Exit |
|---|---|---|---|
| none | `docs/LOGOS.md`, byte for byte | — | 0 |
| `--json` | the manifest, plus a newline | — | 0 |
| `--check` | `guide: docs/LOGOS.md is current` | a stale report | 0 current / 1 stale |

`--check` is a real gate: it regenerates the manual and compares it byte for
byte, so an edit to `docs/LOGOS.md` by hand, or a compiler table change without
a regeneration, fails here. A stale manual prints nothing to stdout and this to
stderr, exit 1:

```text
docs/LOGOS.md is stale: 0 line(s) to add, 2 line(s) to remove; run `logosc guide > docs/LOGOS.md`
--- docs/LOGOS.md (committed)
+++ generated
@@ -933,2 +933,0 @@
-
-stale
```

### The `--json` manifest

This is the cheapest way for an agent to learn the whole surface without
reading markdown. Measured shape — valid JSON, one object, **18,836 bytes**,
eight keys:

| Key | JSON type | Length | Element shape |
|---|---|---|---|
| `schema_version` | int | — | `1`; bumped only for a breaking change |
| `forms` | array | 96 | `{"name": str, "arity": str, "meaning": str}` — `arity` is a string, `"2+"` and `"2"` included |
| `types` | array | 16 | `{"name": ":i64", "kind": str, "bits": int, "signed": bool, "meaning": str}` |
| `operators` | array | 17 | `{"symbol": "+", "arity": str, "meaning": str}` |
| `builtins` | array | 2 | `{"name": "println", "meaning": str}` |
| `reserved` | object | 3 | `{"forms": [str], "prefixes": [str], "variants": [str]}` |
| `codes` | object | 35 | `{"E0100": "type mismatch", …}` — code → one-sentence meaning |
| `categories` | array | 8 | `["parse", "type", "exec", "mem", "thread", "generics", "regress", "diff"]` |

```sh
logosc guide --json | jq -r '.codes | to_entries[] | "\(.key) \(.value)"'
logosc guide --json | jq '.forms[] | select(.name=="match")'
logosc guide --json | jq -r '.reserved.forms[]'      # names you may not define
```

**Stability: guaranteed at `schema_version` 1.** A breaking change to the
manifest bumps that number; an additive key does not. The counts in this table
are the cheapest assertion a tool can make, and `tests/test_cli.py::Guide` pins
the version key and the seven named keys.

## Environment and working directory

Two paths are needed at build time, and both are found **from where the
compiler lives**, not from where it is run:

| Path | Used for | When absent |
|---|---|---|
| `logos/runtime/rt.c` (`share/logos/runtime/rt.c` when installed) | linked into every binary | `logos: runtime not found: …`, exit 1 |
| `src/std/<name>.logos` (`share/logos/std/<name>.logos` when installed) | a `(use map)`, `(use str)`, `(use io)` the asking file cannot satisfy beside itself | `E0005: unknown module 'map'`, exit 2 |

The lookup walks three candidates under the compiler's root — the parent of the
`bin` directory holding the executable: the installed layout (`share/logos/…`),
the checkout layout (`logos/…`, `src/std/…`), and finally the old
working-directory paths, kept so an existing script keeps working. So
`cd /tmp && logosc build hello.logos` works, and so does `(use map)`, from any
directory — `tests/test_cli.py::Portability` pins both. The three candidates are
tried in that order and the first that exists wins.

`(use name)` first looks for `name.logos` **beside the asking file**, then in
the installation's standard library. A module sees the definitions of the
modules it names, not the ones they name: imports are not transitive, and every
module in a program defines a globally unique name (gap A1, still open).
