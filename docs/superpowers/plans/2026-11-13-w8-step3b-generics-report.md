# W8 step 3b — generic instantiation: report

Branch `feat/selfhost-w7-backend`, feature commit `6d6584b`; this report rides
in a docs commit of its own. Measurement
note: `docs/superpowers/plans/2026-11-13-w8-generics-notes.md` (written first;
every claim in it is `file:line` against `logos/check.py` and `logos/lower.py`).

## Status

The port lowers a generic at each instantiation, named and ordered as Python
does it. Four of the five acceptance shapes are byte-identical to Python's IR;
the fifth (`tests/exec/closures.logos`) is **not**, and the two reasons are
named below — one of them is a defect this branch found in W8 step 3a, not in
generics.

## How it works

Python discovers copies in the **checker** and hands the lowerer
`instances` + `call_targets` + `generic` (`logos/check.py:519-523`). The port's
checker has no unifier, so this branch discovers copies **in the lowerer**, at
the call site it is already lowering (`lo-call` → `lo-inst-call`), and memoises
them by mangled name in the tables `lower-build` owns. The naming, the per-module
grouping, the emission point (after every function of the module, in discovery
order) and the breadth-first drain of copies discovered inside copies are
Python's. The trade is stated plainly: `gen2 check` still answers unknown for a
generic call site (`check.md:200-224`), so the checker remains an under-reporting
oracle for generics; nothing in this branch makes a program accepted that Python
rejects.

| piece | where |
|---|---|
| unification (`var`, wrappers, `arr`, `res`, `fn` incl. head) | `lo-unify`, `lo-unify-fn`, `lo-bind-var` |
| the copy's name (`name$i64$s5_point`) | `lo-var-order` + `lo-inst-target` + `type-mangle` |
| the memo and the queue | `lo-inst-find`, `lo-inst-add` (`insn/ivd/ivn/ivt/ivb/ivc`) |
| substituting a copy's signature | `lo-inst-sig` + `type-substitute` |
| substituting inside the body | `lo-parse` now runs `type-substitute` over what it parsed, with the active copy's bindings (`curn`/`curt`) |
| lowering one copy | `lo-inst-drain` → the ordinary `lo-fn`, with the copy's name and concrete signature |
| a definition with no copy | `lo-one-fn` skips it (was `E0002` at `lower.logos:3524`) |

Two supporting changes: the eight instance tables joined the 85-parameter
context that every `lo-*` helper takes, and `emit-types` now leaves a **type
variable** row unspelled (`""`) instead of failing the build — a `:T` row exists
in the arena because a generic's signature is scanned, and Python has no such
rows to print. No emitted line changes for any program without a type variable.

## Acceptance, with evidence

Every fixture is under `src/logosc/fixtures/ir-lower/` and is in
`tools/selfhost-ir.txt`, so the sixth gate re-proves each one on every run.

1. **One definition, one site, one type** — `generic-one.logos` (`id$i64`):
   `cmp` against Python's `build/generic-one.ll`: **identical**.
2. **One definition, two sites, two types** — `generic-two.logos`
   (`id$i64`, `id$str`): **identical**. `generic-struct.logos` adds the named
   type argument (`pick$s5_point`), **identical** — the length-prefixed
   spelling is what keeps `s5_point` apart from the primitive.
3. **A generic calling a generic** — `generic-nested.logos` (`twice$i64`
   discovered first, `id$i64` inside it, printed after it): **identical**.
