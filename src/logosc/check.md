# `src/logosc/check.logos` — the declaration pass and the body pass

The Logos port of `logos/check.py`, in two halves. The **declaration pass** is
everything a module says about a name before any body is read: `fn` and
`extern fn` signatures, `type` declarations and their struct fields or enum
variants, the reserved names, the visibility a `use` buys, and the generic
instantiation counter. The **body pass** (W6 B1–B3) reads a `fn` body and
decides the scalar rules — literals with their widths, arithmetic, shifts,
casts, comparisons, `let`/`letmut`/`set` — the control-flow rules: `if`,
`while`, `match` with exhaustiveness and patterns, `ret`, `break`/`continue`,
the boolean forms, blocks, and E0105 for a function that falls off its end — and
the forms a body actually uses: calls with their arity and argument types,
`print`/`println`, `make`/`get`/`set-field`, the fixed-array, vector and string
families, `alloc`/`free`, the runtime-access forms, and E0107 for a binding
that is never read. `gen2 check <file>` is both.

Ownership is PR C. A form the body pass cannot type answers an unknown type
rather than a diagnostic, so a program is never refused for a rule a later
pass owns. That boundary is the
point of the coverage list in `tools/selfhost-check.txt`: a fixture named there
is one this pass decides, and one that is not named is one it deliberately
leaves to a later pass.

Read `types.md` first. This pass consumes the type arena that module builds and
adds the declaration tables on top of it.

## API

```logos
(type check-error (struct (failed :bool) (code :i64) (path :str) (message :str)))

(fn check-file check-error ((mods (ref (vec resolve-mod)))
                            (nodes (ref (vec node)))
                            (ntexts (ref (vec :str)))))

(fn check-code :str ((n :i64)))
```

`mods` is the module set `resolve-set` handed out: the root and every module
its imports reach, in the resolver's order, with each module's name, file and
definition range. `nodes` and `ntexts` are the root file's parsed arena. The
pass does not free any of the three; it allocates and frees its own arenas.

A diagnostic is the same four-field struct the lexer, tree and resolver use.
`check-code` spells the numeric tail the way `resolve-code` does, so `500` is
`E0500`. `gen2` prints `<path>: <CODE>: <message>` and exits 2, or prints
nothing and exits 0.

Two helpers make the generic machinery reusable by PR B:

```logos
(fn check-instance-name check-error ((tags names elem extra pbase ptypes)
                                     (name :str) (args (ref (vec :i64)))
                                     (where :str) (out (ref (vec :str)))))
(fn check-instance-add check-error ((keys vals slots)
                                    (instances (ref (vec :str)))
                                    (target :str) (where :str)
                                    (out (ref (vec :i64)))))
(fn check-instantiate check-error ((tags names elem extra pbase ptypes)
                                   (name :str) (args (ref (vec :i64)))
                                   (where :str) (keys vals slots instances)
                                   (out (ref (vec :str)))))
```

`check-instance-name` is `mangle_instance`: it appends `$` and each argument's
`type-mangle` spelling, so `(keep :i64 (vec point))` is
`keep$i64$vec(s5_point)`. A type variable argument is E0501 there, at `where`.
`check-instance-add` is the memo and the ceiling: a target already present
answers its old index without consuming budget, a new one is appended, and the
257th distinct target is E0500, `more than 256 instantiations of generic
functions`, at `where`. `check-instantiate` is the two together: it mangles the
name, then memoises the target and answers its index, so PR B's call site needs
one call, not two.

Two lookups are Python's `_owner` and `_in_build`:

```logos
(fn check-visible-owner :str ((ents vindex) (vis-s vis-e) (name :str) (kind :i64)))
(fn check-in-build :bool ((mods) (owner :str)))
```

The first answers the module that declared a visible name — `-1` matches a
type, function or extern, `1`/`2` narrow it — which is how PR B decides that a
call reaches a body this build lowers. The second answers whether that module
is one of the set being lowered. A body outside the set is E0103, not here.

## What it decides

| rule | code | where |
|---|---|---|
| `fn` needs a return type and a parameter list | E0002 | the `fn` |
| `fn` needs a parameter list | E0002 | the `fn` |
| a parameter must be `(name type)` | E0002 | the parameter |
| a parameter needs a name | E0002 | the parameter |
| duplicate parameter | E0003 | the second parameter |
| a parameter cannot be `:void` | E0100 | the parameter |
| `fn` needs a name | E0002 | the `fn` |
| reserved form name (`fn`, `type`, `extern`) | E0003 | the definition |
| `main` cannot have type variables | E0101 | the `fn` |
| `rt_` names are reserved | E0003 | the `fn` |
| `extern` needs a name | E0002 | the `extern` |
| an extern function cannot have type variables | E0101 | the `extern` |
| type does not cross the C boundary | E0002 | the return or parameter type |
| type needs a name / a struct or enum body | E0002 | the `type` |
| unknown type body | E0002 | the body form |
| a struct field must be `(name type)` | E0002 | the field |
| a field needs a name / duplicate field | E0002 / E0003 | the field |
| owning fields are not supported yet | E0002 | the field |
| vector fields are not supported yet | E0002 | the field |
| result fields are not supported yet | E0002 | the field |
| type variable in a field is unbound | E0501 | the field |
| an enum needs at least one variant | E0002 | the enum |
| an enum variant must be `(name)` or `(name type)` | E0002 | the variant / the body |
| a variant needs a name / duplicate variant | E0002 / E0003 | the variant |
| variant name reserved by the compiler | E0003 | the variant |
| a variant cannot hold `:void` | E0100 | the variant |
| vector / owning / result payloads are not supported yet | E0002 | the variant, or the payload type for an owner |
| `enum 'e' contains itself` | E0002 | the `type` |
| `unknown type 'x'` | E0101 | the type item |
| `a ref may name a vector only` | E0100 | the `(ref …)` form |
| `a container of owners is not supported yet` | E0002 | the container |
| `a vector cannot be inside an optional/result` | E0002 | the wrapper |
| `a result cannot be inside another result` | E0002 | the wrapper |
| `a result cannot be a vector or array element` | E0002 | the wrapper |
| the error type of a result must be a declared enum | E0100 | the `(res …)` |
| only a pointer, mutex, channel or atomic can be shared | E0002 | the `(shared …)` |
| shared state must be marked `(shared …)` | E0700 | the handle |
| an atomic needs `:i64` or `:u64` | E0100 | the `(atomic …)` |
| a channel element cannot be void/owner/vector/result/ref/closure | E0100/E0002/E0305/E0502 | the element type |
| duplicate definition `main` | E0003 | the second `main`, naming both |

