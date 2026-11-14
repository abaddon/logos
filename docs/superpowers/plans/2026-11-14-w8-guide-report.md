# W8 step 4 — `guide`: the manual, its manifest, and the drift check

Branch `feat/selfhost-w7-backend`, commit `e61cd31`. The reference is
`logos/guide.py`, `logos/diag.py` and `logos/cli.py:_guide`; Python is the
oracle on the same tree, and the acceptance is byte equality, not resemblance.

**The three acceptances hold on a binary the port built:**

| # | acceptance | result |
|---|---|---|
| 1 | `gen3 guide` is byte-identical to `docs/LOGOS.md` | **yes** — 24,643 bytes, `cmp` clean |
| 2 | `gen3 guide --json` is the same 7-key manifest | **yes** — 18,808 bytes, `cmp` clean vs `python3 -m logos guide --json` |
| 3 | `gen3 guide --check` passes, and fails on an edited chapter | **yes** — exit 0 with one line; exit 1 with Python's stale report in a scratch tree |
| 4 | can the gate run the port's `--check`? | **yes, today**, from the binary the self-hosting gate already builds; the gate does not call it yet. §7 gives the patch and the two costs. |

`tools/pr_gate.sh` on `e61cd31`: **6/6 gates passed**, exit 0 (log:
`build/w8guide/pr_gate2.log`). The self-hosting gate's five phases:
`selfhost: 364 files, 0 differences`, `ir: 90 files, 0 differences`,
`resolve: 14 fixtures, 0 differences`, `check: 123 fixtures, 0 differences`,
`unit: 2 files, 0 differences`.

`gen2` below is the port built by Python, `gen3` the port built by the port
(`gen2 build src/logosc/*.logos src/std/map.logos src/std/str.logos -o gen3`).
Every number in this report is from one of those two binaries under
`ulimit -v 4000000`, or from `python3 -m logos` on the same tree.

```
$ build/w8guide/gen3 guide | cmp - docs/LOGOS.md && echo identical
identical
$ build/w8guide/gen3 guide --json | cmp - <(python3 -m logos guide --json) && echo identical
identical
$ build/w8guide/gen3 guide --check
guide: docs/LOGOS.md is current        # exit 0
$ (cd build/w8guide/scratch && gen3 guide --check); echo $?
docs/LOGOS.md is stale: 2 line(s) to add, 2 line(s) to remove; run `logosc guide > docs/LOGOS.md`
--- docs/LOGOS.md (committed)
+++ generated
@@ -45 +45 @@
-  (expect (out "42\n-7\n255\n…
+  (expect (out "42\n-8\n255\n…
@@ -80 +80 @@
--7
+-8
1
```

The stale report is `difflib.unified_diff(..., n=0)`'s text, line for line, when
the tree is stale for the ordinary reason (a chapter edited, a message changed)
— §6 says where that stops being true.

## 1 What actually had to move

`docs/superpowers/plans/2026-11-13-w8-cutover-inventory.md` §4 lists ten tables
that existed only in Python. Nine of them are data with no logic in them; the
tenth was the chapter walk, which is `fmt` plus `harness`'s directive reader.
They now live in `src/logosc/guide.logos` (1,855 lines) and in the two modules
that already owned the lists:

| table | entries | where it lives now | who else reads it |
|---|---|---|---|
| `diag.CODES` + message | 35 × 2 | `g-codes` | — |
| `guide.FORM_DOCS` | 88 × 3 (name, arity, meaning) | `g-form-docs` | — |
| `guide.TYPE_ARITY` | 12 × 2 | `g-type-arity` | — |
| `guide.TYPE_MEANING` | 12 × 2 | `g-type-meaning` | — |
| `guide.RULES` | 10 × 2 (text, where enforced) | `g-rules` | — |
| `guide.CHAPTER_TITLES` | 20 × 2 | `g-titles` | — |
| `check.RESERVED_FORMS` | 49 | `g-reserved-forms` | — (see §5) |
| `check.RESERVED_PREFIXES` | 4 | `g-reserved-prefixes` | — |
| `check.RESERVED_VARIANTS` | 19 | `g-reserved-variants` | — |
| `types.PRIMITIVES` | 16 | **`types.logos`: `type-primitives`** | `type-primitive?` |
| `types.FORMS` | 12 | **`types.logos`: `type-forms`** | (see §2) |
| `tester.CATEGORIES` | 8 | **`harness.logos`: `h-categories`** | `h-known-category` |

