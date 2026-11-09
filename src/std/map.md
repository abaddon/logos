# `src/std/map.logos` — one map, `:str` to `:i64`

Design §D8. The compiler's tables (functions, types, variables, diagnostic codes)
are all this map; a value is an index into the caller's parallel vectors.

Logos has no comments and no doc form, so this file is the header documentation
the source cannot carry. Read it before calling the map.

## Shape

No generics, no container object. The caller owns three parallel vectors and
passes them by `(ref …)`:

| vector | type | meaning |
|---|---|---|
| `keys` | `(vec :str)` | one key per entry, in insertion order |
| `vals` | `(vec :i64)` | the value of each entry, at the same index as its key |
| `slots` | `(vec :i64)` | one bucket per slot: `entry + 1`, or `0` for empty |

`slots` stores `entry + 1` because `0` must mean "empty" and entry `0` is a real
entry. The value of the entry a bucket points at is
`(vec-get vals (- (vec-get slots idx) 1))`.

```logos
(letmut keys (vec :str) (make (vec :str)))
(letmut vals (vec :i64) (make (vec :i64)))
(letmut slots (vec :i64) (make (vec :i64)))
(map-init slots 8)
```

## API

| function | returns | meaning |
|---|---|---|
| `map-init (ref slots) size` | `:void` | append `size` empty buckets; call once on a fresh `slots` |
| `map-put (ref keys) (ref vals) (ref slots) k v` | `:void` | store `v` under `k`, replacing a present value |
| `map-get (ref keys) (ref vals) (ref slots) k` | `:i64` | the value under `k`, or `-1` when absent |
| `map-has (ref keys) (ref slots) k` | `:bool` | whether `k` is present |
| `map-count (ref keys)` | `:i64` | the number of entries |
| `map-hash s size` | `:i64` | the first bucket of `s`, in `[0, size)` |
| `map-find (ref keys) (ref slots) k` | `:i64` | the bucket of `k`, or `-1` when absent |

`map-hash`, `map-find`, `map-needs-grow`, `map-grow` and `map-insert` are the
implementation; only the first five are the library surface. `map-put` starts an
uninitialised table at 8 buckets, so `map-init` is optional but preferred (it
picks the size).

## Contract: absent key and a stored `-1`

- `map-get` answers `-1` for a key that is not in the table.
- `-1` is also a legal stored value (`map-put … k -1` succeeds), and the two
  cases are indistinguishable through `map-get` alone.
- **Presence is decided by `map-has`, never by comparing `map-get`'s result with
  `-1`.** A caller that may store a negative value asks `map-has` first; a caller
  whose values are indexes, which is every table in the compiler, may read `-1`
  as absent.

The alternative, panicking on an absent key, would need a new runtime code and a
way to raise it from Logos; neither exists, and W3 may not add a form. The two
functions are the separation the design allows.

`src/std/map_test.logos` pins both halves: `value-minus-one` stores `-1` and
asserts `map-has` is true while `map-get` is `-1`; `absent` asserts a missing key
gives `-1` with `map-has` false.

## Hash

`h = h * 1099511628211 + byte`, starting at `h = 0`, over the bytes of the key,
wrapping at 64 bits; then `h % size` with a power-of-two `size`.

Multiply-and-add rather than FNV-1a because the language has no integer `and`,
`or` or `xor` (only `:bool` operators), and a new operator would be a seventh
surface item for one hash.

`:i64` is signed, so the wrapping product goes negative for keys of three bytes
or more, and `%` keeps the sign of its left operand: `h % 8` came back as `-7`
for the key `aaaaa`. `map-hash` adds `size` once to a negative remainder, so
every index is in `[0, size)`. That correction is load-bearing: without it
`(vec-get slots idx)` panics on a negative index (proved by mutation).

## Probing and growth

Linear probing, `(idx + 1) % size`, wrapping at the end. No deletion, no
tombstones; stopping at an empty bucket is a miss. A key's first bucket never
changes for a given `size`, so `map-put`, `map-get` and `map-has` agree.

`map-put` grows when `entries + 1 > 0.7 × buckets`, that is when
`(entries + 1) * 10 > buckets * 7`: 8 buckets hold 5 entries, the sixth put
doubles to 16, 16 holds 11, and 1,000 entries end at 2,048 buckets.

Growth happens in place, because the language has no `vec-clear` and a `(ref …)`
parameter cannot be rebound to a new vector: `map-grow` appends `buckets` zeros,
zeroes every bucket, then re-probes every live entry from its key. One live
bucket per entry, no duplicates, no loss; the test counts occupied buckets after
growth to prove it. This makes a put amortised O(1).

`shortcut:` the map never frees anything. The compiler is a one-shot process and
the vectors are freed in `main`, if at all (design §D9).

## What it does not do

No deletion, no ordered iteration, no iteration at all: walk `keys` by index if
you need insertion order. Keys are `:str` only; values are `:i64` only.