4. **A generic used through a closure** — `generic-closure.logos`
   (`apply$i64$i64`, the closure passed in and called in the copy's body):
   **identical**.
5. **`tests/exec/closures.logos`** — **not identical. It is out of the parity
   list and named here.** Measured: Python's module lowering emits 18 defines
   (five module functions, three `$lambda`s, ten copies); `gen2` emits 9 (five
   module functions, three `$lambda`s, one copy, `id$i64`). Two causes:

   - **Nine copies are only reachable from `(test …)` bodies** (`closures.logos`
     lines 71, 90, 91, 98, 108, 121, 160, 174-175). Python discovers them
     because its *checker* checks test bodies; a copy is discovered here while a
     body is **lowered**, and the port lowers no test body (that is 3c's
     `build --test NAME`). So a copy no function reaches is not discovered.
   - **`add-with$i64` could not be byte-identical anyway**, because a closure
     that captures a *function value* is mis-lowered by W8 step 3a. Repro
     without generics — `(let f (fn :i64 ((n :i64)) (ret (* n 2))))`
     `(let g (fn :i64 ((y :i64)) (ret (f y))))` — fails on the **pre-3b**
     binary `build/selfhost/gen2` exactly as it does on this one: the `f` read
     inside `$lambda$2` becomes `load { i8*, i8* }, { i8*, i8* }* %v.0.addr`,
     the lambda's own parameter slot, because `f` never entered the capture set
     and the enclosing binding stayed visible; clang rejects the file with
     `'%v.0.addr' defined with type 'i64*' but expected '{ i8*, i8* }*'`.
     `add-with` is that shape (`(ret (f (+ y x)))` inside a nested closure).

## Fixtures added

```
src/logosc/fixtures/ir-lower/generic-one.logos      id$i64
src/logosc/fixtures/ir-lower/generic-two.logos      id$i64, id$str
src/logosc/fixtures/ir-lower/generic-struct.logos   pick$s5_point
src/logosc/fixtures/ir-lower/generic-nested.logos   twice$i64 -> id$i64
src/logosc/fixtures/ir-lower/generic-closure.logos  apply$i64$i64
```

`src/logosc/fixtures/ir-refuse/generic-refuse.{logos,refuse}` is deleted: it
pinned the refusal this branch removes. `IR_FLOOR` 56 → 61,
`IR_FIXTURE_FLOOR` 52 → 57, `REFUSE_FLOOR` 2 → 1 (a deliberate act, noted in
`tools/selfhost.sh`), and `tools/selfhost-manifest.txt` regenerated (324 → 329).

## What is deferred

- **Copy discovery from a test body** (nine of `closures.logos`'s ten copies).
  It needs the test-entry mode 3c builds, or a discovery pass over test bodies
  with its own type engine — the second engine is what this branch refused to
  write.
- **A closure capturing a function value** (3a's defect): not fixed here; it is
  a wrong-code defect, reproduced above, and it blocks `add-wit`/`closures.logos`
  independently of generics.
- **Checker-side instantiation**: `gen2 check` still accepts a generic call it
  cannot type. `E0500`/`E0501` at a call site remain unreachable from `gen2
  check`, exactly as `check.md` documents; the lowerer raises `E0501` for an
  unbound variable it can see, which is a diagnostic, not the checker's.
- **Recursive generic instantiation while lowering**: a copy that calls itself
  resolves to itself through the memo (the name is identical), so it terminates
  — but only when the argument's type is the same. A generic that instantiates
  itself at a *different* type per copy would grow the queue; Python's ceiling
  is 256 and is not enforced here.

## Gates

`bash tools/pr_gate.sh` on the committed tree: **6/6**,
`rc=0`. Its own logs:

```
selfhost: 329 files, 0 differences     (fmt fixed point, every tracked .logos)
ir: 61 files, 0 differences            (the five new fixtures included)
resolve: 14 fixtures, 0 differences
check: 122 fixtures, 0 differences
unit: 2 files, 0 differences
```

`emit_test` (the suite for the module this branch also touches) at `-O0` and
`-O2`: 24 passed, 0 failed, 0 leaked — the `emit-type-var` negative case still
pins Python's sentence. `check_test` and `body_test` do not import `lower`
(`src/logosc/{check,body}_test.logos`' `use` lines), so no assertion in them can
move with this diff; they were not re-run. There is no `lower` suite.