`type-primitive?` and `h-known-category` were chains of string tests with no
list behind them — the list was the Python one. Both now scan the table, so the
checker's whitelist, the suite's category order and the manual's two tables are
one copy each. That refactor is behaviour-preserving: `type-primitive?` already
built and freed a 16-element vector per call, and the 308-case corpus, the 123
checker fixtures and the 14 resolver fixtures are unchanged.

The reserved tables are the exception and are reported rather than merged: see
§5.

### What is *derived*, not transcribed

Python computes part of the manual from other tables, and so does the port, so a
table cannot change without the manual changing:

- a primitive's `kind`, `bits`, `signed` and sentence come from its name
  (`g-prim-kind`, `g-prim-bits`, `g-prim-signed`, `g-prim-meaning`), exactly
  `_build_types`;
- the equality operators' meaning is built from the scalar types the primitive
  list names (`g-scalars` → `:i8, :i16, …, :bool, :str; \`:str\` compares
  bytes`), exactly `_build_operators`;
- the composite type forms appended after the 88 documented forms are the
  `type-forms` names `g-form-docs` does not already document (`g-forms`):
  `arr`, `vec`, `own`, `ref`, `fn*`, `res`, `opt`, `shared` — 96 rows in all,
  `_build_forms`'s append and its "a new form cannot be forgotten" rule;
- `guide-consistent` refuses to build when a `type-forms` name has no arity or
  meaning, or when either table names a form the compiler does not — the
  `RuntimeError` in `_build_forms`, as an exit-1 line.

The remaining 514 `vec-push` lines are literal data. They were transcribed by a
one-shot script (`build/w8guide/gen_tables.py`, not committed: it imports
`logos.guide`, so it dies with Python in step 5) and then *proved* by the byte
equality of both outputs — a typo in 600 strings could not survive acceptance 1
and 2. From here the Logos tables are the source of truth; Python remains only
the oracle until it is deleted.

## 2 The generation, and why it is shaped this way

Logos has no module-level constants, no static arrays and no comments. A table is
therefore a function taking an out-parameter — `(fn g-codes :void ((out (ref
(vec :str)))) …)` — which is the idiom the rest of the port already uses
(`type-primitive?`, `lo-*`). Entries are flat with a fixed stride (`g-lookup`,
`g-field`) rather than parallel vectors per column, so nothing can fall out of
alignment.

The markdown is a `<vec :str>` of lines joined with `"\n"` (`g-manual`,
`g-join`), which is `"\n".join(lines)`; the manifest is the same for its lines
and ends with a `"\n"` that `print` would have added. Tables print through
`g-table` → `g-row-at` → `g-cell`, which escapes `|` and newlines.

Nothing in the layout was reinterpreted. The cheat sheet's example, the
`--json`/`--check` pointer, the "20 chapters in learning order" sentence and the
runtime-panic paragraph are copied from `build_markdown` character for
character, including the `"3\n"` in the sample, which is the two characters a
Logos literal spells (`"  (expect (out \"3\\n\") (code 0))"`).

### Chapters: the printer's text, through a file

A chapter is embedded as `fmt.render(root)` — the printer's output, not the
file's bytes — because a chapter written less tidily must still print
canonically. The port's printer writes to a file descriptor and Logos has no
in-memory sink, so `g-render` writes `build/.guide-chapter.logos`, reads it back
and unlinks it. That is the only write `guide` does; the manual goes to stdout
and `--check` only reads the committed file.

The alternative — read the file and skip the printer — is byte-identical on
every tree the formatting gate passes, because `docs/manual` is formatted by that
gate and `fmt` is a fixed point on all 364 tracked `.logos` files. It is *not*
equivalent on a tree where a chapter has been hand-edited into non-canonical
layout: Python would print the canonical form, and the file-reading version
would print what is on disk. The scratch file keeps the port faithful to the
oracle in that case for one `build/` path, which is git-ignored.

Directive reading is `harness`'s: `h-child-find` for the first `(test …)` node
and `h-expect-values` for `(out …)`/`(code …)` — the same reader `test` uses,
which is why the inventory puts `guide` after `test`. A chapter with no test, or
a test with no `(expect (out …))`, prints `logos: guide: <chapter>: …` and exits
1 where Python raises `ValueError`.

## 3 The manifest

`guide-manifest` prints `json.dumps(build_manifest(), indent=2)`: seven keys in
insertion order, `forms` (96), `types` (16), `operators` (17), `builtins` (2),
`reserved` (49/4/19), `codes` (35), `categories` (8). `bits` is a JSON number and
`signed` a JSON boolean, not strings, and the *ordering* of each key is the
manual's: a form's arity and meaning come from the same rows the markdown table
prints.

