# `src/logosc/ir.logos` — the IR arena

The port of `logos/ir.py`. Python's IR is a flat list of instruction tuples whose
item 0 is the opcode; Logos has no tuples and no classes, so this module keeps the
same information in a handful of **parallel vectors**: one row per instruction,
with the opcode, a destination, up to four operand slots, three type ids, an
index and two runs. A block is a slice of those rows, and a function is a slice
of blocks. Nothing here lowers anything: this is storage plus the constructors
a lowering will call, and the vocabulary it may call them with.

Read `emit.md` next: the spelling lives there, and it is the only reader of this
arena.

## API

```logos
(type ir-error (struct (failed :bool) (code :i64) (text :str)))
(fn ir-ok ir-error ())
(fn ir-fail ir-error ((code :i64) (text :str)))
(fn ir-good :bool ((e ir-error)))
```

`ir-error` is the port's `ValueError`: `emit` returns it and a caller reports
`text` when `failed`. The same struct is what the front end already uses for a
diagnostic (`types.logos`'s `type-error` has the same three fields), so `main`
can print either with one function.

Every constructor takes the caller's vectors by `(ref …)` and appends or writes
them; none of them allocates a vector, frees one, or keeps state between calls.

### Vocabulary

```logos
(fn ir-op-none :i64 ())                     ; 0, the guard below
(fn ir-op-alloca :i64 ()) … (fn ir-op-icall :i64 ())   ; 1 … 43
(fn ir-term-ret :i64 ()) … (fn ir-term-unreachable :i64 ())  ; 1 … 4
(fn ir-op-text :str ((op :i64)))            ; the mnemonic, "" when unknown
(fn ir-term-text :str ((op :i64)))
(fn ir-is-binary :bool ((op :i64)))         ; 5 … 19
(fn ir-is-convert :bool ((op :i64)))        ; 26 … 34
```

The numbering is closed and copied from `logos/ir.py` and `logos/llvm.py`; no
constructor invents a mnemonic. `add` through `fdiv` are contiguous so the
emitter can print all fifteen with one shape, and `trunc` through `fptrunc` are
contiguous for the same reason. `ir-op-text` is the one table that spells a
mnemonic, and `emit` prints binary and conversion rows through it.

A constructor given an opcode of the wrong shape records `ir-op-none` instead
(`ir-binary` with a `store`, say). A row with opcode 0 is one `emit` cannot
print, so a mis-shaped row fails loudly at emission rather than printing
something that merely looks like IR — the same guarantee Python gets from
raising on an unknown opcode. `src/logosc/emit_test.logos` pins that path.

## The module

| vector | type | one entry per | holds |
|---|---|---|---|
| `mtriple` | `:str` | module | the target triple (one row) |
| `mqual` | `:i64` | module | 1 when declaration names are module-qualified |
| `snames` / `sbase` / `scount` | `:str` / `:i64` / `:i64` | struct | name, first field in `sftys`, field count |
| `sftys` | `:i64` | field | field type ids, declaration order |
| `enames` / `ewords` | `:str` / `:i64` | enum | name and payload width in eight-byte words |
| `gnames` / `gdata` | `:str` / `:str` | global | name and its exact bytes |
| `dnames` / `dsig` / `dcnt` / `dret` | `:str` / `:i64`×3 | declare | name, first parameter in `sigtys`, count, return type |
| `sigtys` | `:i64` | declare parameter | parameter type ids |
| `fnames` / `fsyms` | `:str` | function | source name and linker symbol ("" when the same) |
| `fint` / `fret` | `:i64` | function | internal linkage flag, return type |
| `fbase` / `fcnt` | `:i64` | function | first block, block count |
| `fparam` / `fpc` | `:i64` | function | first parameter in `pnames`, parameter count |
| `pnames` / `ptys` | `:str` / `:i64` | function parameter | emitted name (no `%`), type id |
| `blabels` | `:str` | block | label |
| `bbase` / `bcnt` | `:i64` | block | first instruction row, row count (`-1` = no terminator yet) |
| `bterm` / `bty` / `bhas` | `:i64` | block | terminator opcode, its type, whether `ret` carries a value |
| `bv1` / `bv2` / `bv3` | `:str` | block | the terminator's operands (below) |
| `ops` | `:i64` | instruction | the opcode |
| `dests` | `:str` | instruction | destination, spelled with its `%`; `""` for a void call |
| `a` … `d` | `:str` | instruction | up to four operand slots (below) |
| `t1` … `t3` | `:i64` | instruction | type ids, `-1` where the shape has none |
| `n1` | `:i64` | instruction | the index a shape carries (field index, `geprec` index) |
| `sst` / `scn` | `:i64` | instruction | first entry in `svals`, entry count |
| `tst` / `tcn` | `:i64` | instruction | first entry in `tvals`, entry count |
| `svals` | `:str` | run entry | operands that are a list of strings (below) |
| `tvals` | `:i64` | run entry | operands that are a list of type ids (below) |

Names are stored exactly as the emitter must print them: a local and a
destination carry their `%` (Python's `IrFn` does the same), a global, a symbol
and a label are bare, and the printer adds `@`, `%` or the quotes. That keeps a
literal (`41`, `null`, `undef`) and a local (`%t3`) distinguishable without a
second naming convention.

### The instruction rows

Every row constructor takes the same sixteen vectors — the fourteen row
columns, `svals` and `tvals` — so a row always lands in all of them at once:

| opcode | dest | `a` | `b` | `c` | `t1` | `t2` | `n1` | run |
|---|---|---|---|---|---|---|---|---|
| `alloca` | `%x` | | | | type | | | |
| `store` | | value | slot | | type | | | |
| `load` | `%x` | slot | | | type | | | |
| `gaddr` | `%x` | global | | | | | | |
| `add` … `fdiv` | `%x` | left | right | | type | | | |
| `icmp`, `fcmp` | `%x` | predicate | left | right | type | | | |
| `phi` | `%x` | | | | type | | | `svals`: value, label pairs |
| `insertvalue` | `%x` | aggregate | element value | | aggregate type | element type | index | |
| `extractvalue` | `%x` | aggregate | | | aggregate type | element type | index | |
| `gep` | `%x` | base | | | base type | | | `svals`: index type text, index pairs |
| `trunc` … `fptrunc` | `%x` | value | | | from type | to type | | |
| `bitcast` | `%x` | value | | | from type | to type | | |
| `call` | `%x` | callee | | | | | | `svals`: arguments |
| `allocarec` | `%x` | | | | | | | `tvals`: field types |
| `geprec` | `%x` | base | | | | | index | `tvals`: field types |
| `bitcastrec` | `%x` | value | | | from type | | | `tvals`: field types |
| `bitcastout` | `%x` | value | | | to type | | | `tvals`: field types |
| `faddr` | `%x` | symbol | | | | | | |
| `fnptr` | `%x` | value | | | return type | | | `tvals`: parameter types |
| `icall` | `%x` | callee | | | return type | | | `tvals`: parameter types, `svals`: arguments |

`phi`, `gep`, `allocarec`, `geprec`, `bitcastrec`, `bitcastout`, `fnptr`,
`icall` and `call` are built in two steps: the row first, then one appender per
list element. The appender writes into the row at `(vec-len ops) - 1`, so it is
the row just built — the same discipline `docs`/`types.logos` uses for a payload
run, and why a run is contiguous.

`ir-gep-index` stores the index type as **text**, not as a type id, because
`lower.py` passes the spelled index type (`i32`, `i64`) rather than a `Ty`: the
index is an integer literal in LLVM's grammar, and the fixture's spelling must
match Python byte for byte.

### Terminators

| opcode | `bty` | `bhas` | `bv1` | `bv2` | `bv3` |
|---|---|---|---|---|---|
| `ret` | the value's type | 1 | value | | |
| `ret` (void) | the declared return type | 0 | | | |
| `br` | `-1` | 0 | target label | | |
| `cbr` | `-1` | 0 | condition | then label | else label |
| `unreachable` | `-1` | 0 | | | |

Each terminator closes the **last** block: it sets `bcnt` to the rows since
`bbase`, so a block that is never terminated keeps `bcnt = -1` and `emit`
reports `block '<label>' has no terminator`, exactly as `llvm.py` does.

## Constructors

| function | builds |
|---|---|
| `ir-module mtriple mqual triple qual` | the header row |
| `ir-struct snames sbase scount name base count` | one named struct row |
| `ir-enum enames ewords name words` | one enum width row |
| `ir-global gnames gdata name data` | one global's bytes |
| `ir-sig-start sigtys`, `ir-sig-param sigtys ty` | a declaration's parameter run |
| `ir-declare dnames dsig dcnt dret name start count ret` | one `declare` row |
| `ir-fn … name symbol internal ret` | a function row; returns its id |
| `ir-param pnames ptys name ty` | one parameter |
| `ir-fn-end fbase fcnt fparam fpc blabels pnames fid` | closes the block and parameter runs |
| `ir-block … label` | a block row |
| `ir-alloca`, `ir-store`, `ir-load`, `ir-gaddr` | the four memory shapes |
| `ir-binary … op dest ty left right` | `add` … `fdiv` |
| `ir-icmp`, `ir-fcmp` | comparisons |
| `ir-phi`, `ir-phi-in` | a `phi` and one incoming pair |
| `ir-insertvalue`, `ir-extractvalue` | aggregate surgery |
| `ir-gep`, `ir-gep-index` | a `getelementptr` and one `(type, index)` step |
| `ir-convert … op dest from to value` | `trunc` … `fptrunc` |
| `ir-bitcast` | one bitcast |
| `ir-call`, `ir-call-arg` | a direct call and one argument |
| `ir-allocarec`, `ir-rec-field` | a literal-struct stack slot and one field type |
| `ir-geprec` | the address of one literal-struct field |
| `ir-bitcastrec`, `ir-bitcastout` | value to record pointer, record pointer to value |
| `ir-faddr` | a function's address as `i8*` |
| `ir-fnptr`, `ir-fnptr-param` | `i8*` to a callable, and one parameter type |
| `ir-icall`, `ir-icall-param`, `ir-icall-arg` | an indirect call, its parameter types and its arguments |
| `ir-ret`, `ir-ret-void`, `ir-br`, `ir-cbr`, `ir-unreachable` | block terminators |

A lowering is expected to open a function, add its parameters, add each block,
emit that block's rows, terminate it, and close the function: the run indices
are computed at `ir-fn` and `ir-fn-end`, never by the caller.

## Indexing

A block is the slice `[bbase[b], bbase[b] + bcnt[b])` of the instruction rows; a
function is the slice `[fbase[f], fbase[f] + fcnt[f])` of the blocks. The two
pairs `ir-block-first` / `ir-block-past` and `ir-fn-first` / `ir-fn-past` are
the only place that arithmetic lives, so a reader never has to reconstruct it.
`ir-instr-count` is the arena's row count.

Because rows are appended in block order, a block's slice is contiguous by
construction; nothing is ever inserted into the middle. That is also why the
emitter can walk a function and its blocks with two integers and no index
vector.

## What it does not do

- **No validation of types.** `t1` is an index into the caller's type arena; the
  arena is `types.logos`'s (or a test's), and neither module knows whether the
  row's types make sense together. The emitter is where a missing layout is
  reported.
- **No lowering.** Nothing here reads a tree; `lower.logos` (PR B) is the caller
  that turns a checked body into these rows.
- **No printing.** `emit.logos` owns every byte of the text.
- **No ownership.** Every vector is the caller's, exactly as in `types.logos`.

## Tests

`src/logosc/emit_test.logos` is generated by `tools/ir_parity.py`: it builds the
same modules the fixtures were emitted from, through these constructors, and
`emit.md` describes the comparison. The four negative cases pin the refusals: a
mis-shaped row (`unknown IR opcode 0`), a primitive outside the closed list, a
block with no terminator, and an enum whose width was never registered.
