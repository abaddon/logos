# Self-hosted `logosc`, wave W0: a multi-file build

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the Python `logosc` builds a program spread over several `.logos` files into one native binary and one `.ll`, which is the precondition for a Logos compiler that lives in `src/logosc/`.

**Architecture:** `resolve` already returns one `Module` per file with its imports attached. W0 teaches the checker that a call to a body in the same build set is legal, teaches the lowerer to emit several modules into one `IrModule`, and qualifies struct names by their owning module in the emitted IR. It also replaces decimal float constants with hex, so no shortest-round-trip float printer stands between the two compilers.

**Tech Stack:** Python 3.14 standard library only, `unittest`, clang, LLVM IR text.

**Spec:** `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md` (D4, D6). Read it before Task 1.

## Global Constraints

- Every commit carries `Signed-off-by:` matching its author: `git commit -s`. `tools/check_dco.sh` stops the gate otherwise.
- Diagnostic codes and node paths are unchanged by this wave. No form is added.
- The four invariants hold: no freed or uninitialised read, `-O0` and `-O2` behave the same, every accepted form is lowered, every diagnostic has a code and a path.
- Do not edit `docs/LOGOS.md` by hand. If the compiler tables change, regenerate with `python3 -m logos guide > docs/LOGOS.md`.
- `.logos` fixtures must be `fmt`-idempotent.
- One logical change per commit; branch name `feat/selfhost-w0-multifile` off `main`.

## Review Focus

1. A build whose `main` sits in a different file from the functions it calls: the root file has no `main`, and the program still links.
2. Two files importing the same third module: one symbol is emitted, not two, and clang sees no duplicate definition.
3. The same plain function or struct name defined in two modules of one build: `E0003` naming both paths, never a clang error about a duplicate symbol.
4. A float literal exact in `:f32` (`0.5`), one inexact (`0.1`), and the same values at `:f64`, in one program, at both optimisation levels.
5. A module that imports a module which does not exist: `E0005` at the `use` node, with a path, not a traceback.

---

### Task 1: The failing regress case

**Files:**
- Create: `tests/regress/multi-module/program.logos`
- Create: `tests/regress/multi-module/util.logos`

**Interfaces:**
- Consumes: nothing.
- Produces: the case every later task in this wave must keep green. Its name is `regress/multi-module/program`.

- [ ] **Step 1: Write the fixture pair**

`tests/regress/multi-module/util.logos`:

```logos
(mod util)

(fn twice :i64 ((x :i64))
  (ret (* x 2)))
```

`tests/regress/multi-module/program.logos`:

```logos
(mod program)

(use util)

(test program
  (expect (out "12\n") (code 0) (leaks 0))
  (println (twice 6)))
```

A file with no `(test ...)` and no expected diagnostic declares no case, so `util.logos` is parsed and skipped by the runner. That is why the helper may sit beside the program.

- [ ] **Step 2: Run it and record the failure**

Run: `python3 -m logos test --only regress 2>&1 | grep multi-module`
Expected: `FAIL regress/multi-module/program -` with `E0103 ... imported functions are not lowered yet: 'twice'`.

- [ ] **Step 3: Confirm the fixture is canonical**

Run: `python3 -m logos fmt tests/regress/multi-module/program.logos tests/regress/multi-module/util.logos`
Expected: no output, files unchanged (`git status --short` shows only the two new files).

- [ ] **Step 4: Commit, with the design and this plan**

The design and this plan are not yet committed; they travel in this branch.

```bash
git switch -c feat/selfhost-w0-multifile
git add docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md docs/superpowers/plans/2026-11-08-selfhosted-logosc-w0.md tests/regress/multi-module
git commit -s -m "docs: self-hosting design and W0 plan, with the failing multi-module case"
```

---

### Task 2: The checker accepts a body in the build set

**Files:**
- Modify: `logos/check.py:592` (`check_module`), `logos/check.py:3985-4005` (the `_bodies` refusal)
- Test: `tests/test_link.py` (new)

**Interfaces:**
- Consumes: `resolve.Module`, `resolve.resolve`.
- Produces:
  - `resolve.program(roots: list[Node]) -> list[Module]` — resolves every root with one loader that answers `use` from the given set first and the asking file's directory second, and refuses two roots that declare one module name (`E0003` at the second).
  - `check_module(m: Module, *, bodies: dict[str, Node] | None = None) -> CheckedModule` — `bodies` names every function in the build set that will have a symbol; `None` means "this module's own".
  - `check_program(modules: list[Module]) -> list[CheckedModule]` — checks each module with the union of all bodies, and raises `E0003` at the second definition when two modules define the same plain function or type name.

- [ ] **Step 1: Write the failing test**

`tests/test_link.py`:

