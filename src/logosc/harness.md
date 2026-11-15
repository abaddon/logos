# `src/logosc/harness.logos` — discovery, running and the report

The `test` verb, six of its seven steps: which files a suite run covers, what
each case is called and in what order, what a case's directives say, how a case
is built and run at every level, how the levels are compared, and what the run
prints. It was written against the Python implementation's `tester.py` and
`cli.py`, which the cutover deleted; that implementation is the historical
oracle for every sentence here, and `./tools/logosc.sh test tests` is now the
behaviour itself. `main.md` owns the command line; this module owns the
corpus.

`h-run` is the entry point: `(h-run ROOT ONLY LEVELS UPDATE)` prints one line
per case, at every level, then the skipped files, then the summary line, and
returns the run's exit status. `main` turns an unknown `--only` into exit 2 and
checks the baseline root before the run. A case is built once per level and run,
the four clauses are compared, and the levels are compared with each other.
`UPDATE` is `--update-baseline`: at the end of such a run every case line is
recorded in `<root>/summary.txt` ("The baseline" below).

## Discovery

`tester._discover` (`222-250`) in order:

- A missing root is a suite failure, not a usage error: `logos: test: <root>:
  no such file or directory` on stderr, exit 1 (`232-233`).
- A file root is the whole set (`234-236`).
- A directory holding **any** directory named in `CATEGORIES` (`tester.py:80`:
  `parse`, `type`, `exec`, `mem`, `thread`, `generics`, `regress`, `diff`) is
  walked category by category in that order (`237-244`), each category's files
  sorted. Any other directory is walked whole and sorted (`245-247`).
- Only `*.logos` are fixtures. A `.logos.txt` is invisible to the walk.
- `--only C` filters by the file's category (`248-250`); an unknown category is
  refused by `main` before this module is called (`222-223`).

The two walk shapes matter for order: a suite root is **not** globally sorted.
`parse` comes before `type` because `CATEGORIES` says so, not because `p` sorts
before `t`. `h-walk-cats` therefore sorts each category on its own and appends,
while `h-discover` sorts a non-category root whole. `h-sort` is a byte
comparison (`sorted(Path)` is `sorted(str)` on this corpus), so a directory
holding both `a.logos` and `a/z.logos` keeps `a.logos` first, which a
per-directory recursion would get wrong.

`read-dir` is readdir order (`rt.c`), so every collection is sorted before it is
used. `h-exists` is `is-dir` or `path-error` empty, because `read-file` panics
where Python raises: an unreadable path must be a case detail, not a crash.

## Category and id

`tester._category` (`253-262`) is the nearest ancestor directory named in
`CATEGORIES`, defaulting to `exec` — a fixture outside the corpus is runnable
by definition. `_category_dir` (`265-270`) is that directory, else the file's
parent. The id is `category + "/" + relative_to(category_dir).with_suffix("")`
(`296`), and a `(test …)` case appends the test's name (`496`):

| fixture | id |
|---|---|
| `tests/exec/hello/prints.logos` | `exec/hello/prints/<test>` |
| `tests/type/loop-move.logos` (negative) | `type/loop-move` |
| a file the parser refuses | `category/relative` |

A test with no name is `unnamed-<index>`, where the index counts **test nodes**
in the file, not top-level forms (`334`). The checker refuses an unnamed test
(`E0002 test needs a name`) before it can be built, so the name rule is reached
in a scratch tree rather than in the corpus.

## The directive reader

`h-directive-detail` mirrors `_expectation` + `_clauses` + the legacy fold in
`_run_case` (`505-514`); `h-expected` mirrors `_expected_diagnostic`,
`_atom` and `_expected_from_sidecar` (`406-454`, `640-721`). A well-formed case
returns `""`; a malformed one returns the sentence Python raises, character for
character:

| rule | detail |
|---|---|
| two `(expect …)` | `test has 2 (expect ...) directives, wanted one` |
| two `(expect-leak …)` | `test has 2 (expect-leak ...) directives, wanted one` |
| no `(expect …)` | `test has no (expect ...) directive` |
| `(leaks N)` beside `(expect-leak N)` | `both (leaks ...) and (expect-leak ...) declare a count` |
| a clause that is not a form | `expect takes clauses, not atoms` |
| no clauses | `expect needs at least one clause` |
| repeated clause | `duplicate directive '(out ...)'` |
| wrong arity | `(out ...) takes one value` |
| non-string `out`/`err-contains` | `(out ...) needs a string` |
| empty `err-contains` | `(err-contains ...) needs a non-empty string` |
| non-integer `code`/`leaks` | `(code ...) needs an integer` |
| unknown clause | `unknown directive '(foo ...)'` |
| `expect-error` not one atom | `(expect-error ...) takes one code` |
| `expect-error` not `E0xxx` | `expect-error needs a code like E0101, found 'nope'` |
| two different `expect-error` | `two expect-error directives: E0101 and E0102` |
| sidecar over one line | `foo.expect holds more than one line` |
| sidecar not a code | `foo.expect needs a code like E0101, found 'nope'` |
| directive and sidecar disagree | `expect-error E0101 disagrees with foo.expect E0102` |

