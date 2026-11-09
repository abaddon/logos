# Self-hosted `logosc` — design

Design document. 2026-11-08. Status: for approval.

This extends `2026-11-06-ai-language-design.md`, whose non-goals said "self-hosting
is a later project". This is that project.

## Intent

Logos gets its own compiler, written in Logos. The Python compiler stays in the
tree as the reference oracle, so the two can be compared forever.

The gate is the fixed point, fixed by the owner:

> gen2, built by Python, and gen3, built by gen2, emit the same IR.

Nothing in this document is worth anything if that line is not provable on every
source file in the repository.

## Goals

1. A Logos-written compiler that accepts the whole language the Python one accepts.
2. IR output that matches the Python compiler byte for byte, so parity is a diff,
   not a judgement.
3. Diagnostic codes, paths and exit codes that match, so the negative corpus runs
   unchanged under both.
4. A gate script that proves all of it, run by `tools/pr_gate.sh`.
5. A language surface large enough for the compiler, and no larger.

## Non-goals

- A new backend. The Logos compiler also emits LLVM IR text and calls clang.
- A new IR format, new diagnostic text, or new node paths. Parity means parity.
- Porting the prose guide. `guide --json` only.
- `show` and `patch`. The AI edits text with its own editor, and `fmt` restores
  canonical form afterwards.
- Removing Python from the repository.
- New targets, cross-compilation, incremental compilation, caching.

## Anti-goals

- A gen2 that equals gen3 because both are wrong. The gate must always include the
  Python compiler as an independent statement of the same semantics.
- A port that improves the IR on the way, which makes the diff unmatchable.
- A language feature added because the port wants it, without its spec paragraph,
  manual chapter, corpus case and regress case. The repo rule is spec, manual,
  corpus, code, in that order.
- Two maintained compilers drifting without noise. Drift must be a failing gate,
  never a hunch.

## Constraints that shaped this design

Each of these was probed against the current compiler, not assumed.

| Fact | Evidence |
|------|----------|
| A struct cannot hold a vector | `E0002 vector fields are not supported yet` |
| A struct can hold a `:str` and be stored in a vector | `(vec node)` of `(struct (kind :i64) (text :str))` builds and runs |
| Passing a container to a function moves it | `E0300 use after move of 'v'` on the next use |
| A function can return a container | returning `(vec :i64)` from a local works |
| A struct can be returned and read in place | `(get (mk 9) name)` works |
| `:str` at an extern boundary passes as `(ptr, len)` | `(extern fn write :i64 ((fd :i64) (text :str)))` writes 2 bytes for `"hi"` |
| A `:str` in the first extern position breaks a C function that expects a C string | `open(path, flags, mode)` declared with a `:str` returns -1 with `EINVAL`, because the callee reads `len` as `flags` |
| `(read-all)` reads standard input only | the checker refuses any argument |
| A program cannot see its command line | the emitted C `main` takes no `argc` or `argv` |
| Strings are process-lifetime and never freed | `str-concat` uses `malloc` and never enters the leak report |
| A program can write a file only through `write` on an fd it cannot open | `open` is unusable per the row above |

Two of these block the port outright, and they are the reason this document has a
language section at all:

- **No argv and no file read by path.** A compiler that cannot read `foo.logos`
  and cannot see `-o out` is not a compiler.
- **No non-owning parameter.** Every helper that touches the compiler's tables
  would steal them. With 20k lines and no helpers, there is no compiler.

## Decisions

### D1. Verbs: `build`, `test`, `fmt`, `guide --json`

An AI works in one loop: write a case, format it, build it, run the in-source
tests, read the diagnostic code and the node path. Every verb in that loop belongs
to the compiler the AI calls, which is now the Logos binary.

`guide --json` belongs there too, because the manifest is a dump of the compiler's
own tables, and those tables now live in Logos source. Prose stays out.

`show`, `patch` and `version` are dropped. `version` prints a literal and can come
back in five lines if wanted.

### D2. The Python compiler stays, frozen

It stays in the tree as the oracle, indefinitely. The fixed point proves
stability, not correctness: two wrongs agree. Only an independently written
compiler says what Logos means. It is also the only judge that exists before a
working gen2 exists.