The body pass adds:

| rule | code | where |
|---|---|---|
| a call's arity | E0102 | the call |
| an argument's type | E0100 | the argument |
| `unknown function 'x'` | E0103 | the call |
| an imported function with no body in this build | E0103 | the call |
| the entry point is not callable | E0108 | the call |
| `print`/`println` arity, and only a number, `:bool` or `:str` | E0102 / E0100 | the call / the argument |
| a vector argument must be a name | E0402 | the argument |
| a ref argument must be a mutable binding (and be one) | E0304 | the argument / the call |
| `make` arity; a vector starts empty; field or element counts | E0102 | the `make` |
| field or element type in a `make` | E0100 | the value |
| an owning array element or `make` of an enum | E0002 | the type / the `make` |
| `get`/`set-field` field lookup and type | E0100 / E0200 | the item / the `get` |
| a `set-field` target is mutable | E0104 | the `set-field` |
| `arr-get`/`arr-set` arity, index, element type, target mutability | E0102 / E0400 / E0100 / E0104 | the form |
| `vec-*` arity and shape | E0102 | the form |
| a vector operand is a `(vec T)` (a ref is read through) | E0100 | the operand |
| a mutating vector form needs a mutable name or a parameter | E0104 | the form |
| an index must be an integer | E0400 | the index |
| an element read copies a vector or owner | E0402 | the form |
| releasing a vector declared outside a loop | E0303 | the form |
| a string operand is a `:str` | E0401 | the operand |
| a runtime operand has its exact type (`:i64`, `:f64`, `:str`, `:run`, `(vec :str)`) | E0100 | the operand |
| `alloc` arity, count, a `:void` or invariant-bearing element | E0102 / E0100 / E0002 | the form / the count |
| `free` of a raw pointer | E0301 | the operand |
| `free` of anything that is not an owner | E0100 | the operand |
| a binding is never read | E0107 | its declaration |

The messages are Python's, word for word, and so are the node paths: the
failing parameter, field, variant or type item, never the whole definition.
Shape is decided where Python decides it: a field is `(name type)` before its
name is read, a parameter's name is read before the two-item shape is tested,
and a duplicate comes last in both — so `(a :i64 :i64)` beside an earlier `a`
is the E0002 Python prints, not the E0003 the repeated name would earn. A
parameter list whose own entries are not forms — `(x)`, `(x :i64)`, `(: x)` —
is E0002 at the `fn` or `extern`, not at the list: Python reads the bare token
where the tree keeps the form's head, and the diagnostic follows Python.

## What it deliberately does not decide

- **Generic call sites, E0500 and E0501.** A call to a definition whose
  signature mentions a type variable is not unified: the checker reads its
  arguments without a declared type (so a name inside one still counts as
  read) and answers the unknown type. `tests/generics/limit.logos` and
  `tests/generics/unbound.logos` therefore carry `.expect` files and `gen2
  check` accepts both. The declaration-side counter (`check-instantiate`) is
  ported and pinned, but a call site does not reach it yet.
- **Generic bodies.** A body is read only for a `fn` whose signature has no
  type variables. Python checks such a body once per instantiation; until the
  call site unifies, `gen2 check` cannot know which copy it is reading, so it
  reads none.
- **Ownership and results.** E0300–E0303, E0305, E0402's move half and
  E0600–E0602 are PR C; the type-shape half that a declaration can state (an
  owning field, a vector field, a result field or payload) is decided here.
  `free`/`vec-free` therefore do not empty a binding, and a call does not move
  its arguments.
- **E0107 and ownership.** E0107 is not reported for a binding whose initialiser
  is a name Python would move, because there Python's first diagnostic is E0302
  at a later line and a bare E0107 here would be the wrong code. The test is
  broader than that case: a plain `alloc` or `make` initialiser also escapes
  E0107, and Python does report it, so `(let v (vec :i64) (make (vec :i64)))`
  with no read is accepted by `gen2 check` and refused by Python. This is an
  under-report PR C narrows.
- **E0107 and unknown types.** A binding whose initialiser is unknown-typed
  (`(some 1)`, a `deref`, a function value) is not reported either. That guard
  exists because an unresolvable name is accepted here and Python's E0005 for
  it would otherwise be replaced by a wrong E0107; it costs the same class of
  under-report, and it goes when E0005 lands.
- **E0005 is not ported.** An atom that resolves to nothing is accepted.
  Python's `unknown name 'zzz'` is therefore missing, a read of another
  function's binding is accepted, and where an unrelated rule fires later the
  first diagnostic can differ (a body that Python refuses with E0005 can be
  refused here with E0105 instead). `tests/type/unknown-name.logos` stays off
  the coverage list for that reason.
