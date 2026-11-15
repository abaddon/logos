# W7 cutover gaps — what `gen2 build src/logosc/*.logos` still needs

Measured at `af01ed8` (branch `feat/selfhost-w7-backend`), 2026-11-13. Every
number below comes from a command in "Reproduce"; the `.ll` files are under
`build/` (git-ignored) and `/root/.hermes/cache/scratch/gaps/`. No source file
was changed.

The goal measured: `gen2 build src/logosc/*.logos` must emit the same `.ll` as
`python3 -m logos build src/logosc/*.logos`, so a gen3 can be built from that
text and compared with gen2.

## 1. What the run says

`./build/selfhost/gen2 build <file> -o <out>` for each of the 18 modules, and
the whole glob at once:

| module | rc | first refusal |
|---|---|---|
| `body_test.logos` | 2 | `body-test/show-check-fail/2/0: E0103: imported functions are not lowered yet: 'check-code'` |
| `check.logos` | 2 | `check/check-code/2/0: E0103: imported functions are not lowered yet: 'type-code'` |
| `check_test.logos` | 2 | `check-test/show-check-fail/2/0: E0103: … 'check-code'` |
| `emit.logos` | 2 | `emit/emit-needs-type/2/0/0/1: E0103: … 'ir-op-gaddr'` |
| `emit_test.logos` | 2 | `emit-test/t-case-empty/61: E0103: … 'ir-module'` |
| `fmt.logos` | 2 | `fmt/0: E0103: imported modules are not lowered yet` |
| `fmt_test.logos` | 2 | `fmt-test/fmt-arena/2/2: E0103: … 'tree-parse'` |
| `ir.logos` | **0** | none — but 9 instructions differ from Python and clang rejects the file |
| `lex.logos` | 2 | `lex/lex-skip/2/0/0: E0100: a comparison needs numbers` |
| `lex_test.logos` | 2 | `lex-test/dump/6/2: E0103: … 'lex'` |
| `lower.logos` | 2 | `lower/lower-code/2/0: E0103: … 'type-code'` |
| `main.logos` | 2 | `main/main-resolve-diag/4/0: E0103: … 'resolve-code'` |
| `resolve.logos` | 2 | `resolve/resolve-mod-find/2/0: E0103: … 'map-get'` |
| `resolve_test.logos` | 2 | `resolve-test/show-fail/2/0: E0103: … 'resolve-code'` |
| `tree.logos` | 2 | `tree/tree-next-id/2: E0100: get needs a struct` |
| `tree_test.logos` | 2 | `tree-test/show-path/2/2: E0103: … 'tree-path'` |
| `types.logos` | 2 | `types/type-fail-here/2/0/1: E0103: … 'tree-path'` |
| `types_test.logos` | 2 | `types-test/t-diag/2/0/0: E0103: … 'type-code'` |
| **whole set** | 2 | the usage block — `build` takes exactly one file |

Grouped by cause: 17 of 18 modules fail for one of B, C or D, and the
whole-set command is blocked separately by A:

- **A — the CLI is single-file (blocks the whole set, and any multi-root
  build).** `main-args` accepts three arguments for `fmt|resolve|check` and
  exactly five for `build` (`src/logosc/main.logos:507-521`); anything else is
  the usage block. Python's `build` takes `nargs="+"` (`logos/cli.py:66-72`).
- **B — the checker refuses a callee declared in another module (14 modules).**
  `body-call` finds the entry and then, when its `owner` is not the module
  being checked, fails E0103 `imported functions are not lowered yet`
  (`src/logosc/check.logos:6236-6246`). This is a deliberate W7 stop, not a
  typing hole: the entry it just found carries the callee's `ty` (the
  `check-entry` field at `check.logos:17`), and the owner rules are written but
  unused
  (`check-visible-owner` at `check.logos:2210`, `check-in-build` at
  `check.logos:2224`; `check-file` already takes the whole `mods` list,
  `check.logos:2079`).
- **C — the lowerer refuses the `(use …)` form itself (1 module, `fmt`).**
  `lo-scan-sigs` fails E0103 `imported modules are not lowered yet` at every
  `use` node (`src/logosc/lower.logos:891`), before it ever looks at a call.
  `fmt` has **zero** cross-module call sites (the counts in §2), so it is
  refused for the import form alone.