Frozen means: it changes only when the language changes, and never to fix a bug
that only the Logos compiler has.

### D3. The gate compares IR text, not binaries

Byte-identical native binaries are not a fair target: clang can embed paths and
timestamps. The gate is:

1. `gen2` and `gen3` emit byte-identical `.ll` for every source in the repo.
2. `python3 -m logos` and `gen2` emit byte-identical `.ll` for every corpus file.
3. Binaries built by `gen2` and by `gen3` pass the corpus at `-O0` and `-O2`.
4. `gen2 test` reports the same pass count and the same leak total as the Python run.

### D4. Parity is a frozen format, so improvements land in Python first

Any change to the emitted IR or to diagnostic text is made in the Python compiler
first, with its corpus case, and only then ported. Otherwise the Logos compiler
cannot match, and the diff gate becomes an argument.

### D5. New language surface: six forms and one parameter kind

Each one needs its spec paragraph, manual chapter, corpus case, negative case and
regress case, in that order, per `AGENTS.md`, and each lands in the Python compiler
first (D4), because the corpus gate runs on Python.

| Surface | Type | Why the compiler needs it |
|---------|------|---------------------------|
| `(read-file path)` | `:str` | read `foo.logos`; a path that cannot be read is `R0007` at the call, naming the path |
| `(args)` | `(vec :str)` | see `build`, `test`, `-o`, `--only` |
| `(str-byte s i)` | `:u8` | the lexer walks bytes; `str-slice` cannot read one byte |
| `(str-from-i64 v)` | `:str` | `%t<n>` names, node paths, JSON numbers |
| `(f64-bits v)` | `:i64` | float constants are emitted as hex, from the value's bit pattern |
| `(run prog args)` | `:run` handle | run clang, and run each test binary; status, stdout and stderr are read by `(run-status r)`, `(run-out r)` and `(run-err r)` |
| `(ref T)` parameter | non-owning | helpers that read and grow the compiler's arenas |

`read-file` panics `R0007` with the path when the file cannot be read. A missing module is
not its job either: `use` names a module in the build set (D6), so a missing import is a
resolve error at the `use` node, never a file probe.

`(f64-bits v)` exists because the emitter writes every float constant as an LLVM
hex literal, and a hex literal is the value's bits. Python today renders `:f64`
through `repr()` and `:f32` through its single-precision bits, which puts a
shortest-round-trip float printer in the path of parity. W0 changes Python to emit
hex for every float, so both compilers only ever format an integer.


`(run prog args)` details: `prog` is a `:str`, `args` is a `(vec :str)` that may be
empty. The vec is moved, so the caller passes a name. The move is a release: the form
copies each element into a NUL-terminated C string, frees the descriptor's buffer and
keeps the C strings for the process lifetime, so the caller must not free it and it never
appears in the leak report; `(args)` returns an ordinary tracked vector the caller frees,
while the `:run` handle, its `out` and `err` buffers are process-lifetime and untracked.
The call uses no shell:
arguments are handed to `execve` one by one, so a path with a space is safe. It
returns an opaque `:run` handle, a process-lifetime value in the shape `:thread` and
`:mutex` already have; its status, stdout and stderr are read by `(run-status r)`,
`(run-out r)` and `(run-err r)`, where the status is the exit code or `128 + signal`.
A spawn failure panics `R0006` with the program name, which is the clean "clang not
found" message.

`(ref T)` details:

- Allowed only as a parameter type of a function or an `extern` free form.
- The argument must be a mutable binding (`letmut`) or a mutable parameter.
- Every container form accepts a ref target: `vec-push`, `vec-set`, `vec-get`,
  `vec-len`, `vec-free`. A ref is a pointer to the descriptor, loaded on use.
- Passing by ref does not move the argument, and the caller can use it afterwards.
- A ref cannot escape: it cannot be returned, stored in a field, pushed into a
  container, placed in an enum payload, captured by a closure, or passed where a
  `(ref T)` is not expected. One predicate, checked at every storage site.
- Two new codes: `E0xxx` for a non-mutable ref argument, `E0xxx` for a ref that
  escapes. The plan assigns the numbers from the current table.

