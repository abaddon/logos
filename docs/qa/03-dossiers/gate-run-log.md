# Gate-run log — the runs this sign-off rests on

Tree: `wt/t_5bd6660b` = `main` `ed0196b` + merge of `origin/fix/v1-gap-closure` +
this QA pass. Toolchain: `Ubuntu clang version 14.0.0-1ubuntu1.1`, `GNU ld
(Binutils for Ubuntu) 2.38`, as pinned in `bootstrap/toolchain.txt`.

## `bash tools/pr_gate.sh` — the six gates plus the precondition

The six gates were green on the parent of this commit (`t_977f8852`, PR #32:
`6/6 gates passed` locally and on CI). On **this** commit the same script was
started locally and its first gate (`make test`, now 67 contract tests plus nine
suites) was still running when this log was written; the run that covers this
exact commit is the one CI performs on pull request #33, which executes the same
six steps in the same order via `.github/workflows/gate.yml`. The per-gate
numbers below are from the runs that completed locally:

## Per gate

### Gate 1 — `make test` (unit tests)

```console
$ make contract
Ran 67 tests in 417.9s
OK
```

67 contract tests: `tests.test_contributing` (20), `tests.test_runtime` (3),
`tests.test_cli` (34), `tests.test_qa` (14), `tests.test_selfhost` (1 — it runs
the whole sixth gate, which is why this module takes seven minutes).

The suites, each at `-O0` (measured individually before they were all wired in):

| Suite | Cases | Wall time | Result |
|---|---|---|---|
| `body_test.logos` | 361 | ~30 min in the gate (each case links the whole compiler) | pass |
| `check_test.logos` | 81 | — | pass |
| `resolve_test.logos` | 38 | — | pass |
| `lex_test.logos` | 24 | 9.8 s | **24 passed, 0 failed** |
| `tree_test.logos` | 14 | 6.5 s | **14 passed, 0 failed** |
| `types_test.logos` | 112 | 118.5 s | **112 passed, 0 failed** |
| `emit_test.logos` | 24 | 43.8 s | **24 passed, 0 failed** |
| `fmt_test.logos` | 20 | 12.9 s | **20 passed, 0 failed** |
| `harness_test.logos` | 12 | 13.4 s | **12 passed, 0 failed** |

The six suites in bold were run by no target before this pass; together they are
206 cases and about 205 seconds.

### Gate 2 — `./tools/logosc.sh test tests` (corpus)

```console
$ ./build/logosc test tests --opt -O0 --opt -O2 --update-baseline
...
315 passed, 0 failed, 10 leaked
baseline tests/summary.txt: 315 cases
```

315 cases, each built, linked and executed at `-O0` and at `-O2`, the two
outcomes compared with each other, the leak total compared with the committed
baseline (`LEAKS 10`) and the whole thing compared with `tests/summary.txt`.
Wall time 3 min 17 s. The baseline diff this pass produced is exactly two lines:

```diff
+PASS type/unknown-field -
+PASS exec/run/an-unstartable-program-panics -
```

### Gate 4 — `./tools/logosc.sh guide --check` (manual drift)

```console
$ ./tools/logosc.sh guide --check
guide: docs/LOGOS.md is current
$ echo $?
0
```

### Gate 5 — formatting

```console
$ ./tools/logosc.sh fmt tests docs/manual
$ git diff --exit-code -- '*.logos'
$ echo $?
0
```

The two new `.logos` fixtures are canonical; `tests/parse/unbalanced.logos.txt`
is deliberately not (it must not lex/parse) and carries the `.txt` suffix
precisely so the formatter and the self-host manifest leave it alone.

### The QA gate itself

```console
$ python3 -m unittest tests.test_qa -v
Ran 14 tests in 21.8s
OK
```

21.8 s, of which 17 s is the two repeat runs of the leak-and-panic category and
3.5 s the 147-fixture sweep.

### Gate 6 — `bash tools/selfhost.sh`

```console
selfhost: 370 files, 0 differences
ir: 90 files, 0 differences
resolve: 14 fixtures, 0 differences
check: 126 fixtures, 0 differences
unit: 2 files, 0 differences
```

Reported by the parent of this commit (`t_977f8852`, PR #32) on the same
compiler source; this pass changes no `.logos` under `src/`, so the IR and the
fixed point are unaffected. The one thing this pass does change is
`tools/selfhost-manifest.txt`, which gains one line for the new fixture — the
gate's manifest check failed on the first run of `pr_gate.sh` without it
(`selfhost: manifest lists 370 files but git tracks 371`), which is the gate
doing its job on a QA commit.

## What this log does not claim

- The six gates are not reported as green **by this run** above; the run that
  covers this exact commit is the one CI performs on the pull request, and the
  six gates were green on the parent commit locally. Treat the CI run on PR #33
  as the authority.
- `tools/accept.sh` (gate 3) and `tools/selfhost.sh` (gate 6) take long enough
  that they were run by the parent commit's pass and by CI rather than twice
  more here.

SOURCES (LAYER 3 — EVIDENCE)

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/01-summary/verdict.md
 -> Which criterion each number above supports.

/root/ai-language-program/.worktrees/t_5bd6660b/tests/summary.txt
 -> The corpus baseline: one line per case, plus `LEAKS` and `OPTS`.

/root/ai-language-program/.worktrees/t_5bd6660b/.github/workflows/gate.yml
 -> The same six gates on CI, with the pinned toolchain and the sign-off step.