- **D — `(vec-get …)` on a `(ref (vec T))` is typed as the vector (2 E0100s
  plus the 9-line divergence in `ir`).** `lo-node-type`'s `vec-get` branch
  takes the element of the operand's type as written
  (`src/logosc/lower.logos:1186`); Python peels the `Ref` first
  (`logos/lower.py:2782-2784`, `vector()`). So `(< (vec-get st 0) n)` with
  `st :(ref (vec :i64))` (`src/logosc/lex.logos:52-55`) is "a comparison needs
  numbers", and `(get (vec-get nodes id) next)` with
  `nodes :(ref (vec node))` (`src/logosc/tree.logos:44-45`) is "get needs a
  struct". **This is not an import error**; it survives every multi-module fix.
  The same bug is why the one module that does build is wrong: `ir.ll` has nine
  `add { i64*, i64, i64 }` instructions where Python has `add i64` (first at
  `src/logosc/ir.logos:248-250`, `ir-block-past`), and clang refuses the file:
  `ir.ll:3166:33: error: '%t11' defined with type 'i64' but expected
  '{ i64*, i64, i64 }'`.

`fmt.logos` shows the two gates are independent: it passes the checker and is
stopped by C; the other 14 are stopped by B before the lowerer runs.

## 2. Multi-module: what Python does, and what it costs the port

**One build set, one translation unit.** `load_program` parses every path and
resolves them as one set (`logos/driver.py:100-113`); `reachable` returns the
roots in argument order followed by each root's imports depth-first, one entry
per module name (`logos/resolve.py:163-189`); `build_program` checks that set
and lowers it once (`driver.py:140-174`, the `main` requirement at 168-169).
`lower_program` lowers every checked module into the *same* `IrModule`, in that
order, with one string table and one generated-name counter
(`logos/lower.py:823-848`). Imports are therefore **not** separate modules:
nineteen modules become one `.ll`.

**What `mqual` controls.** Python has no `mqual`; the equivalent is
`_Lower._qualify = len(self._unit) > 1` (`lower.py:966`), where `_unit` is the
set of module names sharing the object file (`lower.py:961`). It controls
**type spellings only**:

- a struct or enum is spelled `%struct.<module>.<name>` when the unit has more
  than one module, and the bare name when it has one
  (`type_name`, `lower.py:1120-1139`); that is why the unit `.ll` says
  `%struct.check.check-error` and `%struct.tree.node`, and why a one-module
  unit keeps the bare `%struct.ir-error` (`ir.ll:4`, gen2's own output);
- function symbols do **not** depend on it: every non-`main` function is
  `internal @lg.<module>.<name>` and `main` keeps its name
  (`_Lower.symbol`, `lower.py:1107-1118`);
- the emitter is oblivious to module identity: it prints `%struct.` + the
  arena's name and `@` + `fn.symbol` (`logos/llvm.py:272-279`, `347-386`), so
  qualification must be done at lowering, not at emit; struct layouts are
  registered by the *spelled* name and reset once per unit
  (`llvm.py:282-291`).

**What the port has.** `lower-build` is one module, full stop: it takes one
`nod`/`ntx` and scans that root's `type`, `fn` and `extern` forms into its own
tables (`src/logosc/lower.logos:4612`, `4690-4707`), and it opens the module
with `mqual = false` (`lower.logos:4694` → `ir.logos:175-177`). `mqual` is a
dead flag: it is pushed into a one-element vector and threaded through the
pass (489 occurrences, 261 `lo-*` functions out of 266) but never read — the
only other uses are the parameter lists in `emit.logos:760` and `:831`, whose
bodies never read it either. Type rows already have an owner column, `powner`,
but it is written empty (`lower.logos:709`, `type-struct … name ""`), and
type lookup is the current module's `tnk`/`tnv` map only (`lower.logos:508`,
`668-690`), so an imported type name cannot resolve.

**Which `.ll` structure results.** Python's `build src/logosc/*.logos` (all 18
roots, 19 modules with `map`; 36.99 s) wrote `build/body_test.ll`:

- 17,229,018 bytes, 273,304 lines;
- 1,227 `define`s, 18 `declare`s, 13 `%struct` rows, 4,347 `@.strN` globals;
- 19 module prefixes in `@lg.<module>.<name>`;
- header order is triple, struct rows, globals, declares, then functions in
  module order (`llvm.py:347-367`), which is why `body-test`'s functions come
  first — the roots are lowered in argv order.

