# W8 — a `match` in a value position

Branch `feat/selfhost-w7-backend`, on top of `4aaf9f6` (the enum-in-struct fix).
Python is the oracle on the same tree, every time.

The one sentence: `lo-match` decided a `match` was a *statement* whenever its
caller passed no expected type, so a `match` lowered from a position that has no
type in hand — `lo-str-parts`'s `(println …)` operand, for one — lowered its arm
values as statements and refused a string literal with `E0002: a statement must
be a form`. Python types a `match` from the node's own record, never from the
caller's wish, and the port now resolves the same answer in two steps, exactly
as `lo-if` already did. A second half of the same bug sat one line further: the
guard asked whether a type id was above zero, and a type id of `0` is a real
type (`str`, in a unit whose first declaration is a `:str` function).

## 1 Where the port decides a form is a statement — and where Python does not

The port's statement walk is `lo-stmt` (`src/logosc/lower.logos:2401`). It owns
`let`/`letmut`, `set`, `ret`, `while`, `break`/`continue`; everything else falls
through to `(lo-value … node -2)` (`lower.logos:2445-2446`), where `-2` means "no
expected type". `lo-value` dispatches `match` to `lo-match`
(`lower.logos:1655-1657`) **carrying that `-2`**. In `lo-match` the type of the
whole match used to be read straight off that argument:

```
(let void :bool (or (< expected 0)
                    (lo-void? tags tnames expected)))
```

so "the caller passed no expected type" and "this match is void" were the same
answer, and `lo-arm` was called with `statement = true`
(`lower.logos:2684-2687`), lowering every arm body's last item through `lo-stmt`.

Python has one node for a `match` and lets the *type* decide. A `match` in
statement position reaches `match_expr` the same way any other statement does —
`statement()`'s final `self.value(node, node.path)` (`logos/lower.py:1861-1882`)
— and `match_expr` (`lower.py:4279`) opens with

```
ty = self.type_of(node)                                        # lower.py:4295
…
slot = None if _is_void(ty) else self.slot(ty, …)              # lower.py:4358
…
arm = self.arm_value(body, node.path, statement=slot is None)  # lower.py:4397
```

`self.type_of` (`lower.py:3924-3929`) is the checker's record for *this node*;
"the caller passed no expected type" does not exist as a concept there.
`arm_value` (`lower.py:4420-4441`) reads a body as statements only when the match
itself is void. Nor does Python meet the arms in a `phi`: it allocates one slot
before the tests, stores each arm's value into it and loads it once at the
`join` (`lower.py:4358`, `4399-4415`) — the `if_expr` docstring states why a
`phi` is not available (`lower.py:4228-4237`), since a branch may end in a
terminator and a `phi` naming an edge that never branches is invalid IR. The port
already lowered it this way; the missing piece was only which type the slot is.

`lo-if` in the port already resolved the two-step answer
(`lower.logos:2498-2505`): `expected` when there is one, else `lo-node-type …
node`, which for an `if` recurses into the branch. `lo-match` was the one form in
that family that did not.

## 2 The fix

Three statements in `lo-match`, mirroring `lo-if` (`lower.logos:2608-2613`):

```
(let mt :i64 (if (>= expected 0) expected
               (lo-match-type … node)))
(let ty :i64 (if (>= mt 0) mt expected))
(let void :bool (or (< ty 0)
                  (lo-void? tags tnames ty)))
```

`lo-match-type` (`lower.logos:3712`) is already the query `lo-node-type` answers
for a `match` with no context: the scrutinee's payload when an arm body is that
payload binding, the last item's type otherwise. `ty` is then used for the result
slot, every arm store and the final `load` (`lower.logos:2614`, `2691`, `2706`,
`2710`), and `void` is true only when that resolved type is void.

Both comparisons are `>= 0`, not `> 0`, and that is the second half of the bug.
A type id of zero is a real type: in a unit whose first declaration is a
`:str`-returning function, `str` *is* type `0`, and the first version of this fix
(`> mt 0`) still read such a match as void — the same "a legitimate id is not a
sentinel" class as the enum fix this branch opens with. `lo-if` had it right
(`< 0` for "no type"), which is why an `if` in the same position already worked.
It was `exec/match/match-arm-has-a-block-body` that caught the difference: its
`match` prints a `:str` and reaches `lo-match-type` with `0`.

The `-1` failure mode is preserved: if `lo-match-type` cannot name a type (an arm
ending in a `ret`, a `break`, or a `println`, whose void-ness the port's type
query does not spell), `ty` stays `-2` and the match lowers as the statement it
was — which is what the corpus's statement matches (`enum-pad`,
`match-arms-are-statements`, the `println` arms of `match-arms-are-statements`'s
`while` body) need.

