# Vector struct fields, and a field place that moves — design

Design document. 2026-11-17. Status: ruling. This note reverses ruling **R2**
of `docs/history/build-ledger.md:137`, and with it the place-copy reasoning
recorded as R7 at `build-ledger.md:177` that R2 rested on.

Source: issue #9. The root cause and the four change points are enumerated in
the issue comment of 2026-11-16,
https://github.com/abaddon/logos/issues/9#issuecomment-6925799335 — that comment
is the evidence this note decides on, and its four points are carried forward in
§6 rather than re-derived. This note adds the two points that comment does not
name (§6.5, §6.6), because it predates the discovery that the compiler's own
source depends on the behaviour being replaced.

Every line number here was measured at `57a67b6` with the compiler built from
`src/`. Where a number disagrees with the issue comment, the number here is the
corrected one; §2 lists the corrections.

Nothing in this note is implemented. It is the specification the implementation
card works from, and the words "today" and "measured" always mean `57a67b6`.

## 1. The ruling

**R2 and R7 are reversed. A struct may own a vector. A field place is a move,
not a copy.**

Concretely, four sentences of language shape:

1. A `(vec T)` may be a struct field, at any depth (`(get (get b inner) items)`
   is a field place too), and a `(vec T)` may be a fixed-array element.
2. The five vector operations — `vec-len`, `vec-get`, `vec-set`, `vec-push`,
   `vec-free` — take a **place**, not a name. A place is a binding, a `(ref T)`
   parameter, a field of a place, or an element of a place.
3. A field place is a **move**: `(vec-free (get b items))` consumes the field.
   After that the field is uninitialised, and every read of it is refused. A
   write (`set-field`, `arr-set`, `vec-push`, `vec-set`) is how it is
   initialised again.
4. A struct that carries a vector is **move-only**, already, everywhere (Task 9
   R1, `build-ledger.md:136`). It is moved, never copied, and a copy of one is
   `E0402`. Nothing about copying changes in this ruling; what changes is that
   the manual's claim that the field ban *was* what made copies safe was
   describing the wrong mechanism.

Why now. R2's stated reason was "the buffer could never be released" because no
place expression existed to name the field. R4 (`build-ledger.md:140`) then gave
`vec-push`/`vec-set`/`vec-free` a place — a parameter name — for exactly this
reason ("the callee owns a moved vector and must be able to release it"). The
machinery R2 was waiting for exists; the field is the second useful place. A
record that owns a growable list is the most-requested shape in the tracker, and
it is currently unspellable.

The reversal is a product decision, not a bug fix, and it is recorded as one:
the representation, the ownership analysis and the manual sentence all move
together, which is why it is spec-first.

## 2. What is true today, measured

| Claim | Where | Measured |
|---|---|---|
| a vector struct field is refused | `check.logos:1406` `check-field-rules`, vector clause `:1418-1421`, message `:1421` | `E0002: vector fields are not supported yet` at `p1/rec/0/0` |
| a vector array element is refused | `check.logos:985-988` | `E0002: vector array elements are not supported yet` |
| a vector enum payload is refused | `check.logos:1521` | `E0002: vector payloads are not supported yet` |
| the refusal walks nested structs | `check.logos:397-415` `check-holds-vector` | — |
| a field read hands out a second descriptor | `lo-get` `lower.logos:2095-2108`, ends in `lo-w-extract` at `:2107` | `extractvalue` copies all three words |
| a binding is the only place today | `body-vec-target` `check.logos:5600-5638`, name-only at `:5604-5609`; `lo-place` `lower.logos:2110-2117` | `vec-free` needs an atom naming a binding |
| a vector value is three words | `lo-empty-vec` `lower.logos:2041-2049`, slots 0/1/2 at `:2044-2048`; `emit.logos:286-288` | `{ i64*, i64, i64 }` |
| `lo-size` has no vector case | `lower.logos:326-350`, fallthrough `ret 8` at `:350` | a vector measures 8 bytes |
| `lo-align-of` has no vector case either, but its fallthrough is 8 | `lower.logos:359-383`, `ret 8` at `:383` | a vector aligns 8 — correct by accident |
| freeing a place writes the empty descriptor | `lo-vecfree` `lower.logos:3299-3328`, `store … zeroinitializer` at `:3327` | `build/p3.ll:80` |
| a struct holding a vector is not allocatable | `check.logos:4971` `body-invariant-free?` | `(alloc rec 1)` is `E0002` |

