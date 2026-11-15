# W8 step 3a — the capture-fix report: a function value read as a call head

Branch `feat/selfhost-w7-backend`, fix commit `2bee414` on top of `74bbd3d`
(the 3b report). This is a wrong-code fix in W8 step 3a's capture walk, not a
new feature: it changes no accepted program's meaning except the one that used
to be lowered to invalid IR.

## Status

Fixed and pinned. A closure that captures a function value now captures it;
`tests/exec/closures.logos`'s `add-with` shape lowers as Python's `$lambda$3` +
`add-with$i64` and is byte-identical to Python's IR and clang-clean. The 61 IR
entries that were on the list still match, and four new fixtures claim the
neighbouring shapes (65 total).

## Root cause

The port's `lo-captures` walks a form's **children**. A form's head is not one
of them: `tree-finish-head` sets `first` to `tree-child-start`, which is
`next(c1)` — the first argument, past the head token (`src/logosc/tree.logos`).
So for `(f (+ y x))` the walk saw `y` and `x` and never `f`.

A binding of function type is normally read as a call head, `(f arg)`, so the
one place a function value is used was the one place the walk could not see it.
The capture list therefore held no field for `f`, the environment record was
built (or not built) without it, and the lambda body's lookup of `f` found the
**enclosing** function's binding row, still live in `bindn`/`binds`, and loaded
the parent's slot name in the child's frame:

```
define internal i64 @lg.capfn.$lambda$2(i8* %env, i64 %v.0) {
entry:
  %v.0.addr = alloca i64                     ; the lambda's own parameter
  %t1 = load { i8*, i8* }, { i8*, i8* }* %v.0.addr
  ...
```

clang: `'%v.0.addr' defined with type 'i64*' but expected '{ i8*, i8* }*'` —
the exact sentence in the 3b report. In a fixture where the closure is defined
after `main`, the same leak shows as `use of undefined value '%v.1.addr'`
because the parent's slot name belongs to a frame the child never allocated.

This also settles the "field types / offsets" suspicion: there was no
disagreement between the site's `allocarec`/`store`/`bitcastout` and the body's
`geprec`/`load` — both read `bindt[b]` for the same binding row, in the same
order. The record was wrong only because the binding was absent from it. The
first-use order is the same walk, so once the head is visited the head is the
first capture (`{ { i8*, i8* }, i64 }`, not `{ i64, { i8*, i8* } }`), exactly
what Python's checker records when it looks the callee up.

## Fix

- `lo-cap-name` is the name-only capture test (`bound`/`lo-lookup`/`hits`
  dedupe); `lo-cap-hit` is now its atom wrapper.
- `lo-cap-scan-form` applies `lo-cap-name` to `head` **before** walking the
  arguments, so a form's head is a use in first-use order. A head that is not a
  binding falls through: `lo-lookup` answers -1 for `let`, `fn`, a module
  function, an operator.
- `src/logosc/lower.md` ("The closure form") records the rule and why the child
  chain never offered the head.

No block/record/emit code changed. The diff is 6 added lines and 2 removed in
`lower.logos`.

## Shapes pinned