- **Refs beyond the argument shape.** A `(ref (vec T))` parameter is read
  through and its argument is checked for mutability (E0304), which is what
  keeps a call from disagreeing with Python. Returning, storing, capturing or
  sending a ref (E0305) is PR C.
- **Closures, threads, raw pointers and results as expressions.** `fn`,
  `spawn`/`join`, `mutex`/`lock`/`unlock`, `chan`/`send`/`recv`,
  `atomic*`, `ptr`/`deref`/`set-deref`/`ptr-add`, `ok`/`err`/`some`/`none` and
  `try` still answer the unknown type. Nothing inside one is refused for a
  rule this pass owns, and every name an atom in one is marked read so E0107
  cannot blame a binding the deferred form used.
- **Test bodies.** Python checks a module's `test` bodies as well as its
  `fn`s; the port reads only `fn` bodies. A `test` body is therefore accepted
  unread, and any diagnostic Python raises inside one is under-reported.
- **Duplicate `main` across imports.** `check-file` carries
  `_refuse_duplicate_main` and reports it when its module set has two roots
  that each define `main`. `gen2 check` has one root, so for a single-file
  build the resolver's merge refuses the same program first (E0003 at the
  `use`). The check is still exercised by `duplicate-main` with a synthetic
  two-root module set.
- **Parameter and variant names after the module is done.** Names are checked
  for duplicates and for reserved spellings and then dropped; the persisted
  tables hold types and owners, which is what declarations need. The body pass
  reads names from the tree, which it still has (and records the declaring
  node for E0107).

## The body pass (W6 B1–B3)

`check-module-fns` records each own non-generic `fn` as it declares the
signature — the node and its `fn` type id, in the order the source declares
them — and `check-module-fn-bodies` walks that list from `check-module-tree`
once every declaration of the module is in, externs included. That is Python's
order: `run()` builds `_visible(module)` first, so every declaration error
precedes every body error, and the bodies are then read in declaration order.
Bodies are read for the **root module only** and only when the signature has no
type variables. Python's `check_module` checks the root's bodies and leaves an
import's bodies to the module that owns them; a generic body has no single type
and is checked per instantiation, which a call site does not fix yet (see
above). `gen2 check <file>` therefore rejects bodies while every earlier
accepted program — every module Python's checker accepts — stays accepted: a
whole-tree sweep over all 194 tracked sources found no program Python accepts
that `gen2 check` refuses.

`check-module-fn-bodies` carries the visible window (`ents`, `vindex`,
`vis-s`, `vis-e`) and the module's own name, because a call resolves its callee
against the same table a declaration's visibility built. They are threaded
through the body helpers beside the arenas; a call reads the window from
`bctl[2]`/`bctl[3]` and the module name from `bl[1]`.

The walk lives in `check.logos` rather than a new `body.logos` because it needs
the declaration pass's own material: `check-error`, `check-fail-at`,
`check-node-path`, `check-type` (which resolves a `let` annotation through
`dnames`/`dids` and the type arena), and `type-text` for its messages. A
separate module would either duplicate those or import `check`, and `check`
imports the body pass — a cycle the resolver refuses. The section is marked
with the `body-` prefix on every helper.

### The environment

One function's scope is parallel vectors the checker owns, plus the W3 map:

| vector | one entry per | holds |
|---|---|---|
| `bn` | binding | the id of the node that declared it — the path E0107 prints |
| `bt` | binding | the binding's type id |
| `bm` | binding | 1 for `letmut`, 2 for a parameter, 0 for a plain `let` |
| `bv` | binding | moved (never set in B1–B3; PR C sets it) |
| `bu` | binding | used — set by a read, by a call argument, by a place write, and read by E0107 |
| `bd` | binding | the scope depth that declared it (`bctl[0]` at the time) |
| `br` | function | one entry: the declared return type |
| `bl` | function | two entries: the label a message names (`function 'f'`) and the module's own name |
| `bk`/`bvl`/`bsl` | binding | the `map` from name to index; `map-get` is a lookup |
| `bctl` | function | four entries: block depth, loop depth, and the visible window's start and end |

A parameter is `bm == 2` rather than a separate flag: it is immutable like a
`let` (so `set` refuses it), but the mutating container forms accept it (the
callee owns the descriptor) and E0107 never reports it. `bd` still holds the
function block's depth, so a `let` that reuses a parameter's name is the E0003
Python reports.

`bctl` is the block and loop counter B2's forms need. Every branch, every
`while` body and every match arm raises `bctl[0]` for its statements, so `bd`
answers the "same scope" half of the duplicate test and a `let` in an arm is a
fresh binding rather than a redefinition of one in a sibling arm. The function
body is the one block that does not raise it: its statements run at the depth
of its parameters, which is what makes `(fn f :i64 ((x :i64)) (let x :i64 5)
…)` E0003, as Python answers. `body-walk` is that depth-preserving loop;
`body-block` is `body-walk` inside one raise, and is what a `while` body uses
(a nested block raises the depth in `body-block`/`body-arm-run`, so shadowing there is legal; the body itself does not raise).
`bctl[1]` counts the enclosing loops: `break` and `continue` are legal only
when it is non-zero, and it is raised *before* a `while` condition is typed,
because Python puts the condition inside the loop.

`bu` now has its reader: `body-unused` scans a closing scope for the first
binding at that depth that no read reached. The scan runs where Python's
`_unused` does — at the end of every block (`body-block`), every if branch and
match arm (`body-arm-run`), and the function block (`check-body-fn`) — and
after E0105, because a function that falls off its end answers that first. `_`
is the opt-out, a parameter is skipped by its `bm == 2`, and a write never sets
the flag, so a `letmut` that is only ever assigned is E0107. A binding whose
initial value came from a form this pass does not type, or whose value owns
memory, is marked read at its declaration: Python would refuse that
declaration under a rule PR C owns, so E0107 must not be the answer that
disagrees with it.