`g-json-str` escapes by byte the way `json.dumps(ensure_ascii=True)` does:
`\"`, `\\`, `\b \f \n \r \t`, `\u00XX` below `0x20`, and `\u00XX` at or above
`0x7f`. Every table is ASCII, so the last clause never fires today; a non-ASCII
meaning would need a UTF-8 decoder to agree for a multi-byte character, and
`guide.md` says so.

## 4 `--check`, and the one place the text is not difflib's

Equal bytes: `guide: docs/LOGOS.md is current` on stdout, exit 0 — the line the
gate's output would carry. Missing: `docs/LOGOS.md is missing; run \`logosc
guide > docs/LOGOS.md\``, exit 1. Stale: the summary line, `---`/`+++`, then the
first fourteen diff lines, exit 1.

The diff is an LCS: `g-dp` fills a (n+1)×(m+1) table bottom-right to top-left,
`g-step` walks it preferring a removal on a tie (so a replaced line prints `-`
then `+`, as difflib does), and `g-diff-lines` groups the runs into hunks with
`@@ -a,b +c,d @@`, omitting `,1` exactly as `_format_range_unified` does.
Verified byte-identical to `check_current()` for a one-line edit, two hunks
included.

It is **not** `difflib`'s Ratcliff/Obershelp. For an edit that only changes
lines, the two agree; for a rewrite that moves blocks around they can report
different added/removed counts, and the hunk boundaries can differ. Above four
million line pairs (n·m), `g-stale-rough` falls back to trimming the common
prefix and suffix into one hunk, so a pathological comparison cannot allocate
its way out of memory. This is the only place `guide`'s *text* differs from
Python's, and it is on the failure path: the gate and the tests read the exit
status and the success line.

## 5 The one table that did not merge: `atomic`

`check.RESERVED_FORMS` has 49 names; the port's `check-reserved-name` chain has
50. The extra is `atomic`:

```
$ python3 -m logos build x.logos      # (fn atomic :i64 () (ret 1)) + a call
E0102 x/main/2/0: atomic takes a type and an initial value     # the CALL is refused
$ gen2 build x.logos
x/atomic: E0003: reserved form name                            # the DEFINITION is refused
```

Python lets a function be *defined* as `atomic` and then has no way to call it
(`(atomic …)` is always the form), so it refuses the call with `E0102`; the port
refuses the definition with `E0003`. `atomic` is a form head, so the port's
reading is the stricter one, but Python is the oracle and the manual must
describe the compiler whose tables it prints.

So `g-reserved-forms` is Python's 49, and `check-reserved-name` keeps its chain
with the extra name. That is a **checker** divergence, pre-existing and
unrelated to `guide` (no fixture pins it: no tracked `.logos` defines `atomic`).
I did not change it — a check-parity decision belongs with the checker, not with
the manual — but the fix is one line: drop the `(str-eq name "atomic")` test, or
point the predicate at the `g-reserved-forms` table once it is the same 49.
`guide.md` records it next to the table.

Everything else matched: the port's variant list is exactly Python's 19, its
primitive list exactly the 16, and the 12 type forms in the same order.

## 6 What it does to the other gates

- `selfhost: 364 files, 0 differences` — the new `guide.logos` is formatted
  canonically and `gen2 fmt` is a fixed point on it, as on every tracked
  `.logos` file.
- `ir: 90 files, 0 differences` and `unit: 2 files, 0 differences` — the port's
  lowering emits Python's IR for `guide.logos` too, on the whole unit. Nothing
  in the new module is a form the backend cannot emit; that is what the gate's
  phase five proves on every run, and it passed on the first committed tree.
- `resolve: 14 fixtures, 0 differences`, `check: 123 fixtures, 0 differences` —
  unchanged by the `type-primitives`/`h-categories` refactors.
- `308 passed, 0 failed, 10 leaked` for both `python3 -m logos test` and
  `gen2 test tests`; `baseline tests/summary.txt: 0 regression(s)`.
- `make test`: 1,131 tests (1,125 before this step), which now include
  `tests/test_gen2_guide.py` — six cases: markdown vs Python, manifest vs
  Python, check on the committed tree, check on a copy, check with an edited
  chapter, check with the manual missing. It builds its own `gen2` once, as the
  `fmt` and `test` verb tests do, and costs about 52 s.
