# W9 — the baseline comparison, ported

Written 2026-11-15, on top of `4b269b3`. This closes the last item of the
`test` verb's contract: the second line the reference printed, the problems it
printed above it, and the exit status that followed.

## The two lines

Before this change `./tools/logosc.sh test tests` ended at the summary:

```
308 passed, 0 failed, 10 leaked
```

Now it ends with the reference's second line, exits 0, and leaves
`tests/summary.txt` untouched (`git diff` on it is empty):

```
308 passed, 0 failed, 10 leaked
baseline tests/summary.txt: 0 regression(s)
```

## What was ported

The reference is `3606ee5:logos/tester.py` (`_read_baseline` at `845`,
`compare_baseline` at `913`) and `3606ee5:logos/cli.py:255-280`. Every one of
the eight points in the brief:

| Behaviour | Reference | Port |
|---|---|---|
| `baseline_path` is `<root>/summary.txt`, `None` for a single file | `tester.py:760` | `h-baseline-compare` prints `baseline: none` when the root is not a directory, or the file is absent (or is itself a directory) |
| `--update-baseline` on a single file stays exit 2 | `cli.py:260-262` | unchanged, already ported: `logos: test: --update-baseline needs a directory, not a single file` |
| Absent file → no comparison, `baseline: none`, exit 1 only on a failed case | `cli.py:276-280` | `h-none-line` |
| Present file → one `BASELINE <id> <detail>` per problem, then `baseline <path>: <n> regression(s)`, exit 1 on a failure or a problem | `cli.py:273-280` | `h-emit-problems` + `h-run`'s status |
| Three regression kinds | `compare_baseline` | `h-compare-run`, `h-compare-base`, `h-in-scope` |
| Leak total, full run, only at equal `OPTS`, case id `suite/leaks` | `compare_baseline` | `h-compare-leaks`, `h-opts-same` |
| No `OPTS` header → refusal naming the file and asking for a regenerate, exit 1 | `compare_baseline` | `h-judge` |
| Percent-encoded ids, problems sorted by id | `_encode_id` / `_decode_id`, `sorted(problems)` | `h-encode` (already there) / `h-decode`, `h-sort-problems` |

The three kinds, exactly as `compare_baseline`'s docstring states them: a case
in the run with no baseline record (`new case has no baseline result`); a case
recorded `PASS` that now fails (`regression: passed in baseline, now fails:
<detail>`); and a case recorded `PASS` a full run no longer contains
(`regression: passed in baseline, missing from this run`). A filtered run is
responsible only for the categories it ran — `h-in-scope` answers with
`summary.full or not scope or category in scope`, the reference's line 963. A
`FAIL` in both the baseline and the run is not a problem.

The no-`OPTS` refusal is the reference's sentence, verbatim:

```
logos: test: <path>: baseline has no OPTS header, so its leak total cannot be compared with this run; regenerate it with --update-baseline
```

## The split that makes it testable

`harness.logos` has no file-copy primitive, so a test that had to build a
baseline on disk would not be a test. The comparison follows
`harness_test.logos`'s four existing cases: pure functions, string literals.

- `h-baseline-parse : text → (records, total, OPTS text, problem)`. Every
  malformed line is a problem string carrying its line number, in the
  reference's shapes: `baseline line needs a status and a case`,
  `baseline status must be PASS or FAIL, found 'X'`,
  `leak total needs a number, found 'X'`,
  `levels must be spellings like -O0, found 'X'`. `\r\n` is handled the way
  `str.splitlines` handles it.
- `h-baseline-problems : records + total + OPTS + run + leaks + levels + full
  + scope → (ids, details)`. The algebra and nothing else.
- `h-baseline-lines : exists + path + text + run + … → lines to print, stderr
  lines, status`. This is where `baseline: none`, the refusal sentences and
  the count line are decided, so the absent-file and no-`OPTS` cases are pure
  too.
- `h-baseline-compare` is the edge: `is-dir`, `h-file-exists`, `read-file`,
  two print loops, the status. `h-run` calls it once, and only when the run
  is neither an update nor empty nor skipped — the reference's own order.

`h-decode` is `h-encode`'s inverse. It rebuilds bytes 32–126 from a printable
table and tab, newline and carriage return from literals; any other byte keeps
its `%XX` spelling, because the language cannot build a one-byte string that is
not a source literal. Matching is unaffected (both sides decode the same way),
so only the printed spelling of an exotic id could differ from Python's.

## Tests

`src/logosc/harness_test.logos` grows from four cases to twelve, one pure
assertion each:

| Case | Pins |
|---|---|
| `baseline-matches` | a matching baseline prints the count line with 0 |
| `baseline-fail-and-new-case-sorted` | PASS→FAIL with the run's detail, a new case, ids decoded (`exec/a%20b` → `exec/a b`), and the two lines sorted by id |
| `baseline-missing-in-full-run-and-filtered` | the same absent `PASS` is a regression in a full run and not in a filtered one |
| `baseline-leak-total-compares-only-at-the-same-options` | `suite/leaks` at matching `OPTS`; the same total is not compared at different `OPTS` |
| `baseline-refuses-a-file-without-options` | the exact refusal sentence |
| `baseline-refuses-an-unreadable-status` | a malformed line is refused with its line number |
| `baseline-absent-is-not-a-regression` | `baseline: none` |
| `baseline-id-round-trip` | `h-decode (h-encode "exec/a b/c%odd.logos")` |

