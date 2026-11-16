# `src/logosc/guide.logos` — the generated manual and its manifest

The `guide` verb: `docs/LOGOS.md`, the machine-readable manifest, and the drift
check the gate's manual-drift phase runs. The reference is `logos/guide.py`,
`logos/diag.py` and `logos/cli.py:_guide`; Python is the oracle, and the
acceptance is byte equality — `gen3 guide` must print the committed manual and
`gen3 guide --json` must print Python's 18,808-byte manifest. A prettier
rendering is a failure, so the layout below is transcribed, not designed.

`main.md` owns the command line; this module owns the two documents.

## What the manual is

`tester` proves the language runs, `check` proves what it refuses, and this file
tells a reader what the language *is*: a cheat sheet, the twenty chapters under
`docs/manual/` with the output each declares, and a reference built from the
compiler's own tables. The tables are why the manual cannot lie: `g-codes`,
`g-reserved-forms` and the rest are not prose about the compiler, they are the
data it uses, and `guide-consistent` refuses to build when a composite type form
in `types-forms` has no arity or meaning here.

## The tables

Every table is a `g-*` function taking an out-parameter vector, because Logos
has no module-level constants and a vector is the only aggregate it can build.
Entries are flat with a fixed stride, and `g-lookup`/`g-field` read them:

| function | entry | stride | source |
|---|---|---|---|
| `g-codes` | code, message | 2 | `diag.CODES` (36, insertion order) |
| `g-form-docs` | name, arity, meaning | 3 | `guide.FORM_DOCS` (88, manual order) |
| `g-type-arity` | name, arity | 2 | `guide.TYPE_ARITY` (12) |
| `g-type-meaning` | name, meaning | 2 | `guide.TYPE_MEANING` (12) |
| `g-rules` | cheat-sheet text, where enforced | 2 | `guide.RULES` (10) |
| `g-titles` | file stem, heading | 2 | `guide.CHAPTER_TITLES` (20) |
| `g-reserved-forms` | name | 1 | `check.RESERVED_FORMS`, sorted (49) |
| `g-reserved-prefixes` | name | 1 | `check.RESERVED_PREFIXES` (4) |
| `g-reserved-variants` | name | 1 | `check.RESERVED_VARIANTS` (19) |

Two lists are read from the modules that already own them rather than copied:

- `type-primitives` and `type-forms` (`types.logos`). `type-primitive?` now scans
  the first, so the checker's whitelist and the manual's "Primitive types" table
  are one list. `type-forms` is the enumerable form of what `type-form-kind`
  accepts, which was a chain of tests with no list behind it.
- `h-categories` (`harness.logos`). `h-known-category` scans it, so the eight
  category names and their order live in one place: the order is the suite's run
  order and the manual prints it.

Everything else is *derived*, as Python derives it: a primitive's kind, bit
width, signedness and sentence come from its name (`g-prim-kind`,
`g-prim-bits`, `g-prim-signed`, `g-prim-meaning`); the equality operators'
meaning is built from the scalar types the primitive list names (`g-scalars`);
the appended composite forms are those `type-forms` names that `g-form-docs`
does not already document (`g-forms`), which is `_build_forms`'s append.

### `atomic`, the one name the two lists disagree on

`RESERVED_FORMS` has 49 names and `g-reserved-forms` prints Python's list.
The port's `check-reserved-name` has those 49 plus `atomic`, so 50.
which Python does not: Python refuses the *call* (`(atomic)` is the form, so a
function of that name is uncallable, and the error is `E0102` at the call site),
while the port refuses the definition with `E0003`. That is a checker
divergence, not a manual one; the manual reports the compiler whose tables it
reads, so it prints 49 and the report for W8 step 4 records the difference. If
the checker is made to agree with Python, `check-reserved-name` should scan this
same table and the extra test disappears.

## Chapters

`g-chapters` lists `docs/manual` (`read-dir`, sorted with `h-sort`, `*.logos`
only, as `sorted(MANUAL_DIR.glob("*.logos"))` does), and for each chapter:

1. `g-stem` strips `.logos`; `g-titles` must have the stem, so a new chapter
   without a heading is an error rather than a de-slugged title.
2. The file is lexed and parsed (`lex`, `tree-parse`) exactly as `main` does.
3. The first `(test …)` node's `(expect (out …))` is read with `harness`'s
   `h-expect-values` — the same reader `test` uses, which is why `guide`
   follows `test` and does not precede it. A chapter without a test, or whose
   test declares no output, is an error.
