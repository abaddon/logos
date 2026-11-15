# W8 — the enum in a struct, and the `-1` that was not an index

Branch `feat/selfhost-w7-backend`, on top of `03700c1`. The oracle is Python on
the same tree, every time. `gen2 test tests/exec/results.logos` used to fail all
21 cases at type-scan with `lower/lo-reaches/5/2: R0003: vector index out of
bounds`; eighteen of them now lower and pass, and the three that do not are
named in §4 because they do not share this cause.

## 1 The cause

`lo-reaches` answers "does type `ty` reach `target` by value?". A struct and an
enum both descend through `lo-reaches-fields`, which walks
`pchild[pbase[ty] + k]`. For an enum, that row is a variant's payload type id,
and a payload-less variant's row is **`-1`** — this port's `None`, exactly the
`payload is None: continue` Python's `_unlowered` uses.

`lo-enum-body` guards its own walk (`(>= (vec-get pchild q) 0)`), so an enum
with a nullary variant was safe *on its own*. But when a struct holds that enum
by value, the struct's walk enters the enum through `lo-reaches`, and the shared
query had no guard:

```
lo-reaches(struct s)
  → lo-reaches-fields(s)
    → lo-reaches(enum e)          tag 13
      → lo-reaches-fields(e)
        → lo-reaches(-1)          the nullary variant
          → (vec-get tags -1)     R0003
```

`lo-var-reach` has opened with `(if (< ty 0) (ret false))` since it was
written; `lo-reaches` did not. That asymmetry is the whole bug: a negative id is
"no type", not an arena row, and reading `tags[-1]` is the bounds failure the
gate printed.

Reproduced on the smallest shape, before the fix:

```
(type e (enum (a :i64) (b)))     ; b has no payload
(type s (struct (x e)))          ; s holds e by value
→ lower/lo-reaches/5/2: R0003
```

The same file with `(enum (a :i64))` — every variant carries a payload — lowered
and ran. That is the discriminating experiment: the crash is the nullary
variant, not the enum-in-struct edge itself.

## 2 The fix

One guard at the query, in `src/logosc/lower.logos`:

```logos
(fn lo-reaches :bool (...)
  (if (< ty 0)
    (ret false)
    (lo-nothing))
  ...
```

No call site changed: `lo-struct-body`, `lo-enum-body` and `lo-reaches-fields`
still pass whatever `pchild` holds, because the query now answers `false` for
"no type" instead of indexing with it. `lo-enum-body`'s existing guard stays —
it is the same answer at a second layer, and removing it would be a separate
claim.

## 3 Fixtures

Five new files under `src/logosc/fixtures/ir-lower/`, all in
`tools/selfhost-ir.txt` and `tools/selfhost-manifest.txt`, all byte-identical
to Python's `.ll` and clang-clean (`clang -O2 -Werror` over each):

| fixture | shape |
|---|---|
| `enum-in-struct.logos` | a struct holding one enum by value (the crash) |
| `enum-two-shapes.logos` | a struct holding two enums: a nullary-only one and one with `:i64`/`:str` payloads |
| `enum-pad.logos` | `(struct (y :i64) (x e))` — the enum sits after an `i64`, never at offset zero |
| `struct-in-enum.logos` | an enum holding a struct by value (payload edge, the other direction) |
| `enum-in-struct-ref.logos` | the same two shapes reached through `(ref (vec …))` parameters |

The first four are the by-value walk; the fifth pins that a `ref` stops it.
`IR_FLOOR` moves 65 → 70 and `IR_FIXTURE_FLOOR` 61 → 66 in
`tools/selfhost.sh`, with the comments and `lower.md`'s count updated.

A by-value self-reference still refuses correctly: the guard returns "no type"
for a nullary payload and "false" for the cycle it would otherwise walk, and
`src/logosc/fixtures/ir-refuse` stays green.

## 4 What moved, measured

`gen2 test tests/exec/results.logos` (one file, all 21 cases):

| | before | after |
|---|---|---|
| passed | 0 | 18 |
| failed | 21 | 3 |

`gen2 test --only exec tests`:

| | before | after |
|---|---|---|
| passed | 107 | 125 |
| failed | 32 | 14 |
| leaked | 4 | 4 |

`gen2 test tests` (whole suite):

| | before | after |
|---|---|---|
| passed | 273 | 291 |
| failed | 35 | 17 |
| leaked | 10 | 10 |

The failing set moves by **exactly eighteen entries and nothing else**: the
diff of the two `FAIL` sets is 18 removed, 0 added. One `exec/results` case is
IR-identical to Python end to end — `enum-in-a-struct-field` builds, its `.ll`
matches `driver.run_test`'s byte for byte, and it prints `7`.

The three `exec/results` cases that still fail are **not** this cause, and the
fix was not widened to reach them:

- `try-inside-one-expression`, `try-inside-a-loop` — `(println (match …))`:
  the match-in-expression/argument gap (`E0002: a statement must be a form`),
  one of the four match cases this task was told to leave alone. They were
  inside the 21 only because the whole file used to die at type-scan.
- `enum-in-a-vector` — a different bug, a **name** query rather than a type
  query. `(vec-push v b)` lowers to `%t39 = load i64, i64* %v.1.addr` where
  Python emits `insertvalue { i32, [1 x i64] } undef, i32 1, 0`. Instrumenting
  `lo-atom-value` showed `b` resolving to a *binding* (`DBGATOM b idx=9`): the
  scope stack `bindn`/`binda` is not reset between function lowerings, so a
  parameter named `b` from an earlier function in the module is still live
  inside the test body and shadows the nullary variant constructor. It reduces
  to one line in `main`'s IR; it is not reached by any shape in the five
  fixtures, and it needs its own task (scope lifetime, not the arena walk).

Because of those three the counts are 125/14 and 291/17 rather than the
brief's 128 and 14. The eighteen that moved all share the `-1` cause; the
three that did not are the two excluded match cases plus one new, distinct
scope bug.

## 5 The gates

`tools/pr_gate.sh` 6/6 on the commit; `fmt` is a fixed point (the guard is
already canonical, and the five fixtures format to themselves); the manifest,
the IR list and both floors move in the same commit, as the gate requires.