Rejected alternatives, with the reason:

- **One giant file, no ref needed.** A 20k-line single file is the wrong shape for
  the reader this language serves, and it removes every helper boundary.
- **Arena handles in the C runtime.** The tables move to C and the "written in
  Logos" claim gets thin.
- **Threading containers through return values.** A function returns one value,
  and a struct cannot hold a vector, so the pair cannot be returned.

### D6. Multi-file source, one `.ll`

The Python compiler today builds exactly one file, and refuses a call into an
imported module at lowering time. The port cannot live in one file, so the Python
compiler learns `build a.logos b.logos` first: parse each module, resolve each with
its imports visible, lower all of them into one module, emit one `.ll`. Paths stay
per file, so `a/main/2` and `b/main/2` remain distinct.

This lands in Python, per D4, and the Logos compiler inherits the rule.

Three rules make the merged module well defined, and all three land in W0:

- **`use` resolves against the build set, then the asking file, then the standard
  library.** A module named on the command line satisfies `use`; otherwise the
  loader tries `<asking dir>/<name>.logos` and then `<repo>/src/std/<name>.logos`.
  Those two directories are the whole search path: no configuration file, no
  environment variable, no caller directory. Hidden lookup is still an anti-goal,
  and the pair is fixed, so the stdlib is the only place that is not the source's
  own directory. A `use` that names no module in any of the three is `E0005` at
  the `use` node.
- **Every emitted name is module-qualified.** Functions are already
  `lg.<module>.<name>`; struct types become `%struct.<module>.<name>`, not
  `%struct.<name>`. String constants and temporaries come from one counter for the
  merged unit, not one per module, so `@.str0` cannot appear twice.
- **Exactly one module in a build may define `main`.** A second is a duplicate
  definition, `E0003`, reporting both paths.

A unit of one module keeps bare type names for the types that module declares, so a
self-contained single-file build's IR is unchanged. A type declared in another module
is always qualified with the module that declared it, even when the unit holds one
root, because that name is the only one every module can agree on. A unit of several
modules qualifies every named type the same way. Temporaries (`%t<n>`) are per
function, which LLVM scopes correctly; the names that must be unique across the unit
are globals and generated symbols (`@.str<n>`, `$lambda`, `$spawn`, `$fnvalue`), and
they come from one counter.

A type's emitted spelling therefore depends on the shape of the build: the same own
type, built alone and built beside a sibling, is spelled differently. That cost is
accepted — qualification exists to keep one merged unit well defined — and it means IR
is not reusable between build shapes. A pinned single-module IR file is a snapshot of
one shape and is regenerated deliberately when the format changes.


### D7. The compiler's own data model: arenas and integer handles

Vectors cannot live in structs, and containers move. So the compiler's state is a
small set of local vectors in `main`, passed by `(ref ...)`:

- `(vec node)` one arena for the whole tree; children by first-child and
  next-sibling ids; text by id into `(vec :str)`; path built from ids
- `(vec tok)` tokens with `(kind :i64) (text :str) (line :i64) (col :i64)`
- `(vec entry)` one map shape for every table, where `entry` is
  `(struct (key :str) (val :i64))`
- `(vec :i64)` for free lists and output order

Nothing points. Every reference is an index. This is the only shape the language
allows, and it also makes the tree trivially comparable in tests.

### D8. One map, `:str` to `:i64`, written in Logos

Open addressing, linear probing, load factor 0.7, entries appended to the vec and
probed by index. No generics, no deletion, no ordered iteration. Every named table
uses it: functions, types, variables, diagnostic codes. Values are indexes into
parallel vectors.

The hash is multiply-and-add, not FNV-1a. The language has `shl`, `shr` and `shr-u`
but no integer `and`, `or` or `xor`; `and`/`or`/`not` are `:bool` only. A
multiply-and-add hash needs no new operator, and one new operator would be a
seventh surface item for a hash. `h = h * 1099511628211 + b`, wrapping, then `h % size`
with a power-of-two size.

Deletion is not needed by a compiler, and skipping tombstones removes the hardest
part of the implementation.