4. The source is rendered **through `fmt`**: `g-render` writes the printer's
   output to `build/.guide-chapter.logos`, reads it back and unlinks it. The
   manual embeds `fmt.render(root)`, not the file, so a chapter written less
   tidily is still shown canonically. The printer's sink is a file descriptor
   and Logos has no in-memory sink; a scratch file under the ignored `build/`
   is the smallest faithful way to get the text. It is the one thing `guide`
   writes: the manual itself goes to stdout, and the comparison reads the
   committed `docs/LOGOS.md`.

The rendered text and the declared output are both right-stripped of newlines
(`g-rstrip`), as `rstrip("\n")` does, and the chapter number is the count of
chapters taken so far, not the directory position.

### The three externs

`rt_create`, `close` and `unlink` are declared once in the unit, and a
declaration is only visible to a module the declaring one is processed before —
so a second declaration is `E0003` and a use without one is `E0103`. They live
in `harness.logos`, which this module uses: `harness` is processed before both
`guide` and `main` (the unit is built in source-name order), and the baseline
writer was the first module below `main` that needed to open a file. `main`'s
`main-spit` and this module's markdown renderer reach them through
`(use harness)`.

## The markdown

`g-manual` (`guide-markdown`) builds a `<vec :str>` of lines and joins it with
newlines, exactly `"\n".join(lines)`. Order: title, cheat sheet (fixed prose,
the example, the ten numbered rules, the `--json`/`--check` pointer), `## Manual`
and the chapter count, the chapters, then `## Reference` with the rules table,
forms, primitive types, operators, builtins, reserved names, diagnostic codes and
the runtime panic paragraph, and the test categories. `g-table` prints the header
row, the `---` row and one row per entry; `g-cell` escapes `|` and newlines so a
meaning cannot break a table.

The cheat sheet's example and the panic-code paragraph are the only prose in
this file that is not a table lookup. They are copied from `build_markdown`
verbatim, including the `"3\n"` inside the example, which is the two characters
a Logos literal spells.

## The manifest

`guide-manifest` prints `json.dumps(manifest, indent=2)`: `{`, then the seven
keys in Python's insertion order — `forms`, `types`, `operators`, `builtins`,
`reserved`, `codes`, `categories`. `g-json-str` escapes a string the way
`json.dumps` does (`"`→`\"`, `\`→`\\`, the five control shortcuts, `\u00XX`
below `0x20`). `g-jform`, `g-jtype`, `g-jop` and `g-jcode` each push one entry's
lines; `g-jarray` pushes a string array at an indent. Integers (`bits`) and
booleans (`signed`) are emitted as JSON, not as strings.

The tables are ASCII, which is what makes the byte-wise escaping exact. A
non-ASCII meaning would need a UTF-8 decoder to match `ensure_ascii=True` for a
multi-byte character; the escaper says so where it decides, and no table has
one.

## `--check`

`guide-check` compares the regenerated markdown with `docs/LOGOS.md` byte for
byte. Equal: one line on stdout, exit 0. Missing: `… is missing; run
`logosc guide > docs/LOGOS.md`` on stderr, exit 1. Stale: the summary
`docs/LOGOS.md is stale: N line(s) to add, M line(s) to remove; run …`, the
`---`/`+++` pair, then the first fourteen diff lines, and exit 1 — the shape
`check_current` prints, from a line diff.

The diff is an LCS over the two line lists (`g-dp` fills the table bottom-right
to top-left; `g-step` walks it, preferring a removal on a tie so a replaced line
prints `-old` then `+new`), grouped into hunks with Python's `@@ -a,b +c,d @@`
ranges and `,1` omitted. That matches `difflib.unified_diff(..., n=0)` for the
edits a stale manual actually has — an edited chapter, a changed message — but
it is not `difflib`'s Ratcliff/Obershelp algorithm: a rewrite that moves lines
around can be reported as a different number of added and removed lines. Above
four million line pairs `g-stale-rough` falls back to trimming the common prefix
and suffix and reporting one hunk, so a pathological comparison cannot allocate
its way out of memory.

## Errors

A chapter that cannot be read, lexed, parsed, or that lacks a test or its
`(expect (out …))` prints `logos: guide: <chapter>: …` on stderr and exits 1.
Python raises a `ValueError` there and lets the traceback print; the line is the
port's, and it is the only place the two diverge outside the diff counts. The
files it reads are resolved against the working directory — `docs/manual` and
`docs/LOGOS.md`, as every other path a verb takes from the command line does —
where Python
finds the repository from its own file. That is why `guide --check` runs from
the checkout root, as the gate and `tests/test_gen2_guide.py` do. The two paths
the compiler resolves from its own location are the runtime and the standard
library (`sys.md`), not this one.
