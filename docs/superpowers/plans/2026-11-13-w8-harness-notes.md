# W8 step 3c-2 — `logos/tester.py`, the specification `gen3 test` must meet
Read-only survey, 2026-11-14, `feat/selfhost-w7-backend`. No change is proposed to the harness: `logosc test` must match Python, quirks included, gated by design D3
item 4 (`docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md:109` — same pass count, same leak total). Measured: `tests/summary.txt:1-2` records `LEAKS 10` / `OPTS -O0 -O2` over 307 cases (307 `PASS`, 0 `FAIL`), i.e. 614 executions. 163 are `(test …)` nodes (counted by parsing every fixture), 144 negative files; the
inventory's "162 `(test …)` cases" (`docs/superpowers/plans/2026-11-13-w8-cutover-inventory.md:187-188`) is one low. By category: `exec` 139, `type` 105, `regress`
32, `parse` 14, `thread` 8, `mem` 7, `generics` 2, `diff` 0.

## 1 What it does, end to end

- **Entry.** `cli._test` checks the `--update-baseline` root (`logos/cli.py:186-210`), calls `tester.run_suite` (`231`), prints (`239-243`), then handles
  empty/skipped/baseline (`245-277`).
- **Discovery** (`logos/tester.py:222-250`). A missing root raises `SuiteError` (`232-233`) → exit 1 (`cli.py:235-237`). A file root is the whole set
  (`234-236`). A directory holding any known category walks category by category in `CATEGORIES` (`80`) order (`237-244`), each `sorted(directory.rglob("*.logos"))`
  (`242`); every `*.logos` under the root that no category claimed becomes `skipped` (`243-244`) and fails the run (`cli.py:249-255`). Any other directory is
  `sorted(root.rglob("*.logos"))`, no skips (`245-247`). `--only` filters by `_category` (`248-250`). Only `*.logos` are fixtures; a `.logos.txt` is invisible
  (`242`, `246`). Defaults: `OPTS = ("-O0","-O2")` (`93`), 10.0 s timeout (`96`).
- **Category and id.** Nearest ancestor directory named in `CATEGORIES`, default `exec` (`253-262`); `_category_dir` the same else the file's parent (`265-270`).
  The key is `relative_to(category_dir).with_suffix("").as_posix()` (`296`): `exec/hello/prints` for a case (`496`), `type/loop-move` for a negative file (`469`).
- **Per file** (`292-345`). Read UTF-8 (`298`), parse (`310`); a parse failure diverges to `_run_unparsable` (`311-312`); a module-level `(expect-error …)` or a
  `.expect` sidecar selects `_run_negative` (`315-321`, `406-454`); else every top-level `(test …)` node is a case (`323-325`, `333-345`), named `test.name` or
  `unnamed-<index>` (`334`). A file with neither prints nothing (`326-332`) — how `diff` holds C-twin programs.
- **Per case** (`484-530`). Id `category/relative/name` (`496`); one `(expect …)` (`498-504`), legacy `(expect-leak N)` folded in and a collision rejected
  (`505-514`); per level build to `build/harness/<category>/<relative>/<NN>-<safe>.<level>.bin` (`533-542`) via `driver.run_test` (`561`, a debug build:
  `driver.py:195-233`), run with `stdin=DEVNULL`, captured stdout/stderr, UTF-8-replace and the timeout (`565-573`); a leak is a stderr line starting `LEAK `
  (`579`), added to the suite total even when the case fails (`137-139`, `580`); unmet clauses are reported in directive order with both values (`614-637`); failures
  join with `"; "` (`530`).
- **Cross-level disagreement** (`516-530`, `586-611`). Observations are `(stdout, stderr, exit)` (`582`); each later level is compared field by field — stdout,
  exit code, stderr — and a difference is a failure of the case in its own right (`524-529`, `603-608`). Never repaired.
- **`expectation_of`** (`640-647`) is `guide`'s reader too; clauses `out`/`err-contains` (string) and `code`/`leaks` (integer), one value each, duplicates and
  unknowns rejected (`674-721`).
- **Summary and baseline** (`760-976`). `summary.txt` at the suite root, never a file (`760-769`). A full run replaces it — `LEAKS N`, `OPTS …`, one `<status>
  <encoded id> <detail>` line per case (`784-804`, `823-830`); a filtered run merges, rewriting what it ran and dropping a stale line only under a covered category
  (`805-822`). `compare_baseline` reports PASS→FAIL, a PASS missing from the run, a new case with no result, and a full run's leak total above the baseline at equal
  levels (`913-976`); a baseline with no `OPTS` line is refused, not compared (`941-945`).

