# W7 B4 — `spawn` thunks: what Python emits, why the arena breaks, which fix keeps byte order

Design note for B4; branch `feat/selfhost-w7-backend` at `e6321fc`. No source file touched. The gate compares text
(`src/logosc/lower.md:203-208`), so every claim below is about where a line lands, not only well-formedness.

## 1. How Python emits a thunk

**Name, counter, scope.** `spawn_thunk` asks the unit for a name, `next_name("$spawn")` (`logos/lower.py:3206`),
which bumps one counter and spells `"$spawn$" + n` (`lower.py:1567-1581`); the symbol is
`lg.<module>.$spawn$N` (`lower.py:3207`). The counter starts at 0 (`lower.py:1002`), is shared with `$lambda` and
`$fnvalue` (`lower.py:1585`, `lower.py:4466`) and is *unit*-wide, ordered by evaluation, never reset per function:
`build/python-matrix.ll` numbers `main`'s four sites `$spawn$1`–`$spawn$4` at lines 135, 154, 173, 192. The bump
sits after the record is built and before the runtime call (`lower.py:3190`), so a site's lowering position fixes
its number.

**`%env`, and why there is no capture list.** A spawn captures nothing lexically. `fields` is the *callee's*
parameter list (`lower.py:3160`); the arguments are evaluated left to right (`lower.py:3169`), their types
materialised at the site (`lower.py:3170-3171`), sized and aligned (`lower.py:3173-3178`), then copied into one
heap record — `rt_alloc` with the spawn's node path (`lower.py:3180-3182`), `bitcastrec` to the field list
(`lower.py:3185`), one `geprec`+`store` per field (`lower.py:3186-3189`). That record is the `%env`; the runtime
owns it until the target returns (`lower.py:3128-3135`; a closure's `%env` is a stack slot, `lower.py:4540-4551`).

**The thunk itself.** A fresh `IrFn`, no source parameters, one `entry` block, `internal`, returning `i8*`
(`lower.py:3208-3215`); `%env` is appended to `fn.params` directly, costing no binding and no slot
(`lower.py:3224-3227`); body = `bitcastrec %env` (`lower.py:3229-3230`), `geprec`+`load` per field
(`lower.py:3232-3238`), `call target` (`lower.py:3242`), `ret i8* null` (`lower.py:3243`). Its temps belong to a
new `_Fn` (`lower.py:3216-3223`, `lower.py:1704-1706`) and restart at `%t1`: matrix 137-149 spends `%t1`–`%t13`,
and `$spawn$2` starts at `%t1` again. The `faddr` temp at the call site is the *parent's* counter, allocated after
the record stores (`lower.py:3246-3247`; `build/pnested.nested-spawn.ll:76-77`).

**Placement.** Functions print in list order (`logos/llvm.py:363-368`); the enclosing function is appended after
its body (`lower.py:1618`), the thunk during it (`lower.py:3245`). So each thunk's define lands immediately
**before** the define of the function that spawns it, in site order: matrix 135-210 (four thunks) then
`define i32 @main()` at 211; pnested `$spawn$1` 26-33 before `branch` 35, `$spawn$2` 59-66 before `main` 68.

## 2. Why the arena breaks

`ir-fn` fixes a range at open — `fbase = len(blabels)`, `fparam = len(pnames)` (`src/logosc/ir.logos:215-218`) — and
`ir-fn-end` closes it from the *current* lengths: `fcnt = len(blabels) - fbase`, `fpc = len(pnames) - fparam`
(`ir.logos:227-230`). `emit-fn` prints exactly those two runs (`src/logosc/emit.logos:710-720`, `725-730`), so a
range is *everything* appended between open and close; only contiguity makes it that function's.

The port opens at `lower.logos:3358` and closes at 3399, after two passes over the body (3376-3395). A thunk
emitted at a site inside that window appends one `pnames` row (`env`), one `blabels` row (`entry`) and its ops
between them, so:

- the enclosing `fpc` grows by one per site → `define i32 @main(i8* %env, i8* %env, i8* %env)`, spelled at
  `emit.logos:718-724`: the three `%env` params measured on `@main` (`lower.md:430-434`);
- the enclosing `fcnt` grows by one per site → the thunk's `entry:` printed a second time *inside* main
  (`emit.logos:727-730`), its `%t1..%t13` colliding with live numbers: not merely misordered, not valid IR;
- the row order is wrong even if ranges were repaired — the arena creates F's row at open (3358) and the thunk's
  at the site, so `fnames` prints F before its thunks, where Python prints `[t1..tk, F]` (matrix 135 vs 211).

The corruption is one-directional: a thunk's own `ir-fn-end` runs first and closes its ranges correctly; the
*enclosing* range swallows it. `spawn` refuses at the generic `lo-value` fall-through (`lower.logos:1652`), E0002 as
a statement, E0005 as a `let` initialiser (`lower.md:438-442`).

## 3. Two candidate fixes

Both need the same first step: a pending-site record in the context — gensym'd name, resolved target symbol,
callee parameter base and count, node path. That grows the 63-vector list again (`lower.md:16-28`, `85-93`) and
moves every `lo-*` signature: mechanical, but why this is a task and not a missing `case` (`lower.md:436-437`).
Both keep `use_type` at the site (`lower.py:3170-3171`) — a struct materialised at drain time would insert a struct
row after rows the body registered later, and struct order is output order (`llvm.py:153-156`) — and both keep
`declare` at the site (`lower.py:3180`, `3191`).

**(a) Queue drained at function end.** Record the site; emit the thunk's rows in a drain placed after the
enclosing `ir-fn-end` (`lower.logos:3399`), before the next `lo-fn`. *Trade-off:* the cheapest fix that keeps the
arena honest — no row surgery, no stale `fid`, every function's rows in one increasing block, a thunk's `fbase`
monotonic with its parent's. What it cannot do is order: each thunk prints *after* the function that spawns it, so
every spawn fixture differs at its first thunk define and stays red — a legitimate intermediate commit only while
no spawn file is in `tools/selfhost-ir.txt`.

**(b) Deferral to the end plus a row swap that preserves define order.** Same queue, same drain point, plus one
step: once the k thunk rows exist, rotate F's function row right by k (k adjacent exchanges of the eight-column
row `fnames..fpc`), leaving `[t1..tk, F]` in the f-table while the thunks' blocks stay physically after F's.
*Trade-off:* the only one of the two that reproduces Python's order, and here order is the deliverable — matrix
135-210 versus 211 is the entire difference. Its cost: `fid` is stale the moment the rotation runs, so the swap
must be the last thing `lo-fn` does; and afterwards `fbase` is deliberately non-monotonic across the f-table (a
thunk's blocks sit past its parent's), which a later reader must not mistake for corruption, since each row is
still contiguous and `ir-fn-first`/`ir-fn-past` are per-row (`ir.logos:252-257`). `emit-fn-find` searches by name
(`emit.logos:390-397`), so nothing else depends on row order.

