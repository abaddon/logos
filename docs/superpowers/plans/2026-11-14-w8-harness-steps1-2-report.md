# W8 step 3c-2, steps 1–2 — `gen2 test`: discovery, ids and the directive reader

Branch `feat/selfhost-w7-backend`, parent commit `159431b` (W8 3c-1b). The
harness notes (`2026-11-13-w8-harness-notes.md` §5) split `logosc test` into
seven steps and make Python the oracle at each. This task lands **step 1**
(discovery, category filtering, id derivation, ordering, `(test …)`
enumeration) and **step 2** (the directive reader with Python's exact detail
text). Nothing spawns a child process: a case whose directives are well formed
prints `PASS <id> -` without proving anything, and only a malformed directive
prints `FAIL <id> <detail>`. Steps 3–7 — child I/O, one level, both levels, the
summary and baselines — are untouched.

## What landed

- **`src/logosc/harness.logos`** (new module, `harness`, 617 lines):
  - `h-discover`: a missing root, a file root, a directory holding any known
    category (walked in `CATEGORIES` order, each category sorted) and any other
    directory (walked whole, sorted); `*.logos` only; `--only` filters by the
    file's category. Matches `tester._discover` (`222-250`).
  - `h-category-of`/`h-category-dir`/`h-relative`: the nearest ancestor named in
    `CATEGORIES`, default `exec`, and `relative_to(category_dir)` without its
    `.logos` suffix (`253-270`, `296`).
  - `h-tests`/`h-test`: every top-level `(test …)` node, `test.name` or
    `unnamed-<index>`, id `category/relative/name` (`323-345`, `496`).
  - `h-directive-detail`: `(expect (out|code|leaks|err-contains))`,
    `(expect-leak N)` and the collision between them, with `_expectation`'s
    check order (`_run_case` `505-514`, `_expectation` `640-721`).
  - `h-directive`/`h-expect-error`/`h-sidecar`/`h-expected`: the module-level
    `(expect-error …)` and the `.expect` sidecar, their disagreement, and
    `_expected_diagnostic`'s order of checks (`406-454`).
  - `h-run` is the entry point; it prints and returns the failure count, or `-1`
    for a missing root.
- **`src/logosc/main.logos`**: `(use harness)`, a `test` verb in the dispatcher
  (which must now accept a two-word command line, because `PATH` defaults to
  `tests`), and twelve `main-test*` functions. `--only C` (both spellings),
  `--opt`/`--opt=` with `argparse`'s level-swallowing (`--opt -O0 -O2` is two
  levels), one positional path, `--update-baseline` refused with exit 2 until
  W9. A missing root is exit 1 with Python's line; an unknown category is exit 2.
- **`src/logosc/harness.md`** — the module's contract: discovery order, the id
  table, the full sentence table, the order of the checks, and what steps 3–7
  still owe.
- **`src/logosc/main.md`** — synopsis, argv table, the `test` paragraph, the
  usage block, the twelve function rows, and the "no child process" bullet.
- **`tests/test_gen2_test.py`** — 8 tests, 48 s: the whole-corpus id column and
  order against `tests/summary.txt`, the category order, `--only`, a file root,
  a scratch tree of 25 malformed directives compared with `tester.run_suite`,
  and the three usage exits (a missing root, an unknown category, a second
  path).
- **`tools/selfhost-manifest.txt`** regenerated: 335 files (334 + the module).

## Evidence

All runs are on the committed tree, from the repository root, under
`ulimit -v 4000000`.

- **Ids and order — the acceptance.** `gen3 test tests` prints 308 lines, all
  `PASS <id> -`, exit 0, stderr empty. Its id column is byte-identical, in
  order, to `cut -d' ' -f2` of a live `python3 -m logos test tests` run
  (`308 PASS, 0 FAIL, 10 leaked`, exit 0), and to the same column of
  `tests/summary.txt`. Two binaries agree: `gen2-new` (built by Python) and
  `gen3-new` (built by `gen2-new` from the same 21 sources).