The file is `12 passed, 0 failed, 0 leaked` at `-O0`.

## Measured

- **The corpus.** `./tools/logosc.sh test tests` prints 308 case lines,
  `308 passed, 0 failed, 10 leaked`, `baseline tests/summary.txt: 0
  regression(s)`, and exits 0; `git diff tests/summary.txt` is empty.
- **A pass that now fails.** A scratch suite under `build/w9` (`exec/one.logos`)
  is recorded with `--update-baseline` (which prints only `baseline
  build/w9/summary.txt: 1 cases`, the reference's early return), the case is
  changed to fail, and the run prints
  `BASELINE exec/one/works regression: passed in baseline, now fails: -O0:
  stdout: expected '2\n', got '1\n'; -O2: …` and exits 1.
- **A raised leak total.** The same suite recorded as `LEAKS 0` with a leaking
  `(leaks 1)` case prints `BASELINE suite/leaks regression: leak total 2
  exceeds baseline 0` and exits 1; the same run at `--opt -O0` does not compare
  the totals and exits 0.
- **No `OPTS`.** The same file with the header removed prints the refusal above
  on stderr, no count line, exit 1.
- **A single file.** `test src/logosc/harness_test.logos --update-baseline`
  exits 2 with the reference's sentence; `test <file>` prints `baseline: none`.
- **`--only`.** `test tests --only mem` prints `7 passed, 0 failed, 6 leaked`
  and `baseline tests/summary.txt: 0 regression(s)`, exit 0.
- **The fixed point.** `bootstrap/logosc` is rebuilt from this source in the
  same commit (`sha256 4ddac44a…`), and a `build/logosc` freshly built from the
  committed tree is byte-identical to it (`cmp`). `bash tools/selfhost.sh`: 364
  fmt files, 90 IR files, 14 resolve fixtures, 123 check fixtures, 2 unit files,
  0 differences, and gen2 == gen3 (the `cmp -s` at `tools/selfhost.sh:231` is
  silent, which is its only success signal).
- **Formatting.** `fmt` is a fixed point on both touched `.logos` files.
- **`bash tools/pr_gate.sh`**: 6/6.

## Consumers

`tools/accept.sh` counts `grep -c '^PASS '` over `test`'s output, so a second
line that is not a `PASS` line does not change `test corpus (308 cases)`.
`tools/selfhost.sh` never invokes `test`. `make suites` runs the three unit
files as single-file roots, which now end with `baseline: none`; the Makefile
discards the output and the status is the cases'.

## Differences that remain, and one finding

1. **An id with a byte outside printable ASCII** prints percent-encoded where
   Python prints the byte, because there is no way to construct such a byte
   as a string. The comparison is unchanged; `harness.md` and `main.md` say so.
2. **A multi-line detail** in a `BASELINE` line prints the run record's
   one-lined detail; Python printed `case.detail` raw. No corpus detail holds
   a newline, and a one-line-per-problem contract is the stricter reading of
   "print one `BASELINE <id> <detail>` line per problem".
3. **`OPTS` comparison** compares the token lists, not the raw strings, so
   `OPTS  -O0   -O2` equals `-O0 -O2`. Python compared tuples, which is the
   same rule; this is the tuple rule, spelled.
4. **Finding, not fixed here: a three-argument `str-concat` is accepted in the
   compiler's own multi-root build.** The refusal line was first written as
   `(str-concat path ":" (vec-get problem 0))`. The compiler built, and the
   compiled function printed `path:` — the third operand was dropped silently.
   Restoring that spelling today reproduces it (the malformed-status case then
   reads `11 passed, 1 failed`), while the same three-argument call as a
   standalone module is refused `E0102: str-concat takes two strings`. So the
   arity rule is not applied in every build — the gap depends on the root set,
   not on the call's shape — and a dropped operand is a miscompile. The shipped
   code uses the two-argument spelling; the checker gap needs its own change,
   with this reproduction as its starting point.

## Files

- `src/logosc/harness.logos` — 51 new functions: the decoder, the parser, the
  comparison, the sort, the pure report and the edge.
- `src/logosc/harness_test.logos` — eight cases and three helpers (`bt-check`
  drives the pure report, `bt-absent` the no-file case, `bt-print` the lines).
- `src/logosc/harness.md`, `src/logosc/main.md` — the contract, the new section
  and the two remaining differences.
- `bootstrap/logosc`, `bootstrap/logosc.sha256` — rebuilt stage-0.
- `tests/summary.txt` — untouched.

## Commits

- `31dba76 feat: the baseline comparison in the Logos harness (W9)`
- `docs: the W9 baseline comparison report` (this file)