**Recommendation: (b).** The gate is byte equality, so (a) cannot be the answer; (b) pays one O(k) rotation for it.
Landing the queue and drain as (a) first is a fine review-sized step, but the same commit must add the rotation, or
every spawn fixture is red for a reason that looks like a bug in the thunk body.

Two hazards. The drain needs the thunk's own counters: `%tN`, `%v.N` and labels live in `st[0..2]`, reset at
`lower.logos:3364-3366`, so save them, zero them, emit, restore F's (`lower.py:1704-1706` restarts them in Python).
And the name counter must survive the dry pass: `st[12]` is written only by `lo-gensym` (`lower.logos:3659-3662`,
`lower.md:156`), the dry pass must not allocate a name, and the real pass must allocate at the site so `$spawn` and
`$lambda` share one sequence (`lower.py:1567-1581`). The `faddr` temp stays at the site, after the record stores.

## 4. The test that proves it

Add `src/logosc/fixtures/ir-lower/spawn.logos` to `tools/selfhost-ir.txt` and raise `IR_FLOOR=44` to 45
(`tools/selfhost.sh:117`); the set is exactly the directory, so fixture and list move together (`lower.md:480-490`).
The fixture needs **two** spawning functions — a helper that spawns a worker, and `main` that spawns the helper —
because one spawning function cannot tell a unit-wide counter from a per-function one. The specimen is
`build/pnested.nested-spawn.ll`:

- eighteen lines, `define internal i8* @lg.<mod>.$spawn$1(i8* %env) {` to `ret i8* null` and `}`, at once after
  the helper's `}` and before the next `define` (pnested 26-33, `leaf` at 24, `branch` at 35): the (b) claim;
- `define i32 @main()` with empty parentheses (pnested 68, matrix 211), and no `entry:` or `%t1` printed twice in
  any define: the range claim;
- `$spawn$2` numbered by the unit, not by `main` (pnested 59), each thunk's temps restarting at `%t1` (pnested
  61-64, matrix 137-149); and the call site's shape in the parent — `rt_alloc`, `bitcastrec`, `geprec`+`store`,
  `faddr`, `rt_thread_new(path, code, record)` — matching `lower.py:3182-3193`.

Then list `examples/matrix.logos` too: four 18-line thunks at 135-210 of `build/python-matrix.ll` before
`define i32 @main()` at 211 is the end-to-end claim, and its `$spawn$1`–`$spawn$4` numbering with six-field
unpacking is what the larger fixture buys. (`lower.md:443-445` says 687 differ; the artifact holds 75 — that count is stale.)

How failure looks, per candidate. Under **(a)**, or (b) without the rotation, the diff is a pure move: the same
eighteen lines, unchanged, after the parent's `}` instead of before its `define` — no content difference anywhere,
the signature of a correct body in the wrong place. Under **(b)** with the drain *before* `ir-fn-end`, the failure
is content: `%env` back on the parent's define line, `entry:` twice inside it, `%t1` defined twice — the original
symptom (`lower.md:430-434`) returning. A per-function counter shows as `$spawn$1` reused in the second spawning
function, which only the two-function fixture catches.
