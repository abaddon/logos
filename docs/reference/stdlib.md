# Standard library reference

Three modules ship with the compiler. `(use io)`, `(use str)` and `(use map)`
each import a file from `src/std/` and add plain functions — there is no
namespace, no trait, no generic container, and no hidden allocation. Every
function below is implemented in Logos and tested by a sibling `*_test.logos`
suite.

**The whole library is 21 functions.** That is the v1 surface (gap A4): values
in `map` are `:i64` and keys are `:str`, there is no string→integer parse, no
sort, no formatting, no `unlink`, no `stat`, no `getenv`. Plan around it; see
[`limits.md`](limits.md).

- Resolution: `(use name)` looks for `name.logos` beside the asking file, then
  in `src/std/` relative to the **working directory**.
- Signatures below are the declared ones from `src/std/*.logos`.
- Rationale and edge cases: `src/std/io.md`, `src/std/str.md`, `src/std/map.md`.

---

## `io` — files, by descriptor

| Function | Returns | Meaning |
|---|---|---|
| `io-create path` | `:i64` | open `path` for writing, creating or truncating it; mode 0644 less the umask. The descriptor, or `-1` |
| `io-write fd s` | `:i64` | write every byte of `s`; the number written, or `-1` on the first failed write |
| `io-close fd` | `:i64` | `close(fd)`; `0`, or `-1` |
| `io-read path` | `:str` | the whole file. **Panics `R0007`** if it cannot be read |
| `io-temp-path stem n` | `:str` | `/tmp/<stem>-<n>` — a name, not a file |

Rules that matter:

