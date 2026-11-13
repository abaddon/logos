# `src/logosc/lower.logos` — the tree into the IR arena

The lowering: `logos/lower.py` ported to Logos for the forms W7 PR B lists —
declarations, expressions, `if`/`while`/`match`, direct and `extern` calls.
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
            nod ntx
```

Sixty-three vectors, no more and no less: the module tables `emit` prints, the
type arena `types.logos` fills, and the parsed tree (`nod`, `ntx`). The call is
long because the language has no struct of vectors and the arena is passed by
reference; every `lo-*` function below takes the same list in the same order,
and a caller (today `main.logos`'s `main-built`) allocates all of it once.

`lower-build` does four things, in this order:

1. pushes a passing `lower-error` into the one-element `berr` vector, so every
   later lookup can read the verdict in one index;
2. zeroes the twelve `st` counters, so counters start at `%t0`/`%v.0`;
3. opens the module (`ir-module`) with the triple and `mqual = false`;
4. scans the root's children twice — types (`lo-scan-types1`,
   `lo-scan-types2`), then signatures (`lo-scan-sigs`) — and only then lowers
   every `(fn …)` body (`lo-fn`), in source order.

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
rather than a line. `lower-code` renders the number the way `types.logos` does
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
| 12 | `lo-gensym`'s counter, for a name no source can spell (`$N`); nothing calls it yet |

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
- **Functions are looked up by source name**, and the call is emitted against
  the *symbol*: `lo-call` resolves `fnk`/`enk` and hands `fsyms`/the extern's
  own name to the `call` row.
- **Globals.** A string literal becomes one `.strN`, interned by content:
  `lo-intern` returns the existing name when the bytes are already there, so
  two `"hello"`s share one global. `lo-cstring` appends the NUL before
  interning, so the table's bytes are exactly what `emit` prints inside
  `c"…"`, length included (`[5 x i8]` for `"hello"`).
- **Structs and enums.** The row keeps the name the source declared, which for
  a single module is the final name `llvm.py` prints (`%struct.point`). This
  port's `mqual` is always `false`, and the reason is scope: the import closure
  — lowering each `use` into the same unit, and the qualified spellings
  (`%struct.shapes.point`) that only a multi-module unit needs — is **PR C's**
  work, not this PR's. Until it lands, `lower-build` lowers the one root it is
  given: a `use` is resolved for the checker's benefit and never lowered, and a
  qualified spelling has no lookup path here. Every fixture in
  `tools/selfhost-ir.txt` is one module with no `use`, which is what keeps this
  gate honest.

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
Neither fixture spawns a thread, so both lower while `spawn` refuses.
`join` lowers to `rt_join`, but nothing can produce a thread value while `spawn`
refuses (below), so it is exercised only by the forms that type-check it.

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

## String comparison

`(= a b)` with two `:str` operands compares bytes. `lo-compare` asks the
operand's type and sends a string pair to `lo-streq`, the length-first `memcmp`
join `str-eq` already lowers to, so equality never becomes a compare of two
pointers. The other string predicates are still refused: `!=`, `<` and the rest
fail at the form with `E0002 … is not lowered by this backend yet`, because the
runtime has no ordered string comparison to build on.

## What it does not lower

Still refused, each at the form's node path with `E0002: '<head>' is not
lowered by this backend yet`:

- **`spawn`, and closures.** A thunk is a per-site nested function, while this
  arena stores a function's parameters and blocks as contiguous global ranges
  (`fparam`/`fpc`, `fbase`/`fcnt`). Emitting a thunk mid-body therefore corrupts
  the enclosing function's ranges — measured, not assumed: three `%env`
  parameters landed on `@main`. Deferring thunks to the end of the function (a
  pending queue threaded through the context, or a row swap that preserves
  define order) is the shape of the fix, and it is the next task's, not a
  missing `case` in a dispatch. Until then `spawn` refuses rather than
  miscompiles, and it refuses the same way wherever the form sits: as a
  statement and as the initializer of a `let` both print
  `E0002: 'spawn' is not lowered by this backend yet` at the form's own node
  path. The type query refuses the form too (`lo-not-yet-type`, after
  `lo-node-type`), rather than answering "no type" and leaving the declaration
  to report a binding it never made — the old initializer shape was
  `E0005: unknown name '<binding>'`, naming a name declared on the same line.
- **`examples/matrix.logos`**, which lowers otherwise and differs only in its
  four 18-line spawn thunks (75 lines with their separators, at 135–210 of
  Python's `build/python-matrix.ll`, before `define i32 @main()` at 211); it
  refuses at its first spawn site with the same `E0002`.
- **`!=`, `<`, `<=`, `>` and `>=` on `:str`.**
- **`build --test NAME`.** Every positive corpus file under `tests/exec`,
  `tests/thread` and `tests/regress` is a `(test …)`, not a `main`, so
  `gen2 build` refuses it with `no 'main' function to build` before lowering
  starts. That is a missing *mode* (skip the module `main`, lower the test body
  as the entry point, link `rt_leak_report`) and a gate that compares
  `build/<stem>.<test>.ll` per test — not a missing form. It is why the parity
  list holds fixtures and three example programs rather than the corpus the
  other gates run on.

A shape with no finite layout is refused too, with a path and a code; see the
next section.

## A type with no finite layout

A struct that holds itself by value — directly, or through an enum payload or
another struct — has no LLVM spelling; the printer would write `%struct.node`
inside `%struct.node`. `lo-reaches` walks the by-value edges (a pointer, `own`,
`vec`, `ref` or function value stops the walk) and `lo-struct-body` refuses the
declaration with `E0002: struct '<name>' contains itself by value` at the
struct body's node path; `lo-enum-body` refuses the payload case the same way.
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
`tools/selfhost-ir.txt` — forty-three files, all byte-identical to Python's
`.ll`. The list also names three example programs (`examples/hello.logos`,
`examples/json.logos`, `examples/wc.logos`): the first real programs, not
fixtures, whose IR is claimed byte for byte. They are not a survey of the new
forms, and the list's growth is not theirs: `run` appears in none of the three,
`hello` prints one string, `wc` reads all of stdin and prints counts with no
vector operations, and only `json` exercises vectors (and `alloc`/`ptr`). None
of them touches a channel, a mutex, an atomic or a `(shared (ptr T))` —
`concurrency` and `sharedptr` are fixtures because of exactly that gap.
`tools/selfhost.sh` holds `IR_FLOOR=46` over the whole list, so a pruned list
fails rather than passing over fewer files. Set equality is judged on the list's
*fixture* entries against `src/logosc/fixtures/ir-lower/*.logos`: every fixture
on disk is listed and every listed fixture is on disk, so an addition or a
deletion must move both names in the same commit and the count cannot be held
still while one fixture is swapped for another. Set equality alone cannot stop
the list and the directory shrinking together, though, so the fixture entries
carry a floor of their own — `IR_FIXTURE_FLOOR=43` — and a fixture cannot leave
while a path outside the directory takes its place in the total. A path outside
the directory is a claim of its own; it neither hides a missing fixture nor has
to exist there.