The order of the checks is part of the contract, because the first failure is
the sentence:

- Directives are counted before any is read, and legacy `(expect-leak …)` is
  validated before `(expect …)`, in `_expectation`'s order.
- Inside `(expect …)` a repeated clause is reported before its arity, and the
  arity before the unknown-kind test — so `(expect (code 1) (code))` is
  `duplicate directive '(code ...)'` and `(expect (foo))` is `(foo ...) takes
  one value`, not `unknown directive`.
- `_integer` is a regex on the token's text (`^[+-]?[0-9]+$`), so `1.5` is a
  number that "needs an integer", while `x` is an atom that does too.
- Module-level `expect-error` directives are all checked before the sidecar is
  read; a directive that is well formed but disagrees with the sidecar is the
  last check, and identical duplicates are allowed.
- The sidecar is read with `.strip()`, so a trailing newline is not "more than
  one line"; an interior one is.

`h-found` carries `(code, problem)` because the scan needs two answers and the
language has no tuple return. `h-directive` folds the whole top-level chain in
one loop: each node produces a `(code, problem)` pair and the loop stops
consuming at the first problem, which is exactly Python's early `return`.

## Child I/O — `_execute`

`h-execute` mirrors `tester._execute` (`556-583`), and the three things it took
from Python are the three it had to add to the language:

| what | Python | here |
|---|---|---|
| standard input | `stdin=subprocess.DEVNULL` (`567`) | the runtime opens `/dev/null` for every `run` child, so `read-all` sees end of file |
| a case's budget | `timeout=10.0` (`96`, `574-575`) | `(run out rargs 10000)`; a kill reports 124 and the detail is `-O0: timed out after 10s` |
| a child that cannot start | `could not run: …` (`576-577`) | the timed form's handle carries status `-1` and the reason in `(run-err r)`; the detail is `-O0: could not run: <prog>: <reason>` |
| a build's budget | none: clang is only bounded by the runtime | `(run self bargs 0)` — 0 means `RT_RUN_TIMEOUT_MS`, the same 90 s guard as before |

