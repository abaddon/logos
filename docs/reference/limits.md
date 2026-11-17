# Known limits

One page: everything a consumer must know before trusting `logosc` with real
work. None of these is a bug report — each is a deliberate boundary or a
documented gap, and each names what happens when you hit it.

The release criterion is that this page exists and is linked from `README.md`
and `AGENTS.md` (V1-16 in
[`../01-summary/v1-acceptance-criteria.md`](../01-summary/v1-acceptance-criteria.md)).
Gaps are cited from [`../01-summary/gap-register.md`](../01-summary/gap-register.md).

## Reach

| Limit | What you get | Gap |
|---|---|---|
| **One artifact: an x86_64 Linux tarball.** No package manager, no container image | unpack the tarball (`install.md`), or clone and use `./tools/logosc.sh` | D1, D7 |
| A compiled program needs `clang` at **build** time — `logosc` shells out for every binary | `logos: clang failed: …` when it is missing | — |
| The artifact is built by one recorded toolchain (clang 14, `ld` 2.38, Ubuntu 22.04) | the bootstrap byte-identity claim is only measurable there; `tools/toolchain.sh` says so before an hour-long gate | — |

## Platform

| Limit | Why |
|---|---|
| **Two targets, one compiler.** x86_64 Linux (default) and arm64 Linux via `build --target aarch64-unknown-linux-gnu`; Darwin is not built. `bootstrap/logosc` is an x86_64 Linux ELF, so another host needs a stage-0 built where the compiler already runs | the triple is a flag and the runtime is compiled for it in the same clang invocation; the arm64 path needs the aarch64 cross toolchain, and is run under qemu in `tools/accept.sh` |
| **arm64 runs under qemu here, and qemu's `posix_spawn` is not glibc's.** `test --target aarch64-unknown-linux-gnu exec/run/an-unstartable-program-panics` fails | starting a path that does not exist returns `rc=0` and a child that exits 127, where glibc reports the exec failure as `rc=2`, so the case's `R0006` assertion cannot hold under emulation. The case passes natively and as a static x86_64 build, so static linking is not the cause. It is neither skipped nor weakened: `tools/accept.sh` section 8 runs the `regress` category, not `exec`, and the difference is the emulator's, not the compiler's |
| Built and verified on Ubuntu 22.04 with clang 14, gcc 11, jq 1.6 | `tools/accept.sh` uses gcc and jq as differential oracles; the glibc floor is 2.35 |

## The language

| Limit | What happens | Gap |
|---|---|---|
| **No comments, no doc form.** Intent lives in a sibling `.md` | a `;` or `//` is not a comment: `E0001: form outside parentheses`, or a parse error | A7 |
| **Names are global across the whole program.** Two modules may not both declare `point` | `E0003: duplicate definition 'point'` | A1 |
| Imports are **not transitive**: a module sees only the modules it names | call a name from a module you did not `(use …)`: `E0103: unknown function` | A5 |
| No `patch` verb. `show` is read-only | node-addressed *writing* means rewriting the file and running `fmt` | A2 |
| A float literal with no finite value is **accepted** and becomes `inf` | `(println 1e999)` compiles and prints `inf`, where an out-of-range *integer* is `E0106` | A3 |
| **`E0107 unused binding` is an error** | a binding nobody reads fails the build; do not leave debug bindings behind | — |
| `(atomic :i64 n)` only; `map` values are `:i64`, keys `:str` | no 32-bit atomics, no generic map | A4 |
| 21 standard-library functions: no string→int parse, no sort, no formatting, no `unlink`/`stat`/`getenv` | you write them, in Logos | A4 |
| No `str` ordering comparison | `(< "a" "b")` is `E0100: '<' needs numbers, found :str`; `=` and `!=` work | — |

## Memory and threads

| Limit | What happens |
|---|---|
| A `:str` owns nothing. Concatenation allocates a buffer that lives until the process exits | string building never appears in the leak report, and never frees |
| Release builds do not quarantine freed blocks | `R0002 double free` is defence in depth: the ownership rules refuse the programs that could produce it, so this is not reachable from source |
| A mutex held by a thread that exited **stays locked**; the next `lock` blocks forever | `logos/runtime/rt.h`. Relocking from the holding thread is caught: `R0005: could not lock a mutex` |
| An unjoined thread's allocations may or may not appear in the leak report | its handle is allocated, so a thread that is never joined leaks the handle too |
| No data-race detection | `(shared T)` is checked at compile time and the marker is propagated through aggregates; the runtime does not watch accesses |
| `(run prog args)` bounds the child at **90 seconds**; a timeout reports status `124` | the runtime's fixed budget, not a parameter |

## Tooling

| Limit | What happens |
|---|---|
| `fmt` walks `*.logos` names only; a *directory* named `x.logos` is descended rather than read | no general glob; `fmt` is not a project rewriter |
| Baseline lines percent-decode case ids only for printable ASCII plus tab/CR/LF; any other byte keeps its `%XX` spelling | an exotic case name prints encoded; comparisons are unaffected |
| `--keep-ir` is accepted and does nothing (the IR is always kept) | fossil of the deleted Python tool |
| No per-verb `--help`; `-h`/`--help` are rejected as invalid choices | [`cli.md`](cli.md) is the help text |
| An incremental compiler rebuild does not exist; a source change rebuilds the whole compiler | minutes, not seconds |
| `resolve` stops before the checker; `check` runs the full checker but no codegen | pick the cheapest verb that answers your question: [`cli.md`](cli.md) |
| There is no `run` verb, no `--emit`, no IR on stdout | `build`, then execute `build/<stem>`; the IR is always at `build/<stem>.ll` |

## Example programs

| Limit | Detail |
|---|---|
| `examples/wc.logos` matches GNU `wc` through a pipe, which pads to seven columns | a regular-file redirect uses a different width |
| Float literals are converted by libc `strtod` | a non-conforming `strtod` would shift the bits; a non-finite literal is emitted as `inf` rather than refused |
| `examples/json.logos` is an example, not a library | there is no JSON module to `(use …)` |