Every fixture is under `src/logosc/fixtures/ir-lower/`, is in
`tools/selfhost-ir.txt`, and is compared byte for byte by the sixth gate.
All four are clang-clean (gen2's own `build` runs clang and exits 0).

| shape | fixture | before the fix | after |
|---|---|---|---|
| `add-with` — a generic whose closure captures a parameter and a function value | `closure-fnvalue.logos` | clang: `use of undefined value '%v.1.addr'` | identical |
| capture a closure beside an `i64` (call through a captured closure, double call) | `closure-fn-two.logos` | clang: `use of undefined value '%v.1.addr'` | identical |
| capture a struct by value plus an `i64` | `closure-struct.logos` | passed (struct capture was already a plain binding) — kept as a guard | identical |
| capture two widths: `u8`, function value, `i64` → env `{ i8, { i8*, i8* }, i64 }` (offsets 0, 8, 24) | `closure-widths.logos` | clang: `use of undefined value '%v.1.addr'` | identical |
| capture nothing | `closure-none.logos` (existing) | green | green |

`closure-fnvalue` is the `add-with` shape verbatim, with two lambdas ahead of
it so the numbering lands where `tests/exec/closures.logos` has it:

```
define internal i64 @lg.closure-fnvalue.$lambda$3(i8* %env, i64 %v.0)
define internal i64 @lg.closure-fnvalue.add-with$i64(i64 %v.0, { i8*, i8* } %v.1)
```

and the body's record is `{ { i8*, i8* }, i64 }`: the function value first
(the call head), then `x`.

Two shapes the language or the backend does not offer, and their exact
behaviour:

- **A generic function used as a value.** Python refuses it: `E0501 ... id is
  generic: a call fixes its type variables` (`logos/check.py`, the same rule
  pinned by the checker corpus). Nothing to lower, no fixture.
- **A named function used as a value** (`(call-it add-one 5)`). Python
  accepts it; gen2 still refuses `add-one` with `E0005: unknown name`. That is
  the `$fnvalue` wrapper the 3a report already lists as not lowered, and it is
  independent of this defect: the value never reaches a binding, so no capture
  is involved. When `$fnvalue` lands, the binding it creates is captured by the
  fixed walk like any other.

## `tests/exec/closures.logos`

Still not byte-identical, and now for one reason only: **nine copies are
reached from `(test …)` bodies** (3c's `build --test NAME`), plus the closure
inside one of them. Measured on a copy with a `main` appended, because the
corpus file has none and `gen2 build` refuses it:

- Python: 19 defines; gen2: 9.
- The 9 gen2 defines are **exactly** Python's first 9, line for line: five
  module functions, two lambdas, `main`, then `id$i64` (the one copy a module
  function reaches). The only other lines are Python's header rows for the
  missing copies — `%struct.a-b`, `%struct.a_x2db`, six string constants and
  four declares, all used only by those copies.
- The 10 defines gen2 lacks are nine copies (`apply$i64$i64`, `first$i64$str`,
  `first$str$i64`, `id$str`, `map$i64$i64`, `map$i64$str`, `pick$s3_a_x2db`,
  `pick$s6_a_x2db`, `add-with$i64`) and `add-with$i64`'s own `$lambda$3`.

So the residual difference is 3c's test mode, not this fix and not the capture
walk. `add-with$i64` cannot be discovered without lowering the `(test …)` body
that calls it; its shape is proved instead by `closure-fnvalue.logos`.

## Gates

- `bash tools/selfhost.sh` (the run `pr_gate` recorded, after the manifest
  regeneration): `selfhost: 333 files, 0 differences`,
  `ir: 65 files, 0 differences` (61 + 4), `resolve: 14 fixtures, 0`,
  `check: 122 fixtures, 0`, `unit: 2 files, 0`, exit 0.
- `emit_test`: 24 passed, 0 failed, 0 leaked (`python3 -m logos test
  src/logosc/emit_test.logos`).
- `bash tools/pr_gate.sh`: **6/6 gates passed** — sign-off, unit tests,
  corpus, acceptance, manual drift, formatting, self-hosting; `rc=0`.
- `python3 -m logos fmt` over every touched `.logos` is a fixed point.

Floor and manifest moves, all deliberate:

- `tools/selfhost-manifest.txt`: 329 → 333 (the four fixtures are tracked
  `.logos` files; the manifest is `git ls-files '*.logos'` and the gate checks
  that equality).
- `IR_FLOOR` 61 → 65, `IR_FIXTURE_FLOOR` 57 → 61.

## Reproduce

```sh
python3 -m logos build src/logosc/*.logos src/std/map.logos src/std/str.logos \
  -o build/selfhost/gen2
for f in closure-fnvalue closure-fn-two closure-struct closure-widths; do
  build/selfhost/gen2 build src/logosc/fixtures/ir-lower/$f.logos
  cp build/$f.ll /tmp/$f.gen2.ll
  python3 -m logos build src/logosc/fixtures/ir-lower/$f.logos
  cmp /tmp/$f.gen2.ll build/$f.ll || echo "$f DIFFERS"
done
bash tools/selfhost.sh
bash tools/pr_gate.sh
```

The pre-fix binary for the "before" column is built from `git stash` of
`src/logosc/lower.logos` alone (`build/selfhost/gen2prefix` in this session);
it rejects the three defect fixtures with the clang sentence above and lowers
`closure-struct` unchanged.

## Sign-off

The four invariants still hold. No accepted program reads freed or
uninitialised memory — the fix adds a capture, never removes one. `-O0` and
`-O2` behave alike: both compile the same IR, and the whole fixture set is
built by clang in the gate. No form the checker accepts became unimplemented;
one that *was* lowered wrongly is now lowered as Python lowers it. Every
diagnostic still carries a code and a node path.
