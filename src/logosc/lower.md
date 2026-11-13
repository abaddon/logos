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

## The gaps

Two of these are the fixtures that do not reproduce Python's `.ll`; both are
named as known-different in `tools/selfhost-ir.txt`. The third is refused
before there is any text to compare. All three are B2's work:

1. **`str-len` extracts one field; Python extracts two.**
   `str_parts` in `lower.py` pulls *both* the pointer and the length out of the
   `{ i8*, i64 }` value, and `str-len` then discards the pointer — the dead
   `extractvalue …, 0` stays in the text. `lo-strlen` extracts only field 1, so
   the port's IR is one instruction shorter and every later temp is numbered
   one lower.
   *Needs:* extract field 0 into a throwaway temp first, then field 1, matching
   `str_parts`' order.

2. **`match` leaves `entry` unterminated.**
   `lo-match` stores the scrutinee, plans the arm blocks and calls `lo-w-block`
   for the first `matchN.test0` — but never branches from the block it is in
   into that test. `emit` refuses the module (`block 'entry' has no
   terminator`), so `gen2 build` has no `.ll` at all for this fixture; the
   failure is a diagnostic with code `E0002` at the module's node path, not a
   panic.
   *Needs:* the `br` into the first test (or into the wildcard arm's body)
   before the first `lo-w-block`, which is what Python's `match_expr` emits.

3. **A wildcard arm is refused — B2's, not this PR's, and not in the list.**
   `(match x (0 1) (_ 2))` where `x :i64` makes `gen2 build` fail with
   `E0002: a match pattern is an integer literal or _` — printed at the file,
   because the failure carries no node path — where Python lowers it and emits
   no comparison for `_` at all. On an enum scrutinee the same arm fails
   earlier, at `E0100: unknown variant in match`. Either way `_` is not taking
   the wildcard path `lo-match` intends (`iswild`); it is treated as a pattern
   that must be an integer literal or a variant name.
   *Needs:* `_` recognised as a wildcard arm before the test is built, so the
   arm's body is entered with no `icmp` and no `cbr`. No listed fixture uses a
   wildcard arm, so the parity list never sees this one.

## What it does not lower

`lo-value` dispatches `+`, `-`, `*`, `/` and `%` at whatever integer width or
float type the checker resolved, the comparisons, `and`/`or`/`not`, `cast`,
`if`, `while`, `match`, `make`/`get`/`arr-get`, `str-len`, `f64-bits`, direct
and `extern` calls, variant constructors and literals. The bit shifts are not
lowered: `shl`, `shr` and `shr-u` reach `lo-not-yet` like any unhandled head, so
`(shr a 2)` is `E0002: 'shr' is not lowered by this backend yet` at the form's
node path. (`frem` and `fneg` are not forms at all — both front ends reject
them as an unknown function, `E0103` — so they are missing from the language,
not from this pass.) Any other head reaches `lo-not-yet` the same way, failing
at the form's node path with `E0002`: `print`/`println`, `vec-*`, `arr-*`
(other than `arr-get`), `alloc`/`free`, `spawn`/`join`, channels, mutexes,
closures, results and optionals, `str-concat`/`str-eq`/`str-slice`, `run`,
`read-file`, `args`, and the ownership rules around them. That is PR C's list,
and the check phase keeps the boundary honest by listing only what the checker
already decides.
