# Logos

**Code an agent can read, write, and prove.**

Logos is a small compiled language for software an agent writes and a human
still has to trust. Allocation, fallible calls and release are visible in the
source; the compiler refuses the rest. A failure arrives as a code and a node
path, programs carry their own expectations, and the same source builds the same
bytes. MIT, two targets, pre-1.0.

- **Install it and compile something** — five commands below, every output
  pasted from a real run; the long form is
  [`docs/quickstart.md`](docs/quickstart.md).
- **Build something with it** — the
  [Logos Agent Challenge](docs/challenge/01-summary/program.md): three tracks —
  build a program, land a pull request, or port/teach — opening 2026-12-01, no
  prizes but a showcase page and a co-authored commit.
- **Point an agent at it** — [`llms.txt`](llms.txt) is the one-file index,
  [`AGENTS.md`](AGENTS.md) is the contributor contract, and
  [`docs/reference/agent-contract.md`](docs/reference/agent-contract.md) is the
  consumer contract: exit codes, JSON shapes, determinism, traps.
- **Everything else** — [`docs/00-index.md`](docs/00-index.md).

## Quickstart

The consumer path, on x86_64 Linux with `clang` 14 or newer — no checkout, no
Python:

```sh
gh release download v0.2.1 --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
sha256sum -c SHA256SUMS
tar -xzf logos-0.2.1-x86_64-linux.tar.gz && cd logos-0.2.1-x86_64-linux
cat > hello.logos <<'EOF'
(mod hello)

(fn main :void ()
  (println "hello from logos"))
EOF
./bin/logosc build hello.logos -o hello && ./hello     # hello from logos
```

```
SHA256SUMS: OK
hello from logos
```

Or work from a checkout — the compiler's own source, and the route to changing
it:

```sh
git clone https://github.com/abaddon/logos && cd logos
./tools/logosc.sh version                     # logos 0.2.1; builds the compiler on first use (~50 s)
./tools/logosc.sh build examples/hello.logos  # writes build/hello.ll and build/hello
./build/hello                                 # hello
```

The program to copy when starting something new is
[`examples/agent-gate/`](examples/agent-gate/README.md): one 174-line file, nine
`(test …)` nodes, and the rough edges its author hit. The full path — both
routes, the error case, the cheap `check` loop, the corpus and the manifest — is
[`docs/quickstart.md`](docs/quickstart.md), with every command and output copied
from a real run (transcripts:
[`docs/distribution/03-dossiers/verification-log-2026-11-18.md`](docs/distribution/03-dossiers/verification-log-2026-11-18.md)).

## Status

