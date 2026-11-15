# W8 — the float family: a comparison's operand type, the division that took the integer path, and the literal parser that was not correctly rounded

Branch `feat/selfhost-w7-backend`, on top of `f4dd161`. The reference is
`logos/lower.py` (`operand_type`, `_float_text`) and `logos/check.py::_number`;
Python is the oracle on the same tree, every time. Three cases move from the
FAIL set to PASS, `gen2 test tests` goes from **303/5/10** to **306/2/10**, and
the two survivors (`enum-in-a-vector`, `strings/equality`) are untouched.

The one sentence that matters: a float literal's comparison operand was typed
`:i64` because the function that decides the type asked an accessor that only
answers for an *atom*, so it read the empty string and never saw a `.`; the same
default reached arithmetic, which is the whole of the division-by-zero case; and
the literal parser was replaced with the correctly-rounded conversion, so
`1e+300` is now the double Python's `float()` produces rather than one built by
repeated multiplication.

## 1 Three symptoms, two defects

| case | symptom | defect |
|---|---|---|
| `regress/float-literal-compare` | `icmp slt i64 0x3FF8…` — clang: *floating point constant invalid for type* | §2 |
| `exec/floats/division-by-zero-is-not-a-panic` | `sdiv i64 0x3FF0…, 0x0` — the integer divide guard, not `fdiv` | §2 (same default, arithmetic side) |
| `exec/strings/formats-floats` | `1e+300` prints `1.0000000000000002e+300` | §4 |

The first two are one bug seen from two callers. The third is the parser.

## 2 `lo-operand-type` read a number's text through `lo-atom`