No call site changed, and `lo-arm` still receives `expected`. Passing `-2` into
an arm value is also what Python does (`self.value(body[-1], where)`,
`lower.py:4441`), so that half of the call was already faithful.

## 3 Fixtures

Five new files under `src/logosc/fixtures/ir-lower/`, each in
`tools/selfhost-ir.txt` and `tools/selfhost-manifest.txt`, each byte-identical
to Python's `.ll` and clang-clean at `-O0` and `-O2` with `-Werror`:

| fixture | shape | result |
|---|---|---|
| `match-call-arg.logos` | a `:str` function declared first, then `(println (match 2 …))` with `:str` arms | prints `many`, `two` |
| `match-let-init.logos` | `(let v (match (low 4) …))` over an enum payload | exits 5 |
| `match-ret-operand.logos` | `(ret (match n …))` in an `:i64` function | exits 11 |
| `match-arith-operand.logos` | `(+ 5 (match 3 …))` | exits 6 |
| `match-arm-depths.logos` | arms that end in an `if`, in a literal, and in two `let`s and a name | exits 17 |

The first is the shape that failed before the change, and it carries the
`:str` function so `str` is type `0` — both halves of the fix are pinned by it
(the printer's no-expected-type call *and* the id). The fifth's arms end at three
different block depths (nested `if`/join, straight line, two-`let` straight
line), so agreement cannot come from an accidental ordering of the stores.
`IR_FLOOR` moves 70 → 75 and `IR_FIXTURE_FLOOR` 66 → 71 in `tools/selfhost.sh`;
the manifest lists 348 files.

## 4 What moved, measured

`gen2 test --only exec tests`, `--only mem tests`, and the whole suite, against
`/tmp/gen2-old-mx`, the same binary built from `4aaf9f6` before the change:

| | before | after |
|---|---|---|
| exec passed | 125 | **129** |
| exec failed | 14 | **10** |
| mem passed | 5 | **7** |
| mem failed | 2 | **0** |
| suite passed | 291 | **297** |
| suite failed | 17 | **11** |
| suite leaked | 10 | **10** |

The failing set moves by **exactly six entries, and nothing else**: the diff of
the two exec `FAIL` sets is 4 removed, 0 added, and the mem `FAIL` set loses its
only two.

```
exec/loops/fizzbuzz
exec/match/match-arm-has-a-block-body
exec/results/try-inside-a-loop
exec/results/try-inside-one-expression
mem/leak/array-elements
mem/leak/no-leak
```

The brief named four (`try-inside-one-expression`, `try-inside-a-loop`,
`no-leak`, `array-elements`). The other two carry the same `E0002` from the same
call, and neither needs more than the expression lowering:

- `exec/loops/fizzbuzz` is `(println (match (% i 3) (0 "fizz") …))` inside a
  `while` — a call argument exactly like the two `try-inside-*` cases.
- `exec/match/match-arm-has-a-block-body` is `(println (match 2 (2 (let x …)
  (if …)) …))`; once the match is a value its arm's `if` is a value too. This is
  the case the `> 0` first draft left behind, and it is why the counts are
  129/10/7/0/297/11 rather than the brief's 127/13/7 and 295.

The suite's only non-exec failure,
`regress/float-literal-compare/all-literal-comparisons-are-float`, still fails;
297 + 11 = 308 = the case count on both sides, so no case left the suite, and
`LEAKS 10` is unchanged.

## 5 The scope bug next door

Untouched, and this change neither helps nor hurts it. `enum-in-a-vector` is a
*name* query, not a type query: `lo-atom-value` finds the stale parameter binding
`b` in `bindn`/`binda` before it ever reaches a match, and the change adds no name
lookup and no scope push/pop. Its shape — `(vec-push v b)` in a test body whose
module has an earlier function parameter named `b` — is in none of the five
fixtures, and no new name is looked up anywhere in their lowering.

## 6 The gates

`bash tools/pr_gate.sh` — 6/6 (`make test`, `python3 -m logos test`,
`tools/accept.sh`, `guide --check`, `fmt`, `tools/selfhost.sh`), with
`tools/check_dco.sh` as the sign-off precondition. `fmt` is a fixed point on the
changed and new `.logos` files. The self-host gate builds gen2 from the tree and
compares the five new fixtures' IR to Python's byte for byte; the manifest lists
all 348 tracked `.logos` files.
