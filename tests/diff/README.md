# Differential corpus

Each `X.logos` here has a hand-written `X.c` twin. `run_diff.sh` compiles the
Logos file through the project's own driver (LLVM IR, then clang) at `-O0` and
at `-O2`, compiles the twin once with gcc at `-O2`, and requires both Logos
binaries to print the same bytes and leave the same exit status as that one C
run. gcc is the oracle on purpose: a twin built by clang would share the
backend under test, so a miscompilation the two agreed on would pass.

## What a case may use

Only operations C defines. That rules out:

- signed integer overflow, which is undefined in C (Logos defines it as wrap,
  but there is no C behaviour to compare that with);
- shifts by the operand width or more;
- float-to-integer conversion outside the target's range;
- division by zero, and `INT64_MIN / -1`.

Unsigned wrap, truncating division, the sign of `%`, string operations and
fixed-array reads and writes are all defined by C and belong here. Bounds
checks, panics and allocation are Logos's own additions and are covered by the
directive corpus under `tests/exec` and `tests/mem`, not here.

## What a case does not compare

The oracle compares **stdout and exit status**, so it pins values, not layout.
Two consequences a case author has to keep in mind:

- **Struct layout is structural, not observed.** `struct_fields` and
  `struct_nested_fields` build a record with `make` and read it back with
  `get`; the backend lowers those to `insertvalue` / `extractvalue` on an SSA
  aggregate, so no byte offset, size or padding is ever printed or compared. A
  packed or reordered layout would pass these cases. Layout is pinned instead
  by the IR fixtures (`src/logosc/fixtures/ir-lower/struct.logos`,
  `struct-pad.logos`) and the emitter suite they feed, which assert the record
  type and its padding directly. If a case is named `*_layout`, it is claiming
  something this corpus cannot check.
- **`f64` is printed at shortest round-trip, C's `%g` is not.** Logos prints the
  shortest decimal that round-trips to the same double; `printf("%g")` prints
  six significant digits. The two agree on every value these cases print
  (small integers written as `f64`, `2.5`, `4.8`, `6.25`), but a case that
  prints a value needing more than six significant digits will disagree for a
  reason that has nothing to do with codegen. Print integers, halves and
  quarters, or spell the expected digits out deliberately.

## Adding a case

1. Write `X.logos` with a `main` that prints what it computes.
2. Write `X.c` doing the same with the same types and return code.
3. Add `X` on its own line in `manifest.txt`.
4. Run `bash tests/diff/run_diff.sh --verbose`.
5. If the corpus grew past the floor, bump **both** floors in the same commit:
   `MIN_CASES` in `tests/diff/run_diff.sh` and `MIN_DIFF_CASES` in
   `tools/accept.sh`. They encode the same promise, and a change that moves one
   and not the other lets the acceptance gate pass a corpus the oracle itself
   would reject.

The manifest is the corpus's floor: the script fails when a named case is
missing either half, when a pair exists that the manifest does not name, or
when the manifest lists fewer than twelve cases. Deleting a case therefore
fails the run rather than shrinking it to a vacuously green one.

The files carry no `(test ...)` node, so `logosc test` over the tree ignores
them and `tests/diff` contributes no cases to `tests/summary.txt`; this script
is the oracle for the directory.