- Everything is a **byte** count or a byte string. `:str` is a pointer plus a
  length and is never NUL-terminated; `io-create` is the one place a terminator
  is added (inside the runtime's `rt_create`).
- `-1` is the entire error vocabulary. The language cannot carry `errno` out of
  libc, so there is no error type and no message.
- No `unlink`. A file you create stays until something outside the program
  removes it; a test that writes one must truncate it on a rerun instead of
  deleting it.
- No `mkdir -p`: `io-create` in a missing directory returns `-1` and continues.
- `io-read` is the one function here that **panics** rather than returning an
  error.
- `io-write` writes all bytes or reports `-1`; a short write is not reported as
  a partial count.

```text
(use io)

(fn save :void ((path :str) (text :str))
  (let fd :i64 (io-create path))
  (if (< fd 0)
    (println "could not create")
    (if (= (io-write fd text) (str-len text))
      (println (io-close fd))
      (println "short write"))))
```

## `str` — byte strings

The prefix is `string-`, not `str-`: `str-*` names are builtins
(`str-len`, `str-byte`, `str-concat`, `str-slice`, `str-eq`, `str-from-i64`),
and the library's names avoid colliding with them.

| Function | Returns | Meaning |
|---|---|---|
| `string-find hay needle from` | `:i64` | first index at or after `from` where `needle` occurs; `-1` when absent |
| `string-split sep s` | `(vec :str)` | the fields of `s` between separators, **empty fields kept** |
| `string-join parts sep` | `:str` | the parts joined by `sep`; borrows `parts` (`letmut`; the caller frees it) |
| `string-starts-with s prefix` | `:bool` | whether `s` begins with `prefix` |
| `string-match-at hay needle at n` | `:bool` | implementation: do the first `n` bytes of `needle` equal `hay` at `at`? |
| `string-split-nonempty (ref parts) sep s sn` | `:void` | implementation: the split for a separator of at least one byte |

Rules that matter:

- Every index is a **byte** index. `"héllo"` is six bytes, so
  `(string-find "héllo" "llo" 0)` is `3`. Nothing here knows UTF-8 and nothing
  needs to: separators are one-byte ASCII.
- `string-split` returns a vector you own: free it with `(vec-free parts)`.
  The returned fields are **views into `s`**, so `s` must outlive them — do not
  free the source string while holding the fields.
- `string-join` **borrows** its parts vector; the caller frees it.
- No `string-contains`: `(> (string-find hay needle 0) -1)` is the whole of it.
- No trim, case folding, replace, ordering comparison or Unicode segmentation.

```text
(use str)

(letmut fields (vec :str) (string-split "," "a,,b,"))
(println (vec-len fields))          (vec-free fields)
```

That prints `4`; joining the same vector with `"|"` gives `a||b|`, because the
empty fields between the separators are kept.

## `map` — string-keyed tables, by reference

A table is **three vectors you own and pass by reference**: keys, values, and
hash slots. There is no map object. Values are `:i64`; keys are `:str`.

| Function | Returns | Meaning |
|---|---|---|
| `map-init (ref slots) size` | `:void` | append `size` empty buckets; call once on a fresh `slots`. Optional but preferred — `map-put` starts an uninitialised table at 8 buckets |
| `map-put (ref keys) (ref vals) (ref slots) k v` | `:void` | store `v` under `k`, replacing a present value |
| `map-get (ref keys) (ref vals) (ref slots) k` | `:i64` | the value under `k`, or `-1` when absent |
| `map-has (ref keys) (ref slots) k` | `:bool` | whether `k` is present |
| `map-count (ref keys)` | `:i64` | the number of entries |
| `map-find (ref keys) (ref slots) k` | `:i64` | the bucket of `k`, or `-1`; implementation |
| `map-hash s size` | `:i64` | the first bucket of `s`, in `[0, size)`; implementation |

Rules that matter:

- **Absence and a stored `-1` are indistinguishable through `map-get`.** Ask
  `map-has` when a negative value is legal. A caller whose values are indexes
  may read `-1` as absent — that is what the compiler does.
- Reads on a table with no buckets at all are misses: `map-has` false,
  `map-get` `-1`, `map-count` 0.
- No deletion, no iteration. To walk the table, walk `keys` by index
  (`(vec-len keys)` and `(vec-get keys i)`) — insertion order.
- You free all three vectors yourself, exactly once.

```text
(use map)

(letmut keys (vec :str) (make (vec :str)))
(letmut vals (vec :i64) (make (vec :i64)))
(letmut slots (vec :i64) (make (vec :i64)))
(map-init slots 8)
(map-put keys vals slots "answer" 42)
(map-get keys vals slots "answer")             ; 42
(map-has keys slots "missing")                 ; false
(map-count keys)                               ; 1
(vec-free keys) (vec-free vals) (vec-free slots)
```

## One program, all three modules

Built and run while writing this page; the output is copied from the run. It is
also the cheapest smoke test that a checkout's standard library resolves.

```logos
(mod probe)

(use io)
(use str)
(use map)

(fn main :void ()
  (letmut parts (vec :str) (string-split "," "a,,b,"))
  (println (vec-len parts))
  (println (string-join parts "|"))
  (println (string-find "hello" "ll" 0))
  (println (string-starts-with "hello" "he"))
  (vec-free parts)
  (letmut keys (vec :str) (make (vec :str)))
  (letmut vals (vec :i64) (make (vec :i64)))
  (letmut slots (vec :i64) (make (vec :i64)))
  (map-init slots 8)
  (map-put keys vals slots "a" 1)
  (map-put keys vals slots "b" 2)
  (println (map-count keys))
  (println (map-get keys vals slots "b"))
  (println (map-has keys slots "zz"))
  (println (map-find keys slots "zz"))
  (let p (io-temp-path "docprobe" 7))
  (println p)
  (let fd (io-create p))
  (println (io-write fd "hello io"))
  (println (io-close fd))
  (println (str-len (io-read p)))
  (vec-free keys) (vec-free vals) (vec-free slots))
```

```text
4
a||b|
2
true
2
2
false
-1
/tmp/docprobe-7
8
0
8
```

Build and run it as `logosc build probe.logos -o probe && ./probe` — the twelve
lines above are the whole output, in order. `(use map)` resolves from the
installation, so the file builds from any working directory.