### D9. No `free` inside the compiler

Strings are already process-lifetime and untracked. The compiler's vectors are
freed only in `main` before the return, or not at all: the process is one shot.
This is stated as a shortcut in the source, not hidden: `shortcut: the compiler
leaks its own tables, which is fine for a one-shot process; upgrade if `logosc`
ever becomes a server`.

The corpus leak checks still apply to compiled test programs, which are separate
processes.

### D10. Emission writes fragments, so no string builder is needed

The emitter opens the `.ll` once with `rt_create`, writes each fragment with
`write`, and closes. No buffer, no `str-concat` in a loop, no quadratic copy.

Runtime additions, all small and all in `logos/runtime/rt.c`:

- `rt_create(const unsigned char *path, size_t n)` opens a file for writing
- `rt_read_file(const unsigned char *path, size_t n, size_t *out_len)` reads a whole file
- `rt_args(size_t *n)` fills from `/proc/self/cmdline` in a constructor, so the
  emitted `main` signature does not change
- `rt_run(...)` spawns through `posix_spawn`, drains stdout and stderr with one
  `poll` loop so a chatty child cannot deadlock on a full pipe, then `waitpid`.
  It kills the child after 30 s and reports status 124. The timeout is a constant,
  not a parameter: a test that hangs is a bug in the program.

### D11. Diagnostics are data, not concatenation

The Logos compiler holds the same code table and the same message templates as
`diag.py`, and renders the same line: `E0103 p/main/2/1: unknown function 'vec'`.
The negative corpus is the test, unchanged.

### D12. `gen2 test` reproduces the harness contract

`gen2 test` is a port of `tester.py`, not a thinner thing: the same directive
parsing, the same `PASS <category>/<case> -` lines, the same `LEAKS` and `OPTS`
headers, the same exit code, `--only` and `--keep-ir`. It takes explicit paths
(`gen2 test a.logos b.logos`) instead of walking the tree, because the language
cannot list a directory and a directory-walk runtime helper would be a seventh
surface item. `tools/selfhost.sh` passes the file list from `git ls-files`.

`--update-baseline` and reading `tests/summary.txt` are W9: no gate needs them
before the fixed point.

### D13. Staging: nine waves, each a PR

Every wave ends with all five gates green. No wave starts before the previous one
merges. A language wave is done twice, Python then Logos, because the corpus gate
runs on the Python compiler (D4).

| Wave | Content | Its own gate |
|------|---------|--------------|
| W0 | multi-file build, module-qualified names, hex float constants, `use` against the build set, all in Python (D4, D6) | corpus still 63/63, new multi-file case, IR diff of a two-module build |
| W1 | `(ref T)` in Python, then in the language: corpus, escape negatives, both `-O` levels | the full corpus under Python, plus one ref program under `gen2` once it exists |
| W2 | six forms plus the three runtime helpers, Python first (D5, D10) | one corpus case each, negative case for each misuse, manual chapters |
| W3 | the Logos standard library: map, split, args, io | its own tests in `src/std/` |
| W4 | lexer, parser, node arena, paths, `fmt`; `tools/selfhost.sh` and the sixth gate wired in | `gen2 fmt` rewrites all 63 corpus files byte for byte |
| W5 | resolve: names, scopes, duplicates, unused | the negative corpus codes match |
| W6 | types and the checker, in three PRs | the full negative corpus under `gen2` |
| W7 | IR, lowering, emitter | `.ll` identical to Python on every positive corpus file |
| W8 | driver: `build`, `test`, temp files, `-O0`/`-O2` | `gen2 test` matches the Python run, leaks included |
| W9 | `guide --json`, baseline support, the fixed point | gen2 equals gen3 on every source in the repo |

W9 is the definition of done. W4 to W8 are 80% of the work.

### D14. The gate script

`tools/selfhost.sh` exists from W4 and runs as a sixth gate in `tools/pr_gate.sh`
and in CI. Adding it means amending `AGENTS.md`, `.github/workflows/gate.yml` and
the count `tests/test_contributing.py` pins, in the same PR that adds the script.
Before W4 the repo keeps five true gates rather than six with one that skips.

