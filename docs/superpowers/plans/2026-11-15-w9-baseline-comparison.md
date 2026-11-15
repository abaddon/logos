# W9 — the baseline comparison

Written 2026-11-15 at `8cdd8c5`, after the cutover gate passed 6/6. This is the
last piece of the `test` verb's contract, and it is the only part of the
reference implementation's behaviour the port does not yet have.

## The gap, measured

`python3 -m logos test` printed **two** lines at the end:

```
308 passed, 0 failed, 10 leaked
baseline tests/summary.txt: 0 regression(s)
```

The port prints only the first. It also reads the baseline — `--update-baseline`
is ported and byte-identical, verified on the whole corpus — but it never
*compares* against it, so a case that passed yesterday and fails today reports as
a plain failure with no "this is a regression" framing, and a leaked total above
the recorded one is not caught at all.

`tests/summary.txt` is 310 lines: `LEAKS 10`, `OPTS -O0 -O2`, then one line per
case. `OPTS` exists because a baseline recorded at `-O0` cannot judge a run at
`-O0 -O2`; the reference refused a baseline without it rather than comparing
across levels.

## What must be true

1. **A passing run against a matching baseline** prints the second line with
   `0 regression(s)` and exits 0.
2. **A case that passed in the baseline and fails now** is counted as a
   regression, the count is printed, and the run exits 1 — even though the
   summary line already reports the failure.
3. **A leak total above the recorded one**, at the same levels, exits 1 and says
   so. This is the check that catches a leak introduced without any case
   failing.
4. **A baseline with no `OPTS` line** is refused with a request to regenerate,
   exit 1, rather than compared across levels.
5. **`--only CATEGORY`** compares only the cases it ran, and does not call the
   cases it skipped regressions.
6. **A missing baseline file** is not a regression: the reference prints the
   summary and stops.

`tests/summary.txt` itself must not change: the corpus already matches it
case for case, so a correct implementation leaves the file untouched and
`git diff` clean.

## Why this is not cosmetic

The baseline is the only mechanism that notices a *silent* change of behaviour:
the corpus is judged against each case's own `(expect …)` directive, so a case
whose expectation was weakened, or a leak total that crept up, passes the
per-case checks. The trailing line is what turns "308 passed" into "308 passed
and none of them used to fail".

## Order of work

1. Recover the exact reference behaviour. It lived in `logos/tester.py:760-800`,
   which the cutover deleted; the surviving record is
   `docs/superpowers/plans/2026-11-14-w8-cli-tail-report.md` (the
   `--update-baseline` parity work) and the `tests/summary.txt` format itself.
   Where the record is silent, prefer the behaviour that fails loudly.
2. Implement the comparison in `src/logosc/harness.logos`, next to the writer
   that already produces the same lines.
3. Pin it with `tests/summary.txt`-shaped fixtures: a matching baseline, one
   regressed case, a raised leak total, a missing `OPTS` line, a missing file,
   and an `--only` run. Each is a copy under `build/`, never the real file.
4. Rebuild `bootstrap/logosc` in the same commit (the source changes), and let
   `bash tools/selfhost.sh` prove the fixed point.
5. Add the trailing line to the `test` verb's contract in `src/logosc/harness.md`
   and to the manual's testing chapter if it describes the output.

## Acceptance

`./tools/logosc.sh test tests` prints both lines, the second reading
`baseline tests/summary.txt: 0 regression(s)`, exits 0, and leaves
`git diff tests/summary.txt` empty; a deliberately regressed copy exits 1 with
a non-zero count; and `bash tools/pr_gate.sh` is 6/6 on the committed tree with a
rebuilt stage-0.
