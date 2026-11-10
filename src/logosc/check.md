# `src/logosc/check.logos` — the declaration pass and the scalar body pass

The Logos port of `logos/check.py`, in two halves. The **declaration pass** is
everything a module says about a name before any body is read: `fn` and
`extern fn` signatures, `type` declarations and their struct fields or enum
variants, the reserved names, the visibility a `use` buys, and the generic
instantiation counter. The **body pass** (W6 B1) reads a `fn` body and decides
the scalar rules: literals with their widths, arithmetic, shifts, casts,
comparisons, `let`/`letmut`/`set` and `ret`. `gen2 check <file>` is both.

Control flow, calls and containers are B2/B3, and ownership is PR C. A form the
body pass cannot type answers an unknown type rather than a diagnostic, so a
program is never refused for a rule a later pass owns. That boundary is the
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

- **Non-scalar bodies.** The body pass reads a `fn` body and decides the scalar
  rules only. A call, a function or variant name used as a value, `if`,
  `while`, `match`, `and`/`or`/`not`, `make`/`get`/`set-field`/`arr-*`,
  `vec-*`, `alloc`/`free`/`ptr-*`, the thread forms, closures and `try` answer
  the unknown type `-2` and are not refused. So `tests/type/arity.logos`
  (E0102 from a call), `alloc-fn` and `alloc-result` (E0002 from `alloc`) and
  `unknown-name` (E0005) stay out of the coverage list until B2/B3. The full
  boundary is under "The body pass" below.
- **Ownership and results.** E0300–E0305, E0402 and E0600–E0602 are PR C; the
  type-shape half of them that a declaration can state (an owning field, a
  vector field, a result field or payload) is decided here.
- **Allocation invariants.** `_invariant_free` is reached only from `alloc`,
  an expression, so it is PR B even though the enum it refuses is a
  declaration. `tests/regress/alloc-enum*` are therefore absent from the list.
- **Duplicate `main` across imports.** `check-file` carries
  `_refuse_duplicate_main` and reports it when its module set has two roots
  that each define `main`. `gen2 check` has one root, so for a single-file
  build the resolver's merge refuses the same program first (E0003 at the
  `use`). The check is still exercised by `duplicate-main` with a synthetic
  two-root module set.
- **Parameter and variant names after the module is done.** Names are checked
  for duplicates and for reserved spellings and then dropped; the persisted
  tables hold types and owners, which is what declarations need. PR B reads
  names from the tree, which it still has.
- **Generic instantiation, E0500 and E0501.** `check-instance-name`,
  `check-instance-add` and `check-instantiate` decide both, and the suite pins
  them, but `gen2 check` never calls them: an instantiation happens where a
  generic function is *called*, and a call is an expression in a body (PR B).
  `tests/generics/limit.logos` and `tests/generics/unbound.logos` therefore
  carry `.expect` files and `gen2 check` accepts both — the declaration pass
  has nothing to refuse in either. They stay out of the coverage list until
  PR B, which is where a call site exists for a corpus case to name.

## The body pass (W6 B1)

`check-fn-one` calls `check-body-fn` after a function's signature is declared,
for the **root module only** and only when the signature has no type variables.
Python's `check_module` checks the root's bodies and leaves an import's bodies
to the module that owns them; a generic body has no single type and is checked
per instantiation, which is B3. `gen2 check <file>` therefore begins to reject
bodies while every earlier accepted program — every module Python's checker
accepts — stays accepted: a 159-module sweep over `src/` and `tests/` found no
program Python accepts that `gen2 check` now refuses.

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
| `bn` | binding | the name's text id |
| `bt` | binding | the binding's type id |
| `bm` | binding | mutable (`letmut` is 1, `let` and a parameter 0) |
| `bv` | binding | moved (never set in B1; PR C sets it) |
| `bu` | binding | used — set by a read, never by a `set` |
| `bd` | binding | the scope depth that declared it (always 0 in B1) |
| `br` | function | one entry: the declared return type |
| `bl` | function | one entry: the label a message names, `function 'f'` |
| `bk`/`bvl`/`bsl` | binding | the `map` from name to index; `map-get` is a lookup |

`body-bind` appends a declaration and `map-put`s its index; a name already in
the map at the same depth is E0003. `body-snapshot` copies the `moved` and
`mutable` flags in declaration order, and `body-restore` puts them back — the
pair a B2 branch will use, exactly as Python's `_Env.snapshot`/`restore` do.
B1 has one block per function and no branch, so the depth is always 0, the map
never needs a shadowed entry restored, and nothing writes `moved`.

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

### What it deliberately does not decide

Every form outside the table answers `body-unknown` (`-2`). `body-fits` treats
an unknown operand as fitting everything, a literal with an unknown expectation
takes its default width, and no check runs against an unknown — so a body is
never refused because a later pass would have typed it. The forms left alone
are:

- control flow: `if`, `while`, `match`, `break`, `continue`, and the boolean
  forms `and`, `or`, `not`;
- calls, and a bare atom that is not a local binding and not `true`/`false` —
  a visible function's name, a variant constructor, or a name that Python
  would call E0005 are all unknown here (so `tests/type/unknown-name.logos`
  stays out of the list);
