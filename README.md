# Logos

Logos is a prefix-form language built for AI readers, with `logosc`, a compiler
that turns Logos source into native x86_64 Linux binaries.

The design goal is that a model can read and write the language without
guessing. There is no implicit conversion, no hidden allocation, no hidden
global state and no silent error swallowing. A call that allocates shows it. A
call that can fail declares it. Release is manual through `free`.

The compiler is written in Logos. `src/logosc/` is the whole of it: lexer,
parser, resolver, checker, lowering and emitter, each module paired with a
`.md` beside it that carries its contract. The compiler lowers a typed syntax
tree to a small flat IR, prints it as LLVM IR text, and `clang` compiles that
text and links it against the C runtime in `logos/runtime/`.

It is self-hosting. `bootstrap/logosc` is a stage-0 binary whose only job is to
build the compiler from `src/`; the result builds itself again, and the two
binaries are byte-identical. No Python is involved in building anything: the
compiler is the only compiler here.

## Learn it

Start with `docs/LOGOS.md`: one dense reference, cheat sheet first, then one
complete executable chapter per feature in learning order. It is generated from
the compiler's own tables and every example is run by the test harness at `-O0`
and `-O2`, so it cannot drift from the implementation.

- `docs/LOGOS.md` — the manual, generated; do not edit it by hand.
- `docs/CLI.md` — the tool contract: verbs, flags, streams, exit codes, and
  the JSON documents an agent may depend on.
- `logosc guide --json` — the machine-readable manifest: forms, types,
  operators, builtins, reserved names, diagnostic codes and test categories,
  at `schema_version` 1.
- `logosc guide --check` — proves the committed manual is current; exits 1 with
  a diff summary when it is stale.
- `docs/manual/` — the numbered chapter sources the manual embeds.
- `docs/schemas/` — the published JSON schemas for `--json` output.

Regenerate after changing the compiler with `logosc guide > docs/LOGOS.md`.

## Status

Logos v1 is complete for one target: x86_64 Linux. The language, the compiler
and the test harness are built, reviewed, and green.

Verified by execution on this machine:

- `./tools/logosc.sh test tests` runs 309 cases across eight categories at
  `-O0` and `-O2` and compares the two optimisation levels with each other, not
  only with the expected output. 0 failures, 10 deliberate leaks, 0 baseline
  regressions.
- The compiler's own suites run through the same binary: 361 `body_test` cases,
  81 `check_test` cases and 38 `resolve_test` cases, each at both levels.
- `bash tools/accept.sh` runs seven sections and all pass: the harness, a
  differential oracle against gcc, three example programs whose output matches
  `wc`, `jq` and a C reference byte for byte, formatter idempotency over every
  `.logos` file, and a compile-speed floor.
- 47 contract tests pass: the gate list, the C runtime, the self-hosting
  summary, and the CLI contract (`tests/test_cli.py`: exit codes, per-verb
  help, JSON diagnostics for every failing phase, and compiling from a
  directory outside the checkout). The suites that diffed the compiler against
  the Python implementation went with it.
- `bash tools/selfhost.sh` proves the fixed point: the stage-0 binary builds
  `gen2` from `src/`, `gen2` builds `gen3`, the two binaries are identical, and
  their IR agrees on the compiler's own source.

The language has: integers, floats, booleans and strings; structs with C
layout; fixed arrays and growable vectors; enums with payloads; results and
optionals with `try`; generics by monomorphisation; closures confined to their
frame; manual memory with move checking and a leak tracker; threads, mutexes,
channels and atomics over pthreads; `extern` declarations for the C ABI; and
node-addressed tooling (`show`, `fmt`) that treats one subtree as one
editable unit.

### What it refuses, on purpose

These are not gaps. Each one exists because the alternative was a program that
reads freed memory, uses an uninitialised value, or behaves differently at
`-O2` than at `-O0`:

- a vector, an owner, or any type containing one is never copied; binding it
  moves it, and a second use is E0300 or E0402;
- a value cannot be read out of a place (a vector element, an array element, a
  struct field, a dereference) when its type owns memory;
- an owner may not be stored in a struct, an array, an enum payload or another
  owner, so aggregate copies can never duplicate one;