The two waits are deliberately different values with different owners: 90 s
protects a build (clang spends 27 s on the compiler's 18 MB unit), 10 s is one
test case's budget, and sharing one constant would make either a build that
dies too early or a hanging test that occupies the suite for a minute and a
half. `h-build-budget` returns 0 so the build cannot drift from the runtime's
own constant; `h-case-budget` returns Python's 10 000 ms.

The build is one child: `(run SELF ["build" PATH "--test" NAME "--opt" LEVEL
"-o" OUT] 0)`, where `SELF` is `(args)`'s first word — the compiler builds its
own test binaries. A non-zero status becomes `-O0: build failed: <first line>`,
which is Python's shape with the diagnostic's first line in place of
`_message`'s render. The binary then runs with no arguments and a 10 s budget.

The comparison is `_compare` (`614-637`) in directive order: stdout, exit
code, leaks, `err-contains`, joined by `"; "` and prefixed with the level, so a
case with two unmet clauses prints both. `h-leaks` counts `LEAK ` at the start
of a line, as `_execute` does (`579`). `h-repr` is Python's `repr` for the
characters that occur in practice — single quotes, and `\\`, `\'`, `\n`, `\r`,
`\t` escaped — so a detail is readable and equivalence-grade rather than
byte-identical for non-ASCII or control bytes.

## The level loop — `_run_case`

`h-test` is `tester._run_case` (`484-530`). The directives are read first, and
a malformed one fails the case before any child starts. Then `opts` is walked
in order — `-O0 -O2` unless `--opt` said otherwise — and for each level:

1. the binary path is Python's: `build/harness/<category>/<relative>/<NN>-<safe>.<LEVEL>.bin`,
   where `NN` is the test index, `<safe>` is the name with every byte outside
   `[A-Za-z0-9_.-]` replaced by `_` (`533-542`), and `<LEVEL>` is the option
   with every non-alphanumeric byte dropped (`-O0` → `O0`, empty → `O0`);
2. `h-execute` builds and runs it and answers an `h-outcome`: the detail string
   (empty when the case passed), whether the case ran at all, and what it
   printed and exited with;
3. an empty detail is not appended; anything else joins the case's problems
   with `"; "`, each already prefixed with its level (`521`, `530`);
4. a case that ran contributes an observation — stdout, stderr, exit code —
   and its `LEAK ` lines are added to the suite total even when the case
   failed (`580`). A case that did not run (build failure, timeout, a spawn
   that failed) has no observation: there is nothing to compare.

## The cross-level comparison — `_disagreement`

Two levels must agree on all three observation fields, or the compiler changed
meaning while optimising. `h-disagree-one` mirrors `_disagreement`
(`586-611`): the first observation is compared with each later one, field by
field, in the order stdout, exit code, stderr, and the case fails with

```
-O0 and -O2 disagree: stdout 'a' vs 'b', exit code 0 vs 1
```

The difference is a problem of the case in its own right, joined after that
level's problems with `"; "`. It is never repaired, and a case that failed at
one level but ran at both still gets the comparison.

## The report

`h-run` prints what `cli._test` prints (`239-277`), in its order: one
`PASS|FAIL <id> <detail>` line per case, one `SKIP <path>` per `*.logos` file
under a suite root that no category claimed, and the summary

```
<passed> passed, <failed> failed, <leaks> leaked
```

`h-pass` and `h-fail` are the only counters — every printed case line is one
of them, so a reader of the output and the summary cannot disagree. A run with
no case prints `test: no cases found in <path>`; a run with skipped files
prints `logos: test: <n> file(s) outside the known categories were skipped` on
stderr. Both, and any failed case, make the exit status 1, and that status is
`h-run`'s return value. A run without `--update-baseline` prints nothing after
the summary, where Python prints `baseline <path>: n regression(s)`; comparing
a run against the file is W9.

## The baseline

`--update-baseline` rewrites `<root>/summary.txt` (`tester.write_baseline`,
`760-830`). It is the only way that file is ever written, and once Python is
deleted it is the only way it can be: the file is the suite's memory, so its
bytes are Python's.

The format is two headers and one line per case, in **run order** — category
order, each category's files sorted, each file's tests in source order — never
sorted by id:

```
LEAKS 10
OPTS -O0 -O2
PASS parse/duplicate-fn -
```

A `PASS` line's detail is `-`; a `FAIL` line's is the run's detail with `\r`,
`\n` and `\t` escaped and the result cut to 240 bytes (`_one_line`, `745`).
The id is percent-encoded so a name holding a space cannot split the line:
`h-encode` keeps `[A-Za-z0-9]` and `/._-~` and writes every other byte as
`%XX`, which is `urllib.parse.quote(s, safe="/._-")` on UTF-8 — the same
spelling, so the same bytes.

A **full run** (no `--only`, a directory) replaces the file: headers, then every
case it ran. That is what drops a case whose fixture was deleted, and it is what
records the leak total and the levels it came from.

A **filtered run** merges (`h-baseline-merge`, `h-merged`). Each line already in
the file is rewritten if the run has that case, kept untouched if it does not,
and dropped when its category is the one the run covered in full and the case
did not come back — the filter's own ground, which a deleted fixture would
otherwise leave behind as a false regression on the next full run. Cases the
file does not know are appended in run order. The headers are the *previous*
file's `LEAKS` and `OPTS`, not the run's: a filtered run does not see the whole
suite, so its leak total is not the suite's. A run with no file to merge into
writes no headers at all — same lines, no total.

The write is unconditional: Python rewrites the file even when a run changes
nothing (`path.write_text` at `830`), and so does this. The run then prints
`baseline <root>/summary.txt: <n> cases` and exits 1 when any case failed,
Python's `cli.py:263-265`. The path is spelled as the root argument spells it,
because the language has no `cwd` (`main.md` records why); a `test` run's root
is normally the relative `tests`, which is exactly what Python prints.

Nothing is written when the run found no case or skipped a file: Python returns
1 before the write in both cases, and the merge would otherwise record a
truncated view as if it were a run. A refused root is `main`'s check, before
this module is called.

`h-write-text` is `rt_create` + `fmt-emit` + `close`, the same three calls
`main`'s `main-spit` makes; the three externs are declared here rather than in
`guide.logos` because this module is now the first one below `main` that writes
a file, and both `main` and `guide` reach them through `(use harness)`.

## What it does not do yet

The harness is seven steps (`2026-11-13-w8-harness-notes.md` §5) and this
module is steps 1–6: discovery, the directive reader, the child's I/O, one
level, both levels with their comparison, and the whole suite's report. What is
left, with the Python it belongs to:

- **The negative fixtures' judgement.** `_run_negative` (`456-482`) runs the
  checker over the file and its reachable set, and compares the code. This verb
  enumerates the case and prints `PASS`; the code is not checked. Every tracked
  negative fixture passes in Python, so the line matches, but it is not earned
  yet — a fixture whose code changed would still print `PASS` here.
- **`_run_unparsable`** (`348-389`) and the raw-text `EXPECT_ERROR` scan
  (`103`, `392-403`): a file the parser refuses is reported here as `parse
  failed: <message>`, which is Python's sentence only when the message happens
  to match. No tracked fixture fails to parse (the ones that must stay as
  `.logos.txt`, which discovery never sees), so the branch is unreachable in the
  corpus and is deferred rather than guessed.
- **The baseline's comparison** — `compare_baseline` (`760-976`): a
  regression, a case the run no longer contains, a new case with no recorded
  result, and a full run whose leak total exceeds the recorded one. Writing and
  merging are here ("The baseline"); judging a run against the file is W9. The
  run therefore ends at the summary line where Python prints
  `baseline …: n regression(s)`.
- **A malformed baseline.** `_read_baseline` raises a `SuiteError` naming the
  file and line for a status that is not `PASS`/`FAIL`, a `LEAKS` line without
  a number, or an `OPTS` line of non-levels. The merge here reads the headers
  it understands and treats every other line as a case line, so a corrupted
  file is rewritten rather than refused. No tracked baseline is malformed, and
  W9's comparison is where the diagnosis belongs.

## Evidence

- **Ids.** `gen2 test tests` prints one line per case (308 today); their id
  column equals `cut -d' ' -f2 tests/summary.txt` (after its `LEAKS`/`OPTS`
  header) line for line, in order. `tests/summary.txt` at this commit holds 308
  `PASS` lines, not the 307 the harness notes record — one fixture landed with
  W8 step 3c-1b, and the baseline is that run's output.
- **`--only`.** `gen2 test tests --only mem` prints the same 7 ids, in the same
  order, as `./tools/logosc.sh test tests --only mem`, and the same leak total
  (`6`) after the same summary shape. Two of the seven do not build in the
  port's lowering, so the statuses and the exit code differ; see below.
- **Malformed directives.** 26 fixtures under a scratch tree, one variant per
  rule above; the 25 that the reader owns produce byte-identical `FAIL <id>
  <detail>` lines from both implementations, in the same order. The 26th is a
  nameless test: the reader accepts it and Python's *build* refuses it
  (`E0002 test needs a name`), a divergence step 4 owns.
- **Exit status.** A missing root prints Python's line and exits 1; an unknown
  `--only` exits 2 with Python's sentence; a suite tree holding a `.logos` file
  outside every category prints `SKIP <path>` and the stderr sentence and exits
  1; a tree with no case prints `test: no cases found in <path>` after its
  summary and exits 1. All four match `./tools/logosc.sh test` on the same tree,
  except that Python's run ends with a baseline line.
- **Standard input.** `gen2 test tests/exec/read.logos` builds and runs both
  cases, prints two `PASS` lines and returns 0 in about a second. Before the
  redirect it hung: `read-all` in the child inherited the harness's terminal.
- **The case budget.** `src/logosc/fixtures/harness/sleep.logos` sleeps 20 s;
  `gen2 test` on it takes 10 s, prints `FAIL exec/sleep/sleeps-past-its-budget
  -O0: timed out after 10s` and exits 1 — Python's sentence, not a 90 s wait.
- **A child that cannot start.** `src/logosc/fixtures/harness/missing.logos`
  builds normally; when the compiler wrapper in
  `tests/test_gen2_test.py` removes the binary, the run reports `FAIL
  exec/missing/cannot-be-started -O0: could not run: <path>: No such file or
  directory` and exits 1 with empty stderr. Panicking R0006 would exit 2.
- **The exec corpus.** `gen2 test tests --only exec` reports `107 passed, 32
  failed, 4 leaked` over 139 lines at both levels; Python reports `139 passed,
  0 failed, 4 leaked`. The 32 failures are classified in
  `2026-11-14-w8-harness-steps4-6-report.md` §6, and every other line is
  Python's byte for byte.
- **The whole suite.** `gen2 test tests` prints 308 case lines and
  `273 passed, 35 failed, 10 leaked`; Python prints the same 308 lines,
  `308 passed, 0 failed, 10 leaked`, and then a baseline line. The 35 are the
  exec 32, the two `mem` cases of the same `match`-as-an-argument gap, and one
  `regress` case whose float comparison emits an integer compare over float
  constants. None of the three sets is a comparison the harness could have
  avoided: each case does not build.
- **The level loop and the levels' agreement.** `src/logosc/harness_test.logos`
  calls `h-level`, `h-safe-name`, `h-leaks`, `h-summary` and `h-disagree-one`
  directly; both implementations print `4 passed, 0 failed, 0 leaked` for it,
  and its `-O0 and -O2 disagree: …` case is the only pinned form of that
  sentence. `tests/test_gen2_test.py`'s `ReportTest` covers the rest through
  the binary: both levels by their binaries, `--opt` (and `--opt=-O0`)
  selecting a level, two agreeing levels staying silent, the skip line and the
  empty run.