```python
import tempfile
import unittest
from pathlib import Path

from logos import check, parser, resolve
from logos.diag import LogosError


def _parse(text: str, name: str):
    path = Path(tempfile.mkdtemp()) / f"{name}.logos"
    path.write_text(text, encoding="utf-8")
    return parser.parse(text, str(path))


UTIL = "(mod util)\n(fn twice :i64 ((x :i64)) (ret (* x 2)))\n"
PROGRAM = "(mod program)\n(use util)\n(fn main :i64 () (ret (twice 6)))\n"


class CheckProgramTest(unittest.TestCase):
    def test_a_call_into_a_sibling_module_is_legal(self):
        modules = resolve.program([_parse(PROGRAM, "program"), _parse(UTIL, "util")])
        checked = check.check_program(modules)
        self.assertEqual(len(checked), 2)

    def test_two_modules_with_one_plain_name_are_a_duplicate(self):
        a = _parse("(mod a)\n(fn helper :i64 () (ret 1))\n", "a")
        b = _parse("(mod b)\n(fn helper :i64 () (ret 2))\n", "b")
        with self.assertRaises(LogosError) as caught:
            check.check_program(resolve.program([a, b]))
        self.assertEqual(caught.exception.code, "E0003")
```

`resolve.program` owns the set loader, so the fixtures never touch the disk twice and `check_program` stays a pure namespace check.

- [ ] **Step 2: Run it and confirm both fail**

Run: `python3 -m unittest tests.test_link -v`
Expected: FAIL, `AttributeError: module 'logos.check' has no attribute 'check_program'`.

- [ ] **Step 3: Thread `bodies` through the checker**

In `_Checker.__init__`, replace the line `self._bodies = {name: node for name, node in self.module.fns.items()}` with an assignment from a new constructor argument `bodies: dict[str, Node] | None`, defaulting to the module's own functions. `_Checker.bodies` is then every function the build emits, keyed by plain name.

The refusal at `logos/check.py:4000` keeps its text and its code, because a name can still be visible through an import from a module outside the build set. What changes is that a name in `bodies` no longer reaches it.

- [ ] **Step 4: Add `resolve.program` and `check_program`**

`resolve.program(roots)` builds one loader closure over a `dict[str, Node]` of module name → tree, taken from each root's `(mod ...)` form, and falls back to the asking file's directory (the existing rule). It calls the existing `resolve(root, loader, file)` per root. Two roots naming one module is `E0003` at the second, reporting both.

`check_program(modules)` builds one `dict[str, Node]` from every module's `fns`, and one `dict[str, Node]` of every module's `types`. On a repeated plain name, raise `E0003` with the `path` of the second definition and a message naming both paths. Then return `[check_module(m, bodies=shared) for m in modules]`.


- [ ] **Step 5: Run the test and the suite**

Run: `python3 -m unittest tests.test_link -v` then `make test`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add logos/check.py tests/test_link.py
git commit -s -m "feat: check a call to a body in the same build set"
```

---

### Task 3: One `IrModule` for several modules, with per-module symbols

**Files:**
- Modify: `logos/lower.py:803-830` (`symbols`), `logos/lower.py:822` (`symbol`), `logos/lower.py:773` (`__init__`), `logos/lower.py:1068` (`close`)
- Modify: `logos/llvm.py:273` (`reset_structs`), and the `struct_llty` / `register_struct` calls in `lower.py`
- Test: `tests/test_link.py`, `tests/regress/multi-module/`

**Interfaces:**
- Consumes: `Task 2`'s `resolve.program` and `check_program`.
- Produces:
  - `lower.lower_program(checked: list[CheckedModule], *, debug: bool = False) -> IrModule`
  - `_Lower.prepare(cm: CheckedModule) -> None`, filling `self._symbol_maps[cm.module.name]` with that module's own functions plus those it imports, each mapped to its module-qualified symbol `lg.<module>.<name>`
  - `_Lower.symbol(module: str, name: str) -> str`
  - `_Lower.enter(cm: CheckedModule) -> None`, which swaps `self.cm` and `self.body` to the module whose bodies are being lowered

- [ ] **Step 1: Write the failing tests**

In `tests/test_link.py`, three assertions, each pinning one thing the merged unit must get right:

```python
class ProgramLoweringTest(unittest.TestCase):
    def test_two_modules_lower_into_one_ir_module(self):
        modules = resolve.program([_parse(PROGRAM, "program"), _parse(UTIL, "util")])
        ir = lower.lower_program(check.check_program(modules))
        self.assertEqual(len(ir.functions), 2)
        self.assertEqual(len({fn.name for fn in ir.functions}), 2)

    def test_an_imported_call_uses_the_owning_module_symbol(self):
        modules = resolve.program([_parse(PROGRAM, "program"), _parse(UTIL, "util")])
        text = llvm.emit(lower.lower_program(check.check_program(modules)))
        self.assertIn("call i64 @lg.util.twice(", text)
        self.assertNotIn("@lg.program.twice", text)

    def test_a_diamond_import_emits_one_symbol(self):
        base = _parse("(mod base)\n(fn id :i64 ((x :i64)) (ret x))\n", "base")
        left = _parse("(mod left)\n(use base)\n(fn l :i64 () (ret (id 1)))\n", "left")
        right = _parse("(mod right)\n(use base)\n(fn r :i64 () (ret (id 2)))\n", "right")
        modules = resolve.program([base, left, right])
        ir = lower.lower_program(check.check_program(modules))
        self.assertEqual(len({fn.name for fn in ir.functions}), 3)