The `moved` join is the same shape as before: `body-restore` and
`body-union-moved` write `bv`, but nothing sets a moved flag until PR C, so the
join is written and PR C is what makes it observable.

`body-bind` appends a declaration and `map-put`s its index; a name already in
the map at the same depth is E0003. `body-snapshot`/`body-restore` are the pair
a B2 branch uses, and the state they carry is Python's `_Env.snapshot`/`restore`
plus the bindings Python gets from its block scopes:

- the snapshot records the binding count and every binding's `moved` flag, then
  the map's key count and every stored index;
- a restore writes the recorded flags and map values back, and writes `-1` over
  every map entry added since. `map-get` answers `-1` for a missing key, so the
  name is absent again; the key itself stays, and a later `map-put` of the same
  name reuses it, so no branch can make the key vector grow without bound;
- `mutable` is not part of the snapshot. It is a property of the declaration
  that no branch can change, and Python's snapshot does not record it either;
- `used` is not part of it. Python records only `moved`: `moved` is a property
  of the path a branch took, `used` a property of the whole function, so a read
  in one branch is a read after the join and must survive the restore.

A restore is used in exactly one pattern, strictly paired with one snapshot
taken by the same construct: `body-if`, `body-while` and `body-match` take one
before their first branch, restore it before each branch, restore it again after
the last, and then re-apply the union of the branches' `moved` flags through
`body-union-moved`. Restoring in any other order would resurrect a binding an
inner snapshot had killed, so the nesting is by construction LIFO: a form
restores its own snapshot only after every form it contains has returned, and
`match-nested-if` in the suite pins a `match` inside an `if` inside a `match`
arm that binds the same name twice.

Logos has no `vec-truncate`, so no environment vector is ever shrunk. A binding
a branch appended keeps its slot and the restored map is what makes it
unreachable, because every lookup goes through the map; the cost is one dead
slot per binding a branch declared. That is why the snapshot records the map's
values as well as its length: a shadowing `let` replaces a stored index in
place, adding no key, so only the recorded value can put the outer binding back.
The slot table `bsl` is a pure index over `bk`/`bvl`, so restoring the values
restores every lookup and a grow inside a branch only reorders the probes.
Restoring twice is harmless — a snapshot is a value, not a log that is consumed
— which is what sibling branches need: each one starts from the same state.

### What it decides

The walk is `body-statements` → `body-statement` → `body-expr` → `body-value`,
with a token reached by `body-token`. Every rule and message is Python's, at
Python's node:

| rule | code |
|---|---|
| a statement must be a form | E0002 |
| an empty form / a form with no name in front | E0002 |
| `ret` takes at most one value | E0102 |
| a function must `ret` its declared type; a bare `ret` is only for `:void` | E0100 |
| arithmetic takes at least two operands | E0102 |
| arithmetic needs numbers; no implicit widening; `%` is integers only | E0100 |
| a shift takes a value and a count; integer operands; the count keeps the width | E0102 / E0100 |
| `cast` takes a type and a value; both ends are numeric; the type must change | E0102 / E0100 |
| a comparison takes two operands; `< <= > >=` need numbers; `= !=` need scalars | E0102 / E0100 |
| `let`/`letmut` take a name, an optional type and a value | E0102 |
| a binding needs a name; a duplicate definition in the same scope | E0002 / E0003 |
| an annotation that does not resolve | E0101 |
| the initialiser must fit the annotation; `:void` cannot be bound | E0100 |
| `set` takes a name and a value; the name must be bound | E0102 / E0005 |
| `set` needs a mutable binding | E0104 |
| the value must fit the binding's type | E0100 |
| an integer literal outside its resolved width | E0106 |
| `if` takes a condition, a then and an else | E0102 |
| an `if`/`while` condition must be `:bool` | E0100 |
| `if` branches must agree | E0100 |
| `while` takes a condition and an optional body | E0102 |
| `match` takes a scrutinee and at least one arm | E0102 |
| a match arm must be `(pattern body...)`, with a body | E0002 / E0102 |
| `match` needs an integer, an enum, a result or an optional | E0100 |
| a variant pattern must name a variant of the scrutinee's type | E0100 |
| a payload variant needs `(variant name)`; a bare variant takes no name | E0100 / E0102 |
| a variant pattern binds one atom name, not a type | E0002 |
| an arm for a variant already handled can never match | E0002 |
| an arm after `_` can never match | E0002 |
| a closed set must be exhaustive | E0600 |
| match arms must agree | E0100 |
| an integer pattern is a literal that fits or `_` | E0002 / E0106 / E0100 |
| `break`/`continue` take no operands and need a loop | E0102 / E0002 |
| `and`/`or`/`not` take their operands and need `:bool` | E0102 / E0100 |
| a function must not fall off its end (E0105) | E0105 |

The literal's width is the expected type when that type is a matching
primitive, and `:i64`/`:f64` otherwise; arithmetic, shifts, comparisons, a
`let` annotation and `ret` all pass that expectation down, and the look-ahead
rule is Python's: a literal beside a non-literal takes the non-literal's type,
in either argument order. The range test is done on the decimal text, not on a
parsed integer, because a `:u64` literal may exceed `:i64`; a sign, leading
`+`, and leading zeros are handled, and the bounds are the width's decimal
maximum (and the magnitude of its minimum for a signed width).

A `set` still needs `letmut`: a parameter is immutable for `set`, as Python
says, even though a later pass lets some container forms write through one.

### Control flow (W6 B2)

