# W8 step 3c-3 — child I/O: `/dev/null`, a case's ten seconds, a spawn that fails

Branch `feat/selfhost-w7-backend`. Commit `2b73aa6` on top of `0c3c070`
(W8 3c-2, discovery and the directive reader) holds the runtime, the language,
the harness and its tests; the commit that carries this report also updates the
manual's form row. The reference is `logos/tester.py` throughout; the survey
that measured the three gaps is `2026-11-13-w8-harness-notes.md` §3.

`gen2 test` now builds and runs a case. `tests/exec/read.logos` passes both of
its cases and returns in about a second instead of hanging, a 20-second fixture
is killed at ten with Python's sentence, and a child that cannot be started is
a `FAIL` line instead of a panic that takes the run down with it.

## The three gaps, hardest first

### 1. Standard input — `tester.py:567` (`stdin=subprocess.DEVNULL`)

`rt_run_start` duplicated stdout and stderr into pipes and left fd 0 alone, so
a child inherited the harness's standard input. `read-all`
(`tests/exec/read.logos:3-14`) expects `"0\n"`; on a terminal, or on any
inherited pipe, it blocked instead.

The spawn now opens `/dev/null` before the file actions and dup2's it onto
`STDIN_FILENO` (`logos/runtime/rt.c`, `rt_run_launch`), and closes the
descriptor in the parent once `posix_spawnp` has returned. The redirect is part
of the runtime rather than the harness, so every `(run …)` child sees an empty
stream — including `main-exists`'s `test -f` and the clang link. Every existing
child in the corpus ignores stdin, which is why the 308-case Python suite stays
at `308 passed, 0 failed, 10 leaked` with the new runtime.

### 2. The budget — `tester.py:96` (10.0 s) and `574-575`

`RT_RUN_TIMEOUT_MS` was 90 000 ms, a *build* guard: clang spends 27 s on the
compiler's 18 MB unit, and W8 step 2 raised it from 30 s for exactly that
reason. Python gives a *test case* 10 s and prints
`{opt}: timed out after {timeout:g}s` in the detail. Those are different waits
with different owners and must not share one constant.

`(run prog args ms)` is a new optional third argument: the same spawn with the
caller's budget, through a second runtime entry point `rt_run_start_timed`.
`ms` of 0 (or less) means `RT_RUN_TIMEOUT_MS`, so the constant remains the
default and the build's cap cannot drift. `h-execute` gives a case 10 000 ms and
a build 0:

```logos
(let b :run (run self bargs (h-build-budget)))   ; 0 = RT_RUN_TIMEOUT_MS, 90 s
(let r :run (run out rargs (h-case-budget)))     ; 10 000 ms
```

The kill still reports 124, and the harness turns 124 into
`-O0: timed out after 10s`.

### 3. A spawn that can fail — `tester.py:576-577`

A failed `posix_spawnp` panicked `R0006` at the `run` node, which is the right
answer for a program whose toolchain is missing and the wrong one for a
supervisor: Python catches `OSError` and reports `could not run: …` as a case
detail. Panic and detail cannot both win, and the two-argument form's panic is
specified (`docs/LOGOS.md:925`) and tested (`tests/test_run_form.py`).

So the failure follows the budget. The timed form's handle carries status `-1`
— a value no exit code and no `128 + signal` can produce — and
`could not run: <prog>: <reason>` in its error stream; the two-argument form
still panics `R0006`. `h-execute` prints `-O0: ` plus that sentence.

Both compilers learned the third argument (Python `logos/check.py`,
`logos/lower.py`; the port `src/logosc/check.logos`, `src/logosc/lower.logos`),
and `docs/LOGOS.md` was regenerated from `logos/guide.py`, which
`python3 -m logos guide --check` confirms.

## Which wait each call site now uses

| call site | form | budget | spawn failure |
|---|---|---|---|
| `harness.logos` build (`h-execute`) | `(run self args 0)` | 0 → `RT_RUN_TIMEOUT_MS`, 90 000 ms | status -1, `could not run: …` |
| `harness.logos` case (`h-execute`) | `(run out args 10000)` | 10 000 ms | status -1, `could not run: …` |
| `main.logos:218` (`main-exists`: `test -f`) | `(run "test" argv)` | `RT_RUN_TIMEOUT_MS`, 90 000 ms | panics `R0006` |
| `main.logos:280` (the clang link) | `(run "clang" argv)` | `RT_RUN_TIMEOUT_MS`, 90 000 ms | panics `R0006` |
| `resolve.logos:95` (`test -f` again) | `(run "test" argv)` | `RT_RUN_TIMEOUT_MS`, 90 000 ms | panics `R0006` |
| `tests/exec/run.logos`, the IR fixtures | `(run "sh" args)` | `RT_RUN_TIMEOUT_MS`, 90 000 ms | panics `R0006` |

