# W8 — the last two corpus gaps: `!=` on `:str`, and a binding that outlived its function

Branch `feat/selfhost-w7-backend`, commit `242f115` on top of `ec21cec`. The
reference is `logos/lower.py` (`compare`, `str_compare`, `_Lower.__init__`,
`scope`); Python is the oracle on the same tree, every time.

`gen2 test tests` is now **308 passed, 0 failed, 10 leaked**, exit 0 — the same
totals Python's `logos test tests` prints, on the same tree, in the same run.
The port's `test` matches the oracle through the summary line: the FAIL set is
empty, and there is no declared gap set left to explain one.

```text
python3 -m logos test tests
308 passed, 0 failed, 10 leaked
baseline tests/summary.txt: 0 regression(s)

build/w8last/gen2 test tests
308 passed, 0 failed, 10 leaked
```

| run | before (`ec21cec`) | after (`242f115`) |
|---|---|---|
| `gen2 test tests` | 306 passed, 2 failed, 10 leaked | **308 passed, 0 failed, 10 leaked** |
| Python `logos test tests` | 308 passed, 0 failed, 10 leaked | unchanged |

The two FAIL entries removed, none added:

```text
removed
  exec/strings/equality
  exec/results/enum-in-a-vector
```

## 1 `!=` on `:str` — the negation is an `icmp`, the equality is the `phi`

Python decides this in `logos/lower.py::_Lower.compare` (`compare`, line 4024).
The `:str` branch is the first thing it does with the operand type:

```python
if isinstance(ty, Prim) and ty.name == "str":
    if node.kind == "!=":
        equal = self.str_compare(items[1], items[2], node.path)
        dest = self.temp()
        self.emit(("icmp", dest, "eq", Prim("bool"), equal, "false"))
        return dest
    if node.kind == "=":
        return self.str_compare(items[1], items[2], node.path)
```

So `!=` is the equality lowering **plus one instruction**: `str_compare` is
the whole byte comparison (length `icmp`, `memcmp` call, the
`phi (equal, compare), ("false", differ)` — `str_compare`, line 2357), and the
negation inverts that bool with `icmp eq i1 %equal, false`. It is not a second
`phi` and not a rewrite of the comparison; `=` returns the `phi`'s temp
unchanged.

The port's `lo-compare` (line 1902) handled only `=`: every other operator,
`!=` included, fell to `lo-not-yet-str` and `E0002: '!=' is not lowered`. The
new `lo-strneq` (line 2821) is exactly the Python shape — `lo-streq` (the
port's `str_compare`, which already emitted byte-identical IR for `=`) then:

```text
(lo-w-icmp … dest "eq" (lo-prim … "bool") equal "false")
```

and `lo-compare` dispatches `!=` to it. `strneq.logos` pins the IR: both the
`icmp eq` and the `phi` inside `lo-streq` agree with Python byte for byte, and
the program prints `true` then `false`.

## 2 The same corpus case needed a second, one-line cause

The brief named one cause for `exec/strings/equality`, and that was right about
the first error (`'!=' is not lowered`). With `!=` lowered, the case still
failed at its **last two lines**:

```text
exec/strings/equality/5: E0100: 'println' takes a number, :bool or :str
```

`(println (str-eq "abc" "abc"))` is valid Logos — the oracle prints `true` for
it — but `lo-node-type` (line 1237) had no `str-eq` branch, so `lo-print` asked
for the type of the argument and got `-1`. This is the same defect family as
the named one: a builtin the checker types, the lowerer's type query did not.
The added branch is one line and returns `bool`:

```text
(if (str-eq h "str-eq")
  (ret (lo-prim tags tnames elem extra pbase powner "bool"))
  (lo-nothing))
```

It is reported here separately rather than folded into §1 because the brief's
rule is that a case needing more than its named cause must say so. It is a
lowering gap in the same case, not a new corpus gap; `strings/equality` moves
19/1 → 20/0 only with both lines.

## 3 The scope-lifetime bug: `binda` covered the planning pass, not the one that emitted

Python has no lifetime question to get wrong: `_Lower` is constructed per
function and `self.vars = {}` in `_Lower.__init__` (line 1759); a nested block
saves and restores the dict (`scope`, line 1771). A function's bindings cannot
be visible to the next function because there is no shared table.

The port keeps one `bindn`/`bindt`/`binds`/`binda` for the unit. `lo-fn`
(line 3582) snapshots `base = (vec-len bindn)` (line 3610), lowers the body
once to plan slots, calls `lo-close-scope binda base` (line 3630), then lowers
the whole function **again** with emission on (line 3650) — and never closed
that second set. `lo-close-scope` (line 652) sets `binda[i] = 0` from `base`;
`lo-lookup` (line 620) only matches rows whose `binda` is `1`. So every
parameter and `let` from the emitted pass stayed live for the rest of the
module. `lo-atom-value` and `lo-atom-node-type` consult `lo-lookup` before the
variant table, so a live `b` beat the nullary variant constructor `b`:

```text
exec/results/enum-in-a-vector:
  %t39 = load i64, i64* %v.1.addr          ; the stale parameter b
Python:
  %tN = insertvalue { i32, [1 x i64] } undef, i32 1, 0
```

The fix is one call at the true end of the unit, after `lo-site-drain`
(line 3656):

```text
(lo-close-scope binda base)
```

The drain lowers the lambdas, function values and spawn thunks queued by this
function; it must see this function's bindings (their rows are read by index
and their types by name), so the close belongs after it. The lifetime is not
weakened — `binda` still only ever has `1` for the live unit, and every row
from `base` is dead before the next function starts.