`lo-operand-type` is the port's `operand_type`: the operand type of a
comparison, and (through `lo-node-type`'s arithmetic branch) of `+ - * / %`,
is `self.type_of` for a node, the binding's type for an atom, and for a bare
number the literal's own default — `:f64` if any operand is written with a `.`
or an exponent, `:i64` otherwise.

The port tested each number with

```text
(if (lo-float-lit? (lo-atom nod ntx c)) …)
```

and `lo-atom` answers `""` for anything that is not a token of kind atom:

```text
(fn lo-atom :str ((nod …) (ntx …) (id :i64))
  (ret (if (lo-atom? nod id)
         (vec-get ntx (get (vec-get nod id) text)) "")))
```

`lo-atom?` is `(= tok 2)`, and a number's `tok` is `4`. So `lo-float-lit?` was
handed the empty string at every number operand, `isfloat` stayed `false`, and
the answer was the integer default — even for `1.5`. `lo-compare` then took the
`icmp` path with an `:i64` type and `lo-value` spelled each operand as the
literal it is, which is how a hexadecimal *double* landed in an integer
constant slot: `icmp slt i64 0x3FF8000000000000, 0x4000000000000000`.
`lo-arith` consults the same type through `lo-node-type`, so `(/ 1.0 0.0)`
became an `sdiv` and went through the integer divide guard — `icmp eq i64
%x, 0`, `icmp eq i64 -9223372036854775808, -1` — before the division itself.
That whole preamble is what the division-by-zero case was failing on.

The fix is the accessor the rest of the file already uses. `lo-lit-text` reads
the `text` field of any token, by kind:

```text
(if (lo-float-lit? (lo-lit-text nod ntx c)) …)
```

Two other sites (`lo-node-type`'s literal branch, `lo-value`'s) already spelled
it that way; `lo-operand-type` was the only reader that went through `lo-atom`.
One identifier, and both cases move.

`+`/`*` over two float literals had the same wrong type and no corpus case that
notices; it is fixed by the same line, not by a second one.

## 3 What the division-by-zero case is not

There is no rewrite of division in it. `fdiv` with a zero divisor is IEEE and
the port already emits it; `arith` refuses `%` on floats and checks nothing
else. The fixture's failing IR (`sdiv i64 0x3FF0000000000000, 0x0000000000000000`)
is the integer path, which exists only because the type was `:i64`. Its
expectation — `inf`, `-inf`, `ne`, `ge` — is the IEEE answer, and the port now
prints it:

```text
(- (/ 0.0 0.0) (/ 0.0 0.0))   ; NaN = NaN is false  -> "ne"
(< (/ 0.0 0.0) 1.0)           ; ordered compare is false on NaN -> "ge"
```

## 4 The literal parser: correctly rounded, by asking

`logos/lower.py::_float_text` is `float(text)` and then the bits of that double
(`_hex_float`). `float()` is correctly rounded: for the text `1e300` the
nearest double is `0x7E37E43C8800759C`, and `repr` of it is `1e+300`.

The port accumulated the significand in a `:u64` — nineteen significant digits,
the most that fits — and scaled it by a power of ten built by *repeated
multiplication*:

```text
(fn lo-pow10 :f64 ((n :i64))
  (letmut v :f64 1.0) … (set v (* v 10.0)) …)
```

Two independent inexactnesses. The mantissa was truncated past nineteen digits,
and `10^300` built by three hundred roundings is not the double nearest
`10^300`: it is one ulp high, `0x7E37E43C8800759D`, which prints as
`1.0000000000000002e+300`. Note the exponent is *not* the usual suspect here —
`1e300` has one significant digit, so nothing was truncated for this case; the
power of ten was the defect.

Matching Python for every text needs a correctly-rounded decimal→binary
conversion: the mantissa can be any number of digits and the exponent any
value, so the exact value is a rational whose numerator does not fit in any
integer type the language has. Eisel–Lemire and the big-integer fallback are
exactly what "arbitrary precision the language lacks" means.

So the port asks the conversion instead of re-deriving it:

```c
double rt_parse_f64(const unsigned char *p, size_t n);   /* rt.c */
```

which copies the bytes to a NUL-terminated buffer and calls `strtod`. That is
the same correctly-rounded conversion CPython's `float()` implements, so the
answer is Python's bit for bit rather than one ulp away; the runtime already
trusts `strtod` the other way round, in `rt_format_f64`'s shortest-repr loop.
`lo-float-value` is now one line — `(ret (rt_parse_f64 s))` — and `lo-pow10`
and the accumulator are gone. There is no nineteen-digit limit left to state:
the limit that remains is that the compiler now depends on libc for this
conversion, which it already does for I/O, allocation and the printer.

The two spellings that round once are unchanged: `lo-float-text` takes the
double's bits, `lo-float-text-single` rounds through `:f32` first, exactly
`_hex_float` and `_single`.

A battery of extremes lowers byte-identically too — `0.1`, `1e-7`, a
thirty-digit integer-part literal, `1.7976931348623157e308` (the largest
finite double), `4.9406564584124654e-324` (the smallest subnormal),
`-0.0` (`0x8000000000000000`), `0.30000000000000004`,
`2.2250738585072014e-308` (the smallest normal) and `9007199254740993.0`
(2^53+1, which rounds to 2^53). Every `store double` line is equal, which is
the evidence that the new path is the same conversion rather than one that
happens to pass the corpus.

## 5 Fixtures

Four under `src/logosc/fixtures/ir-lower`, each byte-identical to Python's `.ll`
and clang-clean at `-O0` and `-O2` with `-Werror` (the gate's own command):

| fixture | shape | what it pins |
|---|---|---|
| `float-cmp-int` | `(< 1.5 2.0)`, `(= 2 2)`, `(< -1.5 -2.0)` | a float literal pair and an int literal pair each take their own type — `fcmp olt double` / `icmp eq i64` |
| `float-long-literal` | `15084.91740094170017982833087444305419921875`, `1e300` | a 44-digit literal and a three-hundred-exponent one; the old parser gave `0x40CD76756D64E0F7` and `0x7E37E43C8800759D`, Python and the port now give `…F6` and `…9C` |
| `float-div-zero` | `(/ 1.0 0.0)`, `(/ -1.0 0.0)`, `(/ 0.0 0.0)` | `fdiv` where the integer path would have been `sdiv` + the divide guard |
| `float-cmp-f32` | `(let x :f32 0.1)` then `(< x 0.2)`, `(= x 0.1)` | the operand is the variable's `:f32`, and each literal is rounded once to single (`0x3FC99999A0000000`) |

`tools/selfhost-ir.txt` gains the four paths, 216 → 220 lines; the floors move
with it (`IR_FLOOR` 82 → 86, `IR_FIXTURE_FLOOR` 78 → 82), and
`tools/selfhost-manifest.txt` is regenerated (355 → 359 files).

The brief asked for "a float literal compared against an int literal". That
program does not exist: the checker types a number literal standing alone as
`:i64`, and `_number` gives an *integer* literal a width only from an integer
expectation, so `(< 1.5 2)` and `(= 2 2.0)` are `E0100 cannot compare :i64 with
:f64` in both implementations, and `(let x :f64 1)` is `E0100 let 'x' has type
:f64, found :i64`. The fixture pins the shape that does exist — a comparison
whose operands are all literals, one all-float and one all-int — which is the
shape the defect was in.

## 6 The run

| run | before (`f4dd161`) | after |
|---|---|---|
| `gen2 test tests` | 303 passed, 5 failed, 10 leaked | **306 passed, 2 failed, 10 leaked** |
| Python (`python3 -m logos test tests`) | 308 passed, 0 failed, 10 leaked | unchanged |

The FAIL-set diff: **3 removed, 0 added.**

```text
removed
  exec/floats/division-by-zero-is-not-a-panic
  exec/strings/formats-floats
  regress/float-literal-compare/all-literal-comparisons-are-float
remaining (the last task's, untouched)
  exec/results/enum-in-a-vector
  exec/strings/equality
```

## 7 Gate

`bash tools/pr_gate.sh` — 6/6, exit 0 (log `build/w8floats/prgate.log`, not
committed). The self-hosting gate's summaries: `selfhost: 359 files, 0
differences`, `ir: 86 files, 0 differences`, `resolve: 14`, `check: 123`,
`unit: 2`, all zero differences.

## 8 Concerns

- **The compiler now depends on libc for literal parsing.** `rt_parse_f64` is
  the only path from text to a double, and it is `strtod`. Both ends are
  correctly rounded, so Python and the port agree on every finite literal; the
  cost is that a platform whose `strtod` is not correctly rounded would move
  the port's bits away from Python's. glibc's is, and the runtime already
  round-trips through it in the printer.
- **Non-finite literals still diverge, unchanged.** Python's `_float_text`
  raises `LITERAL_RANGE` (`float literal '1e400' is not a finite :f64`); the
  port has no such check and emits the bits of `inf`, before this change and
  after it. Adding it needs `berr`/`where` threaded into `lo-literal`, which is
  a different task and no corpus case asks for it.
- **A `:f32` literal that overflows single precision** is spelled by
  `fptrunc`, which is poison out of range in LLVM; Python raises
  `OverflowError` and spells `inf`. No corpus case reaches it. Untouched.
- **`0x7FF0000000000000`-style NaN text**: `strtod("nan")` would parse, but the
  lexer never hands over a non-numeric token as a number, and `rt_parse_f64`
  rejects anything `strtod` did not consume whole (`end` must reach the
  terminator), so a trailing `e` or a stray byte cannot become a number.
- **The mixed-literal comparison cannot be a fixture** — see §5. The nearest
  legal shape is pinned, and the diagnostic is the checker's, not the
  backend's.
