# `src/std/str.logos` — find, split, join, prefix

Design §D10 needs `str-concat` only for a fragment; the lexer and the tooling need
these four. Logos has no comments and no doc form, so this file is the header
documentation the source cannot carry. Read it before calling the module.

## Names: `string-*`, not `str-*`

The plan first spelled these `str-find`, `str-split`, `str-join`,
`str-starts-with`; it now says `string-*` and `(ref parts)` (commit
`eb727ac`). A `fn` may not be called `str-*` at all: the checker reserves the
`str-` head for the form family (`logos/check.py:RESERVED_PREFIXES`), so the
definition is refused where it is written, before any call is resolved:

```
FAIL exec/str_test/find -O0: build failed: E0003 str/str-match-at: reserved form name
```

`join` on its own is also a reserved form (the thread join), so the four names
are the plan's names with the reserved head expanded: `string-find`,
`string-split`, `string-join`, `string-starts-with`. Nothing else changed. W3
may not touch the checker, so the spelling moves, not the rule; if W9 wants the
`str-` head back it must first make the reservation name-exact rather than a
prefix test.

## API

| function | returns | meaning |
|---|---|---|
| `string-find hay needle from` | `:i64` | the first index at or after `from` where `needle` occurs, `-1` when absent |
| `string-split sep s` | `(vec :str)` | the fields of `s` between separators, empty fields kept |
| `string-join parts sep` | `:str` | the parts joined by `sep`; **borrows `parts`** (a `letmut`; the caller frees it) |
| `string-starts-with s prefix` | `:bool` | whether `s` begins with `prefix` |
| `string-match-at hay needle at n` | `:bool` | implementation: the first `n` bytes of `needle` equal `hay` at `at` |
| `string-split-nonempty (ref parts) sep s sn` | `:void` | implementation: the split for a separator of at least one byte |

Bytes come from `(str-byte s i)` (`:u8`), lengths from `(str-len s)` (`:i64`).
A `:str` is a pointer and a byte count, so every index here is a **byte** index:
`"héllo"` is six bytes and `(string-find "héllo" "llo" 0)` is `3`. Nothing in
this module knows about UTF-8, and nothing needs to: the separators the lexer
uses are one-byte ASCII.

```logos
(use str)
(letmut fields (vec :str) (string-split "," "a,,b,"))
(vec-len fields)                       ; 4
(vec-free fields)
```

## `string-find`

- Returns the index of the first match **at or after** `from`. A match that
  starts before `from` does not count, even if it extends past it.
- `-1` when there is no match, when `from < 0`, when `from > (str-len hay)`, or
  when the needle is longer than the haystack left after `from`.
- An **empty needle matches at `from`**, so `(string-find "hello" "" 2)` is `2`
  and `(string-find "hello" "" 5)` is `5`. The one exception is `from` past the
  end: `(string-find "hello" "" 9)` is `-1`, because there is no position `9` in
  a five-byte string.
- An empty haystack with an empty needle at `from` `0` gives `0`; with any
  non-empty needle it gives `-1`.

The search is naive: it compares the needle at each position, so the worst case
is O(len hay × len needle). That is the right shape for its callers — the lexer
asks for a one-byte operator at a position it already holds — and it never reads
past the end of the haystack: the loop stops when
`at + len needle > len hay`, before any `str-byte`.

`string-find` does not allocate, does not copy, and takes no ownership.

## `string-split`

Splits `s` on every occurrence of `sep` and returns **every field, in order,
empty fields included**:

| call | result |
|---|---|
| `(string-split "," "a,,b,")` | four fields: `"a"`, `""`, `"b"`, `""` |
| `(string-split "," "")` | one field, `""` |
| `(string-split "," "abc")` | one field, `"abc"` — the whole string |
| `(string-split "," ",a")` | two fields: `""`, `"a"` |
| `(string-split "::" "a::b::")` | three fields: `"a"`, `"b"`, `""` |

A trailing separator yields a final empty field, which is what makes the
round trip `join (split s sep) sep` equal `s` for every `s` — join borrows the
fields, so the caller keeps them:

```logos
(letmut parts (vec :str) (string-split sep s))
(let result :str (string-join parts sep))
(vec-free parts)
```

The separator may be several bytes; matches do not overlap.

**Empty separator — pinned: one field holding the whole of `s`.** The language
has no `panic`, `assert` or `abort` (W3 adds no form), so the alternatives were
a wrong-looking value or a contract this module cannot enforce. A one-field
result is exactly what "separator not present" already answers, it keeps the
function total, and it round-trips through `string-join`; splitting on "nothing"
has no other defensible meaning. The caller's duty is not to pass an empty
separator; the behaviour is defined only so that the function has an answer at
all. `(string-split "" "")` is one empty field, not two, and not zero.