Corrections to the issue comment's line numbers, all drift from `6094e08` to
`57a67b6`: `check-field-rules` is at **1406**, not 1409; `lo-size` is **326-350**,
not 322-350; `lo-empty-vec` is **2041-2049**, not 2026-2039; `lo-get` is
**2095**, not 2080; `lo-place` is **2110**, not 2095. `check-holds-vector`
(`:397-415`) and the `E0002` at `:1418-1421` are correct as stated.

The issue also says "the R7 rulings". There are three of them
(`build-ledger.md:146`, `:177`, and the `main`-signature one at `:82`), and only
one governs a field place: **`:177`, the own-in-a-place ruling**, whose reason —
"a place read copies the pointer, so two owners exist and a double free follows"
— is the reason a vector field was refused even though R2's wording puts it down
to places not existing. This note reverses that reasoning **for vectors only**;
§8 says why an `(own T)` in a place stays refused.

## 3. Semantics

### 3.1 The place grammar

A **place** is one of:

- a binding name `v` (`letmut` or `let`), as today;
- a `(ref T)` parameter, as today (Task 9 R4) — it denotes the caller's place;
- `(get <place> field)`, where `<place>` is a place whose type is a struct;
- `(arr-get <place> index)`, where `<place>` is a place whose type is a fixed
  array and `index` is an `:i64` expression.

A place's *root* is the binding or parameter at the bottom of that chain. The
root decides mutability and loop depth; the chain decides the type and the
address. Nothing else is a place: `(deref p)`, `(vec-get v i)`, a call, a
literal and an `if` are not (§8).

`vec-len` and `vec-get` take a place and **read** it. `vec-set` and `vec-push`
take a place and **write** it. `vec-free` takes a place, reads it and writes it,
and consumes it. A read place does not require a mutable root; a write place and
a consumed place do (§3.6).

### 3.2 Live, consumed, and what "uninitialised" means

The checker tracks, per place, whether it has been **consumed**: for a binding
that is the existing `bv` moved flag (`check.logos` `body-moved?`); for a field
or element it is new state (D1 below).

Two levels, and the note is only unambiguous if both are stated:

- **Value level.** A vector value is three words. `(vec-free p)` stores the
  *empty descriptor* — `{ null, 0, 0 }` — into the place, which is the same
  value `(make (vec T))` builds (`lo-empty-vec`). A freed place and an empty
  vector are therefore indistinguishable in memory, and that is deliberate: it
  keeps the descriptor three words, and it makes a write to a freed place mean
  exactly what the same write means to a fresh empty vector. A **move** is not
  that: it stores the descriptor into the destination and leaves the source slot
  holding a copy, so a moved-from place holds a stale `{ p, len, cap }` whose
  buffer the destination now owns. A write there is refused (§3.3).
- **Checker level.** A consumed place is *uninitialised*: no operation may read
  it. `vec-len`, `vec-get`, `vec-free`, reading the field as a value
  (`(get b items)` outside a place position), moving it, pushing it into another
  vector and passing it as an argument all raise **E0300**, the use-after-move
  code (`check.logos:5615-5617` is the binding precedent), with the field named
  in the message: `use after move of 'b.items'`.

So "uninitialised, not empty" is a checker-level claim, and it is the claim that
matters: nothing reads a released buffer, and the second
`(vec-free (get b items))` is E0300 rather than a second free.

### 3.3 Writes initialise a freed place

A write to a place emptied by a **free** is legal and initialises it:

- `vec-push` appends to what the place holds; on a freed place that is the
  empty vector, so the push produces a one-element vector. No liveness check is
  performed and none is needed, because "append to the empty vector" is the only
  meaning a write can have there.
- `vec-set` requires a live element index; on a freed (empty) place its
  bounds check panics `R0003` exactly as it would on a fresh empty vector.
- `set-field` / `arr-set` store a whole descriptor, clearing the consumed bit.

At a branch join the freed bit survives only if no arm left the place stale: a
move clears it, so a free in one arm cannot mask a move in the other, and a
write after the join is refused when either path could still hold the stale
descriptor.