## 2 The exact output contract

`cli.py:239-243`, in this order:

```
<status> <raw case id> <detail>     one per case in run order; detail "-" on PASS
SKIP <path>                         one per unclaimed file, sorted (cli.py:241-242)
<passed> passed, <failed> failed, <leaks> leaked      (cli.py:243)
test: no cases found in <path>      only when no case was recorded (cli.py:245-247)
```

then on a suite root: `BASELINE <id> <detail>` lines plus `baseline <path>: <n> regression(s)` if a baseline file exists, else `baseline: none` (`cli.py:271-276`);
with `--update-baseline`, `baseline <path>: <n> cases` (`cli.py:263-265`). Exit 1 on any failure, any skipped file, an empty run or any regression; 2 on usage
(`cli.py:222-277`). A skipped file also prints one `logos: test: …` line on stderr and returns before the baseline step (`cli.py:249-255`).

Byte-identical: the status word, the raw (unencoded) id, the `-` detail, case order (category, then path, then source), the three summary numbers, the trailing
baseline line, the exit status. Percent encoding belongs to `summary.txt` only (`898-910`), never to stdout (`240`). Equivalence-grade only: the `repr` of
stdout/stderr in details (`604`, `628`, `635`), `"{opt}: build failed: …"` (`563`), `"{opt}: timed out after {timeout:g}s"` (`575`), and `_one_line`'s `\r`/`\n`/`\t`
escapes with 237+3 truncation (`745-750`).

Correction to the brief: `tests/test_selfhost.py` does not read this output. It matches five `^selfhost:|ir:|resolve:|check:|unit: N files, M differences$` lines
from `tools/selfhost.sh` (`tests/test_selfhost.py:29-39`, `53-72`) and never runs the harness. The consumers that do are `tools/accept.sh:77-87` (counts `^PASS `,
fails at zero) and `tools/pr_gate.sh` gate 2 (exit status only). No committed parser reads detail text, and a green run is 307 `PASS <id> -` lines, one summary line,
one baseline line.

## 3 What it needs from the language

Lowered already: `read-file` (`lower.logos:1707-1708`), `read-dir` (`1695-1696` → `lo-readdir` `5250`; `rt.c:865-905`, entry names in readdir order, `.`/`..` skipped),
`is-dir` (`1698-1699` → `5164`), `mkdirs` (`1701-1702` → `5192`), `path-error` (`1704-1705`), `args` (`1710-1711`), `run` (`1713-1714` → `5395`; `rt.c:1186-1411`),
`run-status`/`run-out`/`run-err` (`1716-1719` → `5368`/`5376`; `rt.c:1414-1440`), `print`/`println` (`1765-1767`, `2945`), `str-*` (`1632-1707`), vectors,
`str-from-i64` (`5000`), file writing via `rt_create`/`rt_write` (`main.logos:19-23`, `140-150`), the clang link with `-DLOGOS_DEBUG=1` for a test build
(`main.logos:256-279`, flag `264-266`).

Reading directives in Logos is possible: one `(vec node)` with `text`/`tok`/`first`/`next`/`name` (`tree.logos:3`), tok `-1` form, `2` atom, `3` string, `4` number
(`tree.md:78-86`), named-kind rules (`tree.md:99-110`), string tokens already unescaped (`lex.logos:118-131`, `198`). `LEAK ` comes from `rt.c:362` and
`lo-leak-report` (`lower.logos:2438`, called `3525`); the test entry from `lo-test-find`/`lo-test-main` (`lower.logos:6044-6057`, `6113`) driven by `build --test`
(`main.logos:441-443`, `493-495`, IR path `173-188`).

Missing, hardest blocker first:
1. **A child with stdin `/dev/null`.** `rt_run_start` duplicates only stdout and stderr (`rt.c:1236-1248`) and never opens fd 0; `tester.py:567` passes `DEVNULL`.
   `tests/exec/read.logos:3-14` calls `read-all` expecting `"0\n"`, so a full `gen3 test` hangs rather than diverges.
2. **A 10 s bound with a kill.** `RT_RUN_TIMEOUT_MS` is a compile-time 90 000 (`rt.c:1109-1110`, used `1272`); expiry `SIGKILL`s (`1346-1355`) and reports status
   `124` (`1400`), indistinguishable from an exit-124 program, with no `timed out` fact (`tester.py:574-575`). Needs a per-call timeout.
3. **A spawn that can fail.** It panics on spawn failure (`rt.c:1127-1139`, called `1231`, `1234`); Python reports `could not run: …` as a case failure
   (`tester.py:576-577`). Failure-path only.
