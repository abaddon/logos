# Quality gates — every enforced threshold

A gate is a check that stops a merge. A threshold that nobody enforces is a
comment, so each row below names the command, the number, and what a failure
means. Everything here runs inside `make test`, which is gate 1 of the six in
`AGENTS.md`, which `tools/pr_gate.sh` runs locally and
`.github/workflows/gate.yml` runs on every pull request. Nothing was added to
the six-gate list: the documented contract stayed six commands, and the checks
below hang off the first one.

## The thresholds

| # | Gate | Threshold | Command | A failure means |
|---|---|---|---|---|
| 1 | Negative-fixture agreement | **146/146** fixtures emit the code their sidecar names | `python3 -m unittest tests.test_qa.NegativeFixtureSweep` | A diagnostic changed code, stopped firing, or a sidecar is stale. Exempt fixtures live in `tools/qa-known-gaps.txt` (4 today). |
| 2 | Diagnostic shape | every emitted diagnostic carries exactly the 7 published fields and a node path **or** a source position | same module | The machine surface an agent parses drifted. AGENTS.md invariant 4. |
| 3 | Published-code coverage | **34 of 35** codes in `logosc guide --json` are exercised from `tests/`; the one exception is registered with its measurement | `...NegativeFixtureSweep`, `...DiagnosticCoverage` | The tool advertises a code it cannot emit, or a new code shipped with no case. |
| 4 | Debt register cap | `tools/qa-known-gaps.txt` ≤ **4** entries, each still earned | `...DiagnosticCoverage.test_the_known_gap_register_does_not_grow` | Someone made a gate green by suppressing a new failure. |
| 5 | Corpus floors | per-category minimums (`parse` 15, `type` 107, `exec` 140, `mem` 7, `thread` 8, `generics` 2, `regress` 37) and **316** cases total | `...CorpusBaseline` | Cases were deleted or a category was silently emptied. |
| 6 | Baseline currency | every `*.expect` fixture has a recorded verdict in `tests/summary.txt`; the baseline pins `-O0` **and** `-O2`; no committed case is `FAIL` | same module | A case was added without regenerating the baseline, so its result is unrecorded. |
| 7 | Determinism (repeat) | two runs of the leak-and-panic category are **byte-identical** | `...Flakiness` | Nondeterminism: a flaky test. |
| 8 | Determinism (build) | two builds of one source are byte-identical | `tests/test_cli.py::Determinism` | Codegen or linking picked up ambient state. |
| 9 | Level parity | every corpus case is executed at `-O0` **and** `-O2` and the two outcomes compared | `./tools/logosc.sh test tests` | A lowering difference between levels. AGENTS.md invariant 2. |
| 10 | Gate wiring | `tests.test_qa` is in `CONTRACT_TESTS`, CI runs `make test`, and the debt register is committed | `...GateWiring` | The checks above stopped being enforced anywhere. |

## Why these, and not a line-coverage percentage

There is no line-coverage tool that measures *this* compiler: it emits IR and
shells out to clang, and building it twice under `-fprofile-instr-generate`
would be a second build system to maintain. Rather than report a number nobody
can act on, the gates measure the three things a compiler's coverage actually
means here:

1. **Every published diagnostic is reachable** (gate 3). This is a contract with
   the agent that branches on `code`, and it is checkable exactly.
2. **Every published form is implemented in the backend** (gate 9). AGENTS.md's
   fourth invariant, measured by running each case at both levels.
3. **Every negative case is a real assertion** (gates 1, 2). Before this pass, a
   sidecar was only checked for *shape*.

A fourth, cheap proxy is deliberately skipped: counting which lowering paths the
corpus executes. It would need instrumentation in the compiler, and the form
table in `guide --json` is the same information one level up.

## Fast loop versus the gate

| Loop | Command | Wall time | What it covers |
|---|---|---|---|
| Seconds | `make fast` | ~25 s | contract tests including this suite, the regress category, manual drift |
| Corpus (one category) | `./tools/logosc.sh test tests --only regress` | ~15 s | the 37 regression cases at `-O0` |
| Gate 1 only | `make contract` | ~7 min | everything in `make test` except the compiler's own suites (the self-hosting module is the long pole) |
| Full gate | `bash tools/pr_gate.sh` | ~60 min | the six gates, sign-off first |

`make test` is unchanged in what it documents and unchanged in failure
semantics; it now also runs `tests/test_cli.py` and `tests/test_qa.py`, which
were additions, not substitutes. No gate was weakened, skipped or re-scoped.

## Failure modes that are deliberately loud

- **A pruned checkout fails rather than passes over nothing.** `tests/test_qa`
  asserts a corpus floor and a code-table size; `tools/accept.sh` asserts a
  floor on every section; `tools/selfhost.sh` asserts floors on every phase.
- **The baseline refuses to compare rather than fail open.** A
  `tests/summary.txt` without an `OPTS` line is an error, not a wildcard.
- **An exemption cannot rot silently.** `tools/qa-known-gaps.txt` lines fail the
  suite the moment they stop being needed, so the register can only shrink.

SOURCES (LAYER 2 — NAVIGATION)

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/02-analysis/test-strategy.md
 -> Why a test belongs at one level rather than another, and the classes of
    defect no other level can catch.

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/02-analysis/coverage.md
 -> The measured numbers: what each threshold is at today, and the holes.

/root/ai-language-program/.worktrees/t_5bd6660b/tests/test_qa.py
 -> The module that enforces gates 1-10 above.

/root/ai-language-program/.worktrees/t_5bd6660b/tools/pr_gate.sh
 -> The six gates as executed locally, sign-off first.

/root/ai-language-program/.worktrees/t_5bd6660b/.github/workflows/gate.yml
 -> The same six gates on CI, with the pinned toolchain.
