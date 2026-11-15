# W9 — a wrong-arity form, in every root set

Written 2026-11-15, on top of `baf37f8`. This closes §4 of the baseline report:
a three-argument `str-concat` was accepted in the compiler's own multi-root
build and its third operand was dropped, while the same call as a standalone
module was refused `E0102`.

## The finding, and how it was reproduced

The baseline report's line was `(str-concat path ":" (vec-get problem 0))` in
`harness.logos`'s `h-judge`. Restoring that spelling where the two-argument
form now sits, building, and running the module's own suite gave exactly the
report's symptom:

```
FAIL exec/harness_test/baseline-refuses-an-unreadable-status
  -O0: stdout: expected 'logos: test: tests/summary.txt:3: baseline status must be PASS or FAIL, found \'MAYBE\'\n',
       got 'logos: test: tests/summary.txt:\n'
11 passed, 1 failed, 0 leaked
```

The build succeeded, and at run time the function printed `path:` — the third
operand was not there at all.

## The smallest root set

Two files, and the call in the second one. `a.logos` is the file named on the
command line; `b.logos` is its import, in the same directory:

```
(mod a)

(use b)

(fn main :i64 ()
  (ret (b-cat 7)))
```

```
(mod b)

(fn b-cat :i64 ((n :i64))
  (println (str-concat "path" ":" (str-from-i64 n)))
  (ret (str-len (str-concat "ab" "cd" "ef"))))
```

```
$ ./bootstrap/logosc build /tmp/min/a.logos -o /tmp/min/a.bin     # baf37f8
$ /tmp/min/a.bin
path:
$ ./bootstrap/logosc check /tmp/min/b.logos
b/b-cat/2/0: E0102: str-concat takes two strings
```

`b.logos` matters because it is **not** the root. The very same source is
refused when `b.logos` is the file on the command line and accepted when it is
reached through `(use b)` — so the gap is the module and not the call.

## Where the call sits does not matter. Where the module sits does.

| position of the three-operand `str-concat`, in an imported module | `baf37f8` |
|---|---|
| a diagnostic argument inside a user call | accepted, operand dropped |
| a `let` initialiser | accepted, operand dropped |
| the body of a `fn` closure | accepted, operand dropped |
| a `test` body | **refused** `E0102` |

`test` bodies are the exception because `check-module-tests` has no root gate:
every module's tests are read. `fn` bodies are the hole.

## The mechanism

`check-module-fns` declares each own `fn` and hands the node to `check-fn-one`,
which records it — node and `fn` type id — for the body pass. That record was
taken only for the module at slot 0:

```logos
(vec-push vindex idx)
(if (and (= slot 0)
      (= (vec-get out 2) 0))
  (check-fps-add fps c (vec-get out 0))
  (check-nothing))
```

`slot` is the module's index in the resolver's set, so `(= slot 0)` means "the
file named first on the command line" and nothing else. Every other module ran
its declaration pass — entries, `vindex`, signatures, visibility — and then
`check-module-fn-bodies` walked an empty `fps` list and returned pass: no arity
rule, no type rule, no move rule, no diagnostic. The lowering does not re-check
arity either; `lo-strconcat` reads children 1 and 2 and never touches a third,
so the operand is dead code that never reaches the IR. `tools/logosc.sh build`
passes the 21 `src/logosc` modules, plus `map` and `str`, with
`body_test.logos` first, so in the compiler's own
build exactly one module was ever body-checked and `harness.logos` was not. The
gate arrived in `9414b4d` (W6 B1) as a staged scope — "the declaration pass now
reads function bodies for the root module" — and no later PR lifted it;
`check.md` documented it as Python parity, and Python's checker had the same
hole.

## The fix

One condition, in the one place that decides whether a body is read:

```logos
(if (= (vec-get out 2) 0)
  (check-fps-add fps c (vec-get out 0))
  (check-nothing))
```

The generic guard stays: a generic body has no single type and is checked per
instantiation. The gate does not: `check-module` already visits every module
exactly once (`state` 2), so each module's bodies are read once, in declaration
order, after that module's declarations — the existing order, now applied to
the whole set. No new traversal is added.

Every fixed-arity form lives behind this same gate, because the gate is on the
record, not on the form. Swept with the two-file root above, one call per row,
`baf37f8` and the fixed compiler side by side:

| form, called with one operand too many (or too few) | `baf37f8` | fixed |
|---|---|---|
| `str-concat` ×3 | accepted | `E0102: str-concat takes two strings` |
| `str-eq` ×3 | accepted | `E0102: str-eq takes two strings` |
| `str-len` ×2 | accepted | `E0102: 'str-len' takes a :str` |
| `str-slice` ×4 | accepted | `E0102: 'str-slice' takes a :str, a start and an end` |
| `str-byte` ×3 | accepted | `E0102: 'str-byte' takes a :str and an index` |
| `str-from-i64` ×2 | accepted | `E0102: 'str-from-i64' takes an :i64` |
| `f64-bits` ×2 | accepted | `E0102: 'f64-bits' takes a :f64` |
| `vec-len` ×2 | accepted | `E0102: 'vec-len' takes a vector` |
| `vec-get` ×3 | accepted | `E0102: 'vec-get' takes a vector and an index` |
| `vec-push` ×1 | accepted | `E0102: vec-push takes a vector name and a value` |
| `vec-set` ×2 | accepted | `E0102: vec-set takes a vector name, an index and a value` |
| `vec-free` ×0 | accepted | `E0102: vec-free takes a vector name` |
| `get` ×3 | accepted | `E0102: 'get' takes a struct and a field` |
| `set-field` ×2 | accepted | `E0102: set-field takes a mutable name, a field and a value` |
| `and` ×3 | accepted | `E0102: 'and' takes two operands` |
| `not` ×2 | accepted | `E0102: 'not' takes one operand` |
| `some` ×2 | accepted | `E0102: 'some' takes one value` |
| `ok` ×2 | accepted | `E0102: 'ok' takes one value` |

