# W8 step 3a — closures in the Logos lowering

Branch `feat/selfhost-w7-backend`, parent commit `cf3d7e0` (W8 step 2). This is
the report for the step that makes `(fn :R ((p :T)…) body…)` lower, keeps the
generic refusal honest, and adds five IR-parity fixtures plus one refusal
fixture.

## What the port lowers now

A closure expression is a per-site nested function `$lambda$N`, named from the
same unit-wide counter as `$spawn$N` (`st[12]`), and a two-word value
`{ i8*, i8* }` — the environment record and the code. The same function type
spells both a capturing and a non-capturing closure, and the environment is
`null` when nothing is captured.

- **Site.** `lo-lambda` reads the capture list from `lo-captures` (mirrors the
  checker's walk: bindings from outside the expression, first-use order,
  shadowed by the lambda's own parameters and `let`s), materialises the record
  through the existing plan (`allocarec` run encoded as a negative `planty`
  entry), stores each capture, then spells the value with two `insertvalue`s
  over a `bitcast` of the record and a `bitcast` of `$lambda$N`.
- **Deferred function.** The body is lowered at drain time, after the parent's
  `ir-fn-end`: `$lambda$N`'s own counters, an `env` parameter appended straight
  to `pnames`/`ptys`, one `alloca` per planned binding at the top of `entry`,
  `bitcastrec %env` and one `geprec` per capture bound as the name's slot, then
  the body for real.
- **Indirect call.** A call through a value loads the binding, `extractvalue`s
  the environment and the code, `bitcast`s the code to its real signature
  `R (i8*, T…)`, and emits `icall` with the environment first. The signature is
  the callee's own function type, so arity and argument types come from the type
  query; `lo-node-type` answers the same for the closure and the call so a
  `(let f (fn …))` can be named and `(f 1)` printed.
- **One queue, one rotation.** The deferred-site queue (`st[13]` count,
  `st[14]` base; rows `kind, n, node|slot, count` plus one binding-row index per
  capture) holds spawns and lambdas in site order. `lo-site-drain` dispatches on
  the kind, recurses for sites queued by the deferred body, and rotates the
  parent's f-row once by the row count, so `$spawn` and `$lambda` defines
  interleave exactly where Python prints them.

Two adjacent `emit.logos` repairs came with it: a `%tN` callee is printed
verbatim (an `icall` names its temp, not a global), and `tptypes` contiguity is
preserved when a parameter's own type is a function type (`lo-sig-one` and
`lo-lambda-shape` parse every parameter before appending its run).

## The defect this step had to close

`lo-lambda-fn` opened `entry` with `st[4] = 1`, the dry-pass marker, and then
called `lo-w-block`. `lo-w-block` only appends a block row when `st[4] == 0`,
so the define printed with *no* basic block and every op of the lambda body
landed in the parent's block; clang rejected it with `function body requires at
least one basic block`. The plan's allocas were also emitted while `st[4]` was
still 1, so even with a block the `%v.N.addr` slot would be undefined.

The fix opens `entry` before the dry pass and emits the plan after the second
reset:

```
st[4]=0 → lo-w-block "entry" → cl[0]="entry" → st[4]=1 → dry body
        → reset counters, st[4]=0 → plan allocas → env record → real body
```

Both halves are load-bearing: a block row records its first instruction as the
`ops` length at open, so the allocas and the real body appended later fall
inside its range, while a block opened after them would own none of them. The
comment in `lower.md` ("The closure form") records this.

## Verification

- Five fixtures, compared against Python's `logos build` **byte for byte**:
  `closure-none` (43 lines, 2 defines), `closure-one` (51/3), `closure-two`
  (62/3), `closure-argument` (59/4), `closure-mixed` (108/5).
- `closure-mixed` is the counter/queue claim: `$lambda$1`, `$spawn$2`,
  `$lambda$3` print in that order before `define i32 @main()`.
- `tools/selfhost.sh`: `selfhost: 325 files, 0 differences` (manifest equals
  `git ls-files '*.logos'`, no stale entries), `ir: 56 files, 0 differences`
  (52 fixtures plus the four examples; floors `IR_FLOOR=56`,
  `IR_FIXTURE_FLOOR=52` are the measured counts), `resolve: 14 fixtures, 0`,
  `check: 122 fixtures, 0`, `unit: 2 files, 0`, exit 0.
- `tools/pr_gate.sh`: 6/6 gates passed.
- `python3 -m logos fmt` over the touched sources is a fixed point.

## What still refuses, and the next subject

- **Generic functions.** `lo-fn` refuses a generic definition before spelling
  it: `E0002: function 'id' is generic: this backend lowers no instantiation of
  it` at the definition's node path. Pinned by
  `src/logosc/fixtures/ir-refuse/generic-refuse.logos`, sidecar
  `generic-refuse.refuse`, and `REFUSE_FLOOR=2`.
- **A named function used as a value** (`$fnvalue`): Python wraps each used
  definition once so a function pointer and a closure share the `(i8*, T…)` ABI.
  No fixture claims it; the `lower.md` refusal list keeps it.
- `tests/exec/closures.logos` is still absent from the IR list, and the reason
  is generics, not closures: it declares `id`, `first`, `apply`, `map`,
  `add-with`, `pick`, and Python lowers ten monomorphised instances
  (`id$i64`, `apply$i64$i64`, …). The port has no instantiation record, so the
  clean refusal is the correct answer until it does. **Instantiation lowering is
  the next task.**

## Reproduce

```sh
python3 -m logos build src/logosc/*.logos src/std/map.logos src/std/str.logos \
  -o build/selfhost/gen2
for f in closure-none closure-one closure-two closure-argument closure-mixed; do
  build/selfhost/gen2 build src/logosc/fixtures/ir-lower/$f.logos
  cp build/$f.ll /tmp/$f.gen2.ll
  python3 -m logos build src/logosc/fixtures/ir-lower/$f.logos
  cmp /tmp/$f.gen2.ll build/$f.ll || echo "$f DIFFERS"
done
bash tools/selfhost.sh
bash tools/pr_gate.sh
```
