# `src/logosc/harness.logos` — discovery, ids and the directive reader

The first two steps of the `test` verb: which files a suite run covers, what
each case is called and in what order, and what a case's directives say. The
reference is `logos/tester.py`; Python is the oracle for every sentence here.
`main.md` owns the command line; this module owns the corpus.

`h-run` is the entry point: `(h-run ROOT ONLY)` prints one line per case and
returns the number of failures, or `-1` when `ROOT` does not exist. `main`
turns a non-zero count into exit 1 and an unknown `--only` into exit 2. Nothing
here spawns a process, and nothing here writes a file.

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

## What it does not do yet

The harness is seven steps (`2026-11-13-w8-harness-notes.md` §5) and this
module is steps 1–2. Deferred, with the Python it belongs to:

- **Running a case.** `_execute` (`556-583`) builds `--test NAME --opt LEVEL`,
  runs the binary with stdin `/dev/null`, a 10 s bound and a kill, and compares
  the four clauses. Until then a case whose directive is well formed prints
  `PASS <id> -` without proving anything, which is why the id column is the
  acceptance and not the status.
- **A negative fixture's judgement.** `_run_negative` (`456-482`) runs the
  checker over the file and its reachable set, and compares the code. This verb
  enumerates the case and prints `PASS`; the code is not checked yet.
- **`_run_unparsable`** (`348-389`) and the raw-text `EXPECT_ERROR` scan
  (`103`, `392-403`): a file the parser refuses is reported here as `parse
  failed: <message>`, which is Python's sentence only when the message happens
  to match. No tracked fixture fails to parse (the ones that must stay as
  `.logos.txt`, which discovery never sees), so the branch is unreachable in the
  corpus and is deferred rather than guessed.
- **Skipped files.** A file under a suite root that no category claims is
  printed as `SKIP <path>` and fails the run (`cli.py:241-255`). `h-discover`
  keeps the claimed files only, so a stray fixture would vanish instead of
  failing. `tests/` holds none; the skip set belongs to the whole-suite step
  (6), which owns the exit status.
- **The level loop, the summary line, the baseline** — steps 5–7. `main` parses
  `--opt` and refuses `--update-baseline` with exit 2 rather than pretending.

## Evidence

- **Ids.** `gen2 test tests` prints 308 `PASS <id> -` lines; their id column
  equals `cut -d' ' -f2 tests/summary.txt` (after its `LEAKS`/`OPTS` header)
  line for line, in order. `tests/summary.txt` at this commit holds 308 `PASS`
  lines, not the 307 the harness notes record — one fixture landed with W8
  step 3c-1b, and the baseline is that run's output.
- **`--only`.** `gen2 test tests --only mem` prints the same 7 ids as
  `python3 -m logos test tests --only mem`.
- **Malformed directives.** 26 fixtures under a scratch tree, one variant per
  rule above; the 25 that the reader owns produce byte-identical `FAIL <id>
  <detail>` lines from both implementations, in the same order. The 26th is a
  nameless test: the reader accepts it and Python's *build* refuses it
  (`E0002 test needs a name`), a divergence step 4 owns.
- **Exit status.** A missing root prints Python's line and exits 1; an unknown
  `--only` exits 2 with Python's sentence.