`body-if`, `body-while` and `body-match` are Python's `_if`, `_while` and
`_match`; `body-arm-run` is `_arm` and is also the block an `if` branch uses
(one item, checked as a value). Each branch is checked from the state before the
first one, and the state is restored before each sibling.

`match` reads its spine first, with Python's `match_shape`, and only then the
scrutinee — so a malformed arm beats a bad scrutinee. The spine refuses a match
without an arm or a body, an arm that is not a form, a pattern form whose head
is not a name, and an arm after `_`. The scrutinee then picks one of four
readings: an integer (its arms are literals, because no finite list of them
covers the domain; a fall-through is the runtime's), an enum, a result or an
optional. The last three are *closed* sets, so the same fall-through is
statically impossible and a missing arm is E0600; a `_` arm covers the rest.

The variant table is the one thing the declaration pass had to grow. An enum's
payload types were already in the arena (`extra` variants at `pbase` in
`pchild`), but their *names* were only ever used to refuse a duplicate and then
dropped, so a match on an imported enum had nothing to resolve an arm against.
`pvname` is one name per `pchild` slot, pushed beside every payload and field
the declaration pass records, so variant `i` of enum `e` is
`(pvname (+ (pbase e) i))` with payload `(pchild (+ (pbase e) i))` — `-1` for a
variant that holds nothing. A result's variants are `ok`/`err` and an
optional's are `some`/`none`, spelled in `body-variant-name`; both take their
payload types from `elem`/`extra` of the type node.

E0105 is `body-any-terminates` over the body's statements: a `ret` terminates,
an `if` terminates when both arms do, a `match` when every arm does, and
`(while true ...)` when nothing in it can `break` out. A block terminates when
*any* of its statements does, so unreachable code after a `ret` is allowed, as
Python allows it. The check runs after the statements are read, at the `fn`
node, with the enclosing block's label and return type.

### What it deliberately does not decide

Every form outside the table answers `body-unknown` (`-2`). `body-fits` treats
an unknown operand as fitting everything, a literal with an unknown expectation
takes its default width, and no check runs against an unknown — so a body is
never refused because a later pass would have typed it. The forms left alone
are:

- a bare atom that is not a local binding and not `true`/`false` — a visible
  function's name used as a value, a variant constructor, or a name that Python
  would call E0005 are all unknown here (so `tests/type/unknown-name.logos`
  stays out of the list);
- `fn`, `ptr`, `deref`, `set-deref`, `ptr-add`, `spawn`, `join`, `mutex`,
  `lock`, `unlock`, `chan`, `send`, `recv`, `atomic-*`, `ok`, `err`, `some`,
  `none` and `try` — PR C's forms and the closure form. Their operands are not
  typed, but every atom anywhere inside one is marked read, so E0107 cannot
  blame a binding the deferred form used;
- a scrutinee whose type is unknown — a deferred form's result, or a generic
  call's — is read as "some closed set I cannot see": its arms' shapes are
  checked (the spine is a spine whatever the type) but no variant is resolved,
  counted or required, so `(match (parse x) ...)` is accepted unread;
- `test` bodies, and every `fn` whose signature mentions a type variable;
- ownership, results and every E03xx/E04xx/E06xx rule: PR C. That includes
  `_branches`' other job: E0402 for an `if`/`match` whose arms select a vector
  or an owner, and the `(res …)` obligation a matched scrutinee discharges
  (E0602).

A form's error ordering inside a body is Python's — arguments are visited left
to right and a bad operand stops the form — and the order across the module is
Python's too: every declaration error precedes every body error, because the
bodies are read only after the last declaration. `check_test.logos` pins it with
a module that holds both.

### Calls, containers and E0107 (B3)

A form whose head is not a body rule is `body-call`. It looks for a local
binding first (a function value), then a visible definition in the module's
window, then the printers, then PR C's deferred names, then an enum variant
constructor, and only then answers E0103. Python's order, and Python's reason
for each step: a binding shadows a definition, `print` lives outside the
function namespace, a variant name is not a function, and a name that is none
of those is `unknown function`. A definition is looked up in the same
`ents`/`vindex` window the declaration pass built, so the callee's signature is
the `fn` type node itself: arity is its `extra`, parameter `i` is
`(type-param-type ptypes pbase sig i)`, and the result is its `elem`. An
extern's entry is a `fn` too, so a call across the C boundary obeys the same
argument rules with no separate path. Two refusals happen before the arguments:
a call to a definition owned by another module is E0103 (this build emits no
body for it), and a call to a generic answers unknown after marking its
arguments read (see "What it deliberately does not decide").

`body-arguments` walks the arguments left to right. A `(ref (vec T))`
parameter reads its argument as a place — only a name can be borrowed (E0304),
an unknown name is E0005, and the name must be a `letmut` or another ref
(E0304) — and checks the referenced type, never the address. A parameter that
holds a vector needs the argument to be a whole name (E0402, `a vector argument
must be a name`), because the callee owns the descriptor; a temporary would
leave two names for one buffer. Every other parameter types its argument at
the parameter's type, which is what lets an integer literal sit in a narrower
width, and a mismatch is E0100 with Python's `argument N of 'f' expects …`
sentence.

The container families are one function each, dispatched by `body-expr`. What
they share: `make` reads its type with `check-type` (so a struct or array
spelling is resolved by the same rule a `let` annotation uses), a vector type
starts empty, a struct needs one value per field and an array one per element,
and each value is typed at the field's or element's type; `get`, `arr-get` and
`vec-get` refuse to copy a value that owns memory (E0402 from
`body-refuse-place-copy`), because a place read would give two names one block;
`set-field`, `arr-set`, `vec-push`, `vec-set` and `vec-free` need a mutable
binding or a vector parameter, and the vector forms read a ref through to its
descriptor. `alloc` refuses an element whose every bit pattern is not a value
(`body-invariant-free?`, E0002), and `free` refuses a raw pointer (E0301) and
anything that is not an owner (E0100). The string forms share one operand rule
(E0401) and one index rule (E0400); the runtime forms each name their exact
operand type (E0100) and the shape `run` requires by name (E0100).

E0107 is the scope-closing rule above. It reports the first binding of the
closing scope in declaration order, so a declaration's path is the node recorded
in `bn` and the name is recovered from the map (`body-name-at`). Because a
branch restores the map before its sibling runs, and a scope closes before its
parent resumes, the scan sees exactly the bindings that scope declared.

## The arena of checked modules

The pass owns the same type arena `types.logos` defines, plus three tables that
describe the module set. All are parallel vectors; none is a container of
containers.

| vector | one entry per | holds |
|---|---|---|
| `tags names elem extra pbase powner pnames ptypes` | type node | the A1 arena, `parse-type` and `type-text` |
| `pchild` | struct field or enum payload | the field/payload type id, at `pbase[ty] + i` |
| `pvname` | struct field or enum payload | its name, at the same index — what a match arm resolves against |
| `ents` (`check-entry`) | visible definition | name, type or signature id, kind (0 type, 1 fn, 2 extern), owner module, type-variable range |
| `vindex` | a module's visible entry | an index into `ents`; a module's `vis-s..vis-e` is its slice |
| `mods` (`check-mod`) | module | name, file, own range, visible range, state |
| `fvname` | generic function | the type variables in `mangle_instance` order |

A declared struct or enum is a node in the type arena: `pbase` starts its run in
`pchild`, `extra` is the field or variant count, and `powner` is the declaring
module. A function is a `fn` type node (`elem` is the return type, `extra` the
arity, `pbase` the parameter run in `ptypes`); a generic's variables live in
`fvname` and the entry's `var-s`/`var-n` locate them.

The type-variable order is Python's `_signature` order, not `typevars`'s walk:
the return type first, then each parameter left to right. `typevars` walks a
function type's parameters before its return, so using it directly would name
instances differently from Python's monomorphisation.

## Order

`check-file` first scans every module for `main` (duplicate roots), then visits
module 0 and lets `check-module` recurse through its imports before its own
definitions. Inside a module the order is Python's:

1. each import, in `use` order, once;
2. every own type name declared, in source order (`_declared` body check);
3. every own type name checked against `reserved_name`;
4. every struct/enum body read, in source order;
5. every own enum tested with `enum_contains_itself`;
6. every own `fn`: `rt_`, reserved name, signature — and, for the root module's
   non-generic functions, a record of the node and its type id for step 8;
7. every own `extern fn`: reserved name, signature, C-boundary walk;
8. every recorded body, in declaration order, once the whole module is declared.

Steps 7 and 8 are in Python's order: `run()` reads every declaration of a module
first and only then the root's bodies, so a declaration error in a module beats
a body error in the same module.

Only the first failure is reported. A module is checked once (`state` 2); a
module already being checked is not re-entered, which is what makes a diamond
one visit. An imported module's tree is read from its own file, so a lex or
tree failure there names that file's path (E0006 / E0001), never the root's.

Visibility is exactly one `use` deep: a module's visible table is its imports'
**own** entries plus its own. An import's imports are not copied, so a type
reached only through a second module is `unknown type` (E0101) in the first,
which is Python's E0101 for a declaration and its E0005 for a name inside a
body.

## The C boundary

`_crosses` is ported whole: primitives that are one machine value in C
(every integer and float width, `:bool`, `:str`), a pointer or `(shared …)`
around one, and a struct whose every field crosses. The walk carries the names
of the structs it is inside, and a name already on that stack answers false: a
struct that points at itself does not cross — the pointer does not end the
walk, the cycle does. A struct that contains itself by value cannot exist (the
field rules refuse the cycle's other half). An enum, a vector, an owner, a
result, an optional, a function value and a channel do not cross, so an
`extern` naming one is E0002 at the type.

## Coverage

`tools/selfhost-check.txt` names the corpus cases this pass decides, and
`tools/selfhost.sh` runs `gen2 check` over exactly that list:

```text
tests/type/extern-noncl.logos           E0002
tests/type/unknown-type.logos           E0101
tests/type/ref-not-a-vector.logos       E0100
tests/regress/reserved-name.logos       E0003
tests/regress/recursive-enum.logos      E0002
tests/regress/rt-definition.logos       E0003
tests/type/param-bare-name.logos        E0002
tests/type/cast-nonnumeric.logos        E0100
tests/type/cast-same.logos              E0100
tests/type/float-mix.logos              E0100
tests/type/immutable-set.logos          E0104
tests/type/shift-float.logos            E0100
tests/type/literal-range.logos          E0106
tests/type/compare-bool.logos           E0100
tests/type/non-exhaustive.logos         E0600
tests/type/missing-return.logos         E0105
tests/type/match-duplicate.logos        E0002
tests/type/arity.logos                  E0102
tests/type/unknown-fn.logos             E0103
tests/type/widening.logos               E0100
tests/type/free-raw.logos               E0301
tests/type/vec-get-place.logos          E0402
tests/type/index-type.logos             E0400
tests/type/not-a-str.logos              E0401
tests/type/unused-binding.logos         E0107
tests/type/vec-arg-temp.logos           E0402
tests/regress/vec-place-copy.logos      E0402
tests/regress/main-call.logos           E0108
tests/regress/alloc-enum.logos          E0002
tests/regress/alloc-enum-in-struct.logos E0002
tests/regress/alloc-fn.logos            E0002
tests/type/alloc-fn.logos               E0002
tests/type/alloc-result.logos           E0002
```

The last ten of the original seventeen are the B1/B2 body cases: a cast of a
`:bool`, a cast that would not change the type, a float beside an `:i64` in
`+`, a `set` of a plain `let`, a shift of a `:f64`, a `:u8` literal that does
not fit, an ordered comparison of two `:bool`s, a match that misses a variant,
a function that falls off its end, and a match arm for a variant an earlier arm
already handled. `literal-range`, `compare-bool`, `missing-return` and
`match-duplicate` are new corpus cases added with their pass, because no
existing fixture named E0106, the ordered-comparison rule, E0105 or the
duplicate-arm rule.

The last sixteen are B3's: a call's arity, an unknown function, an argument at
another type, `free` of a raw pointer, an element read that would copy a
vector (twice, from `vec-get` and from the same rule's regress case), a
non-integer index, a string operand that is not a `:str`, an unread binding,
a vector passed as a temporary, the entry point called from a body, and the
five `alloc` cases whose element has an invariant. `index-type`,
`not-a-str`, `unused-binding` and `vec-arg-temp` are new corpus cases added
with the pass: nothing named E0400, E0401 or E0107, and no fixture passed a
temporary where a vector was expected.

The gate compares the whole line `gen2 check` prints — path, code and message —
with the `.check` sidecar beside each fixture, prints
`check: N fixtures, M differences`, and fails on any difference. The sidecars
are generated by `tools/check_parity.py` from the reference implementation, so
a reworded message or a wrong path fails the gate instead of passing on a
matching code. Its floor is 33: a pruned list fails rather than passing over
fewer fixtures. `move`, `loop-move`, `try-mismatch`, `unhandled-result`,
`closure-escape`, the ref-escape cases and `owner-place-read` need PR C;
`limit` and `unbound` need a generic call site; `unknown-name` needs E0005 from
the function/variant namespace; `generic-vector` needs the generic call's
argument rules; the visibility fixtures under `src/logosc/fixtures/check` are
unit cases, not corpus cases.

## Tests

`src/logosc/body_test.logos` has 173 cases for the body pass, each run at
`-O0` and `-O2` with `(leaks 0)`, through `check-file` on a synthetic source:

- literals: a width's maximum, a signed minimum, a `:u64` value beyond `:i64`,
  a leading `+`, leading zeros and a value one past each bound (E0106);
- arithmetic: the literal look-ahead in both argument orders, a width
  mismatch, a float beside an integer, `%` on floats, a non-numeric operand and
  the two-operand arity;
- shifts: the literal look-ahead, a count of the wrong width, a float operand
  and the value-and-count arity;
- casts: a narrowing cast, a cast that names its own type, a `:bool` operand,
  a non-numeric target and the type-and-value arity;
- comparisons: literal adoption, an ordered comparison of `:bool`s, equality
  of `:bool`s and the two-operand arity;
- `let`/`letmut`: a mismatched annotation, a missing value, a missing name, an
  unknown annotation, a `:void` initialiser and a duplicate binding;
- `set`: a plain `let`, a parameter, an unknown name, a type mismatch and the
  accepted `letmut` write;
- `ret`: a value of the wrong type, a bare `ret` in a non-`void` function and
  the arity;
- the boundary: a parameter is typed, and a deferred form's result is the
  unknown type;
- the environment: `body-snapshot`/`body-restore` restore the `moved` flags and
  the map through three branches — one that shadows an outer name, one that
  binds a new name, and one that leaves the environment untouched — asserting
  the state after each branch and again after a second restore;
- `if`: an accepted pair, a value in expression position, the arity, a
  `:i64` condition, disagreeing branches and the void pair;
- `while`: a counted loop, the arity, a `:i64` condition, a body statement that
  is not a form, a binding shadowed inside the body, a duplicate inside the
  body, `(while true ...)` that never returns, one that `break`s, a `break`
  under an `if`, `break`/`continue` outside a loop, a `break` with an operand,
  and `continue` in a body;
- `match` on an enum: an exhaustive pair, one missing variant and two, a `_`
  arm, an arm after `_`, a duplicate arm, an unknown variant, a payload written
  bare, a payload written on a payload-less variant, two bound names, a payload
  whose binding is used at the wrong type, a `:type` where a name belongs, an
  ignored `_` payload, `set` on the payload, a payload that shadows an outer
  binding, a `let` inside an arm, an arm's value, disagreeing arms, a nested
  match, and a `match` inside an `if` inside an arm that rebinds the same name
  twice;
- `match` on a result and an optional: `ok`/`err`, `some`/`none` both spellings,
  and a missing variant in each;
- `match` on an integer: a literal table with and without `_`, a non-literal
  pattern, a literal outside the width, a float pattern, a form pattern and a
  string pattern;
- `match`'s spine and type: the arity, a bare-token arm, an empty arm, an arm
  with no body, a form pattern whose head is not a name, a number-headed form
  pattern, and a `:f64`/`:bool` scrutinee;
- E0105: a function that ends without a `ret`, an `if` with one arm missing it,
  the accepted `if` and `match` pairs, `void` needing none, code after a `ret`,
  and `(while c (ret ...))` which is not a terminating loop;
- `and`/`or`/`not`: the accepted nest, their arities and their operand types,
  and an `if` whose condition is one;
- calls: a direct call, the arity (too few and too many), an argument at the
  wrong width, an unknown function, `main` called from a body, an extern call
  and an extern's arity;
- printers: an accepted `print`/`println` pair, the arity, and a vector
  argument;
- vectors: an accepted build/push/set/len/get/free, the push arity, a string
  index, a vector read out of a vector (E0402), a free and a push of a plain
  `let` (E0104), a `set` index and a `set` value, and `make` with elements;
- fixed arrays: an accepted make/set/get, the get arity, a string index, and
  `make` with too few elements;
- structs: an accepted `get` and `set-field`, an unknown field (E0200), a
  `get` of a non-struct, and a `set-field` of a plain `let`;
- `alloc`/`free`: an accepted allocate-and-free, an enum's invariant (E0002),
  a non-integer count, a raw pointer (E0301) and a non-owner;
- strings: an accepted `str-concat`/`str-len`, a number where a `:str` is
  required (E0401), a slice index (E0400), the `str-from-i64` cast hint, and
  `read-file` of a number;
- runtime access: `args` freed through `vec-free`, and a temporary where
  `run` needs the name of a `(vec :str)`;
- E0107: an unread `let`, the `_` opt-out, a binding read only as a call
  argument, one read only by `set`, a parameter (never reported), a `let`
  inside an if branch, a match payload, and E0105 winning over E0107 when the
  function also falls off its end.

`src/logosc/check_test.logos` has 75 cases, each run at `-O0` and `-O2` with
`(leaks 0)`:

- one per declaration rule above, through `check-file` on a synthetic source —
  including the six "needs a name" messages, the `expected a type after ':'`
  rule, the result-inside/result-element and channel-element rules, the two
  malformed-shape cases that Python answers E0002 before the duplicate E0003,
  and the parameter list whose entries are not forms: a bare name, a name with
  its type and a head-only parameter, each at Python's path;
- the visibility pair: a type imported through one `use` is visible, the same
  name without the `use` is E0101, and a type reached only through a second
  module is E0101 in the first;
- a two-root duplicate `main`, through `check-file`;
- a module holding both a body error and a later declaration error — an unknown
  parameter type and a duplicate parameter — which pins the rule that every
  declaration error precedes every body error;
- `check-instance-name` naming (`keep$i64$vec(s5_point)`), E0501 for a type
  variable argument, the 257th-distinct-target E0500, and a repeated target
  reusing its index without consuming budget;
- `check-code 500` is `E0500`;
- `check-visible-owner` and `check-in-build` over a two-module table.

The "extern needs a name" case is called on `check-extern-signature` directly
with a raw tree: the resolver refuses a nameless `extern` before the checker
sees it, so no source file can reach the rule through `check-file`.

The suite is
`python3 -m logos test src/logosc/check_test.logos --opt -O0 --opt -O2` for the
declarations and
`python3 -m logos test src/logosc/body_test.logos --opt -O0 --opt -O2` for the
body pass, both run from the repository root because the visibility fixtures
are reached by path.

## Parity

The thirty-three coverage fixtures match Python's code **and node path**, not
just the code, and the whole line, message included, is what
`tools/check_parity.py` writes and the gate compares. The ten B1/B2 body cases
pin `cast-nonnumeric/f/2/0`, `cast-same/f/2/0`, `float-mix/f/4/0`, `m/f/3`,
`shift-float/f/2/0`, `literal-range/f/2`, `compare-bool/f/2/0`,
`non-exhaustive/classify/2`, `missing-return/classify` and
`match-duplicate/label/2/2/0`. The sixteen B3 cases pin
`arity/m/f/2/0`, `unknown-fn/m/f/2/0`, `widening/m/f/2/0/0`,
`free-raw/free-raw/f/2`, `vec-get-place/f/4/1`, `vec-place-copy/f/4/1`,
`index-type/f/2/0`, `not-a-str/f/2/0`, `unused-binding/f/2`,
`vec-arg-temp/f/2/0`, `main-call/helper/2/0`, `alloc-enum/f/2/1`,
`alloc-enum-in-struct/f/2/1`, `alloc-fn/f/2/1` (twice, from `tests/regress` and
`tests/type`) and `alloc-result/f/2/1`.

The differential probe behind the body pass compares `gen2 check` with Python's
`check_module` over the tree. A sweep of all 194 tracked sources finds:

- **0 false positives** — no program Python accepts is refused by `gen2 check`;
- **0 code disagreements** — where both refuse, the code is the same;
- 93 sources are accepted by both, and 74 are refused by both: 73 with the
  same line and one with the same code and a different path spelling;
- 27 sources are under-reported, every one of them inside the deferred set:
  8 are an imported call inside a `test` body (the port reads only `fn`
  bodies), 12 are ownership or a ref (E0300/E0302/E0303/E0305, and E0402's
  owner-place half), 2 are E0500/E0501 at an unported generic call site, 1 is
  `generic-vector` (the same call site), 2 are E0601/E0602 from a result, 1 is
  a closure escape (E0502), and 1 is E0005 for an unbound name (B1's deferred
  namespace lookup);
- against the B2 binary, 30 sources are newly refused with Python's line — the
  16 coverage fixtures this pass gains, 13 programs that call an imported
  definition (E0103, the rule a resolved import now reaches), and
  `tests/type/ref-not-mutable.logos` (the argument-shape half of E0304) — and
  nothing B2 refused is accepted now;
- the one source outside those buckets answers the same E0002 with a different
  path spelling: `tests/parse/no-mod.logos`, where Python names an empty path
  for a file with no `(mod …)` and gen2 names the file. It is the W6 A
  declaration edge, untouched by B2 and B3.

## Building it

`check.logos` is part of `gen2`'s module set: it is compiled with every
`src/logosc/*.logos` file and `src/std/map.logos`/`src/std/str.logos`.
`tools/selfhost.sh` builds that binary and runs both `fmt` and the check phase
with it. `gen2` must run from the repository root: a missing import is looked
for beside the asking file and then in `src/std`, both relative to the working
directory, exactly as the resolver's contract says.
