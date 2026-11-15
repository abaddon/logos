# QA — how this build is trusted

The compiler, the corpus and the six gates in `AGENTS.md` are the repository's
existing quality system, and they are strong. This directory is the layer above
them: what the v1 release actually promises, which of those promises a gate
measures, and what is left unmeasured. It is also the record of the QA pass that
scored the build against the release criteria.

## Read in this order

| Layer | File | What it answers |
|---|---|---|
| L1 | [`01-summary/verdict.md`](01-summary/verdict.md) | Is this build releasable? The sign-off, with each of the 18 v1 criteria scored and the blockers named. |
| L2 | [`02-analysis/test-strategy.md`](02-analysis/test-strategy.md) | What each test level proves, what it cannot prove, and where a new test belongs. |
| L2 | [`02-analysis/quality-gates.md`](02-analysis/quality-gates.md) | Every enforced gate, its threshold, its failure mode, and the command that runs it. |
| L2 | [`02-analysis/coverage.md`](02-analysis/coverage.md) | The measured coverage numbers, the four known holes, and what the numbers do *not* mean. |
| L3 | [`03-dossiers/negative-fixture-audit.md`](03-dossiers/negative-fixture-audit.md) | Per-fixture audit: which negative case was judged by which gate, and what the compiler actually emits. |
| L3 | [`03-dossiers/gate-run-log.md`](03-dossiers/gate-run-log.md) | The raw output of every gate run this pass rests on. |

## The one-paragraph version

The gate that judged whether a negative test case passed never compiled it:
`src/logosc/harness.logos` marks a file PASS as soon as its `*.expect` sidecar is
well formed, so a fixture could claim any code and stay green. Six fixtures were
in that state; four of them disagree with the compiler today. `tests/test_qa.py`
closes that hole — it builds every negative fixture and compares the emitted code
with the sidecar — and adds the release-level measurements the gates were
missing: published-code coverage, corpus floors tied to the committed baseline,
repeat-run determinism, and a cap on the debt register. Details and evidence:
[`02-analysis/coverage.md`](02-analysis/coverage.md).

## Running it

```sh
make fast                                   # seconds: contract tests, regress, manual drift
make test                                   # the gate: contract tests + the compiler's suites
./tools/logosc.sh test tests                # the corpus at -O0 and -O2
python3 -m unittest tests.test_qa -v         # the QA gate on its own
```

SOURCES (LAYER 0 — NAVIGATION)

/root/ai-language-program/.worktrees/t_5bd6660b/AGENTS.md
 -> The six gates, the four invariants and the regress-case requirement this
    directory scores the build against.

/root/ai-language-program/.worktrees/t_5bd6660b/tests/test_qa.py
 -> The enforced gate itself: negative-fixture sweep, code coverage, corpus
    floors, repeat-run determinism and the wiring assertions.

/root/ai-language-program/.worktrees/t_5bd6660b/tools/qa-known-gaps.txt
 -> The debt register of expectations the compiler does not satisfy, with the
    measurement for each and a rule that it may shrink but not grow.
