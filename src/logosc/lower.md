# `src/logosc/lower.logos` — the tree into the IR arena

The lowering: the reference implementation's `lower.py`, ported to Logos for
declarations, expressions, `if`/`while`/`match`, direct and `extern` calls. The
Python module was deleted at the cutover; this is the lowering now.
It is the third reader of the parsed tree (after `resolve` and `check`) and the
only writer of the module `emit` prints. `lower-build` returns a `lower-error`
and fills the same arena `emit` reads; it prints nothing and knows no paths.

Read `types.md`, `ir.md` and `emit.md` first. This file adds no language
surface: it walks the tree `tree.logos` builds and records rows in `ir.logos`'s
tables, in the order `llvm.py` would.

## The entry point

```text
lower-build mtriple mqual snames sbase scount sftys enames ewords gnames gdata
            dnames dsig dcnt dret sigtys fnames fsyms fint fret fbase fcnt
            fparam fpc pnames ptys blabels bbase bcnt bterm bty bhas bv1 bv2
            bv3 ops dests sa sb sc sd t1 t2 t3 n1 sst scn tst tcn svals tvals
            tags tnames elem extra pbase powner tpnames tptypes pchild pvname
            nod ntx mnods mntx mstarts mends
```

Sixty-seven vectors, no more and no less: the module tables `emit` prints, the
type arena `types.logos` fills, and the parsed tree. The call is long because
the language has no struct of vectors and the arena is passed by reference;
every `lo-*` function below takes the same list in the same order, and a caller
(today `main.logos`'s `main-built`) allocates all of it once.

The tree is a **unit**, not a root. `mnods` holds every module's nodes
concatenated and `mntx` its texts; `mstarts`/`mends` are the half-open
`[start, end)` range of each module in those two vectors, pushed in pairs
(nodes, texts) by `main-append`. `nod`/`ntx` are the *current* module's slice:
`lo-refill` frees them and re-pushes `[mstarts[2m], mends[2m])` before each
pass over module `m`, so a pass walks exactly one module with node ids that
start at 0 again. That is why every pass below is wrapped in a
`(while (< m nmods) …)` loop rather than a single walk.

`lower-build` does four things, in this order:

1. pushes a passing `lower-error` into the one-element `berr` vector, so every
   later lookup can read the verdict in one index;
2. zeroes the sixteen `st` slots, so counters start at `%t0`/`%v.0`;
3. opens the module (`ir-module`) with the triple and `mqual`, which is
   `nmods > 1`: one module keeps the bare names (`%struct.point`), a unit of two
   or more qualifies them (`%struct.shapes.point`);
4. makes four passes over the whole unit, each refilling `nod`/`ntx` per module
   and walking that module's children in source order: type rows
   (`lo-scan-types1`), then the rows those declarations need (`lo-scan-types2`),
   then signatures (`lo-scan-sigs`), then bodies (`lo-fn`). The order matters:
   a signature may name a type another module declares, so every type row exists
   before any signature is read, and every signature exists before a body calls
   it.

## Errors are data, not exceptions

Python raises `LogosError`; a `lower-error` here is a value:

```logos
(type lower-error (struct (failed :bool) (code :i64) (path :str) (message :str)))
```

The first failure wins. `lo-fail`/`lo-fail-at` write it into `berr[0]` and every
other write is a no-op (`lo-bad` is the guard), so the pass does not have to
unwind: each step begins with `(if (lo-bad berr) (ret …) (lo-nothing))` and the
walk tests `lo-bad` in its loop condition. `lo-fail-at` fills `path` with the
node path from `tree-path`, which is what makes the diagnostic name a form
rather than a line. `lo-path` is the same call behind the `tok = -1` guard, and
it is also what every allocation site passes to `rt_alloc` (the string the leak
report names): the path is a stored text id, so asking for it costs a
`vec-get`, not a walk of the module. `lower-code` renders the number the way `types.logos` does
(`2` → `E0002`, `103` → `E0103`), so the codes are `diag.py`'s, not a second
table.

A form this backend does not lower yet is not a panic: `lo-not-yet` fails with
code 2 and the message `'<head>' is not lowered by this backend yet`, at the
form's own node path. The gate prints that line and exits 2.

## The arena

Every table is a parallel vector whose index **is** the id `ir.logos` stores,
so a row refers to its neighbours by integer and nothing is copied:

| vectors | one row per | holds |
|---|---|---|
| `mtriple`, `mqual` | the module | target triple; whether names are already qualified (`false` here) |
| `snames`, `sbase`, `scount`, `sftys` | struct | final name, first field in `sftys`, field count |
| `enames`, `ewords` | enum | final name, payload words |
| `gnames`, `gdata` | string global | `.strN`, the bytes **with** the trailing NUL |
| `dnames`, `dsig`, `dcnt`, `dret`, `sigtys` | `extern` | name, parameter base, arity, return type |
| `fnames`, `fsyms`, `fint`, `fret`, `fbase`, `fcnt` | function | source name, symbol, `internal`, return type, first block, block count |
| `fparam`, `fpc`, `pnames`, `ptys` | function | parameter base and count, then one row per parameter |
| `blabels`, `bbase`, `bcnt`, `bterm`, `bty`, `bhas`, `bv1`, `bv2`, `bv3` | block | label, first instruction, count, and its one terminator |
| `ops`, `dests`, `sa`–`sd`, `t1`–`t3`, `n1`, `sst`, `scn`, `tst`, `tcn`, `svals`, `tvals` | instruction | opcode, result name, up to four string operands, three type ids, one count, a string run, a type run, and the two values |
| `tags`, `tnames`, `elem`, `extra`, `pbase`, `powner` | type | constructor tag, spelling, first child, field count, first field/param, declaring module |
| `tpnames`, `tptypes`, `pchild`, `pvname` | type | a function type's parameters; a struct's fields |

The type arena is the one from `types.logos`; this file only adds rows to it
(`lo-prim`, `lo-ptr`, `lo-size`, …) and never re-numbers anything. `ir.logos`
bounds-checks a type id when it prints, so a wrong id is an `ir-error` at
`emit`, not a stray `%struct.` line.

`lower-build` also owns the work tables, which are the pass's state rather than
the module's: `nod`/`ntx` (the tree), `tnk`/`tnv`/`tnl` and
`fnk`/`fnv`/`fnl` and `enk`/`env`/`enl` and `vnk`/`vnv`/`vni`/`vnp` (maps from
name to id for types, functions, externs, variants), `bindn`/`bindt`/`binds`/
`binda` (the scope stack: name, type, slot, live), `plan`/`planty` (the alloca
plan), `st` (the counters), `loopx`/`looph` (the loop stack: exit label, head
label), `esc` (labels some branch still targets), `cl` (the open block), `berr`
(the failure). They are freed at the end of `lower-build`; nothing else is
allocated, because a string is a slice of the source or a literal.

## Blocks and slots

The lowering emits into exactly one open block at a time. Its label lives in
`cl`; `lo-w-block` seals it and starts a new one:

- a block is sealed once — `st[7]` is set, and `lo-closed` lets `lo-if` and
  `lo-while` ask whether the branch already ended in a `ret` before adding the
  fall-through `br`;
- **sealing without a terminator is the bug class this discipline exists to
  catch**: `emit` refuses a block with `bterm = 0`, which is exactly how the
  `match` gap below shows up instead of producing invalid IR;
- **the terminator goes to the open block, not the last row.** `lo-term-set`
  searches the block table backwards for the row whose label is `cl`'s and whose
  terminator is still empty. The distinction matters because `match` opens its
  `testN` blocks before the bodies that seal them, so the open block is not
  always the newest row; taking the last one puts the branch on a block the
  branch does not belong to and leaves the intended block unterminated — the
  failure `emit` reports as `block '…' has no terminator`. When no row matches,
  the last block is the fallback; that path exists for the window before the
  first `lo-w-block` opens `entry`, when no row can match at all;
- labels are the function's own counter, `st[2]`, handed out by `lo-label`:
  `thenN`, `elseN`, `joinN`, `headN`, `bodyN`, `exitN`, `matchN.testK` and so
  on. Numbers, not scopes, so two nesting levels never collide.

Slots are allocas, and the function is lowered **twice**: once with
`st[4] = 1` (the *dry* pass) purely to run `lo-slot` and record each alloca's
name and type in `plan`/`planty`, and once for real. `lo-w-alloca` then emits
every planned alloca at the top of `entry` before the first instruction, which
is what keeps the IR shape Python produces (all allocas first) regardless of
where the binding is written. `lo-slot-dry` reuses the plan's name instead of
allocating a new vector row, so the dry pass costs no arena space.

| name | from | used for |
|---|---|---|
| `%tN` | `lo-temp`, counter `st[0]` | every instruction result |
| `%v.N` | `lo-binding`, counter `st[1]` | the stem of an unnamed slot's alloca (a parameter, or a temporary the lowering had to put in memory) |
| `%v.N.addr` | `lo-slot` | the variable's alloca; loads and stores go through it |
| `thenN`, `headN`, `matchN.testK` … | `lo-label`, counter `st[2]` | blocks |

`bindn`/`bindt`/`binds`/`binda` is the scope stack: `lo-bind-row` pushes, a
`base` index marks the scope's floor, `lo-close-scope` clears `binda` above it,
and `lo-lookup` searches backwards for the innermost live row. Nothing is
removed, so a shadowed name and the name it shadows are two rows and the
lookup picks the later one.

The `st` vector, index by index (it is a vector because the language has no
record of counters shared across sixty call sites):

| index | meaning |
|---|---|
| 0 | temp counter, `%tN` |
| 1 | binding counter, `%v.N` |
| 2 | block label counter |
| 3 | cursor into `plan` while the real pass re-reads it |
| 4 | `1` during the dry pass |
| 5 | `1` when the function is `main` |
| 6 | the function's declared return type id |
| 7 | `1` once the open block has been sealed |
| 9 | `esc` depth at function entry |
| 10 | loop depth |
| 11 | `esc` depth at the current loop's exit block |
| 12 | `lo-gensym`'s counter, shared by every name no source can spell (`$spawn$N`, `$lambda$N`); unit-wide, never reset per function |
| 13 | the number of deferred sites queued for the function being lowered |
| 14 | where that queue's first row starts in `st` |

`st` is grown on demand past 16 by `lo-queue-site` (`vec-push` grows it), and
`lo-site-drain` empties it at the end of each function. A row is four words —
kind, generated number, the site's node or signature id, and the number of
captures — followed by one binding-row index per capture; a row's length is
`4 + captures`, so the next row starts where it ends. Two kinds exist today:
`0` a `spawn` thunk, `1` a `(fn …)` closure. The queue is one list, in site
order, because Python prints the deferred defines in exactly that order.

`esc` deserves its own line: `break` pushes its loop's exit label, and
`lo-while` only appends `unreachable` after a `while true` when `lo-escaped?`
finds no branch into the exit block. That is why the escape
depth is saved and restored around each loop instead of reset.

## Names

- **Functions.** A function's symbol is `main` for the entry point and
  `lg.<module>.<name>` for everything else, with `internal` true for the
  latter. `main` also gets the i32 return the C entry point expects, whatever
  the source declared; every other function keeps `:i64`, `:void` and so on
  as its own return type.
- **Functions are looked up per module.** `fnk`/`fnv`/`fnl` is keyed by
  `<module>\0<name>` (`lo-fn-key`), and `lo-fn-id` resolves a call the way
  `lower.py`'s `prepare` does: the caller's own module first, then the modules
  its `use` forms name, in source order. That matters when two modules define
  the same private helper — `body-test` and `check-test` each define
  `show-check-fail` — because a name-only index binds every call to whichever
  module was scanned last. The call is emitted against the *symbol*:
  `lo-call` hands `fsyms`/the extern's own name to the `call` row.
- **Globals.** A string literal becomes one `.strN`, interned by content:
  `lo-intern` returns the existing name when the bytes are already there, so
  two `"hello"`s share one global. `lo-cstring` appends the NUL before
  interning, so the table's bytes are exactly what `emit` prints inside
  `c"…"`, length included (`[5 x i8]` for `"hello"`).
- **Structs and enums.** The row keeps the name the source declared, which for
  a single module is the final name `llvm.py` prints (`%struct.point`). In a
  unit larger than one module the name is spelled `<module>.<name>`
  (`%struct.shapes.point`): `lo-one-type1` prefixes the declaring module's name,
  and `powner` records that module on the row, so a type reached through a
  callee's signature is spelled in the namespace that declared it. Two modules
  may each declare a private `point`; two rows, two spellings, one type each.
  Every fixture in `tools/selfhost-ir.txt` is one module with no `use`, which is
  what keeps this gate honest about the bare spelling.

## Constants

| form | how it is spelled | example |
|---|---|---|
| integer | `lo-norm-int`: drops a `+`, drops leading zeros, keeps one `-`; the width is the checker's, so no truncation happens here | `+007` → `7`, `-0` → `0` |
| float | parsed to the nearest `f64` and printed as LLVM's hexadecimal constant from `f64-bits`, never a decimal re-spelling | `1.5` → `0x3FF8000000000000` |
| string | `@.strN` as `[N x i8] c"…"`, bytes escaped by `emit`, NUL included in `N` | `"hi"` → `[3 x i8] c"hi\00"` |
| zero value | the string `null` for a pointer, `undef` for an aggregate's slots | `insertvalue … undef, i8* …, 0` |
| aggregate | struct and enum values are first-class SSA values; an enum's payload goes to a slot once and every read is a `gep` into it | `%t = insertvalue { i32, [1 x i64] } undef, i32 0, 0` |

A float literal's type is `f64` unless the context asks for another width; the
hex spelling means the text is the bit pattern the parser computed, so the
port and Python agree on the last nibble instead of on a printed approximation.

## Order is the contract

`tools/selfhost-ir.txt` compares text, so an instruction the port emits that
Python does not — or the same instruction with its temps numbered differently —
is a difference. Three consequences shape the code below and are worth knowing
before changing any of it:

- **A throwaway temp still costs a number.** `str-len` pulls *both* fields of
  the `{ i8*, i64 }` value, as `str_parts` does, and discards the pointer: the
  dead `extractvalue …, 0` stays in the text and every temp after it shifts by
  one if it is dropped. `lo-strlen` extracts field 0 into a temp it never reads,
  then field 1.
- **A literal is not lowered like a value.** `(println "hi")` emits a `gaddr`
  and a call whose length is a constant; `(println s)` emits two
  `extractvalue`s first. Building a `:str` value only to take it apart again
  would be one instruction too many, so `lo-print-lit` and `lo-print-parts` are
  two paths, not one.
- **A block is opened where Python opens it.** `lo-w-block` seals the previous
  block, so a branch missing before it leaves the previous block unterminated —
  the failure `emit` reports as `block '…' has no terminator`.

## `match`

Python's arms are `(pattern body…)`: the pattern is the arm's *first item*, not
a wrapper around it. The tree stores an atom-headed arm's head in the node's
`text` and everything from the body in `first`, so the pattern of `(red 1)` has
no node id of its own while the pattern of `((circle r) body)` does. `lo-match`
therefore reads the arm's head text (`lo-head`) and falls back to
`lo-child … 0`:

```
(let armh (lo-head nod ntx c))          ; "red", "_", or "" when the head is a number
(let p    (lo-child nod ntx c 0))       ; the number literal, or a (circle r) form
(let pat  (if (> (str-len armh) 0) armh (lo-head nod ntx p)))
(let iswild (if (> (str-len armh) 0) (str-eq armh "_")
                                    (and (lo-atom? nod p) (str-eq (lo-atom nod ntx p) "_"))))
```

`iswild` must be decided from the pattern and nothing else: `(bad-digit _)` binds
`_` as a payload and is *not* a wildcard arm, which is why the atom test alone
(as the spine had it) was wrong in one direction and the head test alone would
be wrong in the other. A wildcard arm's test block still exists — Python emits
it — and holds only the `br` into the body, so the arm costs no `icmp` and no
`cbr`.

The branch into `matchN.test0` comes before the first `lo-w-block`, which is
what terminated `entry`. Enum arms are compared by variant *index*: the arm's
head names the variant, and `lo-enum-test` looks it up in the enum the
scrutinee's type points at.

A `match` is a value wherever a value is expected, and Python types it from its
own record for the node, not from what the caller hoped for: `ty =
self.type_of(node)` (`lower.py:4295`), then `slot = None if _is_void(ty)` and
`arm_value(..., statement=slot is None)` (`4358`, `4397`) — the match's *own*
type decides whether an arm is a value or a statement. The port has no
per-node type table, so `lo-match` asks in two steps: the caller's `expected`
when it has one, otherwise `lo-match-type`, which is the query `lo-node-type`
already answers for a `match` with no context (the scrutinee's payload when an
arm body is the payload binding, the last item's type otherwise). The resolved
type is the slot's, the arms' and the final `load`'s, and the match is void only
when that type is void — never merely because the caller passed no expected
type. That conflation was the bug: `lo-str-parts` lowers its operand with
`lo-value … -2`, so any `(println (match …))` whose arms produced strings was
read as a statement match and refused the string operand with `E0002: a
statement must be a form`.

The "no type" sentinel here is `-1`, never `0`: a type id of zero is a real
type — `str` is id `0` in a unit whose first declaration is a `:str` function —
so both halves of the resolution test `>= 0`. `lo-if` already used `< 0` for the
same reason (`lower.logos:2498-2505`); the first version of this fix wrote `> 0`
and `str`-as-id-`0` still refused, which is the same "a legitimate id is not a
sentinel" class as the enum fix below.

An enum arm binds its payload only when the arm *reads* it. `((a _) 1)` binds
nothing — Python's `pattern_variant` answers `None` for `_` and the arm body
never sees a name — while `((a n) n)` binds at the payload's declared type. The
second pass now skips the binder when its text is `_`, so the ignored shape
emits no `alloca`, no `getelementptr`, no `bitcast` and no `load`, and no
temp numbers are spent on them: `enumpay` is byte-identical, where the eager
binder cost two slots and five instructions.

## The shifts

`lo-shift` lowers `shl`, `shr` (arithmetic, `ashr`) and `shr-u` (logical,
`lshr`). The count is masked with `and count, width-1` first, because LLVM makes
a shift by the width or more *poison*: at `-O0` it would be the hardware's
masked count and at `-O2` anything at all. Masking makes the two agree and says
what the language means — a count of 64 on an `:i64` is a count of 0.
`lo-node-type` returns the operand's type for a shift, as it does for
arithmetic, so `(let x (shl a 2))` gets `a`'s width.

## Casts

`lo-cast` lowers `(cast T e)` for every pair of numeric primitives, and the pair
decides the instruction: `trunc` to a narrower integer, `zext`/`sext` to a wider
one (the *source*'s sign decides which), and nothing at all between two
spellings of one width, because the bits already mean the target's value.
`sitofp`/`uitofp` to a float, `fpext`/`fptrunc` between two floats, and
`fptosi`/`fptoui` from a float to an integer.

The float-to-integer pair needs a range test in front of it: `fptosi` outside the
target's range is undefined, so `lo-float-to-int` compares the operand with the
target's two bounds — `[0, 2^w)` unsigned, `[-2^(w-1), 2^(w-1))` signed — using
`fcmp oge` and `fcmp olt` joined by `and`, branches to a `bad` block that panics
`R0003` with the cast's own node path, and emits the conversion only in the `ok`
block. A NaN fails both comparisons and takes the same path, which is the one
answer that does not invent an integer. The bounds are powers of two and exact
at both widths; `lo-float-at` spells each one at the *source*'s width — rounded
to single when the operand is an `:f32` — which is the rule Python's
`_float_operand` applies, and the one that keeps `cast-float-int`
byte-identical.

A decimal literal's mantissa is accumulated in a `:u64`, not an `:i64`: a
19-digit significand (`9223372036854774784.0`, the largest `:i64` below `2^63`)
does not fit a signed 64-bit accumulator, and the wrap used to spell the literal
as a different number entirely. Digits past the accumulator's reach keep the
exponent right instead of corrupting the value: a dropped *integer* digit adds
one to `10^extra`, a dropped *fractional* digit is not counted in `frac`, so
`9223372036854775808.0` and `9223372036854774784.0` are the two doubles the
corpus's range-boundary case names.

Every caller-supplied type id in this file is tested with `>= 0`, never `> 0`:
type id `0` is a real type — `str` in a unit whose first declaration returns
`:str` — and `> 0` reads it as "the caller named no type". `lo-if`,
`lo-node-type`'s literal/`if`/`match` arms, `lo-operand-type`, `lo-ctor-type`,
the result and optional readers and `args`/`read-dir` all share the test;
`if-str-zero` pins the shape.

## `print` and `println`

`lo-print` types its one argument and picks the runtime entry point that already
knows how to spell it: `rt_print_str` for bytes and their length,
`rt_print_i64`, `rt_print_u64`, `rt_print_f64`. Narrow integers are sign- or
zero-extended according to their source type, `:f32` is extended to `:f64`, and
a `:bool` branches on itself and prints `true` or `false` — never its 0/1
representation, which is a fact about `i1` and not about the language. The
width test compares widths, not type ids: every `lo-prim` call interns a fresh
id, so two ids for `:i64` are not equal.

## Strings

`str-concat`, `str-eq` and `str-slice` are the three the corpus needs.
`lo-strconcat` sums the two lengths, panics `R0003` if the sum went negative
(signed, so a wrap is visible), then calls `rt_str_concat` with a slot for the
length and rebuilds the `:str` from the pointer and that length
(`lo-str-of`). `lo-streq` compares lengths first and only `memcmp`s when they
agree, so it never reads past the shorter buffer, and joins the two paths on a
`phi`. `lo-strslice` copies nothing: a `:str` is a fat pointer, so the slice is
`gep` of the buffer and `end - start` bytes after three unsigned compares that
also catch a negative bound.

## Vectors

A `(vec T)` is `{ T*, i64, i64 }` — buffer, length, capacity — and
`lo-vec-part` reads one field. `lo-veclen`, `lo-vecget`, `lo-vecset` and
`lo-vecfree` take the descriptor as a value; `lo-vecset` and `lo-vecfree` write
through the binding's slot. A `(ref (vec T))` parameter holds a pointer to the
caller's descriptor, so `lo-ref-load` reads it once more before the fields.
Bounds are `lo-vbounds` (an unsigned compare, panic `R0003`).

The borrowed shape is covered on both sides of the call, and both fixtures that
claim it are in the parity list. At the *callee* the parameter's slot holds the
pointer, so every `vec-*` form loads the descriptor through it once. At the
*caller* a ref parameter takes an address, never a value: `lo-ref-slot` answers
with the address when the argument names a mutable binding whose own type is
not a ref — the binding's slot *is* the descriptor, so `%v.0.addr` is what the
callee must receive — and answers with the empty string otherwise, which sends
the argument through `lo-value` and loads the pointer a ref binding already
holds. That is Python's split in `argument`, and `vecref` (`len`, `get`, `set`,
`push`, `free` through one ref) and `vecref2` (a ref passed on to another ref)
are byte-identical because of it.

The type query peels too. `vec-get`'s branch of `lo-node-type` answers the
element of the *referent*: `lo-peel-ref` first removes a `(shared …)` wrapper
(`lo-peel-shared`) and then a `(ref …)` wrapper, and only then does `elem` read
the `(vec T)`'s element. The value path already read through the ref — that is
`lo-vecget`'s `direct` test — so a type computed from the type as written
disagreed with the value it typed: `(< (vec-get st 0) n)` with
`st :(ref (vec :i64))` was "a comparison needs numbers", `(get (vec-get nodes
id) next)` with `nodes :(ref (vec node))` was "get needs a struct", and in
`ir.logos` nine `add { i64*, i64, i64 }` instructions reached emit, where clang
refused the file. `vecgetref` pins both shapes in the parity list: a `vec-get`
of a ref vector feeding a comparison and feeding `get` on a struct element.

`lo-vecpush` is the one long form: it grows the buffer by *allocate, copy,
release* rather than `realloc`, because the leak tracker owns every block's
record and a block handed to `realloc` would leave the tracker describing an
address it no longer controls. The capacity goes to twice itself plus four, the
sum is checked against the old capacity, and the new size is guarded before it
reaches `rt_alloc`. The two paths — grew, or had room — join on two `phi`s
(the buffer and the capacity) before the append, which is what makes the
element write one `store` instead of two copies of the tail.

## Arrays, fields and memory

`arr-set` and `arr-get` share `lo-place` (the binding's alloca, or a fresh slot
for a value without storage), `lo-index64` (widened to `i64`) and the bounds
check. `set-field` goes through `gep` with two `i32` indices and stores the
field's own type. `alloc` multiplies the element count by the element's size
after an unsigned compare against `(2^63-1)/size`, calls `rt_alloc` with the
alignment `lo-align` computes and the node path as a C string (the leak report
prints that path back), and bitcasts the `void *` to `(own T)`. `free` bitcasts
back and calls `rt_free`; `deref`, `set-deref` and `ptr-add` are one `load`, one
`store` and one `gep`.

`lo-align` mirrors `align_of`: a primitive's alignment is its size capped at
16 (`:str` is 8 — the largest field's, not the aggregate's), a pointer, `own`,
`vec`, `ref`, `fn`, `chan`, `atomic` and `enum` are 8, an array and a `shared`
follow their element, an optional is its element's, a result is the larger of
its two sides, and a struct is the largest of its fields.

`lo-size-struct` is C's layout, which is LLVM's for an identified struct: each
field starts at the next multiple of its own alignment (`lo-pad`, fed by
`lo-align-of`, the same table above without the sixty-three-vector list), and
the whole is rounded up to the largest field's. Summing the fields instead gave
`{ i8, i64 }` nine bytes for the sixteen LLVM lays out, and an `alloc` of it
reserved nine — a heap under-allocation in emitted code that no corpus fixture
could see. `[3 x { i8, i64 }]` is 48, not 27, and `struct-pad` and
`structs-pad` pin the padded number in `rt_alloc`'s size argument.

A struct's fields live in the shared payload table, so `lo-struct-body` records
its base as the table's length at the moment it starts and writes it back into
`pbase[id]`; the first scan cannot know it, because no body has been read yet
and every struct declared there sees an empty table. `lo-enum-body` does the
same for payloads. Without it every struct after the first emitted its
predecessors' fields prepended — `%struct.wide = { i8, i8, i8, i32, i8, i64 }`
for a two-field struct — which no one-struct fixture could see.

Both were ordering defects of the *scan*, not of the layout rule, and the
forward reference the checker allows is the same defect seen from the other
side: a struct whose field names an enum declared after it used to crash the
backend (`gen2 build` exited 139 with nothing on stderr) because the enum's
payload table was still empty when the field was measured. With the base
recorded at the body and the payload table filled before its length is used,
that file lowers and `enumfwd` is byte-identical to Python's `.ll`.

## Results, optionals and `try`

`ok`/`err` spell a result as `{ i1, [1 x T] }` and `some`/`none` an optional as
`{ i1, T }`: both are SSA values built with `insertvalue` from `undef`, so the
payload is written once and every read is an `extractvalue` at the tag or
payload index. `lo-ctor-type` answers the constructor's own type, and
`lo-result-value`/`lo-optional-value` rebuild a value from a tag and a payload.

`try` is the only form that branches on the tag. It requires the enclosing
function and its argument to be results of the same shape — otherwise
`E0601: cannot try this result in this function` — emits `<tag>.err`, which
re-wraps the error at the caller's result type and returns it, and leaves the
`.ok` block's payload as the expression's value (`tryprop`). `match` over a
result or an optional decides each arm from the constructor name in the
pattern (`lo-tag-test`), comparing field 0 rather than an enum's variant index.

## Channels, mutexes and atomics

All three are runtime handles, and their *type* is the only thing the shared
marker changes. `(chan T n)` is `rt_chan_new` with the capacity and the
element's size, and its type is `(shared (chan T))`; `send` and `recv` pass the
handle, and `recv`'s type is the channel's element read from the channel type
(`lo-chan-elem`). `(mutex)` is `rt_mutex_new` and its type `(shared :mutex)`;
`lock` and `unlock` are `rt_mutex_lock`/`rt_mutex_unlock` on that handle.
`(atomic T v)` is `rt_atomic_new` with the initial value, its type
`(shared (atomic T))`, and `atomic-add`/`atomic-load`/`atomic-store` the three
runtime calls (`lo-atomic-elem` answers the element).

Because the shared wrapper is a fact about the type and not about the value,
`deref`, `set-deref` and `ptr-add` see through `(shared (ptr T))` to the pointer
inside, and `lo-ptradd-type` answers the pointee's type so one `ptr-add` can
feed the next. The peel lives in the type query — `lo-peel-shared`, called from
`lo-node-type`'s `deref` branch and from `lo-setderef` — not in one consumer:
the load `lo-deref` emits yields the pointee, so a consumer that still saw
`i64*` would spell `add i64* %t, 1` and clang would reject the file. `sharedptr`
pins it with a `deref` feeding an `add`, a second `deref` bound on its own, a
`set-deref` through the shared pointer and another through a `ptr-add` of it.
The handles have a fixture too: `concurrency` sends and receives on a `chan`,
locks and unlocks a `mutex`, and runs `atomic-add`/`atomic-load`/`atomic-store`.
Neither fixture spawns a thread, so both lower through the plain path;
`join` lowers to `rt_join`, and with `spawn` now spellable it is exercised end
to end — `spawn.logos` and `examples/matrix.logos` both join every thread they
start.

## The thunk form (`spawn`)

`(spawn f args…)` is the one form that emits a *second* function while a
function's body is being lowered. Python does exactly that: the thunk is a
fresh `IrFn` appended to the function list at the site, so its define prints
immediately before its parent's. This arena cannot do it in place — `ir-fn`
fixes a range at open (`fbase`, `fparam`) and `ir-fn-end` closes it from the
*current* lengths — so a nested function's rows would be swallowed by the
enclosing range: its `entry` block counted into `fcnt`, its `%env` parameter
into `fpc`.

So the arena defers. `lo-spawn` emits the site in Python's order — the
arguments, `rt_alloc` with the record's size and alignment, the `bitcastrec`
and one `geprec`+`store` per field, the `faddr`, `rt_thread_new` — with the
`%env` record packed from the callee's *declared parameters*, not from
captures: a spawn captures nothing lexically, and the runtime owns the record
until the target returns. It then records the site on a per-function queue at
the end of `st`: `st[13]` is the count, each entry is the thunk's number and
the target's signature id. The name is allocated *at the site* from `st[12]`,
the counter `lo-gensym` bumps, so `$spawn$1…` are numbered across the unit in
evaluation order and never reset per function — two spawning functions number
`$spawn$1` and `$spawn$2`, not `$spawn$1` twice. The dry pass allocates no
name and queues nothing, so the numbering is the real pass's.

`lo-site-drain` runs **after** `ir-fn-end` in `lo-fn`, and that is what keeps
the parent's ranges honest: its `fcnt`/`fpc` were measured before the drain,
and the thunk's rows land past them. Each thunk is emitted with its own
counters (`%t1` again: `st[0..2]` are saved, zeroed and restored), one `env`
parameter appended straight to `pnames`/`ptys` — no binding, no slot — and a
body of `bitcastrec %env`, `geprec`+`load` per field, `call target` and
`ret i8* null`.

The drain then rotates the parent's f-row right by the number of sites
(`lo-fn-rotate`): the eight columns move together, so the table reads
`[t1 … tk, F]` while the thunks' blocks stay physically after the parent's.
That rotation is the one step that reproduces Python's define order; without
it the same eighteen lines print after the parent instead of before it, which
is a pure move and not byte equality. Its cost is that `fbase` is deliberately
not monotonic across the f-table afterwards — a thunk's blocks sit past its
parent's — so a reader must not mistake that for corruption: each row is still
contiguous and `ir-fn-first`/`ir-fn-past` are per-row. `fid` is stale the
moment the rotation runs, so the rotation is the last thing `lo-fn` does.

`lo-node-type` answers `:thread` (printed `i8*`) for the form, which is what
lets `spawn` sit in a `let` initialiser and be named; before B4 the type query
refused it, so the declaration reported a binding it never made.

## The closure form

`(fn :R ((p :T)…) body…)` is the second thing that emits a function while a
body is being lowered, and it reuses the thunk path rather than repeating it. A
closure is a per-site nested function `$lambda$N`, named from the same
unit-wide counter as `$spawn$N`, plus a two-word value `{ i8*, i8* }`: the
environment and the code. The value's layout is the same for a capturing and a
non-capturing closure, so one function type spells both, and the environment is
`null` when nothing is captured.

The site emits, in Python's order, the environment record first. Python packs
the captured values into one stack slot — `allocarec` of the capture types,
then `geprec`+`store` per capture — and `bitcastout` is the `i8*` the value
carries. `lo-lambda` reads the capture list from `lo-captures`, which mirrors
the checker's walk: a name is a capture when it is bound outside the
expression, in first-use order, with the lambda's own parameters and `let`s
shadowing it.

A form's head is a **use**, but it is not a child: the tree sets `first` past
the head token (`tree-child-start`), so a walk over the child chain alone never
sees it. `lo-cap-scan-form` therefore looks the head up itself, before walking
the arguments, through the same `lo-cap-name` test an atom uses. That is what
captures a function value: in `(f (+ y x))` the read of `f` *is* the call, and
leaving it out of the environment made the lambda body read the enclosing
frame's slot instead — a load whose type the inner frame never allocated, which
clang rejects. A head that is not a binding is not a capture: `lo-cap-name`
asks `lo-lookup`, so `let`, `fn`, a module function and an operator all fall
through. The fields are then the bindings' own types, in the same first-use
order, so the site's record and the body's `geprec` cannot disagree.

The slot is a plan row like any other binding, and the fields
it must spell are appended to `tvals` at the site; the plan row encodes the
run as a negative `planty` entry (`-(start * 4096 + count)`), because
`planty` holds type ids and the record has no type id of its own. The prologue
then emits `allocarec` from that run instead of `alloca`.

The body is lowered at drain time, after the parent's `ir-fn-end`, exactly as a
thunk is: `$lambda$N`'s own counters, an `env` parameter appended straight to
`pnames`/`ptys`, one `alloca` per declared parameter at the top of `entry` (a
fresh builder hoists them, and the source order is the parameter order), then
`bitcastrec %env` and one `geprec` per capture bound as the name's slot, so a
read inside the lambda is the `load` any parameter's read is. That binding is
why the checker's "a capture cannot be assigned" rule matters: the slot is the
environment field, and a store would write the copy.

`lo-lambda-fn` opens `entry` **before** the dry pass, not after it: `st[4]=0`
lets `lo-w-block` append the block row, then `st[4]=1` runs the body that only
plans slots. The order is load-bearing twice. A block row records its first
instruction as the `ops` length at the moment it opens, so every planned
`alloca` appended afterwards — and the whole real body — falls inside the row's
range; a block opened after the allocas would own none of them and `clang`
rejects the unnamed value. And the block must be outside the dry pass's
suppression, or the define prints with no basic block at all (`function body
requires at least one basic block`). The second phase then resets the
counters, emits the plan's allocas with `st[4]=0`, records the environment and
lowers the body for real.

A call through a value is Python's `indirect_call`: load the binding,
`extractvalue` the environment and the code, `bitcast` the code from `i8*` to
its real signature `R (i8*, T…)`, then `icall` with the environment before the
declared arguments. The signature is the callee's own function type, so the
arity and every argument type come from the type query, not from the call site.
`lo-node-type` answers the form's return type the same way, which is what lets
`(let f (fn …))` be named and `(f 1)` be printed.

The queue is one list for both kinds. `spawn` and a closure interleave in
evaluation order, and each row carries its kind, so `lo-site-drain` dispatches
while keeping Python's define order — one rotation of the parent's f-row by the
number of rows, whatever their kind. A deferred function's own body may queue
more sites (a `spawn` inside a lambda); the drain recurses on the row it just
emitted, so the inner defines land before it and the inner row is rotated by
its own count, which is the order Python's list append gives.

One repair this needed beyond the rope: a signature's parameter types must be
contiguous in `tptypes`, and parsing a parameter whose type is itself a
function type appends that function's own parameters. `lo-sig-one` and
`lo-lambda-shape` therefore parse every parameter first and append them
afterwards, so a `(f : (fn (:i64) :i64))` parameter cannot push its own
parameter list into the middle of the enclosing signature's run.

## `$fnvalue`: a named function used as a value

`lo-atom-value` resolves an atom that is neither a literal nor a binding: if
`lo-fn-id` finds a signature for it, the atom is not a name to load but a
*function value*, and `lo-fnvalue` builds one. The value is the same two words a
closure's is — `{ i8*, i8* }`, environment then code — so a function value and
a closure answer one ABI and a call through either is the same
`extractvalue`/`bitcast`/`icall`.

The code word cannot be the definition's own address: a direct call passes
`(T…)` and an indirect one passes `(i8*, T…)`, and the two signatures do not
unify. Python therefore wraps each used definition once in a `$fnvalue$N`
helper that takes the environment it ignores and calls the definition with the
rest; this port does the same, and the memo is the point. `lo-fnv-find` looks
the target's symbol — `lg.<owner>.<name>`, or `main`, which is a plain source
name — up in the `cl` vector from index 4 in pairs (`target`, `wrapper`), so the
second use of one function answers the first wrapper instead of emitting
another. A miss queues a site row of kind 2 carrying the target's *signature*
id in `st[12]`, which is what lets the drain emit the wrapper after the
parent's `ir-fn-end` without parsing the signature again.

`lo-fnvalue-new` gensyms `$fnvalue$N` from the same unit-wide counter as
`$spawn$N` and `$lambda$N`, spells the symbol `lg.<module>.<$fnvalue$N>` from
`cl[1]`, and emits `faddr` for it. Only the real pass queues
(`st[4] != 0`): a dry pass that is planning a body's slots must not emit a
define, exactly as with a closure.

`lo-fnvalue-fn` emits the wrapper at drain time in the shape the closure path
established: counters zeroed, `define R @lg.<mod>.$fnvalue$N (i8* %env, T…)`,
`entry` opened before the dry pass so the block row owns the allocas, one
`alloca` per parameter planned and then emitted, one `load` per argument
(`lo-fnvalue-load`), a direct call to the target, and `ret`/`ret void` chosen by
the target's return type. The environment parameter is named `env` and is never
read.

The signature comes from the type table, not the call site. `lo-atom-node-type`
answers `f` — the signature `lo-scan-sigs` stored for that definition — for an
atom that is not a binding and not a variant, and `lo-node-type` answers a
*generic* call's instantiated result type rather than the generic's own
variable. Those two queries are what let `(let f id)` be annotated, `(apply id
3)` type-check against `(fn (T) U)`, and the wrapper's arity and argument types
be read from the definition instead of guessed.

## Processes, files and arguments

`(run prog argv)` copies the program and every argument into NUL-terminated
strings, calls `rt_run_start` with the vector's contents, releases the temporary
vector *after* the call returns (freeing it first would hand the runtime a
pointer into freed memory) and zeroes its slot. The result is a `:run` handle:
`run-status` reaps it, `run-out` and `run-err` read the process-lifetime buffers
with their byte counts and rebuild a `:str` from pointer and length
(`runprog`). `read-all`/`read-file` are the same shape over `rt_read_all` and
`rt_read_file` (`readall`, `readfile`), and `str-from-i64` over
`rt_str_from_i64` with a slot for the length (`strfrom`). `str-byte` is not a
runtime call: it is a bounds-checked `gep` and `i8` load. `args` asks `rt_args`
for the count and the raw pointer array, allocates the `(vec :str)` through
`rt_alloc` and fills it one argument per element (`argv`).

The four directory forms (`readdir`, `isdir`, `mkdirs`, `patherror`) are the
same shape with the pieces they need. `is-dir` calls `rt_is_dir` and compares
the result against zero — one `icmp`, no branch, so it is an expression like any
other. `mkdirs` returns `rt_mkdirs`'s status unchanged. `path-error` returns
`rt_path_error`'s message with its byte count through a slot, like `strfrom`.
`read-dir` is `args` over `rt_read_dir(ptr, len, &pairs, node_path)`: the pair
array copied into a tracked buffer, a count of zero becoming the `(NULL, 0, 0)`
descriptor `vec-free` releases, and the branch's blocks named `dirN.fill` and
`dirN.done`.

## String comparison

`(= a b)` with two `:str` operands compares bytes. `lo-compare` asks the
operand's type and sends a string pair to `lo-streq`, the length-first `memcmp`
join `str-eq` already lowers to, so equality never becomes a compare of two
pointers. The other string predicates are still refused: `!=`, `<` and the rest
fail at the form with `E0002 … is not lowered by this backend yet`, because the
runtime has no ordered string comparison to build on.

## Generics

A generic definition has no body: each call site that fixes its type variables
gets a copy, named exactly as `mangle_instance` spells it — `lg.<module>.id$i64`
for a copy of `id` at `:i64`, `pick$s5_point` for a `point` argument, and
`map$i64$str` for a copy whose variables are fixed in the *signature's* order
(the return type's variables first, then each parameter's, first appearance).

The call site is what decides a copy, in `lo-call`: a callee whose signature
mentions a type variable is unified parameter by parameter against the
arguments' own types (`lo-unify`, in `lo-inst-call`). Unification binds a
variable, checks an already-bound one for equality, and recurses through
`vec`/`ptr`/`own`/`ref`/`opt`/`shared`/`chan`/`atomic`/`arr`/`res` and `fn` —
`fn` also compares the head, so a capturing `(fn* …)` never unifies with a
`(fn …)`. A variable the arguments do not fix is `E0501`; an argument whose type
this backend cannot compute, or one that does not fit, is a diagnostic rather
than a second, unchecked copy.

The copy is then memoised by its mangled name (`lo-inst-add`), so two call
sites at one type share one define, and the copy's type-argument bindings are
kept in `ivn`/`ivt` with a per-copy range in `ivb`/`ivc`. After every function
of a module has been lowered, `lo-inst-drain` lowers each copy in discovery
order: it installs the copy's bindings as `curn`/`curt`, substitutes them into
the scanned signature (`lo-inst-sig`, through `type-substitute`), and calls the
same `lo-fn` an ordinary function goes through with the copy's name and the
concrete signature. A copy discovered inside a copy appends itself to the queue
and is lowered after the copies already queued, which is Python's breadth-first
order. `lo-parse` substitutes the active bindings into every type it parses, so
a `(vec T)` annotation inside the body becomes `(vec :i64)` for the copy and
`(vec :str)` for the next one.

A generic that no call reaches is not emitted at all: there is no type to emit
it at. The instance name is a source name like any other, so the symbol is
`lg.<module>.<copy>`; no user name can spell one because `$` is not a name
character.

## Test mode: `build --test NAME`

`gen2 build --test NAME file` lowers one `(test …)` body as the entry point, so
the harness can run a single test as an ordinary process and compare its stdout,
stderr and exit status. It is a mode, not a form: nothing below is new grammar.

`main.logos` reads `--test` into `tnames` (`main-arg`, `main-flag-next`) and
takes the last value (`main-test-name`), so the flag may be repeated. Three
things change in `main-built`. The required-`main` rule is skipped
(`main-check-main` returns 0 when a test name is present) because the test body,
not the module, supplies the entry point. The IR path gains the test name:
`main-ir-path-of` writes `build/<stem>.<test>.ll`, `<test>` sanitized by
`main-sanitize` — every `/` and `\` becomes `_` — which is Python's
`test_ir_path` exactly, so two tests of one file cannot overwrite each other's
IR and a test build never stomps the plain `build/<stem>.ll`. And the link
passes `dbg = 1` to `main-link`, which pushes `-DLOGOS_DEBUG=1` **first**, ahead
of the optimisation flag, matching `driver._link`'s argv order: the runtime is
compiled with its leak accounting on, so `rt_leak_report` exists at link time
and a leaked block is visible instead of silently passing.

`lower.logos` carries the name in `tname` and in two slots of `cl`: `cl[2]` is
the name, and `cl[3]` is `"1"` or `"0"`, the test-mode flag every `lo-*` below
can read without threading another parameter. `lower-build` then changes three
things per module. When lowering bodies it skips the module's `main` (a test
build must not emit a second entry point). It runs `lo-test-sweep`, which
replays **every** `(test …)` body of the module in a dry pass — `st[4] = 1`, so
no instruction is written, only the type work — purely to discover the generic
copies those bodies use: a copy a test reaches is emitted only if something
lowers the test, and the sweep is what makes the copy existent. And it defers
`lo-inst-drain` for module 0, because the copies the sweep queued are drained by
the entry-point pass, in the order Python's breadth-first drain gives.

A `fn` written inside a test is lowered by `lo-test-helpers`, which the module
loop runs under `--test` for every `(test …)` node it finds, before
`lo-test-sweep`: it walks the test's children and hands each `fn` to
`lo-one-fn`, the same path a module-level `fn` takes, so a helper gets the
ordinary signature, body pipeline and symbol. `lo-one-fn` qualifies by the
current module, so that symbol is `lg.<module>.<name>` with `internal` linkage
— the same name in another module cannot collide, and the linker's global
namespace is untouched. Nothing in the IR marks it as a helper: the checker has
already refused its undocumented shapes (see `check.md`), and a test's call to
it is an ordinary `call`. A build without `--test` never reaches any of this —
test nodes are dropped, and the helpers inside them with them.

`lo-test-entry` closes the mode after the module loop: it refills the node slice
to module 0, finds the named test with `lo-test-find` (`E0002: no test named
'…'` otherwise), sets `cl[1]` to that module's name so symbols are qualified
correctly, drains the instantiations, builds the entry function with
`lo-test-main`, drains the sites it queued, and rotates the entry row to the end
of the function table so `main` prints last, as in a normal build.

`lo-test-main` is the ordinary body pipeline with a different head: it opens
`main` as `i32` and lowers the test body exactly twice, as a closure's body is
lowered twice. The first pass plans the slots; the allocas are emitted between
the passes; the second pass writes the code. The body is
`(lo-child nod ntx test 2)` — path index 2, which is the first statement after
the `test` head and the test's name — and the walk runs to the end of the
sibling chain, because a test body's statements are siblings, not a wrapped
block. `lo-fn-finish` then closes the block with the leak report below.

The leak report has two exit paths, and both must emit the call for the IR to
match Python. `lo-leak-report` declares `rt_leak_report` and emits a call, and
does nothing when `cl[3]` is `"0"` — a release build's stderr belongs to the
program. `lo-ret-main` calls it before the `ret` that returns the status, and
`lo-fn-finish` calls it on the fall-off-the-end path (`st[5] == 1`), which is
the one an empty or fully-terminating body takes; that path returns `0`
immediately afterwards.

Every claim above is measured on `tests/exec/closures.logos`: all seventeen
tests lower to IR byte-identical to Python's `run_test` output — including the
nine copies that only a test body reaches, `named-function-value`'s `$fnvalue`
wrapper, and the debug `rt_leak_report` on both exits. The comparison is
`gen2 build --test NAME` against `driver.run_test`, one pair of `.ll` files per
test, so it is the same claim phase five makes for a whole unit.

## What it does not lower

Still refused, each at the form's node path with `E0002: '<head>' is not
lowered by this backend yet`:

- **`!=`, `<`, `<=`, `>` and `>=` on `:str`.**

A test build is refused in one further shape, and it is the checker rather than
the lowering: this port's checker has no `test` branch, so `gen2 build --test`
lowers a body the checker never read. A type error inside a test is a
difference only Python sees, and `gen2 check` accepts a test body Python
rejects. That is a known gap of its own (W8 step 3c-2), not a form the backend
cannot spell.

A shape with no finite layout is refused too, with a path and a code; see the
next section.

## A type with no finite layout

A struct that holds itself by value — directly, or through an enum payload or
another struct — has no LLVM spelling; the printer would write `%struct.node`
inside `%struct.node`. `lo-reaches` walks the by-value edges (a pointer, `own`,
`vec`, `ref` or function value stops the walk) and `lo-struct-body` refuses the
declaration with `E0002: struct '<name>' contains itself by value` at the
struct body's node path; `lo-enum-body` refuses the payload case the same way.
`lo-reaches` answers `false` for a negative type id before it reads the arena,
the same guard `lo-var-reach` opens with: a payload-less variant's `pchild` row
is `-1`, Python's `None`, and a walk that treated it as an index read one row
before `tags` and panicked `R0003`.
Python refuses the same program with the same words, but at the *first use* of
the type rather than at its declaration, because `use_type` is its only funnel
and the backend has none. The difference shows only in a module that declares
such a type and never uses it: Python accepts the declaration, this port
refuses it. Nothing that can be lowered is lost — a type with no size cannot be
allocated, passed or read — and the alternative was the self-referential row or
the segfault a forward enum reference used to cause.

The refusal is measured, not assumed: `src/logosc/fixtures/ir-refuse` holds one
fixture per shape with a `.refuse` sidecar naming the exact first line of
stderr, and phase two runs it beside the parity list. A signal, a silent exit
or another line is a difference.

Every fixture under `src/logosc/fixtures/ir-lower` is in
`tools/selfhost-ir.txt` — eighty-six paths, all byte-identical to Python's
`.ll`. The list also names four example programs (`examples/hello.logos`,
`examples/json.logos`, `examples/wc.logos`, `examples/matrix.logos`): real
programs, not fixtures, whose IR is claimed byte for byte. They are not a
survey of the new forms: `run` appears in none of them, `hello` prints one
string, `wc` reads all of stdin and prints counts with no vector operations,
and only `json` exercises vectors (and `alloc`/`ptr`). None of them touches a
channel, a mutex, an atomic or a `(shared (ptr T))` — `concurrency` and
`sharedptr` are fixtures because of exactly that gap. `matrix` is B4's
end-to-end claim: four 18-line thunks at 135–210 of Python's
`build/python-matrix.ll`, numbered `$spawn$1`–`$spawn$4` by the unit-wide
counter and unpacking a six-field record, printed before `define i32 @main()`
at 211 — which is the f-row rotation's whole job.
`tools/selfhost.sh` holds `IR_FLOOR=90` over the whole list, so a pruned list
fails rather than passing over fewer files. Set equality is judged on the list's
*fixture* entries against `src/logosc/fixtures/ir-lower/*.logos`: every fixture
on disk is listed and every listed fixture is on disk, so an addition or a
deletion must move both names in the same commit and the count cannot be held
still while one fixture is swapped for another. Set equality alone cannot stop
the list and the directory shrinking together, though, so the fixture entries
carry a floor of their own — `IR_FIXTURE_FLOOR=86` — and a fixture cannot leave
while a path outside the directory takes its place in the total. A path outside
the directory is a claim of its own; it neither hides a missing fixture nor has
to exist there.