- `tools/selfhost-manifest.txt`: 363 → 364 paths.

## 7 Can the gate run the port's `--check`?

**Yes, today, one command.** The self-hosting gate already builds the port at
`build/selfhost/gen2` from the tree under test, and on this commit:

```
$ build/selfhost/gen2 guide --check
guide: docs/LOGOS.md is current        # exit 0
```

What it takes to have the gate *call* it, in order of size:

1. **Add a phase to `tools/selfhost.sh`** (recommended). The phase has the
   binary, the corpus and the manual in hand, and the gate's meaning — "the
   port reproduces what Python produces" — already covers this claim. Six lines
   after phase five: run `"$BIN" guide --check`, print
   `guide: docs/LOGOS.md is current` on success or the port's one-line report
   and a `guide: 1 difference` summary on failure, and update the header
   comment and `tests/test_selfhost.py`'s summary regexes if a new line is
   added. Cost: one process start, no build. Nothing is re-ordered.
2. **Re-order `pr_gate.sh` and call the port in `gate_guide`.** Move
   `run_gate "self-hosting"` before `run_gate "manual drift"`, then
   `gate_guide` becomes `python3 -m logos guide --check && build/selfhost/gen2
   guide --check`. Cost: the gate order is documented in `AGENTS.md` and pinned
   by `tests/test_contributing.py` (six commands, this order), so both move in
   the same commit; and the manual-drift gate would then depend on a binary
   another gate built, which is exactly the coupling the six-gate split avoids.
3. **Build the port inside `gate_guide`** (`python3 -m logos build … -o
   build/pr_gate/gen2 && build/pr_gate/gen2 guide --check`). Cost: a second
   ~45 s whole-set build per gate run, duplicating the self-hosting gate's.

I did not change `pr_gate.sh` or `selfhost.sh`. Acceptance 3 holds, so the
change is allowed by the brief, but it edits a gate contract that `AGENTS.md`
and `test_contributing.py` pin, and the honest cutover — one gate that builds
the compiler and then judges everything the compiler says about itself — is
step 5's decision, not this step's. Until then the manual drift gate runs
Python's generator, and the self-hosting gate independently proves the port
reproduces its bytes.

## 8 Files

| file | change |
|---|---|
| `src/logosc/guide.logos` | new: the ten tables, the markdown, the manifest, `--check` |
| `src/logosc/guide.md` | new: what the module is and what it does not do |
| `src/logosc/types.logos` | `type-primitives`, `type-forms`; `type-primitive?` scans the first |
| `src/logosc/harness.logos` | `h-categories`; `h-known-category` scans it |
| `src/logosc/main.logos` | `(use guide)`, the `guide` verb, the usage line; the `rt_create`/`close`/`unlink` declarations move from here to `guide.logos`, which `main` depends on, so both modules can create a file |
| `src/logosc/main.md` | the usage block, the verb table, and the `guide` paragraph |
| `tests/test_gen2_guide.py` | new: six cases against Python and the committed manual |
| `tools/selfhost-manifest.txt` | 363 → 364 |

## 9 Concerns

1. **The `atomic` divergence (§5)** is a checker difference the manual now
   surfaces: the manual's reserved list is Python's 49, the port's rule has 50.
   Either the checker drops the extra name or the manual is one name short of
   the compiler it documents.
2. **The diff is LCS, not difflib (§4)**: same added/removed counts for
   line-changing edits, not guaranteed for moved blocks. If the gate ever
   compares `--check`'s stderr, that is the one thing to tighten.
3. **`guide` writes `build/.guide-chapter.logos`** where Python writes nothing,
   and resolves `docs/manual`/`docs/LOGOS.md` against the working directory
   where Python resolves them from its own file. Running `guide` outside the
   checkout root is a usage error in the port and works in Python; every other
   verb in this binary has the same property.
4. **The tables are a transcription** (proved by byte equality, not by
   construction). The generator that produced them lives in
   `build/w8guide/gen_tables.py`, which is git-ignored because it imports
   `logos.guide` and dies with Python in step 5; a future change to a table is a
   hand edit, with `python3 -m logos guide` as the oracle.
5. **`make test` grows by ~52 s** for the sixth compiler build in the suite
   (`test_gen2_build`, `_fmt`, `_test`, `_guide`, and two whole-unit builds in
   `test_selfhost`/`test_gen2_test`). If the suite's wall time matters, the verb
   tests could share one `gen2`; today each owns its build so a failure names
   the verb.
