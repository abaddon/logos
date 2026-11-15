# W8 — the `cast` gap: float to integer, the id-`0` convention, and the literal that hid behind it

Branch `feat/selfhost-w7-backend`, on top of `5986eea`. The reference is
`logos/lower.py` (`cast_value`, `float_to_int`, `_float_text`, `_float_operand`);
Python is the oracle on the same tree, every time. `src/logosc/lower.logos` gains
`lo-float-to-int` and the three helpers it needs, `lo-float-text` becomes
`lo-float-value` plus two spellers so a literal's width can be honoured, and
every caller-expectation test in the file moves from `> 0` to `>= 0`.

The one sentence that matters: the port now lowers every cast shape Python's
lowerer accepts, and the five `tests/exec/cast.logos` cases that died on
`E0002: 'cast' is not lowered by this backend yet` all pass — together with
`exec/floats/f32-arithmetic`, which failed on the same literal rule the fifth
cast case needed.

## 1 What Python accepts — and what the corpus asks for

`cast_value` is reached only after the checker has accepted the form, and the
checker is the gate: `_cast` refuses anything that is not a numeric primitive at
either end (`check.py:2226-2258`), with `a cast needs a numeric type, found :str`
for the target and `cannot cast :str to :i64: a cast converts numbers` for the
operand. There is therefore **no cast to or between `:str`** — the shape the
brief wondered about does not exist; `cast_value`'s own two `cannot cast` arms
(`lower.py:4130-4133`) are unreachable from a checked program. Verified in the
port too: `gen2 check` prints both messages byte-identically to Python's.

What is left is six shapes, and the pair of widths decides the instruction
(`lower.py:4107-4158`):

| shape | instruction | corpus case(s) |
|---|---|---|
| int → narrower int | `trunc` (high bits gone) | `truncate-i64-to-i32` |
| int → wider int, signed source | `sext` | `widen-i32-to-i64` |
| int → wider int, unsigned source | `zext` | `widen-unsigned-zero-extends` |
| int → float | `sitofp`/`uitofp` by the source's sign | `int-to-float` |
| float → float | `fpext` to `:f64`, `fptrunc` to `:f32` | `f32-rounds-to-single` (line 1) |
| float → int | range test, then `fptosi`/`fptoui` | `float-to-int-in-range`, `float-to-int-large-in-range`, `float-to-int-out-of-range-panics`, `float-to-unsigned-out-of-range-panics`, and `f32-rounds-to-single` (line 2, `:f32`→`:i32`) |
| int → int, one width, two signs | nothing — the bits are the value | no corpus case |

The first four rows and the float↔float row were already lowered; the port's
`lo-cast` refused any float source with `E0002`, which is the whole of the
five-case gap.
Note that four of the five cases are the *same* shape — float to integer — and
the fifth reaches it through an `:f32` operand. No corpus case exercises the
same-width sign flip (the no-instruction row); the six fixtures below pin the
other rows directly.

## 2 `lo-float-to-int`

`lo-float-to-int` is `float_to_int` (`lower.py:4160-4179`) line for line:

```text
%t = fcmp oge <src> <value>, <low>       ; low  = 0.0 or -2^(w-1)
%t = fcmp olt <src> <value>, <high>      ; high = 2^w or 2^(w-1)
%t = and i1 %t, %t
br i1 %t, label %castN.ok, label %castN.bad
castN.bad:  call void @rt_panic(path, "R0003", "float out of range for :T")
            unreachable
castN.ok:   %t = fptosi|fptoui <src> <value> to <T>
```

The test is not politeness: `fptosi` outside its range is undefined. A NaN fails
both ordered comparisons and takes the panic, which is the only answer that does
not invent an integer. The two bounds are the powers of two in `_INT_RANGE_F`
(`lower.py:433-442`), computed by `lo-pow2` at the target's width, and spelled by
`lo-float-at` at the **source's** width — rounded to single when the operand is
an `:f32`, exactly Python's `_float_operand` (`lower.py:5205`). That rounding is
what makes the `:f32` case byte-identical: `0xC1E0000000000000`, not the double
that names a slightly different number.

## 3 The id-`0` convention, everywhere