**Cost.** 17 of 18 modules are blocked (§1); the sources hold 1,161
cross-module call sites (below), and the unit is 19 modules. The lowerer has no
module concept to stretch: every `lo-*` function carries the 63-vector arena,
so threading one more per-module value repeats the `mqual` surgery (489 sites).
The cheap route is the one Python takes — one shared arena, and per-module
`enter`/`prepare` that swap the symbol/extern/type maps and re-spell types at
creation (`lower.py:1008-1070`) — which needs a three-pass restructure of
`lower-build` (types for every module, then signatures, then bodies) rather
than 261 signature changes.

Cross-module call sites per module (nodes whose head names a function declared
in another module of the set): `emit-test` 457, `check` 285, `lower` 139,
`types-test` 105, `emit` 41, `check-test` 40, `main` 27, `body-test` 23,
`resolve` 20, `resolve-test` 7, `tree-test` 7, `fmt-test` 5, `lex-test` 4,
`types` 1; `fmt`, `ir`, `lex`, `tree`, `map`, `str` 0. Total 1,161.

## 3. Forms the port refuses that its own sources use

Counts are per module over `src/logosc/*.logos`; "code" excludes occurrences
inside string literals (`body_test.logos` uses `dump-src "…"` to hold test
input as data — `body_test.logos:1451-1961` are strings, not forms).

| form | modules | count | where |
|---|---|---|---|
| `(use …)` imports | 15 of 18 | 50 | 8 in `main.logos`, 6 in `lower.logos`, … (`ir`, `lex`, `tree` are import-free) |
| `(run …)` / `(run-status …)` | 1 | 2 | `resolve.logos:95-96` |
| `(read-file …)` | 6 files, 7 sites | 7 | `check.logos:1629`, `main.logos:143,470`, `resolve.logos:358`, `check_test.logos:89`, `emit_test.logos:59`, `resolve_test.logos:59` |
| `(args)` | 1 | 1 | `main.logos:524` |
| `spawn` in a non-`main` function | 0 | 0 | only inside `body_test`'s `dump-src` strings |
| `$lambda` / `$fnvalue` / `(fn :T …)` closure | 0 | 0 | none; the only `(fn :` text in the tree is inside `fmt_test.logos:124-127` strings and `check_test.logos:158` |
| `join` / `chan` / `send` / `recv` / `mutex` / `lock` / `unlock` | 0 | 0 | `lower.logos:2251` is a parameter named `join` |
| `(some …)` / `(none)` / `(ok …)` / `(err …)` / `(try …)` | 0 | 0 | `types.logos:108` has parameters named `ok` and `err`; no result is constructed |
| `!=` on anything | 0 | 0 | no `(!= ` in the tree |
| `<`, `<=`, `>`, `>=` on `:str` | 0 | 0 | every such site is numeric; Python itself refuses `:str` ordering (`lower.py:3838-3845`), and Python builds this set, so none exists |

`run`, `read-file` and `args` are **not** gaps: a one-module probe using all
three builds with `gen2` and is byte-identical to Python's `.ll`. A static
scan of every list head in the 18 modules against the port's dispatch
(`str-eq h "…"` in `lower.logos`) leaves only imported function names —
there is no other unhandled builtin in the sources.

So the "missing forms" gap is exactly one typing bug (D, §1), not a form
vocabulary.

## 4. The corpus test mode (`build --test NAME`)

