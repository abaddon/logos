# `src/logosc/check.logos` — the declaration pass

The first half of the Logos port of `logos/check.py`: everything a module says
about a name before any body is read. `fn` and `extern fn` signatures,
`type` declarations and their struct fields or enum variants, the reserved
names, the visibility a `use` buys, and the generic instantiation counter.
`gen2 check <file>` is this pass.

Bodies, statements and expressions are PR B; ownership is PR C. This file does
not read a `fn` body at all. That boundary is the point of the coverage list in
`tools/selfhost-check.txt`: a fixture named there is one this pass decides, and
one that is not named is one it deliberately leaves to a later pass.

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
```

`check-instance-name` is `mangle_instance`: it appends `$` and each argument's
`type-mangle` spelling, so `(keep :i64 (vec point))` is
`keep$i64$vec(s5_point)`. A type variable argument is E0501 there, at `where`.
`check-instance-add` is the memo and the ceiling: a target already present
answers its old index without consuming budget, a new one is appended, and the
257th distinct target is E0500, `more than 256 instantiations of generic
functions`, at `where`.

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

## What it deliberately does not decide

- **Bodies.** A `fn` body is not read, not even its statements. A module whose
  declarations are legal passes, whatever its body says. That is why
  `tests/type/arity.logos` (E0102 from a call), `alloc-fn` and `alloc-result`
  (E0002 from `alloc`, which is an expression), `unknown-name` (E0005) and
  every ownership fixture are **not** in the coverage list.
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
6. every own `fn`: `rt_`, reserved name, signature;
7. every own `extern fn`: reserved name, signature, C-boundary walk.

Only the first failure is reported. A module is checked once (`state` 2); a
module already being checked is not re-entered, which is what makes a diamond
one visit.

Visibility is exactly one `use` deep: a module's visible table is its imports'
**own** entries plus its own. An import's imports are not copied, so a type
reached only through a second module is `unknown type` (E0101) in the first,
which is Python's E0101 for a declaration and its E0005 for a name inside a
body.

## The C boundary

`_crosses` is ported whole: primitives that are one machine value in C
(every integer and float width, `:bool`, `:str`), a pointer or `(shared …)`
around one, and a struct whose every field crosses. A struct that points at
itself crosses because the pointer ends the walk; a struct that contains
itself by value cannot exist (the field rules refuse the cycle's other half).
An enum, a vector, an owner, a result, an optional, a function value and a
channel do not cross, so an `extern` naming one is E0002 at the type.

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
```

The gate compares the code with the `.expect` beside each fixture, prints
`check: N fixtures, M differences`, and fails on any difference. Its floor is
6: a pruned list fails rather than passing over fewer fixtures. The other
`tests/type` cases need a body (PR B); `alloc-enum` and `alloc-enum-in-struct`
need `alloc` (PR B); the visibility fixtures under `src/logosc/fixtures/check`
are unit cases, not corpus cases.

## Tests

`src/logosc/check_test.logos` has 51 cases, each run at `-O0` and `-O2` with
`(leaks 0)`:

- one per declaration rule above, through `check-file` on a synthetic source;
- the visibility pair: a type imported through one `use` is visible, the same
  name without the `use` is E0101, and a type reached only through a second
  module is E0101 in the first;
- a two-root duplicate `main`, through `check-file`;
- `check-instance-name` naming (`keep$i64$vec(s5_point)`), E0501 for a type
  variable argument, the 257th-distinct-target E0500, and a repeated target
  reusing its index without consuming budget;
- `check-code 500` is `E0500`;
- `check-visible-owner` and `check-in-build` over a two-module table.

The suite is
`python3 -m logos test src/logosc/check_test.logos --opt -O0 --opt -O2`, run
from the repository root because the visibility fixtures are reached by path.

## Parity

The six coverage fixtures match Python's code **and node path**, not just the
code: `extern-noncl/fill/1/0`, `m/f/1/0`, `ref-not-a-vector/move/1/0/0`,
`reserved-name/get`, `recursive-enum/e`, `rt-definition/rt_create`. The
45-case differential run behind the test file (every declaration rule, both
the message and the path) is the same comparison the suite pins; the one
difference it records is a `ret`-expression type error, which belongs to PR B.

## Building it

`check.logos` is part of `gen2`'s module set: it is compiled with every
`src/logosc/*.logos` file and `src/std/map.logos`/`src/std/str.logos`.
`tools/selfhost.sh` builds that binary and runs both `fmt` and the check phase
with it. `gen2` must run from the repository root: a missing import is looked
for beside the asking file and then in `src/std`, both relative to the working
directory, exactly as the resolver's contract says.