`5986eea` fixed `lo-match` and recorded the rule: a type id of zero is a real
type, so an expectation test reads `>= 0`. `lo-if` and `lo-operand-type` (the
literal-typing test `lo-value` reaches) still read `> 0`, and so did six sibling
tests of the same shape: `lo-node-type`'s literal, `if` and `match` arms,
`lo-ctor-type`, the result and optional readers' `isres`/`isopt` guards, and
`args`/`read-dir`. All ten now read `>= 0`; leaving eight of them would have
left the same misreading reachable through `(some …)`, `(ok …)`, `(try …)`,
`(args)` and `(read-dir)` in a unit whose container type is id `0`.

The shape is pinned by `if-str-zero`: its first declaration returns `:str`, so
`str` is id `0`, and it lowers `(ret (if c "zero" (if …)))`. The honest limit of
that fixture is stated in §8 — it proves the branch runs and stays byte-identical
to Python, not that the old spelling produced different IR, because for a `:str`
expectation the fallback lands on `:str` again.

## 4 The decimal literal that could not hold its own mantissa

`float-to-int-large-in-range` names `-9223372036854775808.0` and
`9223372036854774784.0`. `lo-float-text` accumulated the significand in an
`:i64` and then divided by `10^frac`, so a 20-digit digit string — 19
significant digits plus the `.0` — wrapped and the literal became a different
number (`0x0` and `-1024.0`, which the case then printed). The accumulator is
now an `:u64`; the append is guarded by `mant < 2^64/10`, a dropped *integer*
digit adds one to `10^extra`, and a dropped *fractional* digit is not counted in
`frac`, so the exponent stays right when the mantissa is truncated. Both
boundary literals now spell `0xC3E0000000000000` and `0x43DFFFFFFFFFFFFF`,
Python's own.

This changes no other literal: every ≤18-digit significand takes the same path
as before, which is why the 78-fixture IR parity list is the evidence rather
than a reading of the code.

## 5 The `:f32` literal rule the fifth case needed

`f32-rounds-to-single` opens with `(let x :f32 0.1)`. The port spelled the
literal as the *double* `0x3FB999999999999A` and stored it into a `float`:
clang refuses it (`floating point constant invalid for type`), and even where it
compiled the value would be an `:f32` that never went through single rounding.
Python records the width each literal was checked at and rounds once at
`lower.py:5176`; the port has no literal-type record, so `lo-value` now asks the
expectation it was handed — the declared type at a `let`, the operand type at an
arithmetic or comparison — and uses `lo-float-text-single` when that type is
`:f32`. `lo-float-value` returns the double; `lo-float-text` and
`lo-float-text-single` are the two spellings.

**This is the one deviation from the brief's boundary.** The rule is the "f32
literals" task's subject, and fixing it here was unavoidable: without it the
fifth cast case cannot build, so `cast` could not be reported closed. It also
moves `exec/floats/f32-arithmetic` (same rule, same `store float` failure), so
the FAIL-set diff removes **six** cases, not five. §7 and §8 say what that does
to the counts, and the hunk is `lo-value`'s number branch — reverting it leaves
`f32-rounds-to-single` failing with the clang error above.

## 6 Fixtures

Seven new fixtures under `src/logosc/fixtures/ir-lower`, each byte-identical to
Python's `.ll` and clang-clean at `-O0` and `-O2` with `-Werror` (the gate's own
command: `clang -DLOGOS_DEBUG=1 -O<n> -target x86_64-unknown-linux-gnu … rt.c`):

| fixture | shape | what it pins |
|---|---|---|
| `cast-trunc` | `:i64`→`:i8`, printed through `:i64` | `trunc` then `sext`, the high bits gone |
| `cast-widen` | `:i8`→`:i64` (value −7) | `sext` carries the sign |
| `cast-int-float` | `:i64`→`:f64` | `sitofp` |
| `cast-float-int` | `:f64`→`:i64` (2.75) | the `fcmp`/`and`/`br` range test, then `fptosi` |
| `cast-zext` | `:u32`→`:i64` (4000000000) | `zext`, the source's sign choosing it |
| `cast-chain` | `:i64`→`:f64`→`:i64` in one expression | two conversions and a range test in one value |
| `if-str-zero` | first declaration returns `:str`, `if` as the returned value | the id-`0` expectation path |