- a binding declared outside a loop may not be moved or freed inside it,
  condition included;
- a capturing closure may not cross a call boundary; its environment lives in
  the creating frame;
- `alloc` refuses any type with an invariant (a vector, a result, an optional,
  a function value, a string, an enum tag), so nothing uninitialised is ever
  read as a typed value;
- a result that is never handled is an error, and `try` requires the exact
  error type;
- shared state must be marked `(shared T)` before it can reach another thread,
  and the marker is checked through aggregates;
- a form the checker accepts but the backend cannot emit is a bug; the backend
  never fails silently at run time.

### Known limits

- One target: x86_64 Linux. The target triple is a flag, but arm64 and Darwin
  have not been built or tested. `bootstrap/logosc` is an x86_64 Linux binary,
  so another platform needs a stage-0 built where the compiler already runs.
- Release builds do not quarantine freed blocks, so `R0002` in a release build
  is defence in depth. A stale double free cannot be constructed from Logos
  source, because the ownership rules above refuse it.
- A `:str` owns nothing: concatenation allocates a buffer that lives until the
  process exits, and it does not appear in the leak report.
- A mutex held by a thread that exited stays locked; an unjoined thread's
  allocations may or may not appear in the leak report.
- `examples/wc.logos` matches GNU `wc` through a pipe, which pads to seven
  columns; a regular-file redirect uses a different width.
- Float literals are converted by libc `strtod`, the same correctly rounded
  conversion Python's `float()` uses; a non-conforming `strtod` would shift the
  bits. A literal with no finite value in its type — `1e999` for `:f64`,
  `3.5e38` for `:f32` — is refused with `E0106`, not emitted as `inf`. The
  decision is a decimal digit-string comparison against the type's maximum
  (`17976931348623157` for `:f64`, `34028234` for `:f32`), so a literal within
  one ulp of the maximum is refused too.

## Requirements

- Ubuntu 22.04, x86_64
- clang 14 and lld: `apt-get install -y clang lld` (`lld` is unused so far;
  clang links through the system linker)
- gcc 11 and jq 1.6 for `tools/accept.sh`: gcc builds the differential oracle's
  C twins, jq is the JSON example's reference
- GNU make
- Python 3.10 or newer, for the contract tests only — no gate runs a compiler
  written in Python

## Usage

```sh
./tools/logosc.sh version                      # logos 0.1.0
./tools/logosc.sh version --json               # {"schema_version":1,...}
./tools/logosc.sh build examples/hello.logos   # build/hello, and build/hello.ll
./build/hello                                  # hello
./tools/logosc.sh build bad.logos --json       # diagnostics as JSON on stderr
./tools/logosc.sh build -h                     # that verb's flags, exit 0
./tools/logosc.sh guide                        # the generated manual
./tools/logosc.sh guide --json                 # the machine-readable manifest
./tools/logosc.sh guide --check                # fail if docs/LOGOS.md is stale
./tools/logosc.sh test tests                   # run the directive-driven corpus
./tools/logosc.sh test tests --only exec --opt -O0   # one category, one level
bash tools/accept.sh                           # corpus, gcc oracle, examples, fmt
```

`tools/logosc.sh` is a thin wrapper: it checks `bootstrap/logosc` against its
recorded SHA-256, rebuilds `build/logosc` from `src/` whenever the source is
newer, and runs that. Use it, not the bootstrap binary, whenever you are
testing a change to the compiler.

`logosc test` reads the `(expect ...)` directive in each `(test ...)` node and
the module-level `(expect-error E0xxx)` of a negative case, runs every case at
`-O0` and `-O2`, and writes to `tests/summary.txt` with `--update-baseline`.
The baseline records the optimisation levels it ran (`OPTS -O0 -O2`), one line
per case and the suite's leak total; a case that passed in the baseline and
fails now is a regression and exits 1, as is a full run that leaks more than
the baseline recorded at the same levels. A baseline that has no `OPTS` line
cannot be compared and is refused with a request to regenerate it, rather than
silently leaving the leak total ungated. `--update-baseline` with `--only`
merges: it rewrites the cases it ran, drops the ones the category no longer
contains, and keeps the rest. A `.logos` file outside the known categories
(`parse`, `type`, `exec`, `mem`, `thread`, `generics`, `regress`, `diff`) is
reported and fails the run rather than being skipped.