### Test mode: the drain lives in the caller

The first placement also closed at the end of `lo-test-main`, which broke five
`tests/exec/closures.logos` cases with `E0005: unknown name 'k'` (`k`/`a` are
captured `let`s of lambdas in a test body). The control-flow answer is (a):
`lo-test-main` is not the end of its unit. `lo-test-entry` builds the synthetic
main, calls `lo-test-main` (line 6271), and only then calls `lo-site-drain`
(line 6275) — the lambda sites it has to lower are the ones the body queued.
Closing inside `lo-test-main` therefore closed **before** the drain.

The final shape snapshots the table before the test main and closes after the
entry's drain:

```text
(let tbase :i64 (vec-len bindn))     ; lo-test-entry, before lo-test-main
(lo-test-main …)
(lo-site-drain …)
(lo-close-scope binda tbase)         ; after the drain
```

The lambda body's captures were already the site's problem, not the enclosing
scope's: `lo-lambda` computes the capture rows at the site
(`lo-captures`/`lo-queue-site`, line 4659) and `lo-lambda-fn` re-binds each one
with `lo-bind-row` from the environment record's field (line 4779). No lookup
change was needed; the close was simply on the wrong side of the drain. With
this placement `exec/closures` is 17 passed, 0 failed, and `exec/results` is
21/0.

## 4 What the pins cover

Four new fixtures under `src/logosc/fixtures/ir-lower`, all byte-identical to
Python and clang-clean (the gate builds both sides for every one):

| fixture | shape | before the fix |
|---|---|---|
| `strneq.logos` | `(println (!= "abc" "abd"))` and the equal case | E0002, not lowered |
| `shadow-param.logos` | `(fn keep ((b :i64)) …)`, then `(fn make-shade shade () (ret b))` | clang: `'%t1' defined with type 'i64' but expected '{ i32, [1 x i64] }'` |
| `shadow-let-variant.logos` | `(let b :i64 5)` in one function, `(ret b)` constructing the variant in the next | same clang error |
| `shadow-let-type.logos` | `(let point :i64 5)` in one function, `(make point 3 4)` in the next | passes **before and after** |

The fourth is the brief's "same with a `let` named after a struct type". It is
not a regression pin for this bug, and the report says so plainly: a struct
type name is resolved by `lo-type-arg`→`lo-parse-id` against the type tables,
never by `lo-atom-node-type`/`lo-lookup`, so a leaked binding named `point`
cannot shadow it. The fixture pins that namespace separation — the property
that makes `(make point …)` immune to a `let point` — rather than the change.
The `let`-shaped regression pin is `shadow-let-variant`, which does fail
without the close and is the same table as the enum case.

## 5 Corpus bookkeeping

- `tools/selfhost-ir.txt`: 86 → 90 paths (82 → 86 fixtures, four examples
  unchanged).
- `src/logosc/fixtures/ir-lower`: 82 → 86 files.
- `tools/selfhost.sh`: `IR_FLOOR` 86 → 90, `IR_FIXTURE_FLOOR` 82 → 86, with
  the two count comments.
- `tools/selfhost-manifest.txt`: regenerated from `git ls-files '*.logos'`,
  359 → 363.
- `src/logosc/lower.md`: the two counts it states (`IR_FLOOR`, fixture floor
  and the fixture path count) updated to the values above.

## 6 The gates

- `tools/pr_gate.sh` on `242f115`: **6/6 gates passed**, exit 0 (log:
  `build/w8last/pr_gate.log`; `PASS unit tests` is 1125 tests).
- The self-hosting phase: `selfhost: 363 files, 0 differences`,
  `ir: 90 files, 0 differences`, `resolve: 14 fixtures, 0 differences`,
  `check: 123 fixtures, 0 differences`, `unit: 2 files, 0 differences` — the
  four new fixtures are inside the 90 and agree byte for byte through the gate,
  not only in the hand comparison above.
- `fmt`: `src/logosc/lower.logos` and all four fixtures are a fixed point, and
  the gate's `git diff --exit-code -- '*.logos'` phase passed.
- `gen2 test tests`: 308/0/10, exit 0, under `ulimit -v 4000000`.
- Python `logos test tests`: 308/0/10, exit 0, same tree.
- `gen2 test tests` also passes inside the unit suite (`test_gen2_test`), which
  builds its own `build/test-gen2-test/gen2` from the same tree.