```

The exact symbol text comes from a one-module build of `util.logos`, because `symbol()` escapes through `_escape_name`.

- [ ] **Step 2: Run them and confirm they fail**

Run: `python3 -m unittest tests.test_link -v`
Expected: FAIL, `lower_program` does not exist.

- [ ] **Step 3: Replace the flat symbol table**

`_Lower.symbols` becomes `self._symbol_maps: dict[str, dict[str, str]]`, filled per checked module by `prepare(cm)`: it walks `cm.module.fns` and, for each imported module, that module's `fns`, mapping plain name to `self.symbol(owner_module, name)`. `symbol(name)` becomes `symbol(module: str, name: str)`.

A single-module build must produce byte-identical IR before and after this change. Save `build/vec.ll` before the edit and diff it after.

- [ ] **Step 4: Implement `lower_program`**

Call `llvm.reset_structs()` once, then `_Lower(checked[0])`, then for each remaining `CheckedModule` call `prepare(cm)`, `enter(cm)` and lower its functions. `close()` runs once, after every module, so there is one `ir`, one `strings` map and one counter for the whole unit.

Struct and enum names become `"<module>.<name>"` where the module declared the type, so `%struct.util.point` cannot collide with `%struct.program.point`. `struct_llty` and `register_struct` take the qualified name. Two modules declaring one plain struct name are already `E0003` from Task 2, so the owner is unambiguous.

- [ ] **Step 5: Prove the regress case now runs**

Run: `python3 -m logos test --only regress 2>&1 | grep multi-module`
Expected: `PASS regress/multi-module/program -`.

- [ ] **Step 6: Run the suite**

Run: `make test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add logos/lower.py logos/llvm.py tests/test_link.py
git commit -s -m "feat: lower several modules into one translation unit"
```

Struct and enum names become `"<module>.<name>"` where the module declared the type, so `%struct.util.point` cannot collide with `%struct.program.point`. `struct_llty` and `register_struct` take the qualified name. Two modules declaring one plain struct name are already `E0003` from Task 2, so the owner is unambiguous.

- [ ] **Step 5: Prove the regress case now runs**

Run: `python3 -m logos test --only regress 2>&1 | grep multi-module`
Expected: `PASS regress/multi-module/program -`.

- [ ] **Step 6: Run the suite**

Run: `make test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add logos/lower.py logos/llvm.py tests/test_link.py
git commit -s -m "feat: lower several modules into one translation unit"
```

---

### Task 4: `logosc build a.logos b.logos`

**Files:**
- Modify: `logos/cli.py` (`build` parser), `logos/driver.py` (`load`, `build`)
- Test: `tests/test_cli.py`, `tests/test_link.py`

**Interfaces:**
- Consumes: `resolve.program`, `check.check_program`, `lower.lower_program`.
- Produces:
  - `driver.load_program(paths: list[str]) -> list[Module]`
  - `driver.build_program(paths: list[str], out: str | None = None, opt: str = "-O2", keep_ir: bool = True, *, debug: bool = False) -> str`
  - `logosc build FILE [FILE ...]`

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, one test builds two files where only the second has `main`, then runs the binary. Follow the file's existing pattern for a temporary directory and `subprocess.run`:

```python
def test_build_accepts_two_files(self):
    with tempfile.TemporaryDirectory() as tmp:
        util = Path(tmp) / "util.logos"
        util.write_text(GOOD_UTIL, encoding="utf-8")  # (mod util) with twice
        main = Path(tmp) / "main.logos"
        main.write_text(GOOD_MAIN, encoding="utf-8")  # (use util), prints (twice 21)
        out = Path(tmp) / "prog"
        done = subprocess.run(
            [sys.executable, "-m", "logos", "build", str(util), str(main), "-o", str(out)],
            capture_output=True, text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(subprocess.run([str(out)], capture_output=True, text=True).stdout, "42\n")
```

In `tests/test_link.py`, the missing-module case from Review Focus 5:

```python
def test_a_use_of_a_module_outside_the_build_set_still_fails(self):
    loads = _parse("(mod loads)\n(use absent)\n", "loads")
    with self.assertRaises(LogosError) as caught:
        resolve.program([loads])
    self.assertEqual(caught.exception.code, "E0005")
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `python3 -m unittest tests.test_cli -k two_files tests.test_link -v`
Expected: FAIL, argparse rejects the second positional; the `E0005` test passes only if `resolve.program` already answers a loader miss with `E0005`, which Task 2 must leave intact.

- [ ] **Step 3: Implement the driver entry points and the parser change**

`load_program` parses every path, calls `resolve.program(roots)`, and returns the modules. `build_program` mirrors `build`, but takes the module list, requires exactly one `main` across the set, and writes the IR to `build/<first stem>.ll`. `build(src_path)` becomes a one-element call to `build_program`, so there is one code path.

The `build` subparser takes `nargs="+"` on `file`. Do not use `nargs="*"`: it swallows options and `-o` stops parsing.

- [ ] **Step 4: Run the test and the gates**

Run: `python3 -m unittest tests.test_cli -v` and `make test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add logos/cli.py logos/driver.py tests/test_cli.py
git commit -s -m "feat: build several source files into one binary"
```

---

### Task 5: Float constants in hex

**Files:**
- Modify: `logos/lower.py` (`_float_text`, `_hex_float`), spec `docs/superpowers/specs/2026-11-06-ai-language-design.md`
- Test: `tests/test_emit.py`

**Interfaces:**
- Consumes: nothing.
- Produces: every float constant in the emitted IR spelled `0x` plus sixteen hex digits of its double bit pattern, at both `:f64` and `:f32`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_float_constant_is_hexadecimal(self):
    text = emit_source("(mod f)\n(fn main :i64 () (println 1.5) (ret 0))\n")
    self.assertIn("double 0x3FF8000000000000", text)
    self.assertNotIn("double 1.5", text)
```

`emit_source` is the helper the file already uses; keep its name.

- [ ] **Step 2: Run it and confirm it fails**

Run: `python3 -m unittest tests.test_emit -k hexadecimal -v`
Expected: FAIL, the IR holds `double 1.5`.

- [ ] **Step 3: Replace the decimal path**

`_float_text` returns the hex form for both widths: for `:f64`, `0x%016X` of `struct.unpack("<Q", struct.pack("<d", value))[0]`; for `:f32`, the existing `_hex_float`. Delete the `repr` path and its docstring paragraph, and add one line to the language spec: a float constant is emitted as its bit pattern, so no decimal spelling can round differently.

- [ ] **Step 4: Prove behaviour did not change**

Run: `make test && python3 -m logos test --only exec 2>&1 | tail -3`
Expected: PASS, including `float-literal-compare` and `cast`. The runner builds every case at `-O0` and `-O2` by default (`OPTS -O0 -O2` in `tests/summary.txt`), so this step is also the optimisation-parity check for Review Focus 4.

- [ ] **Step 5: Commit**

```bash
git add logos/lower.py tests/test_emit.py docs/superpowers/specs/2026-11-06-ai-language-design.md
git commit -s -m "feat: emit float constants as bit patterns"
```

---

### Task 6: The five gates and the pull request

**Files:**
- Modify: none, unless a gate fails.

- [ ] **Step 1: Run the gate**

Run: `bash tools/pr_gate.sh`
Expected: `PASS sign-off`, then PASS for `make test`, corpus, acceptance, guide check and fmt.

- [ ] **Step 2: Regenerate the manual if a table moved**

Run: `python3 -m logos guide > docs/LOGOS.md && python3 -m logos guide --check`
Expected: exit 0, no diff. Nothing in W0 should move a table; a diff here means a table changed by accident.

- [ ] **Step 3: Record the regress evidence**

Note in the pull request: `regress/multi-module/program` failed with `E0103` before Task 1 and passes after Task 3; the commit before Task 2 is the branch state that reproduces the failure.

- [ ] **Step 4: Commit and open the PR**

```bash
git commit -s --allow-empty -m "chore: gate W0" # only if something is uncommitted
git push -u origin feat/selfhost-w0-multifile
gh pr create --title "feat: W0 multi-file build for self-hosting" --body-file .github/PULL_REQUEST_TEMPLATE.md
```

Fill every section of the template, including the reason for any change to `tests/summary.txt` (there should be none) and the statement that the four invariants hold.

## Later waves

Each wave gets its own plan file when the previous one merges, because each depends on interfaces the previous wave creates. W1 (the `(ref T)` parameter) is next, then W2 (six forms), W3 (the Logos standard library), W4 to W9 (the compiler itself). W4 to W8 hold 80% of the work.