`tools/accept.sh` is the end-to-end gate: the corpus, `tests/diff/run_diff.sh`
(Logos against gcc at `-O0` and `-O2`, floored by `tests/diff/manifest.txt`),
the three example programs against `wc`, `jq` and a C reference build,
`logosc fmt` idempotency over every `.logos` file in the tree, and a generated
200-function program with structs, a generic and a thread that must compile in
under five seconds. A section that examined zero items is a failure, and the
script exits 0 only when all seven sections print PASS.

The IR is always kept beside the binary under `build/`: it is the artefact to
read when a compiled program misbehaves.

## Examples

| Program | What it does | Reference |
| --- | --- | --- |
| `examples/wc.logos` | counts lines, words and bytes from standard input | `wc -c -w -l` |
| `examples/json.logos` | parses JSON and prints a structural summary | `jq` |
| `examples/matrix.logos` | multiplies two 200x200 matrices on four threads | `examples/matrix_ref.c` |

`wc` reads through `(read-all)` and prints GNU wc's three seven-wide columns in
GNU's order: lines, words, bytes. It splits words on the same set GNU does:
ASCII space and the C-locale controls, then the UTF-8 space separators
(U+00A0, U+1680, U+2000 to U+200A, U+202F, U+205F, U+3000); U+2028 and U+2029
are line and paragraph separators, not spaces, and GNU wc does not split there
either. `json` is a recursive-descent parser over `(res :i64 json-error)` that
validates every value, including string escapes and number grammar, counts
objects, arrays, members, scalars and nesting depth, and resolves duplicate
keys the way jq does (the last member wins). `matrix` fills two matrices from a
fixed integer pattern, hands each of four threads fifty rows through
`(shared (ptr :i64))`, and prints a checksum, a weighted checksum, the centre
cell and the last cell. `examples/sample.json` is the JSON fixture the
acceptance script feeds to both the program and jq; `examples/inputs/` holds
the Unicode word-separator inputs and the duplicate-key and malformed JSON
documents the script also compares.

## Development

```sh
make test    # 24 contract tests, then the compiler's own suites at -O0 and -O2
make fmt     # ./tools/logosc.sh fmt .
make clean   # remove build output and caches
```

After changing `src/logosc/`, rebuild the stage-0 binary in the same commit:

```sh
./tools/logosc.sh version
cp build/logosc bootstrap/logosc
( cd bootstrap && sha256sum logosc > logosc.sha256 )
```

## Contribute

Read `AGENTS.md` first if you are an AI agent, or `CONTRIBUTING.md` if you are a
person; `tools/pr_gate.sh` runs every gate a pull request must pass. The
repository accepts pull requests from humans and from AI agents acting through
their operator's account. Every commit must carry a `Signed-off-by` trailer that
matches its author: `tools/pr_gate.sh` checks that first, and stops before any
gate if it fails.

## Layout

| Path | Purpose |
| --- | --- |
| `src/logosc/` | The compiler, in Logos, one module per file with its `.md` beside it |
| `src/std/` | The standard library, in Logos |
| `bootstrap/logosc` | Stage-0 binary that builds the compiler; its SHA-256 is recorded |
| `logos/runtime/rt.h` | Declarations of the C runtime reached through `extern` |
| `logos/runtime/rt.c` | C runtime implementation, linked into every binary |
| `examples/` | Three real programs, their input fixture and the matrix reference |
| `docs/LOGOS.md` | The generated manual: cheat sheet, executable chapters, reference tables |
| `docs/manual/` | The numbered chapter sources the manual embeds |
| `tests/` | The directive corpus and the contract tests |
| `tests/diff/` | Programs with hand-written C twins, compared against gcc |
| `tools/accept.sh` | The end-to-end acceptance gate |
| `tools/logosc.sh` | Builds the compiler from source and runs it |
| `docs/superpowers/` | Design spec and implementation plan |

## License

MIT. See `LICENSE`. By opening a pull request you agree to license your
contribution under these terms.

Not chosen yet.
