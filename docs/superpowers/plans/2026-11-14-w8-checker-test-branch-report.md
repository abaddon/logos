# W8 step 3c-1b — test bodies are checkable, and the two defects that blocked it

Branch `feat/selfhost-w7-backend`, parent `40949bd` (the W8 harness survey).
W8 3c-1 lowered a test body but deliberately left the checker reading only `fn`
bodies: turning the `test` branch on exposed two checker defects that made
`gen2 build --test` refuse its own flagship fixture. This step fixes those two
defects in the order the previous worker measured, then re-applies the test
branch with its one-line mis-walk corrected, and proves the lowering evidence
(`tests/exec/closures.logos`, 17 of 17 byte-identical) survives.

## What landed

**1. A `match` arm's payload name is bound when the scrutinee is unknown.**
The arm-binding code was already there for enum, result and optional
scrutinees; what was missing is the unknown-type case. A variant value such as
`(let e overflow)` still answers the unknown type in value position
(`body-atom-value`, a documented deferral), so `body-family` returned `3`,
`body-match` skipped `body-pat-var` entirely, and the arm body then read `n` as
an unbound name. The new `body-pat-open` reads a one-name form pattern
(`(bad-digit n)`) and binds the name at the unknown type; `_`, a bare atom and a
malformed pattern bind nothing, and the exhaustiveness and duplicate-variant
rules are skipped because an unknown type has no variant table. Pinned by
`body_test.match-unknown-payload-binds`.

Before (HEAD binary, `build/repro/pin-match.logos`):

```
m/f/3/1/1: E0005: unknown name 'n'
```

after: accepted.

**2. A generic call's result type is the argument's own type.**
`body-generic-ret`'s identity case used to read the argument as a *name* and
look it up in the binding map, so only a binding could answer the type;
`(id "abc")` was `?` and `(str-len (id "abc"))` was refused. It now types the
argument node itself through `body-value` (`body-generic-arg-type`), answers
that type, and requires every parameter that carries the same type variable to
answer the same type. A form argument is typed too, which is what lets
`(pick (make a-b 1))` answer `a-b` rather than `?` — that third shape showed up
only after the branch was on (see "The third defect" below). A failed argument
typing answers unknown and is not re-raised, so a deferred shape stays deferred
instead of becoming a new refusal. Pinned by
`body_test.generic-call-result-type`.

Before (HEAD binary, `build/repro/pin-generic.logos`):

```
m/f/2/0/0: E0401: 'str-len' takes a :str, found ?
```

after: accepted.

**3. The checker's `test` branch, re-applied.** Four pieces, as W8 3c-1
specified, with the mis-walk corrected:

- `check-module-tests` walks the module's top-level `test` forms in source
  order and is called from `check-module-tree` after `check-module-fn-bodies`
  (Python's `run()` order: fns first, then tests, then the instantiation
  drain).
- `check-body-test` builds the same environment as `check-body-fn` with a
  `:void` return, no parameters and `bctl[4] = 1`, then walks the body and runs
  `body-pending`/`body-unused` at depth 0. It owes no E0105 (a test is `:void`).
- The body starts at `check-child nodes c 0`, **not 2**. A node's `first` is
  already past the head and the name, so index 0 is the `expect` directive and
  the statements follow it. Index 2 was the mis-walk that left a two-statement
  body unread and began a three-statement body at its third statement.
- `body-walk` skips `expect`/`expect-leak` and a `test`-local `fn` when
  `bctl[4] == 1`. The directive is a harness directive, not an expression
  (Python skips it too); a `fn` is skipped rather than refused, see
  "Concerns".

Pinned both ways by `tests/type/test-body-type.logos` (first `binds`, a valid
body with `let`/`letmut`/`set`/read; second `wrong-type`, `(let y :str x)`), its
`.expect`/`.check` sidecars and `body_test.test-body-valid` /
`test-body-type`. Before the branch the fixture exits 0; after it prints
Python's exact line:

```
test-body-type/test/wrong-type/2: E0100: let 'y' has type :str, found :i64
```

The `.check` is written by `tools/check_parity.py` from Python, not typed by
hand.

## The third defect the branch exposed

With the branch on, `gen2 build --test tests/exec/closures.logos` still failed
— not at the two known defects but at `distinct-type-arguments`:

```
closures/test/distinct-type-arguments/3/0: E0100: 'get' needs a struct, found ?
```

The test calls `(pick (make a-b 1))`; `pick` is the identity generic, and the
first version of fix 2 only typed atoms, so a form argument still answered `?`
and `(get p x)` blamed the unknown. This is why the generic fix reads the
argument through `body-value`: the identity case has to answer the *argument
expression's* type, not a name's. With that, closures checks cleanly and the
17-test parity passes. This is the one place where the task's step 2 turned out
to need more than a name lookup; no further defects appeared behind it.

## Verification

- **Lowering evidence survives: 17 of 17.** `python3
  tools/test_ir_parity.py tests/exec/closures.logos` →
  `test-ir: 17 tests, 0 differences`, against the rebuilt gen2 with the test
  branch on.