4. **`repr` of a string** for every stdout/stderr detail (`tester.py:604`, `628`, `635`). Failure-path only.
5. **Percent-encoded ids and the baseline merge/compare** (`tester.py:903-905`, `784-976`) — W9 by the inventory's split
   (`2026-11-13-w8-cutover-inventory.md:196-199`); needs a byte→hex encoder, only `str-from-i64` exists (`LOGOS.md:760`).
6. **Sorted paths** — `read-dir` is readdir order (`rt.c:885-905`), Python sorts (`tester.py:242`, `246`); `main-sort` (`main.logos:873`) exists, and `sorted(Path)`
   == `sorted(str)` on this corpus (verified), so a byte sort suffices.
7. **Not needed for the gate:** `_run_unparsable` (`348-389`) and the raw-text `EXPECT_ERROR` scan (`103`, `392-403`) — no `tests/**/*.logos` fails to parse today
   (verified; such fixtures live as `.logos.txt`, unseen by `_discover`). Also non-gating: the port's checker has no `test` branch
   (`2026-11-13-w8-cutover-inventory.md:105-109`), so a type error inside a test body is caught by Python only.

## 4 The state it keeps

Per run: `Summary` — `passed`, `failed`, `failures`, `leaks`, `cases`, `categories`, `opts`, `covered`, `full`, `skipped` (`tester.py:133-165`); `leaks` sums every
execution, failing cases included (`137-139`, `580`). Per level: the binary path (`533-542`), the `(stdout, stderr, code)` observation (`582`), that level's problems
(`516-523`), its leak count (`579`). Per category: `_category`/`_category_dir` (`253-270`), `covered` (`273-289`), file order (`239-242`). Per file: the relative id
(`296`) and the test index, which only disambiguates the binary name (`334`, `540`).

- `--only C` must name a category (`202-203`), filters files (`248-250`), narrows `covered` (`284-289`), forces `full = False` (`212-216`).
- `--opt` replaces the level tuple (`204`); totals compare only at equal levels (`966-972`).
- `--update-baseline` is refused for a file and for a category directory (`cli.py:186-210`); full replaces (`801-804`), filtered merges and drops stale lines
  only under `covered` (`805-822`), headers always rewritten (`823-828`).

## 5 The smallest decomposition

Python is the oracle at every step, on the same tree.

1. **Discovery and ids.** `test PATH [--only C] [--opt O]…`, walk with `is-dir`/`read-dir`, sort, filter, derive ids, enumerate `(test …)`. Evidence:
   `tester.py:222-270`, `323-345`; `lower.logos:1695-1699`; `main.logos:873`. Acceptance: the id column of `gen3 test tests` equals `cut -d' ' -f2` of Python's run
   (307 ids, same order).
2. **Directive reader.** `(expect (out|code|leaks|err-contains))`, `(expect-leak N)`, `(expect-error …)` plus sidecar, and the malformed sentences. Evidence:
   `tester.py:406-454`, `640-721`; `tree.logos:3`, `tree.md:78-110`. Acceptance: on a temp tree with one malformed variant per rule, both fail with the same detail
   text.
3. **Child I/O.** stdin `/dev/null`, 10 s kill, non-panicking spawn. Evidence: §3 items 1-3; `tests/exec/read.logos:3-14`. Acceptance: `gen3 test
   tests/exec/read.logos` passes both cases without inheriting the terminal, and a 20 s fixture prints `-O0: timed out after 10s`.
4. **One level.** Build `--test NAME --opt -O0`, run, compare four clauses, count `LEAK `, print `PASS|FAIL <id> <detail>`. Evidence: `tester.py:484-583`, `614-637`.
   Acceptance: `gen3 test --only mem` prints the 7 `PASS mem/… -` lines and Python's `7 passed, 0 failed, N leaked`, exit 0.
5. **Both levels.** Loop `opts`, keep observations, add the cross-level comparison and the suite total. Evidence: `tester.py:516-530`, `586-611`. Acceptance: `gen3
   test --only exec` prints 139 PASS lines and Python's `139 passed, 0 failed, K leaked`, exit 0.
6. **Whole suite.** `gen3 test` on `tests`, plus the trailing baseline line. Evidence: `cli.py:239-277`. Acceptance: stdout equals Python's byte for byte through the
   summary line (307 pass, 0 fail, 10 leaked), differing only in the baseline line until W9.
7. **Baselines (W9).** Write/merge/compare, percent-encoded ids, `OPTS` refusal. Evidence: `tester.py:760-976`; inventory `196-199`. Acceptance: `--update-baseline`
   leaves `git diff` clean, and deleting one case fails `gen3 test` at exactly the id Python names.
