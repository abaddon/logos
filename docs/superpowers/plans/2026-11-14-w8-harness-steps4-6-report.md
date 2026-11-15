# W8 harness steps 4–6 — the level loop, the levels' agreement, and the report

Branch `feat/selfhost-w7-backend`, on top of `56fbd68` (step 3, child I/O). The
reference is `logos/tester.py` and `logos/cli.py`; Python is the oracle on the
same tree, every time. `src/logosc/harness.logos` gains the level loop and the
cross-level comparison, `src/logosc/main.logos` gains the `--opt` levels it used
to consume and throw away, and the run now ends with `cli._test`'s summary line
instead of stopping at the last case.

The one sentence that matters: `gen3 test` on the whole suite prints Python's
stdout, line for line, through the summary — except the baseline line (W9) and
the 35 cases the port's *lowering* still refuses, which print the `FAIL` line
Python's own `_run_case` would print if it had the same lowering gaps. The
brief names 32; the suite has 35, and §6 accounts for all three extra ones
rather than widening the exemption.

## 1 One case, every level — `_run_case` (`tester.py:484-530`)

`h-test` used to build and run one case once, at `-O0`. It now walks `opts` in
order — `-O0 -O2` unless `--opt` said otherwise — and for each level:

| step | Python | here |
|---|---|---|
| the path | `re.sub(r"[^A-Za-z0-9_.-]", "_", name)`, `level = re.sub(r"[^A-Za-z0-9]", "", opt) or "O0"` (`533-542`) | `h-safe-name`, `h-level`; byte-wise, so a multi-byte character is more than one `_` |
| build and run | `driver.run_test(..., opt=opt)` then `subprocess.run(timeout=10)` (`556-583`) | `h-execute` → `build --test NAME --opt LEVEL`, then the binary with 10 000 ms |
| the clauses | `_compare` in directive order, `{opt}: ` prefixed (`581`, `614-637`) | `h-compare`; unchanged from step 3 |
| the leaks | `LEAK ` at the start of a line, added to the suite total even when the case failed (`579-580`) | `h-leaks`; added to a three-slot counter vector |
| the observation | `(stdout, stderr, returncode)`, kept only when the process ran (`582`, `522`) | `h-outcome`'s `has` flag; a build failure, a timeout and a spawn failure have none |

`h-execute` returns an `h-outcome` rather than a string because `_execute`
answers two things: the problems it found and what it saw. An empty detail is
not appended to the case's problems; everything else joins them with `"; "`,
already carrying its level, so a case that fails both levels prints both
clauses in the order the levels ran, exactly as Python's `problems.extend` +
`"; ".join` does.

## 2 The levels against each other — `_disagreement` (`586-611`)

`h-disagree-one` compares the first observation with each later one, field by
field, in Python's order — stdout, exit code, stderr — and fails the case in
its own right:

```
-O0 and -O2 disagree: stdout 'a' vs 'b', exit code 0 vs 1, stderr '' vs 'x'
```

The fields that agree are absent, the joining is `", "`, and the sentence is
appended after that level's problems, never repaired (`524-529`). A case that
runs at only one level has one observation and is not compared, which is what
`len(observed) > 1` says (`524`).

The comparison is pinned by `src/logosc/harness_test.logos` — a new unit module
that calls `h-disagree-one` with two hand-made observations and expects the
sentence, once with three fields differing and once with only stderr. Python
runs it (`4 passed, 0 failed, 0 leaked`), and so does the port, byte for byte;
that is the only way to prove the text without a program that really optimises
differently, and no fixture in the corpus does.

## 3 The report — `cli._test` (`239-277`)

`h-run` now prints, in this order:

```
PASS|FAIL <id> <detail>          one per case, in run order
SKIP <path>                      one per *.logos file under a suite root that no category claims
<passed> passed, <failed> failed, <leaks> leaked
test: no cases found in <path>   only when no case was recorded
```

and writes `logos: test: <n> file(s) outside the known categories were skipped`
to stderr when a file sat outside every category, failing the run before the
baseline step as `cli.py:249-255` does. The exit status is 1 when a case
failed, when a file was skipped, or when nothing ran; 0 otherwise. That status
is `h-run`'s return value, and `main` returns it unchanged.