### The fields are views, and the source must outlive them

`str-slice` builds a **view** — the same buffer at an offset with a shorter
length (`lower.py:str_slice`), no bytes copied. Every field `string-split`
returns therefore points into `s`, and **the caller must keep `s` alive for as
long as the vector is used**: freeing or overwriting the source while the
fields are still read leaves them pointing at dead bytes, and the language will
not stop you.

The vector itself is the caller's: `(vec-free fields)` when done. Nothing else
is owned — the strings in it are views, and there is no per-element free.

Cost: one `string-find` per field plus one `vec-push` per field, linear in
`|s|` because each search starts where the last field ended. The vector grows
amortised; `(string-split "," line)` on a 96 KiB (98,304-byte) line with 32,769
fields leaks nothing (`str_test.logos` case `growth`).

## `string-join`

- Zero parts give `""`, and no `str-concat` call is made.
- One part gives **that part itself** — unchanged, not copied: the first part is
  not concatenated.
- Two or more parts give `p0 + sep + p1 + …`, built by `str-concat`.

Each part after the first costs two calls — one appends the separator to the
accumulated result, one appends the part — so `n` parts cost `2(n−1)`
`str-concat` calls, **not** `2n−1`: zero for `n` = 0 and `n` = 1, two for `n` =
2, and so on. Each call copies the accumulated result, so joining costs
O(n × result length) bytes copied. **It is the simple shape, not the fast one.**
A caller joining a hundred thousand fields wants a preallocated buffer and a
per-field `memcpy`, which the language does not offer yet.

### It borrows the vector; the caller frees it

`string-join` takes `parts` as `(ref (vec :str))` — a **borrow**, not a move —
and never frees it. After the call the caller still owns the vector:
`(vec-len parts)` is unchanged, a second `(string-join parts sep)` is legal, and
`(vec-free parts)` is the caller's line to write when it is done with the
fields.

The argument must be a `letmut` binding; an immutable `let` is refused:

```
E0304 a ref argument must be a mutable binding, and 'parts' is not
```

The trade-off is the one to keep in view. A vector passed by value could be
freed inside the join and could not leak, but that made every join a hidden
ownership transfer: the caller's vector was gone, and touching it again was
`E0300 use after move`, with no way to ask for a join that kept the fields. The
borrow removes that trap and moves one obligation to the caller: **a forgotten
`(vec-free parts)` is a leak, not an `E0300`.** The checker cannot catch it,
because nothing was consumed. The free therefore belongs in the same function
that allocated the vector, on the line after the last read.

```logos
(letmut fields (vec :str) (string-split "," "a,b"))
(println (string-join fields ","))
(vec-free fields)
```

### What the result points at

**The result is a fresh buffer for `n ≠ 1` and a view of the single part for
`n = 1`.** (For `n` = 0 that "fresh buffer" is the empty literal `""`; no copy
is made.) With two or more parts every `str-concat` allocates a new buffer, so
the result points into nothing the caller owns — and, per §D9, that buffer is
kept for the process's life and is never freed. With exactly one part the code
returns `(vec-get parts 0)` unchanged: the result **is** that string, so it
aliases whatever the part aliases — for a part that came from `string-split`,
the source string. The keep-the-source-alive rule above therefore extends to a
join of one part. Freeing the vector is not the hazard (its elements are views
and own nothing); freeing or overwriting the string a part was sliced from is.

## `string-starts-with`

`true` when `s` begins with `prefix`, `false` otherwise. An **empty prefix is
always true**, a prefix longer than `s` is `false` — checked before any byte is
read, so it does not panic. `(string-starts-with "" "a")` is `false` and
`(string-starts-with "" "")` is `true`.

## What it does not do

- No `string-trim-left`. The plan offers it "if the lexer needs it"; the lexer
  does not exist yet and skips whitespace by advancing its own index, so there
  is no caller to pin a contract for. Adding it later is a few lines over
  `str-byte`.
- No trimming, case folding, replacement, comparison beyond equality, or
  Unicode segmentation. Bytes only.
- No search that allocates or caches; no KMP. `string-find` is linear per call
  and its callers start where the last match ended.
- No `string-contains`: `(> (string-find hay needle 0) -1)` is the whole of it,
  and two names for one question is how a library drifts.

`src/std/str_test.logos` pins the edges above: empty haystack, a needle at `0`,
at the end and absent, the empty needle, `""` split, a split with no separator,
`"a,,b,"`, the empty separator, joins of zero, one and many parts, a round trip
matrix over nine strings, and a 96 KiB (98,304-byte) line split into 32,769
fields with `(leaks 0)`.
