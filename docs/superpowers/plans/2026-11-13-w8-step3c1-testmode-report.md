# W8 step 3c-1 — `build --test NAME`, `$fnvalue`, and the checker's test branch

Branch `feat/selfhost-w7-backend`, parent commit `2bc8382` (W8 capture-fix
report). This step makes the port lower a single `(test …)` body as a program,
which is what the harness needs before a `gen3 test` can exist. It also records
an attempted fourth piece — the checker's `test` branch — that was **reverted**,
because fixing its mis-walked body exposed two older checker defects that make
`gen2 build --test` refuse the flag's own flagship fixture.

## What landed

- **Test mode.** `gen2 build --test NAME file` lowers one test body as `main`.
  `main.logos` parses the flag into `tnames` (last value wins), skips the
  required-`main` rule (`main-check-main`), names the IR
  `build/<stem>.<sanitized>.ll` (`main-sanitize`: `/` and `\` to `_`), and links
  with `-DLOGOS_DEBUG=1` **first** in the clang argv, which is
  `driver._link`'s order.
- **The lowering's side.** The name rides in `tname` and in `cl[2]`/`cl[3]`.
  A test build skips the module's `main`, runs `lo-test-sweep` over *every*
  test body of the module so the generic copies only tests reach are
  discovered, and defers module 0's `lo-inst-drain` to the entry pass.
  `lo-test-entry` refills module 0, finds the named test (`lo-test-find`,
  `E0002: no test named '…'`), sets `cl[1]` to the module for symbol
  qualification, drains, builds `lo-test-main`, drains sites, and rotates the
  entry row to the end of the function table.
- **Two-pass entry body.** `lo-test-main` opens `main` as `i32`, lowers the
  body once to plan slots, emits the plan's allocas, then lowers it for real —
  the closure path's shape. The body starts at `(lo-child nod ntx test 2)`,
  path index 2 = the first statement after the `test` head and the name, and
  the walk runs to the end of the sibling chain.
- **Debug leak report on both exits.** `lo-leak-report` is gated on
  `cl[3] = "1"`, declares `rt_leak_report` and calls it. `lo-ret-main` calls it
  before the `ret` that returns the status; `lo-fn-finish` calls it on the
  fall-off-the-end path (`st[5] == 1`) and returns `0` there.
- **`$fnvalue`.** An atom that is not a literal, a binding or a variant, and
  that `lo-fn-id` resolves, is a *function value*: `lo-fnvalue` looks the
  target's symbol up in `cl` from index 4 in `(target, wrapper)` pairs
  (`lo-fnv-find`), and on a miss `lo-fnvalue-new` gensyms `$fnvalue$N` from the
  unit-wide counter, spells `lg.<module>.<$fnvalue$N>`, queues a kind-2 site
  carrying the target's signature in `st[12]`, and emits `faddr`. At drain time
  `lo-fnvalue-fn` emits `define R @…$fnvalue$N (i8* %env, T…)`, binds
  parameters through `lo-fnvalue-param` in the two-phase shape, loads each
  argument (`lo-fnvalue-load`), calls the definition, and returns. A function
  pointer and a closure therefore share the `(i8*, T…)` ABI.
- **Two pre-existing gaps closed alongside.** `lo-atom-node-type` answers a
  definition's stored signature for an atom naming it (previously `-1`, so a
  named function value had no type), and `lo-node-type` answers a *generic*
  call's instantiated result instead of the generic's variable.

## Verification

- **`tests/exec/closures.logos`: 17 of 17 tests byte-identical** to Python's
  `driver.run_test` IR, comparing `gen2 build --test NAME` against
  `run_test(file, NAME)` one pair of `.ll` files per test. This includes the
  two shapes the step exists for — `named-function-value` (`$fnvalue`) — and
  the nine monomorphised copies that only `(test …)` bodies reach.
  Command: `python3 tools/test_ir_parity.py tests/exec/closures.logos`
  → `test-ir: 17 tests, 0 differences`.
- Wider lowering parity, measured on the previous step's tree and unchanged
  here: `tests/exec` 104 of 138 identical, every miss a lowering gap that also
  fails in a plain `main` build (21 × `R0003` in `lo-reaches` for a struct
  holding an enum by value, 5 × `'cast' is not lowered`, 2 × `a statement must
  be a form` for `match`-in-`while`, 1 × `'!='`, 2 × f32 literal as a double,
  2 × nested-`vec` element size, 1 × float literal 1 ULP).
- `python3 -m logos fmt src/logosc/*.logos` is a fixed point on the two files
  this step touched.
- `bash tools/pr_gate.sh`: **6/6** gates, and `tools/selfhost.sh` prints
  `selfhost: …, 0 differences`, `ir: 65 files, 0`, `resolve: 14, 0`,
  `check: 122, 0`, `unit: 2 files, 0`.

## The checker's `test` branch: found, fixed, reverted

The branch existed half-landed in the tree: `check-module-tests`, a fifth
`bctl` flag (`bctl[4] == 1` = "this walk is a test body"), the directive and
`fn` skips in `body-walk`, and `check-body-test`. It compiled and it was wrong:
a valid test body was refused with a false `E0005`.

**The defect, exactly.** `check-body-test` started the body walk at
`(check-child nodes c 2)` — path index 2. It should be index 0. A node's
`first` is already past the head *and* the name (`tree-child-start`), so a
`test` node's child chain is its statements: index 0 is the first one. Index 2
is the third, and a body with fewer than three statements was not walked at
all. Reproduced before any change:

```sh
gen2 check /tmp/t3.logos          # (let x :i64 5) (expect true) (println x) (expect …)
t3/test/seven/2: E0005: unknown name 'x'    # wrong: Python ACCEPTS
```

and after the one-line change (`check-child nodes c 2` → `0`) both sides agree:
the valid file is accepted and a fixture with a type error in a test body prints
Python's exact line.

**Two fixtures were built and proven, then not committed** (they would fail the
gate without the branch): `tests/type/test-body-type.logos` holds a *valid*
`binds` test (a `let`, a `letmut`, a `set`, a `println`, an `expect`, i.e. the
binding must be seen by later statements) and a `wrong-type` test whose third
statement is `(let y :str x)`. Python's verdict:
`test-body-type/test/wrong-type/2: E0100: let 'y' has type :str, found :i64`.
On the pre-fix branch gen2 printed
`test-body-type/test/binds/2: E0005: unknown name 'y'` — the wrong test,
the wrong statement, the wrong code. With the branch on and the one-line fix,
all 123 listed check fixtures passed, and a sweep of 193 corpus files showed
exactly two disagreements with Python.

**Why the branch still could not land.** Both remaining disagreements are
pre-existing checker defects that the branch merely made reachable, and both
reproduce in a plain `main` body, independent of tests:

- A generic call's result type is `?` in any body. `(println (str-len (id
  "abc")))` in a `main` prints `E0401: 'str-len' takes a :str, found ?`; Python
  accepts. This is what `tests/exec/closures.logos`'s `two-instantiations`
  test hits.
- A `match` arm's payload name is not bound: `(match e ((bad-digit n) (println
  n)) …)` prints `E0005: unknown name 'n'` in a `main`; Python accepts. This is
  `tests/exec/results.logos`'s `enum-payload-less`.

Because `gen2 build --test` runs the checker before the lowering, a test branch
that exposes those two gaps makes `build --test tests/exec/closures.logos` fail
at the first test — i.e. it destroys this step's own 17/17 evidence and turns
two accepted corpus files into refusals. A missing check is a known gap; a check
that refuses valid programs is a regression, so **all four checker edits were
reverted** (`src/logosc/check.logos` is byte-identical to `2bc8382`), and the
`tools/selfhost-check.txt` entry, the `CHECK_FLOOR` bump and the three fixture
files went with them.

For the next attempt, in order:

1. Bind a `match` arm's payload name (`body-arm-run`/`body-match`): needed for
   `results.logos`, and it is a `main`-visible bug on its own.
2. Answer a generic call's instantiated result type in the body walk: needed for
   `closures.logos`, `generics/*`, and anything that monomorphises in a body.
3. Re-apply `check-body-test` with `check-child nodes c 0`, then the two
   fixtures above as the pin, then re-measure the sweep.

## What still does not lower

`!=`, `<`, `<=`, `>` and `>=` on `:str`, refused with
`E0002: '<head>' is not lowered by this backend yet`.

`lo-test-main` and `lo-test-entry` are measured only through
`tests/exec/closures.logos`. The rest of the positive corpus (`tests/exec`,
`tests/thread`, `tests/regress`) has not been run through `build --test`; the
`tests/exec` numbers above are lowering parity from the previous step, not test
mode.

## Reproduce

```sh
python3 -m logos build src/logosc/*.logos src/std/map.logos src/std/str.logos \
  -o build/selfhost/gen2

# 17/17: gen2 build --test NAME vs Python's run_test, per test.
python3 tools/test_ir_parity.py tests/exec/closures.logos  # -> 0 differences

bash tools/selfhost.sh
bash tools/pr_gate.sh
```

`tools/test_ir_parity.py` reads the `(test …)` names out of the file, runs
`gen2 build <file> --test <name> -o …` and `driver.run_test(<file>, <name>, …)`,
moves both `build/<stem>.<name>.ll` files under `build/test-ir/` and compares
them byte for byte. A build that fails, or an IR file that is not written, is a
difference like any other.