Nothing outside the harness changed its wait, and nothing that used to panic
stopped panicking.

## The harness's `_execute`

`h-execute` mirrors `tester._execute` (`556-583`):

- **Build.** `(run SELF ["build" PATH "--test" NAME "--opt" "-O0" "-o" OUT] 0)`
  where `SELF` is `(args)`'s first word: the compiler builds its own test
  binaries, with the same `build/harness/<category>/<relative>/<NN>-<name>.O0.bin`
  path Python uses. A non-zero status becomes `-O0: build failed: <first line>`.
- **Run.** The binary with no arguments and a 10 s budget.
- **Compare.** `_compare` (`614-637`) in directive order — stdout, exit code,
  leaks, `err-contains` — joined by `"; "` and prefixed with the level, so a
  case with two unmet clauses prints both. `h-leaks` counts `LEAK ` at line
  starts (`579`); `h-repr` is Python's `repr` for the characters that occur in
  practice (`\\`, `\'`, `\n`, `\r`, `\t` escaped, single quotes).

Only `-O0` runs. `--opt` is still parsed and ignored: the level loop and the
cross-level comparison are step 5. The negative fixtures
(`_run_negative`, `456-482`) still print `PASS` without checking their code —
step 4.

## Fixtures and evidence

All runs are on the committed tree, from the repository root, under
`ulimit -v 4000000`.

| fixture | what it proves | result |
|---|---|---|
| `tests/exec/read.logos` | stdin is `/dev/null`; a `read-all` case terminates | two `PASS` lines, exit 0, 0.98 s |
| `src/logosc/fixtures/harness/sleep.logos` | a case's budget is 10 s, not 90 | `FAIL exec/sleep/sleeps-past-its-budget -O0: timed out after 10s`, exit 1, 10.3 s |
| `src/logosc/fixtures/harness/missing.logos` | a spawn that cannot start is a detail | `FAIL exec/missing/cannot-be-started -O0: could not run: build/harness/exec/missing/00-cannot-be-started.O0.bin: No such file or directory`, exit 1, stderr empty |

`missing.logos` builds normally; `tests/test_gen2_test.py::ChildIoTest` starts
the harness under a wrapper's *name* (`subprocess.run(..., executable=…)`, so
the harness's `argv[0]` is the wrapper), the wrapper forwards the build to the
real compiler and deletes the binary it produced, and the run's only failure is
the spawn. A panic would exit 2 with `R0006` on stderr; the assertion is exit 1
and empty stderr.

Unit evidence:

- `python3 -m unittest tests.test_run_form` — 35 tests, 7.4 s: the two-argument
  form still panics `R0006`; a 200 ms budget against `sleep 5` reports 124; a
  child running `cat` reads end of file; the timed form reports status -1 and
  `could not run:` for a missing program.
- `python3 -m unittest tests.test_gen2_test` — 11 tests, 145 s: the 308 ids in
  baseline order, `--only mem`, a file root, the 25 malformed directives, the
  usage exits, and the three `ChildIoTest` cases above.
- `python3 -m logos test` (the Python oracle, with the new runtime) —
  308 passed, 0 failed, 10 leaked, exit 0.
- `python3 -m logos guide --check` — current.
- `bash tools/pr_gate.sh` — **6/6**, exit 0, 27 min 33 s: unit tests (1120),
  corpus (`308 passed, 0 failed, 10 leaked`), acceptance, manual drift,
  formatting, and self-hosting (`337 files, 0 differences`; `ir: 65 files, 0
  differences`; `resolve: 14`; `check: 123`; `unit: 2`).

## The exec corpus: 107 of 139 pass

`gen2 test tests --only exec` at `-O0`: **139 cases, 107 `PASS`, 32 `FAIL`, 0
timeouts, 0 `could not run`**, exit 1. The brief says 138; the corpus is 139,
which is also the number in the survey (`2026-11-13-w8-harness-notes.md` §5
step 5), and `python3 -m logos test tests --only exec --opt -O0` reports 139
`PASS`. So one case is missing from the brief's count, not from the run.

Every failure, by its detail line, classified. All 32 reproduce at `0c3c070`
with a compiler built from the parent commit in a worktree — they are port
gaps this step exposed, not regressions it introduced.

