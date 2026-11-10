# `src/logosc/types.logos` — the type arena

The Logos port of `logos/types.py` and of `mangle_type` from `logos/check.py`.
A type is a node in a flat arena, not a Python object: `parse-type` reads one
tree node into that arena, `compatible` compares two ids, `substitute` and
`typevars` walk it, and `mangle-type` spells it exactly as the IR does.

Logos has no comments and no doc form, so this file is the documentation the
source cannot carry. Read `tree.md` first: `parse-type` reads the arena
`tree-parse` built, and that arena's shape decides how a type form is read
(see *The tree's shape* below).

## API

```logos
(fn type-parse type-error ((nodes (ref (vec node))) (ntexts (ref (vec :str)))
                           (dnames (ref (vec :str))) (dids (ref (vec :i64)))
                           (tags (ref (vec :i64))) (names (ref (vec :str)))
                           (elem (ref (vec :i64))) (extra (ref (vec :i64)))
                           (pbase (ref (vec :i64))) (powner (ref (vec :str)))
                           (pnames (ref (vec :str))) (ptypes (ref (vec :i64)))
                           (id :i64) (where :str) (out (ref (vec :i64)))))
(fn type-compatible :bool ((tags …) (names …) (powner …) (elem …) (extra …)
                           (pbase …) (ptypes …) (a :i64) (b :i64)))
(fn type-substitute :i64 ((tags …) (names …) (elem …) (extra …) (pbase …)
                          (powner …) (pnames …) (ptypes …)
                          (bnames (ref (vec :str))) (btypes (ref (vec :i64)))
                          (ty :i64)))
(fn type-variables :void ((tags …) (names …) (elem …) (extra …) (pbase …)
                          (ptypes …) (ty :i64) (out (ref (vec :str)))))
(fn type-has-var :bool ((tags …) (names …) (elem …) (extra …) (pbase …)
                        (ptypes …) (ty :i64)))
(fn type-mangle type-error ((tags …) (names …) (elem …) (extra …) (pbase …)
                            (ptypes …) (ty :i64) (where :str)
                            (out (ref (vec :str)))))
```

`type-parse` takes the id of the tree node that spells the type, writes the new
arena id to `out[0]`, and returns the first failure. It never frees the caller's
arena or the tree; the ids it returns are indices into the caller's vectors.
`type-mangle` writes its spelling the same way and returns `E0501` when the type
still mentions a type variable.

Every walker takes the vectors it reads and nothing else, so the same arena can
be threaded through a checker pass without a second copy.

## The arena

Ten parallel vectors, all the caller's:

| vector | type | one entry per |
|---|---|---|
| `tags` | `:i64` | type node: the tag below |
| `names` | `:str` | type node: a primitive's spelling, a declaration's name, a variable's name; otherwise `""` |
| `elem` | `:i64` | type node: the first child type id, `-1` when none |
| `extra` | `:i64` | type node: the second child or the count (below) |
| `pbase` | `:i64` | type node: the first row of its payload run, `-1` when none |
| `pnames` | `:str` | `fn` parameter: its name |
| `ptypes` | `:i64` | `fn` parameter: its type id |
| `pattrs` | `:i64` | `struct`/`enum` field or variant: the field name's **text id** in `ntexts` |
| `pchild` | `:i64` | `struct`/`enum` field or variant: its type id, `-1` for a payload-less variant |
| `powner` | `:str` | type node: the module that declared a `struct`/`enum`; `""` when unresolved |

`pbase` is the one vector the wave's sketch did not name, and it is the one the
arena cannot do without: a payload run needs a start. The alternative — summing
the earlier nodes' counts — is O(n) per access and silently wrong the moment a
run is appended out of node order.

The fifteen tags, in the order `types.py` lists them:

| tag | name | `names` | `elem` | `extra` | payload |
|---|---|---|---|---|---|
| 0 | `prim` | the primitive | — | — | — |
| 1 | `ptr` | `""` | element | — | — |
| 2 | `own` | `""` | element | — | — |
| 3 | `arr` | `""` | element | length | — |
| 4 | `vec` | `""` | element | — | — |
| 5 | `ref` | `""` | the `vec` | — | — |
| 6 | `res` | `""` | ok type | error type | — |
| 7 | `opt` | `""` | element | — | — |
| 8 | `fn` | `"fn"` or `"fn*"` | return type | arity | `pnames`/`ptypes` |
| 9 | `shared` | `""` | element | — | — |
| 10 | `chan` | `""` | element | — | — |
| 11 | `atomic` | `""` | element | — | — |
| 12 | `struct` | the name | — | field count | `pattrs`/`pchild` |
| 13 | `enum` | the name | — | variant count | `pattrs`/`pchild` |
| 14 | `var` | the variable | — | — | — |

There is no separate closure tag: the fifteen the wave names are all of them, so
`(fn* …)` is tag `fn` with `names` = `"fn*"`. The head is part of the type
(`FnTy.captures` in Python), and spelling it from `names` is how `compatible`
and `mangle-type` see the difference.

`pattrs` holds a **tree text id**, not an arena string, because a field name is
already an atom in the tree and the text table outlives every parse; copying it
would duplicate the one thing the caller already owns. `pnames` holds a copied
`:str` because a function type is also built from a call's expected signature,
which has no tree row behind it.

## Constructors

One per `Ty` constructor, plus the two declaration forms:

| function | builds |
|---|---|
| `type-prim name` | `:name` |
| `type-ptr child` … `type-own`, `type-vec`, `type-ref`, `type-opt`, `type-shared`, `type-chan`, `type-atomic` | the unary forms |
| `type-arr child count` | `(arr T n)` |
| `type-res ok err` | `(res T E)` |
| `type-fn head ret arity base` | `(fn …)`/`(fn* …)`; `base` is the `ptypes` index its parameters were appended at |
| `type-var name` | a type variable |
| `type-struct name owner base count` | a declaration; `base`/`count` index `pattrs`/`pchild` |
| `type-enum name owner base count` | the same for an enum |

Each takes the six core vectors by `(ref …)` and returns the new id, which is
always `(vec-len tags) - 1`. `type-param` appends one `(name, type)` row;
`type-params-append` copies a temporary run in order. `type-field` appends one
`(name text id, type id)` row. Callers capture a run's start *before* appending
with `type-param-start` / `type-field-start`.

The two-phase shape is not ceremony. A parameter's type may itself be a function
type, whose own parameters are appended while the outer list is being read; if
the outer rows were appended as each type came back, the two runs would
interleave and `pbase`/arity would describe a mixture. `type-parse-fn` and
`type-substitute` therefore collect into temporary vectors and append once, so a
run is contiguous.

## Accessors

`type-tag`, `type-name`, `type-elem`, `type-extra`, `type-owner`,
`type-param-name`, `type-param-type`, `type-field-name`, `type-field-type`,
`type-field-count`, `type-param-start`.

`type-param-*` and `type-field-*` add `pbase[ty]` to their index, so `-1` rows
are never read when the arity or the count is zero: `type-fn` stores `pbase = -1`
for a function type with no parameters.

## `parse-type`

`parse-type` is pure syntax. It validates the closed primitive list first,
because that list needs no module to know, and leaves a bare name as a
`struct` node with `owner = ""` for the checker to resolve — unless the caller's
declaration table holds the name, in which case the declaration's own id is
returned. That table is `(dnames, dids)`; `type-decl-find` scans it and returns
`-1` for an absent name. A module's namespace holds one entry per visible name,
so a duplicate is refused before the table is built (E0003, A2's rule), and the
first match is the answer.

| source | result |
|---|---|
| `:i64`, `:str`, … | `prim`, exactly `PRIMITIVES` |
| `:nope` | `E0101 unknown type ':nope'` |
| `T`, `:T` | `var` (a single capital, with or without the colon) |
| `point` | the declared id, or a `struct` node with an empty owner |
| `(vec T)`, `(ptr T)`, `(own T)`, `(opt T)`, `(shared T)`, `(chan T)`, `(atomic T)` | one element type; extra or missing items are `E0101` |
| `(arr T n)` | `n` must be a `NUMBER` token of digits: `E0101 an array length must be a non-negative integer` otherwise |
| `(ref (vec T))` | `ref`; anything else is `E0100 a ref may name a vector only` |
| `(res T E)` | `res` |
| `(fn :ret ((p :t) …))`, `(fn* …)` | `fn`, with the parameter names in `pnames` |
| `()` or a list with no atom head | `E0101 expected a type, found an empty list` |
| `(wat :i64)` | `E0101 unknown type form 'wat'` |
| a number or a string in a type slot | `E0101 expected a type, found number` / `… string` |

Diagnostics carry `code`, `path` (the caller's `where`) and `message`; `type-code`
spells the code (`E0101`, `E0501`, …). The struct is the same one the lexer and
the resolver use, so `main` can print any of the three with one function.

A parameter is `(name type)` or `(name :type)` — the marker form. A malformed
one is `E0002 a parameter must be (name type)`; a missing or `:`-prefixed name
is `E0002 a parameter needs a name`.

### The tree's shape

Two facts about the tree arena decide this file:

1. **`first` already skips the head.** `tree-parse` stores a list's head text in
   `node.text` and points `node.first` at the first item *after* the head, so a
   type form's payload starts at `first` and has no head in the chain.
   `type-nth`/`type-count` read that chain, and the arities in the table above
   are payload counts: `(vec)` has none, `(arr :i64 4)` has two.
2. **A `fn`-headed list also skips a name slot.** `tree-parse` treats `fn` as a
   named kind, so for `(fn :i64 ((a :i64)))` the "name" is `:i64` — which
   `tree-plain-text` rejects because it starts with `:`, leaving `first` on the
   return type. For `(fn point ((a :i64)))` the bare name *is* taken as the
   name, `first` lands on the parameter list, and the return type is only
   reachable through `node.name`'s text. `type-parse-fn` handles both: a node
   with a name has one payload item (the parameter list) and reads its return
   type from that text id; a node without one has two (return type, parameters).

The second is a property of the tree, not of the type language, and it is why
`parse-type` reads `node.name` at all. A `fn` *declaration* has the same shape
and A2 inherits the same rule: `(fn f :i64 ((a :i64)))` has payload
`[ret, params, body…]`, while a `fn` type with a bare-name return has
`[params]` and its return in `node.name`.

## `compatible`

Identity, never conversion:

- `-1` (no type) matches only `-1`.
- a type variable compares by name and is not a wildcard;
- primitives compare by spelling;
- `struct`/`enum` compare by name **and** owner, where an empty owner means "not
  resolved here" and matches any owner;
- `arr` compares length and element; `res` compares both halves;
- `fn` compares head (`fn` vs `fn*`), arity, every parameter and the return type.

There is no widening, no subtyping and no conversion: `:i64` never matches
`:i32`, and `(arr :i64 4)` never matches `(arr :i64 5)`. The relation is
symmetric because every clause is.

Two declarations with one name from two modules are therefore different types
while spelling identically — `point` is `s5_point` either way, which is exactly
why `compatible`, not the spelling, is the question the checker asks.

## `substitute`

`substitute` replaces each bound variable by the type the caller chose, and
leaves an unbound one in place: only the caller knows whether that is a call
site's E0501 or a signature that is not being instantiated yet. Primitive and
declaration nodes are returned unchanged (a declaration is not rebuilt: its
fields belong to the declaration, not to the use). Composites are rebuilt in the
same arena, so a substituted type is a new id and the original is untouched;
sharing the unchanged ids is deliberate — a type is immutable.

Bindings are two parallel vectors, `bnames`/`btypes`; the last binding for a name
wins, as a dict assignment does.

## `typevars` and `has-typevar`

`typevars` appends every variable in first-appearance order, and for a function
type it walks the **parameters first and the return type last**. That is what
`types.py` does, and it is not what its own docstring says ("read from the return
type first"): the caller at `check.py:1734` compensates by taking `typevars(ret)`
first and then folding the parameters in. The port matches the code, and the
test `vars-params-before-return` pins it — `(fn :T ((a (vec U)) (b :V)))` answers
`U,V,T`. A port that trusted the docstring would name a copy's type arguments in
a different order and disagree with Python's monomorphisation.

`type-has-var` is the same walk returning a bool, without allocating.

## `mangle-type`

The spelling `logos/check.py:547` produces, form for form:

| type | spelling |
|---|---|
| primitive | its name: `i64` |
| declaration | `s`/`e` + length + `_` + escaped name: `s5_point`, `e11_parse_x2derror` |
| unary wrapper | `ptr(…)`, `own(…)`, `vec(…)`, `opt(…)`, `shared(…)`, `chan(…)`, `atomic(…)` |
| array | `arr(elem,n)` |
| result | `res(ok,err)` |
| function | `fn(p1,p2)ret` / `fn*(…)ret` |
| type variable | `E0501 type variable T cannot be a type argument` |

`mangle-type` refuses a type variable rather than spell it: encoding one would
give every unbound variable the same fragment and silently merge two copies. The
message names the first variable in `typevars` order.

`type-fragment` is `_name_fragment`: the character count, `_`, then every
character outside `[A-Za-z0-9_]` as `_xHH`. The length prefix is what makes the
pair injective — `_escape_name` alone maps `a-b` and `a_x2db` to the same text.
The escape is byte-wise, so a name outside ASCII spells each UTF-8 byte; Python's
`ord(char)` would spell the code point. Names are atoms from the lexer, and the
corpus is ASCII; the difference is stated here rather than hidden.

### The one divergence: `ref`

`mangle_type` has no `Ref` branch. `(ref (vec :i64))` is a legal type —
`parse_type` produces it, `Ref` is in the `Ty` union — and mangling it raises
`E0101 cannot mangle (ref (vec :i64))`. The port spells it `ref(vec(i64))`, the
way every other unary wrapper spells itself, because a checker that cannot spell
a legal type cannot instantiate a generic call that passes one. The two parity
rows below are the only rows the reference cannot answer; the generator records
its diagnostic beside the port's spelling. Fixing Python is a separate change
with its own regress case, and this wave may not make it.

## The module-qualified declaration form

`type-decl-spelling` is `lower.Symbols.type_name`: with `qualified = false` it is
the bare name; with `true` it is `<owner>.<name>` (`m.point`). A single-module
unit keeps the bare name — that is `_qualify` being false — and a multi-module
unit prefixes the declaring module, because one LLVM identified type cannot be
two modules' `point`. It is a separate function from `mangle-type` on purpose:
the mangled fragment must stay owner-free to match Python byte for byte, while
the IR's declaration name must not.

## What it does not do

- **No declaration checking.** `pattrs`/`pchild` are storage; whether a struct
  may hold a vector, whether an enum contains itself, and whether a field name
  repeats are A2's rules.
- **No resolution.** A bare name with no table entry stays a `struct` node with
  an empty owner, as `parse_type` leaves a `StructRef`. E0101 for an undeclared
  name is the checker's.
- **No unification.** `substitute` applies a binding the caller already chose;
  binding a variable to an argument is the call checker's.
- **No output.** Every function returns a value; `main` prints it.

## Tests

`src/logosc/types_test.logos` has 87 cases, each run at `-O0` and `-O2` with
`(leaks 0)`: 56 parity rows, 2 `ref` rows, and 29 behaviour cases.

The parity half is generated by `tools/types_parity.py`. Each row names a Logos
source spelling and the `logos.types` value it stands for; the expected text is
`logos.check.mangle_type` of that value, so the table cannot drift from the
reference by a typo. The test parses the source with the real lexer and tree,
calls `type-parse` and `type-mangle`, and asserts the printed line. Run
`python3 tools/types_parity.py` to regenerate; it rewrites the file and formats
it, so the result is a fixed point of `fmt`.

| source | table | spelling |
|---|---|---|
| `:i8` | — | `i8` |
| `:i16` | — | `i16` |
| `:i32` | — | `i32` |
| `:i64` | — | `i64` |
| `:u8` | — | `u8` |
| `:u16` | — | `u16` |
| `:u32` | — | `u32` |
| `:u64` | — | `u64` |
| `:f32` | — | `f32` |
| `:f64` | — | `f64` |
| `:bool` | — | `bool` |
| `:str` | — | `str` |
| `:void` | — | `void` |
| `:thread` | — | `thread` |
| `:mutex` | — | `mutex` |
| `:run` | — | `run` |
| `(vec :str)` | — | `vec(str)` |
| `(vec (vec :i64))` | — | `vec(vec(i64))` |
| `(vec (ptr :u8))` | — | `vec(ptr(u8))` |
| `(vec (arr :i64 4))` | — | `vec(arr(i64,4))` |
| `(ptr point)` | struct | `ptr(s5_point)` |
| `(ptr (vec :i64))` | — | `ptr(vec(i64))` |
| `(ptr (ptr point))` | struct | `ptr(ptr(s5_point))` |
| `(own point)` | struct | `own(s5_point)` |
| `(own (vec :str))` | — | `own(vec(str))` |
| `(arr :i64 4)` | — | `arr(i64,4)` |
| `(arr (vec :i64) 2)` | — | `arr(vec(i64),2)` |
| `(arr (arr :i64 3) 2)` | — | `arr(arr(i64,3),2)` |
| `(arr (ptr point) 8)` | struct | `arr(ptr(s5_point),8)` |
| `(arr :bool 0)` | — | `arr(bool,0)` |
| `(opt point)` | struct | `opt(s5_point)` |
| `(opt (vec :i64))` | — | `opt(vec(i64))` |
| `(opt (own point))` | struct | `opt(own(s5_point))` |
| `(res :i64 parse-error)` | enum | `res(i64,e11_parse_x2derror)` |
| `(res (vec :i64) e)` | — | `res(vec(i64),s1_e)` |
| `(res :i64 (vec :str))` | — | `res(i64,vec(str))` |
| `(res (opt :i64) (vec point))` | struct | `res(opt(i64),vec(s5_point))` |
| `(shared (chan point))` | struct | `shared(chan(s5_point))` |
| `(shared (atomic :i64))` | — | `shared(atomic(i64))` |
| `(chan :str)` | — | `chan(str)` |
| `(chan (vec :u8))` | — | `chan(vec(u8))` |
| `(atomic :i64)` | — | `atomic(i64)` |
| `(atomic :bool)` | — | `atomic(bool)` |
| `(fn :i64 ((a :i64) (b :str)))` | — | `fn(i64,str)i64` |
| `(fn* :void ((a point)))` | struct | `fn*(s5_point)void` |
| `(fn :void ())` | — | `fn()void` |
| `(fn (vec :i64) ((v (vec :i64))))` | — | `fn(vec(i64))vec(i64)` |
| `(fn (fn :i64 ((a :i64))) ((f (fn :i64 ((a :i64))))))` | — | `fn(fn(i64)i64)fn(i64)i64` |
| `(fn point ((a :i64)))` | struct | `fn(i64)s5_point` |
| `(fn point ((a :i64) (b point)))` | struct | `fn(i64,s5_point)s5_point` |
| `point` | struct | `s5_point` |
| `parse-error` | enum | `e11_parse_x2derror` |
| `(ptr i64)` | — | `ptr(s3_i64)` |
| `(vec parse-error)` | enum | `vec(e11_parse_x2derror)` |
| `(res parse-error (vec parse-error))` | enum | `res(e11_parse_x2derror,vec(e11_parse_x2derror))` |
| `(ref (vec :i64))` | — | `ref(vec(i64))` — Python: `E0101 cannot mangle (ref (vec :i64))` |
| `(ref (vec point))` | struct | `ref(vec(s5_point))` — Python: `E0101 cannot mangle (ref (vec point))` |

`table` names the declaration table the test passes: `struct` declares `point`
in module `m`, `enum` declares `parse-error` in module `m`, `—` is an empty
table. The last row is how `(ptr i64)` stays `ptr(s3_i64)`: a bare `i64` is a
declared name, and the `s` prefix is what keeps it from passing for the
primitive.

The behaviour cases pin the parts a spelling cannot show:

| case | pins |
|---|---|
| `compat-vec-same`, `compat-width`, `compat-arr-length` | identity, not widening; array length is part of the type |
| `compat-fn-captures`, `compat-fn-param-names` | `fn` vs `fn*` differ; parameter *names* do not |
| `compat-var-same`, `compat-var-different`, `compat-var-is-not-a-wildcard` | a variable compares by name and matches nothing else |
| `compat-owner` | two `point`s from two modules are different, and each is itself |
| `subst-vector`, `subst-fn` | substitution is total over the vocabulary |
| `subst-leaves-unbound` | an unbound variable survives and then refuses to be mangled |
| `vars-params-before-return`, `vars-nested` | `typevars` order, including inside `res` |
| `has-var-yes`, `has-var-no` | `has-typevar` sees a nested variable |
| `decl-spelling` | `point` and `m.point` |
| `struct-fields`, `enum-payloadless-variant` | `pattrs`/`pchild`/`pbase` read back, and a variant with no payload is `-1` |
| `parse-*`, `mangle-var-error` | each `E0100`/`E0101`/`E0501` message |

Run the suite from the repository root:

```text
python3 -m logos test src/logosc/types_test.logos --opt -O0 --opt -O2
python3 -m logos test src/logosc --opt -O0 --opt -O2
```

## Build set

`src/logosc/types.logos` imports `tree` (`(use tree)`) and nothing else; it is
part of `src/logosc/*.logos`, so `gen2` and the self-hosted gate build it with
the rest of the front end. `src/logosc/types_test.logos` is likewise a module
whose `(test …)` forms are run by the suite and never by `gen2`'s `main`.
