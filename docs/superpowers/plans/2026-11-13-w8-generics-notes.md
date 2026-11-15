# W8 step 3b — generic instantiation: what Python does (measurement)

Read against `logos/check.py` and `logos/lower.py` at `08a5765`, and the port's
`src/logosc/{check,lower}.logos`. Every claim has a `file:line`.

## Where instances are discovered, and where recorded

- The **checker** owns discovery. `_check_call` sends a call whose callee's
  signature has a type variable to `_generic_call` (`logos/check.py:4602`).
- `_generic_call` reads each argument, unifies the parameter against the
  argument's type (`_unify`, one binding dict per call), then calls
  `_instantiate` and records `call_targets[node.path] = target.name`
  (`check.py:4672-4673`). Argument typing uses `hint = None` when the parameter
  holds a type variable (`check.py:4653`), so the literal widens to its default
  width — the instantiation is *not* inferred from a hint.
- `_instantiate` (`check.py:4676`) memoises on the **mangled name**: a second
  call with the same type tuple returns the existing copy (`check.py:4710`).
  A new one is appended to `self._instances` (insertion order) and pushed on
  `self._pending` (`check.py:4749-4750`).
- The type-parameter order is `_signature`'s: `typevars(ret)` first, then each
  parameter left to right, first appearance (`check.py:1752-1756`). This is the
  order the arguments are mangled and stored in.
- After **every** body of the module is checked (`run` walks fns then tests,
  `check.py:1570-1576`) the worklist is drained oldest-first (`_drain`,
  `check.py:4757-4767`). Checking a copy's body may append more copies, so the
  order is breadth-first from the module's bodies — a generic that calls a
  generic appends **after** its caller (`tests/test_generics.py:247-252`:
  `["twice$i64", "id$i64"]`), a recursive generic is one copy
  (`:255-261`).
- Copies are **per module**: `CheckedModule.instances` (`check.py:521`). An
  imported generic is refused, never instantiated in the caller
  (`check.py:4690-4696`).
- Ceiling: 256 distinct copies; the 257th is E0500 (`check.py:491`,
  `check.py:4733-4740`).

## Naming

- `mangle_instance(name, args)` = `name + "$" + mangle_type(arg)` per argument
  in type-parameter order (`check.py:534-546`). The fragments are **type text**,
  not codes: primitives keep their spelling (`i64`, `str`), a named type is
  `s<len>_<escaped>` (`s5_point`), composites spell their form
  (`vec(...)`, `fn(...)…`) (`check.py:547-600`). Two named types whose escapes
  collide stay distinct because the length is prefixed
  (`pick$s3_a_x2db` vs `pick$s6_a_x2db`, measured below).
- The lowerer mangles the copy like any other function: `lg.<module>.<copy>`
  (`lower.py` `symbol()`), so `lg.closures.id$i64`.

## How the lowerer treats definitions and copies

- A generic definition is **skipped**: not in the symbol map
  (`lower.py:1092-1096`) and not lowered (`lower.py:1122`). It has no body of
  its own.
- Each module lowers its ordinary functions **in source order**, then its
  `cm.instances.values()` **in discovery order** (`lower.py:1109-1126`).
- `instance()` (`lower.py:1651-1695`) lowers the *same source node* with the
  copy's `params`/`ret`, and with the copy's own `Types` record, so one path
  can mean `:i64` in one copy and `:str` in the next.
- A call site uses `call_targets[node.path]` and never re-unifies
  (`lower.py:4454-4470`): "Falling back to the source name would call a function
  this module never emitted, or emit a second copy the checker never saw."
- An **uninstantiated** generic is not emitted at all — no type to emit it at
  (`tests/test_generics.py:484-487`).

## Measured on `tests/exec/closures.logos`

`logos.driver.checked_program` + `lower.lower_program` (module lowering — no
test entry), ten copies, in this order:

```
id$i64, apply$i64$i64, first$i64$str, first$str$i64, id$str,
map$i64$i64, map$i64$str, add-with$i64, pick$s3_a_x2db, pick$s6_a_x2db
```

`generic` = `add-with apply first id map pick`. Emitted functions: five
non-generic module fns, `$lambda$1`…`$lambda$3` (from `make-doubler`,
`through-a-parameter`, and inside `add-with$i64`), then the ten copies — every
copy after every module function, and each `$lambda` before its enclosing
define.

**The copies come from test bodies as well as functions.** `id$i64` is the only
one a non-test body reaches (`twice-by`, line 13); `apply$i64$i64`,
`first$i64$str`, `first$str$i64`, `id$str`, `map$i64$i64`, `map$i64$str`,
`add-with$i64` and both `pick` copies are reached only from `(test …)` bodies
(lines 71, 90, 91, 98, 108, 121, 160, 174-175). The checker checks test bodies
and the lowerer does not emit them — that split is what the order above shows.

## What the checker hands the lowerer

`CheckedModule` (`check.py:519-523`): `instances` (name → `Instance{name, fn,
args, params, ret, body}`, `check.py:472-489`), `call_targets` (node path →
copy name), `generic` (names with no body). The port's equivalent handover would
be the same three: per (module, node) a copy name, per module an ordered copy
list with each copy's type-argument bindings, and the set of generic names to
skip.

## The port today

- `check.logos` has the naming and counting helpers (`check-instance-name`,
  `check-instance-add`, `check-instantiate`, `check.logos:2195-2252`) but no
  call site reaches them: a generic call site answers unknown
  (`check.md:200-224`). The `var-s`/`var-n` range on a `check-entry` holds the
  type-parameter order (`check.md:1001-1014`).
- `lower.logos` refuses a generic **definition** at its own node
  (`lower.logos:3500`), pinned by `fixtures/ir-refuse/generic-refuse`.
- The lowerer owns its own type arena and re-derives every expression type from
  the source (`lo-node-type`, `lower.logos:1235`), so a copy needs only a
  substitution from type-variable names to concrete arena ids; parsing the
  declaration's annotations under that substitution yields the copy's
  parameters, return type and every `let`/closure annotation inside its body.
- Checker node ids and lowerer node ids do not meet across the two modules (the
  checker loads each module's tree into a local arena, `check.logos:2092-2120`,
  and frees it), so a node-keyed handover would need a new module-indexed table
  on both sides. The lowerer's own walk sees the same call sites, so step 3b
  discovers copies there and drains them per module in the checker's order.
