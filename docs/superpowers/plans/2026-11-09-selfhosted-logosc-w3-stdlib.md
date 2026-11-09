# W3 — the Logos standard library

Wave W3 of `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md`. The
compiler's own tables, string tools and file IO written in Logos, tested in
Logos, before any compiler code moves.

Read with the design, §D7 (arenas and integer handles), §D8 (one map), §D9 (no
free inside the compiler), §D10 (fragments), and the layout (`src/std/`).

## Shape

The language has no vector inside a struct and no generics in the plan, so the
library is **functions over parallel vectors passed by `(ref …)`**, never a
container object:

```
src/std/map.logos   one map, :str to :i64   (D8)
src/std/str.logos   find, split, join, byte helpers
src/std/io.logos    file open/write/read, temp path, run wrapper
```

A table is three vectors owned by the caller:

```
(letmut keys  (vec :str) (make (vec :str)))
(letmut vals  (vec :i64) (make (vec :i64)))
(letmut slots (vec :i64) (make (vec :i64)))
```

`slots` holds `entry + 1` per bucket (`0` means empty), `keys`/`vals` hold the
entries in insertion order. No deletion, no ordered iteration, load factor 0.7,
power-of-two bucket count, the multiply-and-add hash of §D8.

## Global constraints

- Every `.logos` file is `fmt`-canonical and idempotent; `logosc fmt` changes nothing.
- Each task adds tests that **fail before** its code and pass after; record the
  failing line in the report.
- The library is tested by `python3 -m logos test src/std`, run at `-O0` and
  `-O2`, with `(leaks 0)` wherever the test frees.
- `git commit -s`; one logical change per commit; `docs/LOGOS.md` only through
  `python3 -m logos guide`.
- No new language form and no compiler change in this wave. If a task believes
  it needs one, stop and report — that is a design decision, not a task.

## Task 1: the map

- [ ] `src/std/map.logos`: `map-init (ref slots size)`, `map-put (ref keys)
      (ref vals) (ref slots) k v`, `map-get (ref keys) (ref vals) (ref slots) k`
      returning `-1` when absent, `map-has`, `map-count`.
- [ ] `src/std/map_test.logos`: empty table; one key; a key that collides at the
      first bucket (compute two keys with the same `h % size`); growth when the
      load passes 0.7 (the bucket vector doubles and every live entry is
      re-probed); absent key; 1,000 keys inserted and read back; a value of `-1`
      stored (so `-1` cannot double as "absent" — decide and pin the contract).
- [ ] Probe before writing: the hash's wrapping multiply, `%` on a power of two,
      and whether a `:str` key compares with `str-eq` in a loop without copying.

## Task 2: the string tools

- [ ] `src/std/str.logos`: `str-find (hay needle from) :i64` (-1 when absent),
      `str-split (sep) (s) -> (vec :str)` (empty fields kept, a trailing
      separator yields a final empty field), `str-join (parts) (sep) :str`,
      `str-starts-with`, `str-trim-left` if the lexer needs it.
- [ ] `src/std/str_test.logos`: empty haystack, needle at 0, at the end, absent;
      split of `""`, of a string with no separator, of `"a,,b,"`; join of zero
      parts (empty), one part, many; round trip `join (split s) == s` for a
      table of strings including one with a NUL byte.
- [ ] Growth: splitting a 100 KB line yields the right count and leaks nothing.

## Task 3: file IO and the run wrapper

- [ ] `src/std/io.logos`: `io-create (path) :i64` over `rt_create`,
      `io-write (fd) (s) :i64` over `rt_write`, `io-close (fd)`, a read that
      reuses `(read-file …)`, `io-temp-path (stem) :str` (using the environment's
      temp directory), and `io-run (prog) (args) :(vec :str)` — no: keep the run
      wrapper to what the driver needs, decided by Task 3's implementer and
      recorded in the report.
- [ ] `src/std/io_test.logos`: write a file, read it back, compare; write 1 MB
      through fragments; create in a missing directory fails as a code, not a
      crash; temp paths differ between two calls.
- [ ] `rt_create`/`rt_write` are declared as `(extern fn …)` in the file; the
      runtime is already linked into every binary.

## Task 4: the suite and the gate

- [ ] `tests/test_stdlib.py`: runs the tester over `src/std` and asserts the case
      count and zero failures, so `make test` covers the library.
- [ ] `python3 -m logos test src/std --opt -O0 --opt -O2` green.
- [ ] `bash tools/pr_gate.sh` 5/5; branch `feat/selfhost-w3-stdlib`; PR; squash
      merge with the admin bypass.

## Review focus

1. The map's contract for an absent key and for a stored `-1`: a caller must not
   be able to confuse them.
2. Rehash correctness: every live entry re-probed, no duplicate, no lost key.
3. `str-split`'s empty-field rule, at the start, the middle and the end.
4. No leaks in paths that allocate (split, join, rehash, read).
5. Every function documented in the file's header comment: the AI reader needs
   the contract in the source, not in a manual chapter.