The counters are kept where the lines are printed: `h-pass` and `h-fail` are
the only two functions that print a case line, and each increments its own slot
of a three-slot total, so the summary cannot disagree with the report above it
— the property the step-3 report could not state, because there was no summary.

`h-discover` now also answers the skip set: when the root holds a category
directory it walks the whole root sorted, subtracts the claimed files, and
keeps the rest in walk order — Python's `sorted(root.rglob("*.logos"))` minus
`claimed` (`243-244`). `--only` filters the claimed set after that subtraction,
so a stray file is reported even in a narrowed run, as Python does. `tests/`
holds no such file, so the corpus is unaffected; a scratch tree proves it
(§5).

**Not printed: the baseline line.** Python ends with
`baseline tests/summary.txt: n regression(s)` or `baseline: none`
(`271-276`). Writing, merging and comparing a baseline — with percent-encoded
ids — is W9, and this run prints nothing after the summary rather than a line
it has not earned.

## 4 What `main` hands the harness

`--opt` was parsed and discarded; `main-test-opts` now pushes each level it
consumes into a vector, `--opt=-O0` pushes its attached value (index 6, the
mistake that cost this step a rebuild: `--only=` is seven characters, `--opt=`
is six), and `h-run` takes the list. An empty list is `OPTS`, so a run with no
`--opt` is both levels. `main-test-run` returns `h-run`'s status instead of
turning a failure count into 1.

## 5 The run

All runs are on the working tree, from the repository root, under
`ulimit -v 4000000`, with `build/w8s46/gen2` built from
`src/logosc/*.logos src/std/map.logos src/std/str.logos` by Python.

| run | Python | gen3 | exit (python / gen3) |
|---|---|---|---|
| `--only mem` | `7 passed, 0 failed, 6 leaked` | `5 passed, 2 failed, 6 leaked` | 0 / 1 |
| `--only exec` | `139 passed, 0 failed, 4 leaked` | `107 passed, 32 failed, 4 leaked` | 0 / 1 |
| `tests` (whole suite) | `308 passed, 0 failed, 10 leaked` | `273 passed, 35 failed, 10 leaked` | 0 / 1 |

Line counts: mem 7 cases + 1 summary on both sides; exec 139 + 1 on both sides;
the whole suite 308 + 1 against Python's 308 + summary + baseline.

The comparator's verdict, one line per run:

```
mem    python lines: 8    gen3 lines: 8    classified failures: 2 of 2     MATCH
exec   python lines: 140  gen3 lines: 140  classified failures: 32 of 32   MATCH
tests  python lines: 309  gen3 lines: 309  classified failures: 35 of 35   MATCH
```

The comparison is `build/w8s46/compare.py` (a scratch tool, not committed),
and it is deliberately strict — it is the thing that decides whether "the 32
are the only difference" is true:

- Python's last line is dropped (the baseline, W9), and the two files must then
  have the same number of lines;
- every line that is not one of the classified cases must be **byte identical**;
- a differing line must name the same id, must be `PASS` in Python and `FAIL`
  here, must carry exactly one clause per level in the levels' order, each
  starting `{level}: build failed: ` (or, for `formats-floats`, `{level}:
  stdout: `), and must contain the substring that classifies it (§6);
- the failing set must be exactly the classified cases present in that run: a
  case that used to pass and now fails, or a classified case that quietly
  starts passing, is a problem;
- the summary must be Python's numbers moved by exactly the number of cases
  that did not run: `passed − n`, `failed + n`, and the leak total must not
  rise.

That last line is worth its own sentence: the leak totals match Python's
exactly — 6 for `mem`, 4 for `exec`, 10 for the suite — because none of the 35
cases that do not build gets as far as allocating, so the count of `LEAK `
lines is the same number either implementation prints.

**The whole suite found a 33rd build-refused case that step 3 could not see,
and it is in `regress` — a category step 3 never ran.** `gen3 test tests`
reports `FAIL regress/float-literal-compare/all-literal-comparisons-are-float`
at both levels:

```
-O0: build failed: logos: clang failed: clang … build/float-literal-compare.all-literal-comparisons-are-float.ll …
```

and clang's own line, one below it, is
`error: floating point constant invalid for type` on
`%t1 = icmp slt i64 0x3FF8000000000000, 0x4000000000000000`: the port lowers a
comparison of two float literals to an integer compare over two float
constants. A compiler built at the parent commit `56fbd68` in a worktree
reproduces it byte for byte, so it is a port gap this step exposed, not a
regression it introduced. It is the 35th line, and the comparator would have
failed the run if it were anything else.

## 6 Reconciling the 35 — 32 `exec`, 2 `mem`, 1 `regress`

The brief allows 32 known failures for `exec`, and `exec` has exactly 32. The
suite has 35, and the other three are accounted for one at a time:

- **2 `mem`** (`mem/leak/no-leak`, `mem/leak/array-elements`) are the same
  lowering gap as `exec/loops/fizzbuzz` and
  `exec/match/match-arm-has-a-block-body`: a `(match …)` used as a **call
  argument** (`(println (match …))`) is refused by the port's lowering with
  `E0002: a statement must be a form`, while the same `match` under `(ret …)`
  or `(let …)` lowers. `2026-11-14-w8-harness-step3-report.md` already named
  these two; they are not `exec`, which is why the 32 is still 32.
- **1 `regress`**
  (`regress/float-literal-compare/all-literal-comparisons-are-float`) is new to
  the classification because step 3 never ran the category. It reproduces at
  `56fbd68` (§5), and it is one build failure, not a comparison failure.

That is also why step 4's acceptance — `--only mem` printing 7 `PASS` and
exiting 0 — is **not** met: the harness is right and the case does not build.
The port cannot be made to pass it from `harness.logos`; it is the lowerer's
argument walk, which is the work queue the step-3 report opened, not this
step's subject. `tests/test_gen2_test.py` asserts the id set, the order and the
leak total for `mem` and explicitly leaves the exit status out.

Buckets, by the detail's own words (both levels alike):

| detail | cases |
|---|---|
| `lower/lo-reaches/…: R0003: vector index out of bounds` | 21 (`tests/exec/results.logos`) |
| `…: E0002: a statement must be a form` | 4 (2 `exec`, 2 `mem`) |
| `…: E0002: 'cast' is not lowered by this backend yet` | 5 (`tests/exec/cast.logos`) |
| `…: E0002: '!=' is not lowered by this backend yet` | 1 (`strings/equality`) |
| `logos: clang failed: …` (invalid float constant) | 3 (2 f32 `exec` cases, 1 float-comparison `regress` case) |
| `stdout: expected '…1e+300…', got '…1.0000000000000002e+300…'` | 1 (`strings/formats-floats`) |

**How the disagreement is reconciled without weakening the comparison.** Python
prints `PASS` for all 35; the port prints `FAIL`, so *something* must differ,
and the honest question is whether the difference is confined to the thing
that is actually broken. It is, and the comparator proves it field by field
rather than by trusting a list: the status word, the id, the order, the number
of levels, the level labels, the clause separator and the `build failed: `
prefix all have to be Python's — only the diagnostic *inside* the clause is the
port's own text, which is exactly the text Python would print if its lowering
refused the same program (Python's `_execute` builds the same sentence from
`{opt}: build failed: {_message(error)}`, `563`). So the accepted difference is
one string per clause — the port's diagnostic — and any other difference is a
failure of this step, including a case moving between the two sets. The 21
`R0003` cases and the two `E0002` `match` cases are also the two largest items
on the queue that a later wave inherits.

## 7 Fixtures and evidence

