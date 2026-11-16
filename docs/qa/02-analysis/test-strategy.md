# Test strategy — what each level proves, and what it cannot

A compiler has an unusual testing problem: the thing under test *is* the tool
that runs the tests. Every level below therefore exists because it catches a
class of defect the level above it structurally cannot see. The rule for a new
test is not "add coverage" but "name the class of defect only this test can
catch".

## The levels

| Level | Suite | Runs | Catches | Cannot catch |
|---|---|---|---|---|
| **Unit — front end** | `src/logosc/body_test.logos`, `check_test.logos`, `resolve_test.logos`, `tree_test.logos`, `types_test.logos` (>480 cases) | `make test` at `-O0` | A checker rule that is wrong in isolation: the case asserts the exact code, node path and message text | Nothing about lowering: no case here is ever compiled to a binary |
| **Unit — runtime** | `tests/test_runtime.py` | `make test` | A C runtime that computes the wrong size, leaks, or disagrees with the compiler's type layout | Nothing about the compiler: it calls `rt.c` functions directly |
| **Integration — corpus** | `./tools/logosc.sh test tests` (316 cases) | Both `-O0` and `-O2`, every case built, linked and executed, outputs compared *and* the two levels compared with each other | A case that works at one level and not the other; a leak-accounting regression; a panic that changes code | A defect in a form no case exercises; a diagnostic that no sidecar pins |
| **Integration — negative fixtures** | `tests/test_qa.py::NegativeFixtureSweep` (146 fixtures) | `make test` | A diagnostic that fires with the wrong code, the wrong shape, or not at all | The message text (that is the checker suites' job) |
| **Integration — contract** | `tests/test_contributing.py`, `tests/test_cli.py`, `tests/test_qa.py` | `make test` | The gate list drifting from `AGENTS.md`, a CLI promise (exit code, stream, `--json` shape) breaking silently, the six gates disagreeing with CI | Anything about the language |
| **End to end — differential** | `tests/diff/*` vs hand-written C twins | `bash tools/accept.sh` | A semantic the project's own expectations get wrong: gcc is an oracle that shares no code with this compiler | Anything gcc cannot express: ownership, results, optionals, threads |
| **End to end — examples** | `examples/` vs `wc`, `jq`, a C reference | `bash tools/accept.sh` | Integration bugs that only appear in a whole program | Language semantics |
| **End to end — install** | `tools/verify_install.sh` (5 checks) | `make release` / `release.yml` | "It works in the checkout and nowhere else": the v1 promise | Anything inside the compiler |
| **Self-hosting** | `bash tools/selfhost.sh` | The sixth gate (~7 min) | A stale stage-0, an IR difference between the two compilers, a formatter that is not a fixed point | A defect both compilers share |
| **Property** | `fmt` fixed point over every tracked `.logos`; `-O0`/`-O2` output equality; repeat-run equality | Gates 2, 5, 6 and `test_qa` | Nondeterminism, non-idempotence, level-dependent behaviour | A property nobody thought to state |

## The order that matters

1. **A defect gets a regress case first** (`tests/regress/`), because the case is
   what proves the fix. A positive case is `name.logos`; a negative one is
   `name.logos` plus `name.expect` naming the code.
2. **Then the diagnosis is moved to the tightest level that can hold it.** A
   checker rule belongs in `check_test.logos`, not in the corpus: it runs in
   seconds and asserts the message, not just the exit status.
3. **The corpus proves the behaviour survives lowering.** A case that only
   exists in a unit suite has never been compiled, so its `-O0`/`-O2` parity is
   unverified — that is why the fourth invariant ("no form the checker accepts
   may be unimplemented in the backend") is a corpus claim.
4. **Only the differential suite proves the project's beliefs are true.** Every
   other level compares the compiler with an expectation this project wrote.

## What is deliberately not tested

| Not tested | Why | What would change that |
|---|---|---|
| Random program generation (fuzzing) | No generator exists, and a generated program needs an expected result — random *input* without an oracle only finds crashes, of which the corpus has none today | A crash found in the wild, or a `fmt` round-trip property over generated text (the cheapest first step) |
| Insane/generated source bytes | The lexer's error paths are pinned by cases, but not against megabytes of malformed UTF-8 | A lexer panic reported by a user |
| arm64 and Darwin | One target, one toolchain, pinned in `bootstrap/toolchain.txt` | A second target becomes a release commitment |
| Cross-host container behaviour | The release pipeline builds on `ubuntu-22.04` twice and compares digests; the compiler itself is measured byte-identical after two linker-owned sections are stripped | A second distro becomes supported |
| Coverage instrumentation of the compiler itself | The compiler emits IR; there is no `llvm-cov`-able binary of *its own* control flow without a second build system | Someone adds a coverage build; the diagnostic-coverage gate below is the cheap substitute |

## The trade-off this strategy accepts

The gate is about an hour, and an agent iterating needs seconds. Two loops,
documented in `CONTRIBUTING.md` and `make fast`:

- **seconds** — `make fast`: the contract tests (including this suite), the
  37-case regress category, and the manual-drift check.
- **the gate** — `bash tools/pr_gate.sh`: everything, before a pull request.

The repeat-run determinism check in `tests/test_qa.py` is the one place where
the fast loop is deliberately made slower (about 17 seconds: two runs of the
leak-and-panic category). Repeat-run equality cannot be established any cheaper,
and a flaky suite is worse than a slow one.

SOURCES (LAYER 2 — NAVIGATION)

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/02-analysis/quality-gates.md
 -> The enforced thresholds, with the command and failure mode of each.

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/02-analysis/coverage.md
 -> The measured numbers behind the table above, and the four known holes.

/root/ai-language-program/.worktrees/t_5bd6660b/Makefile
 -> `test`, `fast`, `suites`, `suites-all` and what each one actually runs.

/root/ai-language-program/.worktrees/t_5bd6660b/tests/test_qa.py
 -> The module that enforces the integration and property levels named here.