- **Test mode over `tests/exec`:** all 138 `(test …)` bodies across the 20
  files, each built with `gen2 build FILE --test NAME`:
  - **107 lower** (build and link),
  - **31 refused**, every one a known lowering gap:
    - 21 × `R0003` (`tests/exec/results.logos`, a struct holding an enum by
      value),
    - 5 × `E0002: 'cast' is not lowered by this backend yet`
      (`tests/exec/cast.logos`),
    - 2 × `E0002: a statement must be a form` — the match-as-a-statement
      shapes: `loops/fizzbuzz` (a `match` inside a `while`) and
      `match/match-arm-has-a-block-body` (an arm body with two statements),
    - 1 × `E0002: '!=' is not lowered by this backend yet`
      (`tests/exec/strings.logos`),
    - 2 × clang/IR failure for an f32 literal stored as `float`
      (`tests/exec/floats.logos`: `floating point constant invalid for
      type`).
  - **0 new refusals.** No refusal carries a checker code inside a test body;
    every line is the lowering's own. The three tests the 3c-1 report counted
    as IR differences without a refusal (2 × nested-`vec` element size, 1 ×
    float ULP) lower here, so 107 − 3 = 104 agrees with that report's 104
    IR-identical tests.
- **Checker sweep:** `gen2 check` against Python's `checked_program` over all
  334 `.logos` files in the tree (including every `(test …)` body):
  **0 false positives**, 180 accepted by both, 151 refused by both, 3
  under-reported (`tests/generics/limit`, `tests/generics/unbound`,
  `tests/regress/owner-place-read` — the documented generic-call-site and
  deferred-`deref` gaps). Test bodies being read did not turn any accepted
  program into a refusal.
- `python3 -m logos fmt` is a fixed point on the changed `.logos` files.
- `tools/selfhost-manifest.txt` regenerated for the new fixture: 334 entries,
  equal to `git ls-files '*.logos'`. `CHECK_FLOOR` is 123.
- `tests/summary.txt` regenerated with `python3 -m logos test --update-baseline`
  from a real run: 308 cases, including `type/test-body-type`. The new case's
  absence was the only regression the first gate run reported.
- `python3 -m logos test src/logosc/body_test.logos --opt -O0`: **361 passed,
  0 failed, 0 leaked**, the four new cases included. The `-O2` level of that
  unit suite was not re-run; the corpus fixture `type/test-body-type` is
  exercised at both levels by pr_gate's corpus gate.
- `bash tools/pr_gate.sh`: **6/6** gates (`build/w8/prgate.log`, not committed).

## Concerns

- **A `test`-local `fn` and a bare token in a test body are under-reported.**
  Python refuses both (E0002 `test-local helper functions are not lowered yet`
  at the helper, and E0002 `a test body must be a form` at the test node). The
  walk is over the tree's child chain, which contains no bare token, and the
  `fn` skip is deliberate: refusing it needs a path spelling the tree does not
  currently agree with (`m/test/t/helper` here vs Python's `m/test/t/1`). Both
  are missing checks, not false refusals, so a valid program is never refused.
- **The generic identity rule is not unification.** It answers the type of the
  argument beside a bare return variable; a variable nested in a parameter or
  the return still answers unknown, and a multi-parameter variable must get
  equal types at every position or answers unknown. This is enough for the
  corpus, not a unifier.
- **Directive/fn skipping is flag-wide, not depth-scoped.** `bctl[4]` is set
  for the whole test walk, so an `expect` nested inside an `if` would also be
  skipped. No corpus file writes one; Python would refuse it.
- The test-mode sweep is a build-level statement. A test that builds but prints
  different bytes is not visible to it; the IR-parity tool covers `closures`
  only, as before.
- **The Logos unit suites are not part of `pr_gate`.** The four new
  `body_test.logos` cases, and the 357 that came before them, are run by
  `python3 -m logos test src/logosc/body_test.logos --opt -O0 --opt -O2`, not
  by a gate. The test branch's gate-enforced pin is the `test-body-type`
  fixture in `tools/selfhost-check.txt`; the two checker-defect pins are
  unit-level and depend on that documented command being run.

## Reproduce

```sh
python3 -m logos build src/logosc/*.logos src/std/map.logos src/std/str.logos \
  -o build/selfhost/gen2

python3 tools/test_ir_parity.py tests/exec/closures.logos   # 17 tests, 0 differences
python3 tools/check_parity.py                               # writes the 123 sidecars

# the pins, against a HEAD-built gen2 and this one
gen2 check build/repro/pin-match.logos     # HEAD: E0005; now: 0
gen2 check build/repro/pin-generic.logos   # HEAD: E0401 found ?; now: 0
gen2 check build/repro/pin-test.logos      # HEAD: 0; now: E0100 at m/test/t/2

gen2 check tests/type/test-body-type.logos # test-body-type/test/wrong-type/2: E0100: ...
bash tools/selfhost.sh
bash tools/pr_gate.sh
```