### build crashed — 21 (the port's lowerer panics)

Detail, all 21: `-O0: build failed: lower/lo-reaches/5/2: R0003: vector index
out of bounds`. Every case in `tests/exec/results.logos`; the crash is in
`lo-reaches`, i.e. the *test-mode* build path (`--test`) does not seed the
reachability pass the way a normal build does, and the file's enums/optionals
walk off the end of a vector. One fix clears all 21.

`exec/results/match-ok`, `match-err-payload`, `match-str-payload`,
`try-success`, `try-propagates`, `optional-some`, `optional-none`,
`optional-binding`, `enum-payload-less`, `enum-in-a-struct-field`,
`result-through-a-parameter`, `result-in-a-binding`,
`match-produces-a-value`, `wildcard-covers-an-enum`,
`enum-payload-of-an-enum`, `enum-in-a-vector`,
`alloc-of-a-struct-of-scalars`, `try-inside-one-expression`,
`try-inside-a-loop`, `owner-in-an-optional`, `owner-in-a-binding`.

### build refused (checker) — 2

Detail: `-O0: build failed: <file>: E0002: a statement must be a form`. A
`(match …)` used in expression position (inside `println`) is refused by the
port's checker (`check.logos:3816`, `3851`); Python lowers the same shape. The
same gap fails two of the seven `mem` cases.

`exec/loops/fizzbuzz`, `exec/match/match-arm-has-a-block-body`.

### build refused (lowering stub) — 6

Detail: `E0002: '<form>' is not lowered by this backend yet` — the port's
explicit stub (`lower.logos:734-738`).

| case | form |
|---|---|
| `exec/cast/float-to-int-in-range` | `cast` |
| `exec/cast/float-to-int-large-in-range` | `cast` |
| `exec/cast/float-to-int-out-of-range-panics` | `cast` |
| `exec/cast/float-to-unsigned-out-of-range-panics` | `cast` |
| `exec/cast/f32-rounds-to-single` | `cast` |
| `exec/strings/equality` | `!=` |

### build refused (clang) — 2

Detail: `-O0: build failed: logos: clang failed: …` — the port emits IR clang
rejects (`build/floats.f32-arithmetic.ll:15:15: error: floating point constant
invalid for type`).

`exec/floats/f32-arithmetic`, `exec/floats/division-by-zero-is-not-a-panic`.

### case fails (stdout) — 1

`exec/strings/formats-floats`: `-O0: stdout: expected
'3.5\n0.5\n2\n-1.25\n0.1\n1e+300\n', got
'3.5\n0.5\n2\n-1.25\n0.1\n1.0000000000000002e+300\n'`. The port's float
formatting rounds the last digits of `1e+300` into `repr`-style text; the rest
of the case matches.

### Notes for the queue

- The 21-case crash is one bug and the largest single win.
- The 2 checker cases (`match` in expression position) and the 2 `mem` cases
  are the same gap; fixing it takes `--only mem` to 7/7.
- Only after those 25 does the corpus get to the comparison work steps 4-6
  actually own (level loop, summary, baselines).

## Concerns

- **124 is ambiguous.** A program that exits 124 and a program killed at the
  budget are the same status at the language level (`tester.py` distinguishes
  them). No fixture exits 124, and step 4 could not tell the difference either;
  I left it as the runtime documents it.
- **`repr` is equivalence-grade.** `h-repr` escapes backslash, quote, newline,
  carriage return and tab and passes other bytes through; Python escapes
  non-ASCII and control bytes as `\xNN`. No current detail needs them.
- **`_one_line`'s 240-byte truncation is not implemented.** A pathological
  stderr could make a longer detail than Python's.
- **Build failures use the first stderr line**, where Python renders the
  diagnostic (`E0002: …` with file, line and column). The `E0002` sentences
  match; the prefix format is close but not chosen per error kind.
- **The whole-corpus test no longer asserts every case passes.** It pins the
  308-case id column and order and tolerates the 32 known failures, which is
  step 3's scope: the failures are the work queue, not a claim this commit
  makes. `--only mem` asserts its 7 ids and not exit 0 for the same reason.
  Both comments say so.
- **Test time grew.** `tests.test_gen2_test` now runs the corpus (~145 s); the
  Python oracle suite is unchanged at ~3 min.
- **`(run prog args ms)` is a language change**, mirrored in both compilers and
  in the manual. It is additive: the two-argument form's IR, wait and panic are
  unchanged, which is what keeps the self-hosting fixed point safe.