Python's `test` command builds each `(test NAME …)` body as a standalone
program: `run_test` calls `lower_test_program(checked_program(path), name,
debug=True)` and links it (`logos/driver.py:197-222`). `lower_test_program`
finds the test in the root module (`lower.py:867-873`), skips every module's
`main` (`forget_main`, `lower.py:877`, `1072-1076`), lowers the rest of the set
beside it (`lower.py:878-879`), and emits the test body as
`IrFn("main", [], i32, …)` with the harness directives `(expect …)` /
`(expect-leak …)` filtered out (`lower.py:883-893`; `DIRECTIVES` at
`check.py:1429`). Because it is a debug build, every exit from that `main`
first calls `void rt_leak_report(void)` — at the fall-through (`lower.py:
1786-1788`) and at each `ret` (`lower.py:1922-1927`), emitted only when
`lowering.debug` (`lower.py:1933-1938`), declared at `lower.py:503`, and
implemented to print one `LEAK …` line per live block (`logos/runtime/rt.c:
350-365`); the runner counts those lines (`tester.py:579-580`). The IR lands at
`build/<stem>.<test>.ll`, with `/` and `\` in the test name replaced by `_`
(`test_ir_path`, `driver.py:134-137`), and the link adds `-DLOGOS_DEBUG=1` so
the runtime quarantines frees (`driver.py:243-247`). What the port's `build`
must add, therefore, is a `--test NAME` operand that (a) selects the named
`(test …)` from the root module and lowers its body as `main` after skipping
every module `main` and the `expect` directives, (b) carries a `debug` flag
into `lower-build` that declares and calls `rt_leak_report` before every exit
from `main` (the port has the `main` i32 truncation and linkage already:
`lower.logos:3373-3382`, `2140-2150`, `3345-3360`, but no debug notion), and
(c) writes the same `build/<stem>.<sanitized>.ll` path convention. It is a
missing *mode*, not a missing form. It is also **not on the gen3 path** (§5);
it is what extends the gate to the 146 `(test …)` cases under `tests/exec`
and `tests/thread` (and 7 under `tests/regress`), which also exercise
closures (17 cases in `tests/exec/closures.logos`) that the port still refuses
(`lower.md`, "What it does not lower").

## 5. The ordered plan to gen3

| # | task | evidence it is needed | one-line test |
|---|---|---|---|
| 1 | Peel `ref`/`shared` in the `vec-get` type: type the element of the referent, as `vector()` does. | 9 invalid `add` lines in `ir.ll` (clang rejects :3166); `lex`/`tree` E0100 (§1-D). | `cmp` gen2's `ir.logos` `.ll` with Python's single-module `.ll` → identical. |
| 2 | Accept N roots: `build <file>… -o <out>`, and require `main` somewhere in the set. | `main.logos:507-521` takes exactly one file; the whole set is refused today (§1-A). | `gen2 build src/logosc/*.logos -o out.ll` writes IR, not usage. |
| 3 | Resolve the set as a unit: loop `resolve-set` over roots with shared tables and the module→file registry. | `resolve.logos:444-478` takes one root's `nod`; Python resolves all roots together (`driver.py:100-113`, `resolve.py:150-160`). | `gen2 resolve` on two roots yields the same module list as Python's `reachable`. |
| 4 | Let the checker type a callee whose owner is in the build set instead of failing E0103. | `check.logos:6246` refuses it; the entry's `ty` and `check-in-build`/`check-visible-owner` already exist (`check.logos:2210-2240`). | `gen2 build src/logosc/check.logos` gets past `check/check-code/2/0`. |
| 5 | Restructure `lower-build` over a module list: shared string/gensym/struct tables, per-module type/symbol/extern maps, types pass first. | `lower-build` takes one `nod` (4612) and refuses every `use` (891); Python's `prepare`/`enter` is per module (`lower.py:1008-1070`). | `gen2 build src/logosc/fmt.logos` (0 cross-calls) matches Python's `{fmt, tree}` unit `.ll`. |
| 6 | Qualify spellings: `%struct.<module>.<name>` / `%enum.…` when the unit is >1, symbols `lg.<module>.<name>` for callees; fill `powner`. | `_qualify` at `lower.py:966`, `type_name` at 1120-1139, `symbol` at 1107-1118; `powner` is written `""` (`lower.logos:709`). | `grep '%struct.tree.node'` in gen2's unit `.ll`; `cmp` against Python's unit `.ll`. |
| 7 | Byte parity on the unit, then the fixed point. | 17.2 MB / 273,304 lines, 1,227 functions, 4,347 globals — all of it must match. | `cmp` gen2's `.ll` with `build/body_test.ll`; clang gen2's `.ll` to gen3 and require gen3 to emit the same text. |
| 8 | *(not on the gen3 path)* `build --test NAME` and the `build/<stem>.<test>.ll` convention. | Needed only to extend the gate to `tests/exec`/`tests/thread`; §4. | `gen2 build --test hello tests/exec/hello.logos` matches Python byte for byte. |

## Reproduce

```sh
G=/root/.hermes/cache/scratch/gaps
for f in src/logosc/*.logos; do ./build/selfhost/gen2 build "$f" -o "$G/x.ll"; done
./build/selfhost/gen2 build src/logosc/*.logos -o "$G/all.ll"  # usage, rc 2
python3 -m logos build src/logosc/*.logos -o "$G/gen2py"       # 36.99 s, build/body_test.ll
python3 -m logos build src/logosc/main.logos -o "$G/gen2-main" # build/main.ll
./build/selfhost/gen2 build src/logosc/ir.logos -o "$G/ir.ll"  # rc 0, still wrong
clang -c "$G/ir.ll" -o /dev/null                                # rejects line 3166
cmp "$G/ir.ll" "$G/ir.python.ll"                                # 9 changed lines
```