1. build `gen2` with the Python compiler
2. `gen2 test` over the manifest list and compare the pass count and leak total
3. `gen2 build` every positive corpus file and diff its `.ll` against Python's
4. build `gen3` from `src/` with `gen2`; compare every `.ll` between the two
5. run the corpus binaries built by `gen2` and by `gen3` at both levels

The file set is `tools/selfhost-manifest.txt`, written once in W4: every positive
corpus case, `examples/hello.logos`, and every `src/**/*.logos`. Negative cases
carry no `.ll`, so they are compared by diagnostic, not by IR. Manual chapters are
documentation and are not compiled by this gate.

The floor: the script asserts it compiled exactly the manifest's count and diffed
exactly that many `.ll` files, so a pruned tree or a broken glob cannot report PASS
over zero files.


## Layout

```
src/logosc/main.logos      CLI, argv, exit codes
src/logosc/diag.logos      code table, rendering
src/logosc/lex.logos       tokens
src/logosc/parse.logos     tree, paths
src/logosc/resolve.logos   names and scopes
src/logosc/types.logos     type forms and layout
src/logosc/check.logos     the checker
src/logosc/ir.logos        instruction records
src/logosc/lower.logos     tree to IR
src/logosc/emit.logos      IR to LLVM text
src/logosc/fmt.logos       canonical printer
src/logosc/test.logos      directives, run, compare
src/std/map.logos          the one map
src/std/str.logos          split, find, join, byte helpers
src/std/io.logos           file, temp path, run wrapper
```

## Decisions taken after review

A fresh builder read this document and listed the questions it would have to ask.
These are the answers, settled here so the plan cites them instead of relitigating.

| Question it raised | Ruling |
|---|---|
| Where does `use` look for a module? | The build set, then the file's own directory, then `src/std`. No other search path (D6). |
| What disambiguates two modules' `%struct.x` and `@.str0`? | Module-qualified types, one counter for the merged unit, one `main` (D6). |
| How are float constants spelled? | Hex, from the bits, in Python first; `(f64-bits)` added (D5). |
| FNV-1a needs XOR, which the language lacks | Multiply-and-add hash, no new operator (D8). |
| Do W1 and W2 include the Python side? | Yes, every language wave is Python first, then Logos (D13). |
| What is `gen2 test`'s contract? | Full harness parity, explicit paths, baseline in W9 (D12). |
| How does `gen2 test` find the corpus with no arguments? | It does not: the gate passes the list (D12). |
| How does a missing file become a clean error? | `read-file` panics `R0007`, naming the path it could not open; a missing module is `E0005` at `use` (D5). |
| Is the selfhost check a sixth gate? | Yes, from W4, with `AGENTS.md`, CI and the pinned count amended in that PR (D14). |
| What does the gate compile, and what does its floor assert? | A frozen manifest of positive corpus files plus `src/`, counted exactly (D14). |

## What is left to the builder

- The exact node and token record fields, and their order.
- The two new `E0xxx` numbers and the `R000x` numbers, taken from the current table
  without reusing a code that already means something else.
- The parser's error recovery policy: today the Python parser stops at the first
  error. Matching it is required, so this is not open, only to be found.
- How `fmt` handles a file the checker rejects. Python's answer is the one to copy.
- The wave boundaries inside W6 and W7, where the checker and the emitter are big
  enough to split differently.


## Risks

- **Parity is a clone, not a design.** Every quirk of the Python emitter becomes a
  requirement. This is the price of D3 and it was chosen deliberately.
- **Doing the checker twice.** 5,199 Python lines become 7k to 9k Logos lines, and
  the corpus will find every disagreement. Budget for a long fix wave after W7.
- **The ref feature leaks into the language.** Once `(ref T)` exists, programs want
  it everywhere. The escape rules are the whole safety story, and they need the
  probe set from the language skill, not one example.
- **Compile time.** A self-compiling compiler is built three times in the gate.
  Measure it at W7; if the gate takes minutes, it belongs in CI only.
- **Byte-identical IR under a real module.** The Python compiler has never emitted
  one `.ll` for eight modules. D6 says it will, and W0 measures it.