A place emptied by a **move** is dead, not empty, and a write to it is E0300
`use after move of '<name>'` — `vec-push` and `vec-set` refuse it for the same
reason `set` refuses a moved binding (`check.logos:3530`). The free is what makes
the write well defined, because the free is the operation that stores the empty
descriptor; the move only copies, so the source slot still names the buffer the
destination owns. Accepting the write would grow from the stale length, free the
buffer the new owner holds, and the program would die `R0002` on the owner's
`vec-free`: a program the checker accepted, reading and releasing memory it does
not own. Refusing it costs nothing a program wants — a push after a move is
always a mistake, since the data the program wanted went to the destination —
and it is the direction `set` already takes.

`set-field` over a **live** vector field overwrites the descriptor and strands
the buffer it pointed at. That is allowed, and it is not silent: the stranded
block is an `rt_alloc` block the leak tracker already holds, so it appears in
the leak report by construction (`lo-fn-finish` / `lo-leak-report`). It is the
same trade the language already made for `set` over a live owner ("Deferred
minor (Task 8): `set` on a live owning binding silently leaks the old block").
Where a program must not leak, the shape is free-then-set:

```logos
(vec-free (get b items))
(set-field b items (make (vec :i64)))
```

### 3.4 What `set-field` does to a moved field

`(set-field b items v)` requires `b` to be a `letmut` binding (`bm == 1`,
`check.logos:5441-5444`) — unchanged. It:

1. evaluates `v` first;
2. moves `v` if the field type is move-only, i.e. calls `body-move-out`
   (`check.logos:5157`) on it, so `(set-field b items v)` leaves `v` consumed and
   a second use of `v` is E0300. `(set-field b items (make (vec :i64)))` needs no
   move: a fresh temporary has no binding to consume;
3. writes the field, and clears the field's consumed bit.

`set-field` never reads the old value, so it works on a consumed field and on a
live one alike.

### 3.5 Construction

`(make rec v 0)` moves each move-only argument into its field, by the same
`body-move-out` call, so `(make rec v v)` is E0300 on the second `v` and the
"two descriptors for one buffer" hazard cannot be spelled that way. A fresh
temporary in that position is constructed in place and needs no move. The
implementation point is `body-make-struct` (`check.logos:5307-5346`), which
today has no move-out call because no field type could be move-only; it needs
one after the `body-fits` check, matching `body-vec-push`
(`check.logos:5730`). `body-make-array` (`:5348`) needs the same for the
array-element case.

### 3.6 Ownership: which code fires where

| Situation | Code | Where it is decided |
|---|---|---|
| read a **live** vector field as a value — `(get b items)` outside a place position | `E0402` | `body-get` → `body-refuse-place-copy`, `check.logos:5205-5225` (vector sentence `:5223`); the word "yet" comes out of the message, because this is no longer pending work |
| read a **live** vector array element as a value | `E0402` | same function, via `body-arr-get` |
| copy a struct that carries a vector (at any depth) | `E0402` | `body-transfer`, `check.logos:5197-5198` — already correct, unchanged |
| read, free or move a **consumed** place | `E0300` | new: place-aware `body-vec-target` / `body-vec-operand` / `body-get` |
| free or move a place whose root is a `let` | `E0104` (vec ops) / `E0302` (move) | `check.logos:5622-5627` and `body-move-out` |
| free or move a place inside a loop, whose root was declared outside it | `E0303` | `body-vec-free` `check.logos:5788-5793`; the rule keys on the **root's** declaration depth, so a field inherits the record's |

The distinction the issue asked to settle: a *live* vector in a place is E0402
(it is a copy, and the language has no copy); a *consumed* vector in a place is
E0300 (there is nothing there to copy). The E0300 check runs first, so a consumed
field reports one reason, the true one.

Two descriptors for one buffer stay refused by invariant 1, and the whole set of
ways to mint one is closed: a value read (`E0402`), a struct copy (`E0402`), a
second push of an already-moved vector (`E0300`, `check.logos:5730`), a second
descriptor through `make`/`set-field`/`arr-set` (`E0300`, §3.5), and a second
free through a field (`E0300`, §3.2). There is no path that yields two live
descriptors for one allocation.

### 3.7 What a struct copy means now

The sentence at `docs/reference/language.md:154-159` — "That restriction is what
makes every struct copy safe" — stops being true, and it was never the mechanism.
The mechanism is R1 (`build-ledger.md:136`): a type that contains a vector at any
depth **moves instead of copying**, so:

- `(let c b)` moves `b`; `b` is consumed and its later use is E0300;
- passing `b` to a by-value parameter moves it (`body-plain-arg`,
  `check.logos:6292-6299`, which also keeps R6: the argument must be a name);
- any attempt to *copy* such a struct is `E0402` from `body-transfer`
  (`check.logos:5197`: `a value containing a vector is not copyable`);
- `(ref rec)` is not a copy: a reference parameter borrows the place, and a
  vector operation through `(get r items)` mutates the caller's record.

So a record that owns a buffer behaves exactly like a bare vector: you can move
it, borrow it, mutate its fields and free its buffer, and you cannot copy it.
The field ban was protecting the same property with a sledgehammer; R1 protects
it precisely, and it is already implemented and already tested.

## 4. Layout

### 4.1 A vector is three words, 8-aligned

A vector value is `{ T*, i64, i64 }` — data pointer, length, capacity — as
`emit.logos:286-288` renders it and `lo-empty-vec` (`lower.logos:2041-2049`)
builds it, slot 0 pointer, slot 1 length, slot 2 capacity. Size **24**, aligned
**8**. That is exact for the one target the backend accepts —
`x86_64-unknown-linux-gnu`, the only value `--target` takes
(`docs/reference/cli.md:311`) — where the pointer and both counters are 8 bytes;
a 32-bit target would make it 12 bytes, and this note would have to be revisited
before that target exists.

Consequences for a record: `(type rec (struct (items (vec :i64)) (n :i64)))` is
`{ { i64*, i64, i64 }, i64 }`, 32 bytes, align 8, `n` at offset 24. Alignment 8
is satisfied by the builder's own `lo-pad` (`lower.logos:352-357`), so no field
padding rule changes.

The layout rules that must learn this:

- `lo-size` (`lower.logos:326-350`) needs a `type-tag-vec` (4, `types.logos:36`)
  case returning 24, before the `ret 8` fallthrough at `:350`. Without it a
  vector measures 8 bytes.
- `lo-align-of` (`lower.logos:359-383`) already returns 8 for a vector through
  its `ret 8` at `:383`; give it an explicit branch anyway, so a later tag
  cannot silently change it.
- `lo-align` (`lower.logos:3141-3162`) likewise: explicit is cheaper than a
  comment.
- `lo-size-struct` (`lower.logos:508-524`) and `lo-fields-size` /
  `lo-fields-align` (`lower.logos:3968-3979`, `:3957-3967`) compose those two
  functions, so they come out right with no edit of their own. Field *offsets*
  in emitted IR are structural geps and were never affected.

Why this is not cosmetic. `lo-vecpush` grows by `size(element) × count` bytes
(`size` at `lower.logos:3388`, `bigger × size` for the `rt_alloc` at
`:3402-3410`, `length × size` for the memcpy at `:3430-3438`), so the first
`(vec rec)` that has to grow would under-allocate by 8 bytes per element — a heap
overwrite, not a diagnostic. That is the concrete failure the `lo-size` case
prevents, and it is reachable from ordinary code: `(vec-push v (make rec …))` on
a full vector.

### 4.2 Arrays of vectors

The same two rules, one stride instead of one field:

- `(arr (vec :i64) 4)` is 4 × 24 = 96 bytes, align 8, stride 24 — this falls out
  of the `lo-size` fix, since `lo-size`'s array case (`:340-342`) multiplies by
  the element size and `lo-align-of`'s array case (`:371-374`) recurses into the
  element's alignment.
- `emit-type-one`'s array case (`emit.logos:281-284`) renders
  `[4 x { i64*, i64, i64 }]`, and LLVM computes the same 96/8/24, so the written
  layout and the emitted layout agree by construction — which is the property
  `lo-size` exists to preserve, and the one R2's reversal makes load-bearing.

An array element is a place in the grammar of §3.1, so `(vec-push (arr-get a 0)
x)` and `(vec-free (arr-get a 1))` work; the index is evaluated and
bounds-checked (`lo-arr-get`'s `lo-bounds`, `lower.logos:2137-2149`) before the
descriptor is touched, so a failed check panics before any mutation.

## 5. `vec-push` through a field place: the store-back and its aliasing rule

`lo-vecpush` (`lower.logos:3340-3491`) already implements grow-in-place through a
place, because R4 gave it one. The place is a binding's alloca today; the only
new thing is that the address may be a field projection.

The sequence it emits, which the field case inherits unchanged:

1. evaluate the pushed value into a temp (`:3355`);
2. load the three-word descriptor from the place (`current`, `:3357-3358`);
3. if full, compute `2*cap+4`, overflow-check it, `rt_alloc` the new buffer,
   `memcpy` (skipped when the old pointer is null), then `rt_free` the old
   buffer;
4. `gep` to `buffer[len]` and store the element;
5. store the new descriptor back into the place —
   `lo-w-store … ty (lo-vec-value …) place` at `:3489`.

The field case changes only how `place` is obtained: instead of the binding's
slot, it is the gep that `lo-setfield` already emits for a field address
(`lower.logos:3556`):

```llvm
%t3 = getelementptr %struct.point, %struct.point* %v.0.addr, i32 0, i32 0
store i64 5, i64* %t3
```

quoted from `build/p6.ll:15-16` — the same `lo-w-gep2` call, with the field's
type, produces `{ i64*, i64, i64 }*` for a vector field, and steps 1-5 then use
it as their pointer. The implementation is one resolver (D2) returning that
address, called once per vector operation; the existing
`direct` / `lo-ref-load` branch (`:3341-3352`) folds into it, because a `ref`
parameter is just a place whose root address is loaded instead of taken.

**The aliasing rules, stated so they survive review:**

1. **The pushed value is evaluated before the descriptor is loaded.** `value` is
   assigned at `:3355`, `current` at `:3357-3358`. This is what makes
   `(vec-push v (vec-get v 0))` safe: the element is read out of the old buffer
   while the old buffer is still live.
2. **Nothing reads the place between the free of the old buffer and the
   store-back.** That window still holds a dangling pointer. The region contains
   only `rt_alloc`, `memcpy`, `rt_free`, `icmp`, `phi`, `gep`, the element store
   and the descriptor `insertvalue` — no call that can name the struct, and no
   load from `place`. An implementation that evaluates an argument or a bounds
   check there breaks the rule; the operative sentence is "grow, then store
   back, with nothing in between that can see the place".
3. **One address, computed once.** The load in step 2 and the store in step 5 use
   the same address value, so a place expression cannot be evaluated twice (which
   would matter for an element place whose index expression is a call).
4. **A place's address does not escape this operation.** No vector operation
   returns a pointer into the record; `vec-get` returns a loaded element, and the
   grammar's place forms appear only in the operand position of the five vector
   operations. That is what keeps "one descriptor per buffer" checkable by the
   type of a value rather than by an alias analysis.

## 6. What the implementation must change

### 6.1-6.4: the four points from the issue comment

Carried forward as stated in the issue comment (change points 1-4), because they
are right and already reviewed:

1. **Place expressions that project a struct field** — extend `lo-place` so
   `vec-push` / `vec-free` take a field place rather than a copy.
2. **Sizing** — a `vec` case in `lo-size` and `lo-align-of`: 3 words, 8-aligned,
   and the same for the array-element case R2 refuses.
3. **Ownership analysis** — a field place is a move, not a copy, so `E0402` /
   `E0300` and `set-field` have to agree with the lowered code.
4. **The manual sentence** — "that restriction is what makes every struct copy
   safe" stops being true and is rewritten in the same change.

### 6.5 The checker's place rule covers five operations, not three

The comment says `vec-push`/`vec-free` take a field place. `vec-len` and
`vec-get` must as well, or a record that owns a list cannot be measured or read
— `(vec-len (get b items))` is the first thing every caller writes. So the
checker's change is: one place resolver returning (type, root binding row, chain
of steps), used by `body-vec-target` (`check.logos:5600`), `body-vec-operand`
(`:5580`, used by `vec-len` and `vec-get`), and by the new consumed-place checks;
`body-get`'s `body-refuse-place-copy` call (`:5426`) stays for value positions.

### 6.6 The compiler's own source depends on free-then-use, and the ruling keeps it

`lo-refill` (`lower.logos:5710-5716`) and `lo-refill-texts` (`:5719-5725`) free a
`(ref (vec …))` parameter and then push into it. Under the reading "free leaves
nothing behind", those two functions would be E0300 and the compiler would stop
building itself. The ruling in §3.3 is what keeps them legal and unchanged:
a write initialises. This is also why §3.2 insists the consumed state *is* the
empty descriptor — the `p5` probe below is that shape, measured: free a
parameter's vector, push, and `vec-len` is 1 — and this ruling makes that meaning
explicit rather than accidental.

An audit of every tracked `.logos` file for "free then use the same name",
scope-aware by enclosing `(fn …)`, finds only those two sites. So the tightening
in §3.2 — the second `vec-free` of a binding is now E0300, where it is accepted
and runs clean today — costs the corpus nothing.

## 7. Invariants, and how each survives

Four non-negotiables from `AGENTS.md`, checked one at a time:

1. **No accepted program reads freed or uninitialised memory.** Reads of a
   consumed place are E0300 (§3.2); writes to one are writes to the empty
   descriptor (§3.3); the only dangling pointer in the compiler's output is the
   grow window described in §5, and no instruction in it can read the place.
2. **No accepted program behaves differently at `-O0` and `-O2`.** Every new
   check is a check-time refusal; the emitted instruction sequence is a gep plus
   the existing push/load/store sequence, identical at both levels, and the
   bounds and capacity guards are explicit branches rather than assumptions.
3. **No form the checker accepts is unimplemented in the backend.** The set of
   newly accepted forms is exactly: five vector operations over the four place
   shapes, `set-field` / `arr-set` / `make` of a move-only field, and a value
   read of a non-move-only field of a record that carries a vector. Each has a
   lowering named in this note (§5, §3.4, §3.5) — and the self-hosting gate is
   what proves it, since the compiler is the largest program in the language.
4. **Every diagnostic carries a code and a node path.** The new refusals reuse
   E0300, E0402, E0303, E0104 and E0302, each raised at the offending node: the
   field atom for a field place, the `get` node for a value read, the root
   binding for the loop rule. No new code is introduced.

## 8. Non-goals

Each of these is refused in this change, with the reason, so the boundary is not
re-litigated per pull request.

- **`(own T)` in a field, in an array element, or read out of a place.** Stays
   `E0402`/`E0002` (R7, `build-ledger.md:177`). A vector's buffer is reachable
   only through its descriptor, and the descriptor is a *value* of the record;
   an owner is a raw pointer whose only handle is the binding, and moving it out
   of a place is the thing invariant 1 forbids rather than defers.
- **`(vec (vec T))` elements as places.** `(vec-get v i)` is not in the place
  grammar, so a nested vector's buffer still cannot be released through the
  element — the deferred minor already recorded in the ledger. It is the next
  reversal (same mechanism, one more production in the grammar), not this one;
  `vec-get` needs a bounds check inside a place resolver, which is its own
  change with its own regress cases.
- **`(deref p)` as a place.** A record that owns a vector cannot be heap
  allocated: `body-invariant-free?` (`check.logos:4971`) refuses a type carrying
  a vector, so `(alloc rec n)` is E0002 and `(deref p)` cannot be the root of a
  vector place. That refusal is unchanged here. When `alloc` learns composite
  invariants, `deref` joins the grammar and nothing else in this note moves.
- **Vector enum payloads** (`check.logos:1521`) stay refused. A payload is
  reached only by a `match` that binds it, and a `match` binding is a copy of
  the payload; there is no place to move through until form-moves exist (Task 9
  R7, `build-ledger.md:146`), which also keeps a vector-typed `if`/`match` result
  refused.
- **A `(vec T)` as an `extern` argument or return.** Unchanged; structs cross
  Logos function boundaries as LLVM aggregates, which the C ABI does not define
  (Task 7's recorded concern).
- **Cloning a vector.** There is still no `clone`; §3.7 says a carrying struct
  moves, so the shape "I want two copies" remains unspellable by design.

## 9. Regress cases the implementation must carry

A change to the compiler is not done until a case under `tests/regress/` fails
before it and passes after it (`AGENTS.md`). This change needs six:

1. `vec-field-push` — a record with a vector field, pushed through the field,
   read back through the field place, freed through the field place; exit 0,
   zero leaks, and identical at `-O0` and `-O2`. This is the growth case that the
   missing `lo-size` case corrupts, so it must push past capacity.
2. `vec-field-after-free` (negative, `E0300`) — `(vec-free (get b items))` then
   `(vec-len (get b items))`.
3. `vec-field-double-free` (negative, `E0300`) — free through the field twice.
4. `vec-field-read` (negative, `E0402`) — `(let c (get b items))`: a value read of
   a live vector field, which is the double free the issue warns about.
5. `vec-field-copy` (negative, `E0402`) — `(let c b)` then a use of `b`: a copy of
   a struct that carries a vector.
6. `vec-array-element` — the array-element case: `(arr (vec :i64) 2)`, push
   through `(arr-get a 0)`, free through `(arr-get a 1)`, exit 0, zero leaks,
   `-O0` == `-O2`. Positive, because the layout fix is the thing being tested.

Plus, in the harness corpus: one case asserting the *edge* that §3.3 allows —
free, then push through the same field, then `vec-len` = 1 — because the ruling
makes that shape legal on purpose and a future reviewer will otherwise read it as
a hole.

## 10. Manual chapter plan

The manual is generated: `docs/manual/*.logos` are the chapter bodies verbatim,
`src/logosc/guide.logos` holds the titles (`g-titles`, `:434`) and the rule
list, and `docs/LOGOS.md` is the output that `guide --check` gates. Chapter
sources cannot be edited without regenerating the manual, so the chapter edits
below land in the PR that regenerates it, not in the PR that lands this note.

Numbered listing of the changes, in chapter order:

1. **Chapter 5, "Structs"** (`docs/manual/05-structs.logos`, title at
   `guide.logos:443-444`) — add to the `(test structs …)` body a record with a
   vector field and an array-of-vector field, constructed, read through a scalar
   field, and *moved* into a second binding; expected stdout gains one line and
   `(leaks 0)` still holds. Purpose: the copy rule (§3.7) shown as code, in the
   chapter that owns `(get …)` and `set-field`.
2. **Chapter 8, "Vectors"** (`docs/manual/08-vectors.logos`, title at
   `guide.logos:449-450`) — add a `(type bucket (struct (items (vec :i64)) (label
   :i64)))` to the chapter's `(test vectors …)`: push through the field place,
   `vec-len` through the field place, `vec-get` through it, `vec-free` through
   it, then `set-field` of a fresh vector and a second push. Expected stdout gains
   three lines, `(leaks 0)` holds. Purpose: the five place-taking operations and
   the free-then-set reinitialisation (§3.3-§3.4) as one runnable chapter.
3. **Chapter 6, "Fixed arrays"** (`docs/manual/06-fixed-arrays.logos`, title at
   `guide.logos:445-446`) — one `(arr (vec :i64) 2)` pushed through
   `(arr-get …)` and freed through it. Only if the array half lands in the same
   PR; the chapter stays untouched otherwise.
4. **The rule list** (`guide.logos`, `g-rules`) — one sentence beside the existing
   vector rules: "A vector field is a place: `push`, `set`, `len`, `get` and
   `free` reach it, a read of it is a move, and a record that owns one is moved,
   never copied." This is the manual's one-line statement of the ruling and it is
   what a reader of `docs/LOGOS.md` will search for.
5. **Regenerate** — `./tools/logosc.sh guide > docs/LOGOS.md` in the same PR, or
   `guide --check` fails and the gate says so by name.

`docs/reference/language.md` is hand-written and is *not* generated, which is why
the amendment in §6.4 lands here (§11 of this note governs the wording) and the
chapter edits do not.

## 11. The reference wording this note fixes

`docs/reference/language.md:154-159` today:

> A struct field may be a scalar, `:str`, a fixed array, an enum, an `(opt T)` or
> a function value. It may **not** hold a vector, a result or an owner — those
> three are `E0002` … That restriction is what makes every struct copy safe.

That paragraph was replaced in this pull request, which is the change the note is
the specification for: a field may be a vector; a vector field is a place, and
the five vector operations take it; a field read is a move, a freed field is
uninitialised, and a struct carrying a vector is moved, never copied. The vec
section (`### Vectors — allocate, fill, free`) does not repeat the restriction,
so it was left alone rather than given a cross-reference to a chapter that the
regeneration PR has not landed yet. The new wording reads as the language's
shape, with no forward reference to code that does not exist.

## 12. Evidence

Probes run against the compiler built from this tree (`./tools/logosc.sh`, which
rebuilds `build/logosc` from `src/`):

| Probe | Shape | Result |
|---|---|---|
| `p1` | `(type rec (struct (items (vec :i64)) (n :i64)))` | `p1/rec/0/0: E0002: vector fields are not supported yet`, exit 2 |
| `p2` | `(arr (vec :i64) 2)` | `p2/main/2/1: E0002: vector array elements are not supported yet`, exit 2 |
| `p3` | `(vec-free v)` twice, then build and run | accepted, runs clean, exit 0 — the gap §3.2 closes |
| `p4` | `(let w v)` then `(vec-free w)` | `E0104: cannot free immutable binding 'w'` — a record that owns a buffer must be `letmut` (§3.4) |
| `p5` | free a `(ref (vec :i64))`, push, print `vec-len` and element | `1` and `9`, exit 0 — write-initialises is what the runtime does today |
| `p6` | `set-field` on a two-field record | the gep quoted in §5, from `build/p6.ll:15-16` |

IR quoted in this note, both from those builds and both reproducible with
`logosc build … --keep-ir` (`build/<stem>.ll` is always written):

- the three-word descriptor and the empty vector — `build/p3.ll:18-21`;
- free as a zeroed descriptor — `build/p3.ll:80`;
- the grow path's `mul bigger, size` (`:58`) and `mul length, size` (`:62`) —
  `build/p5.ll:58` and `:62`;
- the field address gep — `build/p6.ll:15`.

The probe sources, so each of those lines can be reproduced without asking for
the scratch directory:

```logos
(mod p3)
(fn main :void ()
  (letmut v (vec :i64) (make (vec :i64)))
  (vec-push v 7)
  (vec-free v)
  (vec-free v)
  (println 0))
```

```logos
(mod p5)
(fn refill :void ((v (ref (vec :i64))))
  (vec-free v)
  (vec-push v 9))
(fn main :void ()
  (letmut v (vec :i64) (make (vec :i64)))
  (vec-push v 1)
  (vec-push v 2)
  (refill v)
  (println (vec-len v))
  (println (vec-get v 0))
  (vec-free v))
```

```logos
(mod p6)
(type point (struct (x :i64) (y :i64)))
(fn main :void ()
  (letmut p point (make point 1 2))
  (set-field p x 5)
  (println (get p x)))
```

## 13. Decisions

Each is stated so it can be rejected on its own.

**D1. Consumed state is per place, not per binding.** `(vec-free (get b items))`
consumes `items` and leaves `(get b n)` readable, which is the whole point of a
record. Cost: new checker state — a flat list of (binding row, field/element
path) consumed places, or the equivalent per-root bit set — threaded through the
body checker the way `bv` already is. Cost if wrong: over-refusal, or a second
free through a field.

**D2. One place resolver in the checker and one in the lowerer.** Four place
shapes, five operations, one function each side; the `direct`/`lo-ref-load`
special case in the four vector lowerings folds into it. Cost if wrong: four call
sites to fix instead of one.

**D3. Reads are refused, writes initialise a *freed* place.** Stated in
§3.2-§3.3. This is what keeps `lo-refill` (`lower.logos:5710`) legal and
unchanged. Cost if wrong: a forgotten free-then-read is caught, a deliberate
free-then-push is legal — a program that frees and then pushes gets an empty
vector, which is the only meaning appending to nothing can have. A place emptied
by a *move* is not freed and not empty, so `vec-push` and `vec-set` refuse it
with the E0300 `set` already gives a moved binding; the free's `bv` handled bit
is what tells the two apart, because the free is the only operation that stores
the empty descriptor into the place.

**D4. `set-field` over a live vector field is allowed and leaks visibly.** Same
trade as `set` over a live owner; the leak report names the stranded block. Cost
if wrong: a program can leak a buffer it could have freed.

**D5. No new diagnostic code.** E0300 for consumed places, E0402 for value reads
and copies, E0303 for the loop rule, E0104/E0302 for mutability. Cost if wrong:
two situations share a code whose message is less specific than it could be.

**D6. The refused-message word "yet" comes out.** `a vector cannot be read out of
a place yet` (`check.logos:5223`) and `vector fields are not supported yet`
(`:1421`) are statements about pending work; after this change the first is a
rule, and the second no longer exists. Cost if wrong: a message that reads like a
promise.

**D7. Refusals keep raising `E0002` only where `E0002` is honest.** The field
refusal uses code 2 while `docs/reference/diagnostics.md:73` defines `E0002` as
"unknown node" — the code is the contract, and this one mis-states it. Deleting
the refusal deletes the mis-use; nothing added here reuses code 2 (see D5). Cost
if wrong: none, unless a reviewer wants the old code preserved for
compatibility, which nothing depends on.

**D8. Enum payloads, nested-vector elements, `deref` places, and `extern` stay
out** (§8). Each has a stated condition that brings it in. Cost if wrong: three
shapes stay impossible a while longer.