`tools/selfhost-ir.txt` gains the seven paths, 209 → 216 lines; the floors move
with it (`IR_FLOOR` 75 → 82, `IR_FIXTURE_FLOOR` 71 → 78), and
`tools/selfhost-manifest.txt` is regenerated (348 → 355 files).

## 7 The run

All runs are on the working tree, from the repository root, under
`ulimit -v 4000000`, with `gen2` built from `src/logosc/*.logos
src/std/map.logos src/std/str.logos` by Python.

| run | before (`5986eea`) | after |
|---|---|---|
| `gen2 test tests/exec/cast.logos` | 4 passed, 5 failed | **9 passed, 0 failed** |
| `gen2 test tests` | 297 passed, 11 failed, 10 leaked | **303 passed, 5 failed, 10 leaked** |
| Python `gen2`-equivalent (`logos test tests`) | 308 passed, 0 failed, 10 leaked | unchanged |

The FAIL-set diff: **6 removed, 0 added.**

```text
removed (5 + the :f32 literal rule)
  exec/cast/float-to-int-in-range
  exec/cast/float-to-int-large-in-range
  exec/cast/float-to-int-out-of-range-panics
  exec/cast/float-to-unsigned-out-of-range-panics
  exec/cast/f32-rounds-to-single
  exec/floats/f32-arithmetic          <- §5, not a cast case
remaining (untouched, other tasks)
  exec/floats/division-by-zero-is-not-a-panic
  exec/results/enum-in-a-vector
  exec/strings/equality
  exec/strings/formats-floats
  regress/float-literal-compare/all-literal-comparisons-are-float
```

The brief's arithmetic was `297 + 5 = 302/6`; the actual result is `303/5`
because one of the five cast cases could not pass without the shared `:f32`
literal rule and that rule fixes one more case. `removed exactly those 5` is met
as `those 5 and no other cast or f32 case beyond the rule's own`, and `adds
none` is met exactly.

## 8 Evidence and concerns

- **`bash tools/pr_gate.sh` — 6/6, exit 0.** The self-hosting gate's own
  summaries: `selfhost: 355 files, 0 differences` (the manifest, byte for byte),
  `ir: 82 files, 0 differences` (every fixture and the four example programs,
  including the seven new ones), `resolve: 14`, `check: 123`, `unit: 2`, all
  zero differences. The log is `build/w8cast/prgate2.log`, not committed.
- **Concern: 303/5, not 302/6.** Explained in §5 and §7. If the parallel
  f32-literal task runs, it will find `floats/f32-arithmetic` already green; my
  hunk in `lo-value`'s number branch is the overlap and is small.
- **Concern: the `if-str-zero` fixture is latent by construction.** With `:str`
  as id `0`, the old `> 0` test fell back to `lo-node-type` on the same `if`,
  which answers `:str` from the arm and therefore the same id — so the fixture's
  IR does not change if the test is reverted. It pins the shape and the branch,
  not a visible difference. The shape where the misreading *is* visible is a
  narrow integer id `0` (`(let x :u8 (if c 1 2))` with a first declaration
  returning `:u8`), where the fallback answers `:i64`; that unit is not in the
  corpus and was not added, because the brief named the `:str` shape.
- **Concern: the literal parser still truncates past 19 significant digits.**
  It truncates the *mantissa* rather than wrapping, and keeps the exponent, but
  it is not correctly-rounded beyond what a `u64` holds; `float(text)` in Python
  is. No corpus literal is that long.
- **The two `if`s in the digit loop repeat the digit test.** Logos `if` takes
  exactly one then and one else, so a shared `let` could not be hoisted into a
  multi-form branch; the duplication is the price of the language's arity rule,
  not an oversight.
- The remaining five failures are untouched: `!=` on `:str`,
  `enum-in-a-vector`, `strings/formats-floats`, `float-literal-compare` and
  `division-by-zero-is-not-a-panic` (which is the same integer-compare-over-two-
  float-literals defect as `float-literal-compare`, seen through `(= (/ 0.0 0.0)
  (/ 0.0 0.0))`).