18 of 18 were accepted before and 18 of 18 refused after; the sweep is one
`check` per form, no build.

## What the fix found in the compiler's own source

Turning the body pass on for every module refused exactly one shipped form:
`h-level-token` tests an `-O` level token with a three-operand `and`.

```logos
(ret (and (>= n 3)
       (str-eq (str-slice s 0 2) "-O")
       (>= (h-digits (str-slice s 2 n)) 0)))
```

`and` is binary in both halves of the compiler — `body-logical` refuses a count
other than two, and `lo-logical` reads children 1 and 2 — so the third
condition, `(>= (h-digits ...) 0)`, was being dropped: `h-level-token` answered
true for `-Oxx` as well as `-O2`, and `OPTS` parsing was weaker than the source
says. That is the same silent drop as `str-concat`, in shipped code, hidden by
the same gate. It is now the nested binary spelling, with the same
short-circuit order:

```logos
(ret (and (and (>= n 3)
            (str-eq (str-slice s 0 2) "-O"))
       (>= (h-digits (str-slice s 2 n)) 0)))
```

The rest of `src/` is unchanged by the wider check: with the fix in place the
23-module source builds with no diagnostic and every suite stays green.

Two behaviour changes follow, and only two. A program carrying a wrong-arity
form in **any** module is now refused `E0102` with the module, the function and
the node in the path, where before it built and ran with an operand missing; no
correct program changes, and the 309-case corpus replays unchanged. And an
`OPTS` token must now really end in digits, which is what `h-level-token` said
it checked all along.

## The regress case

`tests/regress/arity-in-import/` is the two-file root above, with `program`
playing the part of `a` and `helper` the part of `b`:

| file | content |
|---|---|
| `program.logos` | `(mod program)`, `(use helper)`, `main` calling `helper-length` |
| `helper.logos` | `(mod helper)`, `helper-length` building its string with a three-operand `str-concat` |
| `program.expect` | `E0102` |
| `program.check` | `helper/helper-length/2/0/0: E0102: str-concat takes two strings` |

`program.expect` records the case in the corpus; `program.check` is what
`tools/selfhost.sh`'s checker phase compares, byte for byte, and it is the half
that fails before the fix: at `baf37f8` `gen2 check` exits 0 on that fixture
where the gate expects a line. (The corpus records an `.expect` case without
compiling it — a compile-negative case cannot also be a run — so the corpus
line is `PASS` on both sides and the checker phase is the judge that flips.)
`tools/selfhost-check.txt` lists it
(`CHECK_FLOOR` 123 → 124) and both new sources are in
`tools/selfhost-manifest.txt`, which that gate requires to equal the tracked
`.logos` set. `check_test.imported-body-arity` pins the same fixture from inside
`check_test.logos`, so the unit suite refuses it too.

## Suites

| suite | `baf37f8` | after |
|---|---|---|
| `./tools/logosc.sh test tests` | 308 passed, 10 leaked, 0 regression(s) | 309 passed, 10 leaked, 0 regression(s) |
| `harness_test.logos` `-O0` | 11 passed, 1 failed | 12 passed, 0 failed |
| `check_test.logos` `-O0` | 80 passed, 0 failed | 81 passed, 0 failed |
| `body_test.logos` `-O0` | 361 passed, 0 failed | 361 passed, 0 failed |

The corpus and `harness_test` were measured on both sides. `check_test` is 80
before and 81 after because the only change to it is the new case;
`body_test` is unchanged, so its 361 is the same suite at both ends (measured
after; no case was added or removed).

## The stage-0

`src/` changed, so `bootstrap/logosc` was rebuilt from the new compiler and its
hash recorded:

```
cp build/logosc bootstrap/logosc
( cd bootstrap && sha256sum logosc > logosc.sha256 )
```

`bootstrap/logosc.sha256` is now
`95f7f4c2384a7426c0d7dd011740b989d1049120fc611f6de5eb272c37a4066c`. The
stage-0, `build/logosc` and a gen3 built from `src/` by the new stage-0 are the
same bytes, which is the fixed point `tools/selfhost.sh` requires: it refuses a
stage-0 that is not the binary its own source produces (that check landed in
`baf37f8`), so a stale bootstrap fails by name rather than by a symptom.

## Branch

`fix/arity-in-every-root-set`, one signed-off commit on `baf37f8`.

## Files

- `src/logosc/check.logos` — the slot gate in `check-fn-one`.
- `src/logosc/harness.logos` — `h-level-token`'s `and`.
- `src/logosc/check.md` — the body pass is every module's, and the Python
  parity this deliberately gives up.
- `src/logosc/check_test.logos` — `imported-body-arity`.
- `tests/regress/arity-in-import/{program,helper}.logos`,
  `program.expect`, `program.check`.
- `tools/selfhost-check.txt`, `tools/selfhost-manifest.txt`,
  `tools/selfhost.sh` (`CHECK_FLOOR`).
- `tests/summary.txt` — regenerated by `--update-baseline`.
- `bootstrap/logosc`, `bootstrap/logosc.sha256`.
- The case counts that say 308 or 80: `Makefile`, `README.md`,
  `src/logosc/harness.md`, `src/logosc/check.md`.