- every container and aggregate form: `make`, `get`, `set-field`, `arr-*`,
  `vec-*`, `str-*`, `read-*`, `args`, `run*`, `alloc`, `free`, `ptr*`,
  `deref`, `set-deref`, `spawn`, `join`, `mutex`, `lock`, `unlock`, `chan`,
  `send`, `recv`, `atomic-*`, `ok`, `err`, `try`, `some`, `none`;
- closures, and `test` bodies;
- E0105 (`missing return`): deciding it needs the `if`/`match`/`while`
  termination walk, which is B2;
- E0107 (`unused binding`): a name read inside a form this pass leaves alone
  must not be reported unused, and the block-exit bookkeeping that makes the
  answer exact arrives with B2's scopes;
- ownership, results and every E03xx/E04xx/E06xx rule: PR C.

A form's error ordering inside a body is Python's — arguments are visited left
to right and a bad operand stops the form — but bodies are checked as each
`fn` is declared, so a module with both a body error and a later declaration
error may name the body error first, where Python checks every declaration
first. No corpus case has two errors.

## The arena of checked modules

The pass owns the same type arena `types.logos` defines, plus three tables that
describe the module set. All are parallel vectors; none is a container of
containers.

| vector | one entry per | holds |
|---|---|---|
| `tags names elem extra pbase powner pnames ptypes` | type node | the A1 arena, `parse-type` and `type-text` |
| `pchild` | struct field or enum payload | the field/payload type id, at `pbase[ty] + i` |
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
6. every own `fn`: `rt_`, reserved name, signature, then its body — the body
   only for the root module and only when the signature declares no type
   variables;
7. every own `extern fn`: reserved name, signature, C-boundary walk.

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
tests/type/extern-noncl.logos          E0002
tests/type/unknown-type.logos          E0101
tests/type/ref-not-a-vector.logos      E0100
tests/regress/reserved-name.logos      E0003
tests/regress/recursive-enum.logos     E0002
tests/regress/rt-definition.logos      E0003
tests/type/param-bare-name.logos       E0002
tests/type/cast-nonnumeric.logos       E0100
tests/type/cast-same.logos             E0100
tests/type/float-mix.logos             E0100
tests/type/immutable-set.logos         E0104
tests/type/shift-float.logos           E0100
tests/type/literal-range.logos         E0106
tests/type/compare-bool.logos          E0100
```

The last seven are the body pass's: a cast of a `:bool`, a cast that would not
change the type, a float beside an `:i64` in `+`, a `set` of a plain `let`, a
shift of a `:f64`, a `:u8` literal that does not fit, and an ordered
comparison of two `:bool`s. `literal-range` and `compare-bool` are new corpus
cases added with the pass, because no existing fixture named E0106 or the
ordered-comparison rule.

The gate compares the whole line `gen2 check` prints — path, code and message —
with the `.check` sidecar beside each fixture, prints
`check: N fixtures, M differences`, and fails on any difference. The sidecars
are generated by `tools/check_parity.py` from the reference implementation, so
a reworded message or a wrong path fails the gate instead of passing on a
matching code. Its floor is 14: a pruned list fails rather than passing over
fewer fixtures. `widening` (E0100 at an argument) and `arity` (E0102 at a call)
still need B2's call rule; `move`, `loop-move`, `free-raw` and the other
ownership cases need PR C; `alloc-enum` and `alloc-enum-in-struct` need
`alloc`; `unknown-name` needs the function/variant namespace; the visibility
fixtures under `src/logosc/fixtures/check` are unit cases, not corpus cases.

## Tests

`src/logosc/body_test.logos` has 44 cases for the scalar body pass, each run at
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
- the boundary: `if` and a call are accepted unread, and a parameter is typed;
- the environment: `body-snapshot`/`body-restore` put the `moved` and
  `mutable` flags back.

`src/logosc/check_test.logos` has 73 cases, each run at `-O0` and `-O2` with
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

The fourteen coverage fixtures match Python's code **and node path**, not just
the code, and the whole line, message included, is what
`tools/check_parity.py` writes and the gate compares. The seven body cases pin
`cast-nonnumeric/f/2/0`, `cast-same/f/2/0`, `float-mix/f/4/0`, `m/f/3`,
`shift-float/f/2/0`, `literal-range/f/2` and `compare-bool/f/2/0`.

The differential probe behind the body pass is a 154-source comparison of
`gen2 check` against Python's `check_module`, covering every scalar rule, the
literal boundaries, both look-ahead orders, shapes, arities and error ordering:
**no unexpected difference**. The 28 differences it records are exactly the
deferred set — E0107 unused bindings and E0103 from a call, both of which this
pass deliberately leaves to B2 — plus `make` and `get`, which are B3. A sweep
of all 159 tracked modules over `src/` and `tests/` found no program Python
accepts that `gen2 check` refuses.

## Building it

`check.logos` is part of `gen2`'s module set: it is compiled with every
`src/logosc/*.logos` file and `src/std/map.logos`/`src/std/str.logos`.
`tools/selfhost.sh` builds that binary and runs both `fmt` and the check phase
with it. `gen2` must run from the repository root: a missing import is looked
for beside the asking file and then in `src/std`, both relative to the working
directory, exactly as the resolver's contract says.