| fixture / command | what it proves | result |
|---|---|---|
| `gen3 test tests --only mem` | the level loop on a category | 7 lines, `5 passed, 2 failed, 6 leaked`, exit 1 — Python's stdout except the 2 classified cases |
| `gen3 test tests --only exec` | both levels over the largest category | 139 lines, `107 passed, 32 failed, 4 leaked`, exit 1 — same, except the 32 |
| `gen3 test tests` | the whole suite through the summary | 309 lines, `273 passed, 35 failed, 10 leaked`, exit 1 — Python's stdout except the 35, and no baseline line |
| `gen3 test src/logosc/harness_test.logos` | the cross-level sentence and the report helpers | `4 passed, 0 failed, 0 leaked`, byte-identical to Python's run of the same file |
| `python3 -m unittest tests.test_gen2_test.ReportTest` | both levels, `--opt`, the skip line, the empty run | 5 tests, OK |
| a scratch suite tree | `SKIP <path>` + the stderr line + exit 1; `0 passed, 0 failed, 0 leaked` + `test: no cases found in <path>` + exit 1 | both byte-identical to Python's, in order |
| `--opt=-O0` | the attached spelling names the level that runs | one `PASS`, exit 0, `.O0.bin` only |

`tests/test_gen2_test.py` changed with the output: the whole-corpus test now
asserts 308 case lines **plus** a summary whose numbers count them, `--only
mem` asserts its leak total is Python's 6, and the two child-I/O tests expect
the summary line after their case lines. `ReportTest` is new and covers what
the corpus cannot cheaply: a scratch tree whose two cases differ only in what
they print (both levels, both clauses), `--opt` selecting one level (and
`--opt=-O0` naming the same one), two agreeing levels staying silent, the skip
line and its exit status, and an empty run.

`bash tools/pr_gate.sh` — **6/6**, exit 0 (`build/w8s46/prgate.log`, not
committed): unit tests, the Python corpus (`308 passed, 0 failed, 10 leaked`),
acceptance, manual drift, formatting, and self-hosting (`338 files, 0
differences`; `ir: 65 files, 0 differences`; `resolve: 14`; `check: 123`;
`unit: 2`).

`src/logosc/harness_test.logos` is a new tracked fixture, so
`tools/selfhost-manifest.txt` was regenerated (`git ls-files '*.logos' | sort`,
338 entries). It has no `fn`s, so the fixed point and the IR parity lists are
untouched.

## Concerns

- **Step 4's acceptance is not met as written.** `--only mem` prints 5 `PASS`
  and 2 `FAIL` and exits 1, because the port's lowering refuses a `match` used
  as a call argument. This step did not touch the lowerer: the harness's own
  contract for those two cases — build both levels, fail with Python's sentence
  shape, count the leaks — is exercised and correct, and the two cases are in
  the classified set.
- **The negative fixtures are still not judged** (`_run_negative`,
  `456-482`). Every tracked one passes in Python, so the `PASS` lines match and
  the whole-suite equality holds, but the status is not earned: a fixture whose
  diagnostic code changed would still print `PASS`. That is a visible hole in
  "the whole suite matches", and it is the largest remaining piece of the
  harness.
- **Build-failure details are the port's own text.** Python renders the
  diagnostic with a file, line and column; the port prints the node path and
  the code (`cast/test/…/1/0: E0002: …`). The sentence shape is Python's, the
  text is not, and no oracle can produce it. Accepted here only for the
  classified cases, and only inside the clause.
- **`h-repr` and `_one_line` are still equivalence-grade** (`745-750`, `604`),
  as in step 3: no current detail needs the escapes or the truncation.
- **`h-safe-name` is byte-wise.** Python's `re.sub` replaces one *character*
  with `_`; a non-ASCII test name would be several `_` here. No test name in
  the corpus is non-ASCII.
- **`--opt -O0 -O2` two spellings.** `--opt=-O0 -O2` is a usage error in
  argparse (the `-O2` is not attached to a flag) and a usage error here too,
  with the port's fixed usage line rather than argparse's sentence. Exit 2
  both ways.
- **The suite costs what the gate costs.** Both levels mean 616 clang links
  for `tests`; the run is minutes, not seconds. `make test` grew with it — the
  16 cases in `tests/test_gen2_test.py` now take 305 s instead of about 145 s,
  because the whole-corpus test and the twenty-second timeout fixture each run
  everything twice.
- **A case that leaks and then fails counts its leaks twice at two levels** —
  Python's rule, kept: 6 `mem` leaks for three leaking cases, 10 in the suite.