**v0.2.1 is the current release** — 0.2.0 was the first published one. Obtain it
from the releases page or with `gh release download`
([`docs/install.md`](docs/install.md)); what it contains is
[`CHANGELOG.md`](CHANGELOG.md). It is **pre-1.0**: five of the
eighteen v1 acceptance criteria are still open, each listed under
[Known limits](#known-limits), where they are tracked rather than implied.

What is proven on every pull request, measured by the gate rather than asserted
(evidence: [`docs/qa/`](docs/qa/00-index.md)):

- **The six documented gates pass**: the contract tests and all ten compiler
  suites; the corpus at `-O0` and `-O2` compared against each other, not only
  against expected output; `tools/accept.sh` (the gcc differential oracle, the
  example programs against `wc`, `jq` and a C reference, formatter idempotency
  and a compile-speed floor); the generated manual's drift check; formatting;
  and self-hosting.
- **Self-hosting is measured, not claimed.** The stage-0 builds `gen2` from
  `src/`, `gen2` builds `gen3`, the two binaries are byte-identical, and
  `gen2`'s `fmt` reproduces every tracked `.logos` file byte for byte. The gate
  also requires the stage-0 to be *what this source produces*, so a stale
  bootstrap fails by name.
- **Every negative fixture is judged by the compiler** (`tests/test_qa.py`,
  inside `make test`): each `*.expect` sidecar is built through `build --json`
  and compared with the code the compiler actually emits, published-code
  coverage and corpus floors are enforced, and repeated runs must agree.
- **The artifact is reproducible.** `tools/dist.sh` fixes file order,
  ownership, mtime and the gzip header; the release workflow rebuilds the
  tarball on a second runner and requires the two SHA-256 sums to be equal.
- **A failure is machine-readable**: `--json` gives an agent a stable `code`
  and a `node_path` it can hand back to `logosc show`.

Not done, and why this is 0.2.x rather than 1.0.0:

- **Names are global** across a whole program: two modules cannot both declare
  `point`. The design for module-qualified names exists; the change does not.
- **`logosc test` prints text only** — no `test --json`, so an agent gating a
  pull request cannot read per-case results as data.
- **No `logosc doctor`** (an install self-check) and **no `patch` verb**.
- **The standard library is 21 functions**: no `str` → integer parsing, and
  `map` is `:str` keys with `:i64` values only.
- **Two targets**: x86_64 Linux by default, arm64 Linux with
  `--target aarch64-unknown-linux-gnu`, which needs the aarch64 cross
  toolchain. clang is still required at build time of every program.

Read the status as: *you can hand a compiler to somebody else today, and you
can see exactly which corners are unfinished.*

## Requirements

| Need | For |
|---|---|
| x86_64 Linux (verified: Ubuntu 22.04) | where the compiler runs and the default target; arm64 output needs `gcc-aarch64-linux-gnu` and `libc6-dev-arm64-cross`, and running it needs `qemu-user-static` |
| glibc 2.35 or newer | the shipped binary is dynamically linked against it |
| clang 14 or newer | compiles the IR and links every binary — at build time of **every program**, not only of the compiler; `apt-get install -y clang-14 lld-14` |
| GNU make | the `make test` / `make suites-all` targets |
| gcc 11 and jq 1.6 | only for `tools/accept.sh`: gcc builds its C reference programs, jq is the JSON example's oracle |
| Python 3.10 or newer | only for the contract tests; no gate runs a compiler written in Python |

An installed compiler needs none of the checkout: the tarball ships the runtime
and the standard library beside `bin/logosc`, and Python is not required at all.

## Using it

Eight verbs. The reference is [`docs/reference/cli.md`](docs/reference/cli.md);
these are the ones you will use:

```sh
./tools/logosc.sh version                      # logos 0.2.1
./tools/logosc.sh build examples/hello.logos   # build/hello, and build/hello.ll
./build/hello                                  # hello
./tools/logosc.sh check FILE                   # the cheap validation call (hidden verb)
./tools/logosc.sh show FILE PATH               # print one node, e.g. hello/main/2
./tools/logosc.sh test FILE                    # build and run its (test ...) nodes
./tools/logosc.sh test tests --only regress    # the fast corpus subset
./tools/logosc.sh guide                        # the generated manual
./tools/logosc.sh guide --json                 # the machine-readable manifest
./tools/logosc.sh guide --check                # fail if docs/LOGOS.md is stale
bash tools/accept.sh                           # corpus, gcc oracle, examples, fmt
```

Two things to know before scripting against it:

- **Exit codes are three, not two.** `0` success · `2` the source or the command
  line is wrong · `1` the environment is wrong (missing file, missing runtime,
  clang failure). The table is in [`docs/reference/cli.md`](docs/reference/cli.md#global-behaviour).
- **There is no per-verb `-h`.** `logosc -h` is an invalid choice, exit 2. Read
  the reference.

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
the baseline recorded at the same levels. A baseline with no `OPTS` line cannot
be compared and is refused rather than silently leaving the leak total ungated.
`--update-baseline` with `--only` merges. A `.logos` file outside the known
categories (`parse`, `type`, `exec`, `mem`, `thread`, `generics`, `regress`,
`diff`) is reported and fails the run rather than being skipped.

`tools/accept.sh` is the end-to-end gate: the corpus, `tests/diff/run_diff.sh`
(Logos against gcc at `-O0` and `-O2`, floored by `tests/diff/manifest.txt`),
the three example programs against `wc`, `jq` and a C reference build,
`logosc fmt` idempotency over every `.logos` file in the tree, and a generated
200-function program with structs, a generic and a thread that must compile in
under five seconds. A section that examined zero items is a failure, and the
script exits 0 only when all seven sections print PASS.

The IR is always kept beside the binary under `build/`: it is the artefact to
read when a compiled program misbehaves.

## Learn it

- [`docs/LOGOS.md`](docs/LOGOS.md) — the generated manual: a cheat sheet, then
  one complete executable chapter per feature in learning order, then the
  reference tables. Every example is run by the test harness at `-O0` and
  `-O2`, so it cannot drift from the implementation. **Do not edit it by hand.**
- [`docs/reference/language.md`](docs/reference/language.md) — the same language
  as a one-page decision reference: the model, the ten rules with the code each
  one raises, a verified idiom per feature, and what v1 refuses.
- `logosc guide --json` — the machine-readable manifest: forms, types,
  operators, builtins, reserved names, diagnostic codes and test categories.
- [`docs/reference/stdlib.md`](docs/reference/stdlib.md) — all 21 library
  functions with signatures and ownership rules.
- [`docs/reference/limits.md`](docs/reference/limits.md) — every known limit in
  one place, including the ones this README only summarises.

The language has: integers, floats, booleans and strings; structs with C
layout; fixed arrays and growable vectors; enums with payloads; results and
optionals with `try`; generics by monomorphisation; closures confined to their
frame; manual memory with move checking and a leak tracker; threads, mutexes,
channels and atomics over pthreads; `extern` declarations for the C ABI; and
node-addressed tooling (`show`, `fmt`) that treats one subtree as one editable
unit.

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
  never fails silently at run time;
- a binding nobody reads is `E0107` — an error, not a warning.

### Known limits

A summary; the full list is
[`docs/reference/limits.md`](docs/reference/limits.md).

- Default target x86_64 Linux; `--target aarch64-unknown-linux-gnu` emits arm64
  Linux ELFs (needs the aarch64 cross toolchain) and `test --target` runs the
  corpus under qemu. Darwin is not built. `bootstrap/logosc` is an x86_64 Linux
  binary, so another host needs a stage-0 built where the compiler already runs.
- Names are global across a whole program: two modules cannot both declare the
  same name.
- `logosc test` prints text only; there is no `test --json`.
- There are no comments in the language, and no doc form.
- Release builds do not quarantine freed blocks, so `R0002` in a release build
  is defence in depth. A stale double free cannot be constructed from Logos
  source, because the ownership rules above refuse it.
- A `:str` owns nothing: concatenation allocates a buffer that lives until the
  process exits, and it does not appear in the leak report.
- A mutex held by a thread that exited stays locked; an unjoined thread's
  allocations may or may not appear in the leak report.
- `(run …)` gives its child a fixed 90-second budget and reports status 124 on
  timeout.
- `examples/wc.logos` matches GNU `wc` through a pipe, which pads to seven
  columns; a regular-file redirect uses a different width.
- Float literals are converted by libc `strtod`, the same correctly rounded
  conversion Python's `float()` uses; a non-conforming `strtod` would shift the
  bits. A literal with no finite value in its type — `1e999` for `:f64`,
  `3.5e38` for `:f32` — is refused with `E0106`. The check compares decimal
  digit strings against the type's maximum, so a literal within one ulp of the
  maximum is refused too: the safe direction.

## Examples

| Program | What it does | Reference |
| --- | --- | --- |
| `examples/wc.logos` | counts lines, words and bytes from standard input | `wc -c -w -l` |
| `examples/json.logos` | parses JSON and prints a structural summary | `jq` |
| `examples/matrix.logos` | multiplies two 200x200 matrices on four threads | `examples/matrix_ref.c` |

The directory to copy when starting something new is
[`examples/agent-gate/`](examples/agent-gate/README.md): one 174-line program, a
policy gate for an agent's tool calls, with a quickstart, nine `(test …)` nodes
that check it, and a list of the rough edges found while writing it. The three
programs above are the ones the acceptance gate compares against an independent
implementation.

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

## Build something with it

Write the program you were going to write in Python as one Logos file, with a
`(test name (expect (out "…") (code 0) (leaks 0)) …)` node that states the
output you expect. `logosc test` runs it at `-O0` and `-O2`: if it fails you have
a code and a node path, and if it compiles you have a native binary with nothing
to install at run time.

- **Fork a working program.** [`examples/agent-gate/`](examples/agent-gate/README.md)
  is a policy gate for an agent's tool calls in 174 lines, with nine tests, a
  measured transcript, and a list of the rough edges it hit. Its "Remix this"
  section names three extensions that fit in an afternoon.
- **Enter the [Logos Agent Challenge](docs/challenge/01-summary/program.md)** —
  three tracks: build a program, land a pull request, or port and teach. Round 1
  opens 2026-12-01; the awards are a showcase page and a co-authored commit, not
  money.
- **Fix the compiler.** [`docs/reference/limits.md`](docs/reference/limits.md) is
  the honest list of what is missing, and [`AGENTS.md`](AGENTS.md) is the route
  in: a regress case that fails first, then the fix.

## Done means these six commands pass

Run them from the repository root, in this order:

```sh
make test
./tools/logosc.sh test tests
bash tools/accept.sh
./tools/logosc.sh guide --check
./tools/logosc.sh fmt $(git diff --name-only main...HEAD -- '*.logos')
bash tools/selfhost.sh
```

`bash tools/pr_gate.sh` runs exactly this list, prints PASS or FAIL for each
gate, and exits non-zero if any failed. Every commit must carry a `Signed-off-by`
trailer matching its author; the gate list checks that first and stops if it
fails. Do not weaken a gate, skip one, or change its expected result to make a
change pass. The full contract, the invariants and the bootstrap rule are in
[`AGENTS.md`](AGENTS.md).

## Development

```sh
make test          # the contract tests, then all nine compiler suites at -O0
make suites-all    # the same suites at -O0 and -O2 (not run by the gate: ~90 min)
make fmt           # ./tools/logosc.sh fmt .
make clean         # remove build output and caches
```

After changing `src/logosc/`, rebuild the stage-0 binary in the same commit:

```sh
./tools/logosc.sh version
cp build/logosc bootstrap/logosc
( cd bootstrap && sha256sum logosc > logosc.sha256 )
```

## Contribute

Read [`AGENTS.md`](AGENTS.md) first if you are an AI agent, or
[`CONTRIBUTING.md`](CONTRIBUTING.md) if you are a person; `tools/pr_gate.sh`
runs every gate a pull request must pass. The repository accepts pull requests
from humans and from AI agents acting through their operator's account. Every
commit must carry a `Signed-off-by` trailer that matches its author.

## Layout

| Path | Purpose |
| --- | --- |
| `src/logosc/` | The compiler, in Logos, one module per file with its `.md` beside it |
| `src/std/` | The standard library, in Logos: `io`, `str`, `map` |
| `bootstrap/logosc` | Stage-0 binary that builds the compiler; its SHA-256 is recorded |
| `logos/runtime/rt.h` | Declarations of the C runtime reached through `extern` |
| `logos/runtime/rt.c` | C runtime implementation, linked into every binary |
| `examples/` | Three oracle-matched programs, the reference project to fork (`agent-gate/`) and their input fixtures |
| `docs/00-index.md` | **The documentation index — start here** |
| `docs/quickstart.md` | Checkout → running binary, verified end to end |
| `docs/reference/` | CLI, diagnostics, language, stdlib and limits references |
| `docs/LOGOS.md` | The generated manual: cheat sheet, executable chapters, reference tables |
| `docs/manual/` | The numbered chapter sources the manual embeds |
| `docs/01-summary/` | The v1 audit: gap register, findings, 18 acceptance criteria |
| `docs/history/build-ledger.md` | The rulings behind the design, in order |
| `tests/` | The directive corpus and the contract tests |
| `tests/diff/` | Programs with hand-written C twins, compared against gcc |
| `tools/accept.sh` | The end-to-end acceptance gate |
| `tools/logosc.sh` | Builds the compiler from source and runs it |
| `docs/superpowers/` | Design specs and implementation plans |

## License

MIT. See [`LICENSE`](LICENSE). By opening a pull request you agree to license
your contribution under these terms.