- **The count is 308, not the notes' 307.** `tests/summary.txt` at `159431b`
  holds 308 `PASS` lines; the one the survey predates is `type/test-body-type`,
  added by 3c-1b (`diff` of the two commits' baselines shows exactly that line).
  The brief's "307" is the previous commit's number, so the port was matched to
  the current baseline and to a live run of the current tree, not to 307.
- **The id edge cases match.** `--only mem` → the same 7 ids as Python; a
  category directory (`tests/mem`) → the same 7, still `mem/leak/…`; a nested
  non-category directory (`tests/regress/result-foreign-enum`) → the doubled
  `regress/result-foreign-enum/program/program`; a file root
  (`tests/exec/hello.logos`) → `exec/hello/hello`; a negative fixture
  (`tests/type/loop-move.logos`) → `type/loop-move`, no `/test` suffix.
- **The sort is the oracle's everywhere.** `sorted(Path)` (Python's
  `rglob` order) and `sorted(str)` (the port's byte sort) give the same list for
  `tests` and all eight category directories — 191 files, no difference — so
  the global sort is not merely equal on the concatenation.
- **Directive details — the second acceptance.** A scratch tree with one
  malformed variant per rule (26 fixtures): both implementations print
  byte-identical `FAIL <id> <detail>` lines, in the same order, for the 25 that
  the reader owns — from two `(expect …)` through `duplicate directive`, the
  arity-before-unknown order, `expect-leak`, the `(leaks …)` collision, every
  `expect-error` shape, and the three sidecar rules. `tests/test_gen2_test.py`
  pins the same tree against `tester.run_suite` so the sentences cannot drift.
  The 26th fixture is a nameless test: the reader accepts it and Python's
  *build* refuses it (`E0002 test needs a name`) — see Concerns.
- **Exit statuses.** Missing root → 1, `logos: test: nope: no such file or
  directory`; unknown `--only` → 2 with Python's sentence; a second positional
  path or a bare `--opt` → 2 with the usage block; `gen2 test` with no argument
  runs `tests` as Python's default does.
- **Formatting.** `python3 -m logos fmt` is a fixed point on both `.logos`
  files (md5 unchanged on a second run).

## Concerns

- **The 307 in the brief and the notes is one behind the tree.** The committed
  baseline at this parent is 308 and a live Python run agrees; the extra case is
  `type/test-body-type` from 3c-1b. Any later step that quotes 307 is quoting
  `40949bd`, not `159431b`.
- **A nameless test diverges, and the divergence is step 4's.** The id rule
  `unnamed-<index>` is implemented and reachable in a scratch tree, but Python
  reaches it only to be refused by the checker (`E0002 test needs a name`), so
  the port prints `PASS <id> -` where Python prints `-O0: build failed: …`.
  Fixing that here would mean implementing the build, which is step 4.
- **A file the parser refuses is reported as `parse failed: <message>`, not
  Python's `_run_unparsable`.** That branch needs the raw-text
  `EXPECT_ERROR` scan (no regex in the language) and is unreachable in
  `tests/**/*.logos`; the fixtures that must fail to parse live as
  `.logos.txt`, which discovery never sees. Recorded in `harness.md`, deferred
  by the notes' §3 item 7.
- **Skipped files are dropped, not reported.** A `*.logos` under a suite root
  that no category claims is `SKIP <path>` and exit 1 in Python. `tests/` holds
  none, and the skip list belongs with the exit status (step 6).
- **An empty run exits 0 here and 1 in Python** (`test: no cases found in
  <path>`), e.g. `--only mem` on a file root. Again step 6, which owns the
  summary line and the status.
- **`path-error` decides readability** (`access(R_OK|W_OK)`), so a file that is
  readable but not writable would be reported `cannot read …: Permission
  denied`. `fmt` makes the same bargain; no fixture is read-only.
- **`--update-baseline` is refused with exit 2** rather than silently ignored.
  The baseline is W9, and a flag that pretends to work is worse than one that
  says it does not.

## Gates

`bash tools/pr_gate.sh` on the committed tree: **6/6**.

```
PASS sign-off (precondition)
PASS unit tests            (1110 tests, 701.7 s)
PASS corpus
PASS acceptance
PASS manual drift
PASS formatting
PASS self-hosting
6/6 gates passed
```

`tools/selfhost.sh` inside that run: `selfhost: 335 files, 0 differences`
(334 + `harness.logos`), `ir: 65 files, 0`, `resolve: 14 fixtures, 0`,
`check: 123 fixtures, 0`, `unit: 2 files, 0`. The unit phase is the one that
matters for the new module: `gen2 build` and Python's `logos build` over the
whole 21-source set produce byte-identical IR, so the port lowers its own
harness code exactly the way the reference compiler does.

## Not done, and deliberately

Steps 3–7 of the harness (child stdin `/dev/null`, the 10 s bound and the
non-panicking spawn; one level; both levels and the cross-level comparison; the
whole-suite summary line; baselines and percent-encoded ids). The skip list, the
`_run_unparsable` branch, a negative fixture's judgement and
`test: no cases found` are named under Concerns and in `harness.md`.
