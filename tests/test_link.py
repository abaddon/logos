import subprocess
import tempfile
import unittest
from pathlib import Path

from logos import check, driver, llvm, lower, parser, resolve
from logos.diag import LogosError


def _parse(text: str, name: str, directory: str | Path | None = None):
    directory = Path(directory) if directory is not None else Path(tempfile.mkdtemp())
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.logos"
    path.write_text(text, encoding="utf-8")
    return parser.parse(text, str(path))


UTIL = "(mod util)\n(fn twice :i64 ((x :i64)) (ret (* x 2)))\n"
PROGRAM = "(mod program)\n(use util)\n(fn main :i64 () (ret (twice 6)))\n"


class CheckProgramTest(unittest.TestCase):
    def test_a_call_into_a_sibling_module_is_legal(self):
        modules = resolve.program([_parse(PROGRAM, "program"), _parse(UTIL, "util")])
        checked = check.check_program(modules)
        self.assertEqual(len(checked), 2)

    def test_private_names_may_repeat_across_roots(self):
        # Task 3 spells every symbol ``lg.<module>.<name>``, so two roots may
        # each declare a private function and a private type of one name.
        a = _parse(
            "(mod a)(type entry (struct (x :i64)))"
            "(fn init :i64 () (ret 1))"
            "(fn main :i64 () (ret (init)))",
            "a",
        )
        b = _parse(
            "(mod b)(type entry (struct (y :i64)))"
            "(fn init :i64 () (ret 2))",
            "b",
        )
        checked = check.check_program(resolve.program([a, b]))
        self.assertEqual([cm.module.name for cm in checked], ["a", "b"])

    def test_two_mains_are_a_duplicate(self):
        a = _parse("(mod a)(fn main :i64 () (ret 1))", "a")
        b = _parse("(mod b)(fn main :i64 () (ret 2))", "b")
        with self.assertRaises(LogosError) as caught:
            check.check_program(resolve.program([a, b]))
        self.assertEqual(caught.exception.code, "E0003")
        self.assertIn("main", caught.exception.message)
        self.assertIn("a/main", caught.exception.message)
        self.assertIn("b/main", caught.exception.message)


class LoneModuleTest(unittest.TestCase):
    def test_a_module_checked_alone_refuses_an_import(self):
        directory = Path(tempfile.mkdtemp())
        program = _parse(PROGRAM, "program", directory)
        _parse(UTIL, "util", directory)
        modules = resolve.program([program])
        with self.assertRaises(LogosError) as caught:
            check.check_module(modules[0])
        self.assertEqual(caught.exception.code, "E0103")
        self.assertIn(
            "imported functions are not lowered yet", caught.exception.message
        )
        self.assertIn("twice", caught.exception.message)


class ResolveProgramTest(unittest.TestCase):
    def test_a_module_absent_from_the_set_is_e0005(self):
        a = _parse("(mod a)(use missing)", "a")
        with self.assertRaises(LogosError) as caught:
            resolve.program([a])
        self.assertEqual(caught.exception.code, "E0005")
        self.assertIn("missing", caught.exception.message)

    def test_two_roots_with_one_module_name_are_a_duplicate(self):
        a = _parse("(mod same)(fn f :i64 () (ret 1))", "a")
        b = _parse("(mod same)(fn g :i64 () (ret 2))", "b")
        with self.assertRaises(LogosError) as caught:
            resolve.program([a, b])
        self.assertEqual(caught.exception.code, "E0003")
        self.assertIn(a.file, caught.exception.message)
        self.assertIn(b.file, caught.exception.message)

    def test_an_import_is_answered_beside_the_file_that_asked(self):
        # ``a`` imports ``x`` beside it. ``b``'s directory holds an unrelated
        # ``x.logos``; it must not answer ``a``'s import just because ``b`` is
        # in the same build.
        directory = Path(tempfile.mkdtemp())
        dir1 = directory / "dir1"
        dir2 = directory / "dir2"
        x = _parse("(mod x)(fn g :i64 ((v :i64)) (ret 1))", "x", dir1)
        a = _parse("(mod a)(use x)(fn f :i64 () (ret (g 1)))", "a", dir1)
        b = _parse("(mod b)(use a)(fn main :i64 () (ret (f)))", "b", dir2)
        _parse("(mod other)(fn g :i64 ((v :i64)) (ret 9))", "x", dir2)

        modules = resolve.program([a, b])

        self.assertEqual([m.name for m in modules], ["a", "b"])
        self.assertEqual(modules[0].imports["x"].root.file, x.file)


class LoadProgramTest(unittest.TestCase):
    """The driver's build-set entry points keep the resolver's refusals."""

    def test_a_use_of_a_module_outside_the_build_set_still_fails(self):
        directory = Path(tempfile.mkdtemp())
        _parse("(mod loads)\n(use absent)\n", "loads", directory)
        with self.assertRaises(LogosError) as caught:
            driver.load_program([str(directory / "loads.logos")])
        self.assertEqual(caught.exception.code, "E0005")

    def test_build_program_builds_every_file_in_the_set(self):
        directory = Path(tempfile.mkdtemp())
        (directory / "util.logos").write_text(UTIL, encoding="utf-8")
        program = directory / "program.logos"
        program.write_text(
            "(mod program)\n(use util)\n(fn main :void ()\n"
            "  (println (twice 21)))\n",
            encoding="utf-8",
        )
        out = str(Path(tempfile.mkdtemp()) / "prog")
        self.assertEqual(
            driver.build_program(
                [str(program), str(directory / "util.logos")], out
            ),
            out,
        )
        done = subprocess.run([out], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "42\n")
        # The IR is named after the first source, which is the file the
        # command line names first.
        self.assertTrue(driver.ir_path(str(program)).is_file())


class ImportedGenericTest(unittest.TestCase):
    # A generic is instantiated from the definition it was declared in. An
    # imported generic therefore never runs in the caller's namespace, where
    # its body's names would resolve to the caller's definitions.
    A = (
        "(mod a)(use b)"
        "(fn helper :i64 ((y :i64)) (ret (* y 2)))"
        "(fn main :i64 () (ret (bump 3)))"
    )
    B = "(mod b)(fn bump :T ((x :T)) (ret (helper x)))"

    def test_a_sibling_generic_is_not_instantiated_in_the_caller(self):
        modules = resolve.program([_parse(self.A, "a"), _parse(self.B, "b")])
        with self.assertRaises(LogosError) as caught:
            check.check_program(modules)
        self.assertEqual(caught.exception.code, "E0103")
        self.assertEqual(
            caught.exception.message,
            "imported functions are not lowered yet: 'bump'",
        )

    def test_the_callers_helper_does_not_type_the_siblings_copy(self):
        # With the leak this is E0100 at ``b``'s node: the copy is checked
        # against the caller's ``helper``. It must be the same E0103 instead.
        incompatible = (
            "(mod a)(use b)"
            "(fn helper :str ((y :str)) (ret y))"
            "(fn main :i64 () (ret (bump 3)))"
        )
        modules = resolve.program([_parse(incompatible, "a"), _parse(self.B, "b")])
        with self.assertRaises(LogosError) as caught:
            check.check_program(modules)
        self.assertEqual(caught.exception.code, "E0103")


class UnbuiltImportTest(unittest.TestCase):
    def test_checking_one_module_alone_refuses_an_imported_call(self):
        # ``check_module`` names one module, so nothing emits that module's
        # imports: a call into one is the E0103 refusal. The driver does not
        # take this path — it passes the import closure to ``check_program``
        # — which is why this is a statement about ``check_module`` alone.
        directory = Path(tempfile.mkdtemp())
        _parse("(mod m1)(fn helper :i64 ((v :i64)) (ret 7))", "m1", directory)
        a = _parse(
            "(mod a)(use m1)(fn main :i64 () (ret (helper 1)))", "a", directory
        )
        with self.assertRaises(LogosError) as caught:
            check.check_module(resolve.program([a])[0])
        self.assertEqual(caught.exception.code, "E0103")
        self.assertIn("helper", caught.exception.message)

    def test_a_disk_import_in_the_closure_is_accepted_and_lowered(self):
        # Only the root is named, so ``util`` reaches the checker through the
        # closure the driver passes — and is lowered with the root.
        directory = Path(tempfile.mkdtemp())
        util = directory / "util.logos"
        util.write_text(UTIL, encoding="utf-8")
        program = directory / "program.logos"
        program.write_text(
            "(mod program)\n(use util)\n(fn main :void ()\n"
            "  (println (twice 21)))\n",
            encoding="utf-8",
        )
        out = str(Path(tempfile.mkdtemp()) / "prog")
        self.assertEqual(driver.build_program([str(program)], out), out)
        done = subprocess.run([out], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "42\n")
        text = driver.ir_path(str(program)).read_text(encoding="utf-8")
        self.assertIn("define internal i64 @lg.util.twice", text)
        self.assertIn("define i32 @main()", text)


SIBLINGS = (
    "(mod util)"
    "(fn twice :i64 ((x :i64)) (ret (* x 2)))"
    "(fn apply :i64 ((f :(fn (:i64) :i64)) (x :i64)) (ret (f x)))"
    "(fn work :void ((n :i64)) (println n))"
)


class ProgramLoweringTest(unittest.TestCase):
    """One ``IrModule`` for a whole build set, with per-module symbols."""

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

    def test_private_types_of_one_name_keep_their_own_layout(self):
        # Each root declares its own ``entry``; the qualified name is what
        # keeps one definition from standing for both.
        a = _parse(
            "(mod a)(type entry (struct (x :i64)))"
            "(fn main :i64 () (let p entry (make entry 1)) (ret (get p x)))",
            "a",
        )
        b = _parse(
            "(mod b)(type entry (struct (y :i64) (z :i64)))"
            "(fn pair :i64 () (let q entry (make entry 1 2))"
            " (ret (+ (get q y) (get q z))))",
            "b",
        )
        text = llvm.emit(
            lower.lower_program(check.check_program(resolve.program([a, b])))
        )
        self.assertIn("%struct.a.entry = type { i64 }", text)
        self.assertIn("%struct.b.entry = type { i64, i64 }", text)

    def test_private_enum_widths_do_not_leak_between_modules(self):
        # The payload width is measured from the declarations of the module
        # being lowered, so one name in two modules is two widths.
        a = _parse(
            "(mod a)(type tone (enum (quiet) (loud :i64)))"
            "(fn show :i64 ((t tone)) (ret (match t ((quiet) 1) ((loud n) n))))",
            "a",
        )
        b = _parse(
            "(mod b)(type tone (enum (red) (green)))"
            "(fn other :i64 ((t tone)) (ret (match t ((red) 1) ((green) 2))))",
            "b",
        )
        text = llvm.emit(
            lower.lower_program(check.check_program(resolve.program([a, b])))
        )
        self.assertIn("define internal i64 @lg.a.show({ i32, [1 x i64] }", text)
        self.assertIn("define internal i64 @lg.b.other({ i32, [0 x i64] }", text)

    def test_a_sibling_function_value_calls_the_owners_symbol(self):
        # The thunk a function value becomes must call the module that owns
        # the body, not the module that took the address.
        program = _parse(
            "(mod program)(use util)(fn main :i64 () (ret (apply twice 3)))",
            "program",
        )
        ir = lower.lower_program(
            check.check_program(resolve.program([program, _parse(SIBLINGS, "util")]))
        )
        thunk = next(fn for fn in ir.functions if fn.name.startswith("$fnvalue"))
        self.assertEqual(_called(thunk), ["lg.util.twice"])
        self.assertEqual(thunk.symbol, "lg.program." + thunk.name)

    def test_a_sibling_spawn_calls_the_owners_symbol(self):
        program = _parse(
            "(mod program)(use util)"
            "(fn main :i64 () (let t (spawn work 1)) (join t) (ret 0))",
            "program",
        )
        ir = lower.lower_program(
            check.check_program(resolve.program([program, _parse(SIBLINGS, "util")]))
        )
        thunk = next(fn for fn in ir.functions if fn.name.startswith("$spawn"))
        self.assertEqual(_called(thunk), ["lg.util.work"])
        # The runtime is handed the thunk, and the thunk the owner's symbol.
        main = next(fn for fn in ir.functions if fn.name == "main")
        self.assertIn(thunk.symbol, _addresses(main))


class ExternAcrossModulesTest(unittest.TestCase):
    """Every module of the unit carries its own ``extern`` declarations."""

    UTIL = (
        "(mod util)\n"
        "(extern fn getpid :i64 ())\n"
        "(fn pid :i64 () (ret (getpid)))\n"
    )
    MID = "(mod mid)\n(use util)\n(fn midpid :i64 () (ret (pid)))\n"
    PROGRAM = "(mod program)\n(use mid)\n(fn main :i64 () (ret (midpid)))\n"

    def test_a_module_two_hops_down_calls_its_own_extern(self):
        directory = Path(tempfile.mkdtemp())
        _parse(self.UTIL, "util", directory)
        _parse(self.MID, "mid", directory)
        _parse(self.PROGRAM, "program", directory)
        ir = lower.lower_program(
            driver.checked_program(str(directory / "program.logos"))
        )
        text = llvm.emit(ir)
        self.assertIn("declare i64 @getpid()", text)
        self.assertIn("call i64 @getpid()", text)

    def test_a_second_root_calls_its_own_extern(self):
        first = _parse(
            "(mod a)\n(extern fn getpid :i64 ())"
            "(fn pa :i64 () (ret (getpid)))\n",
            "a",
        )
        second = _parse(
            "(mod b)\n(extern fn getppid :i64 ())"
            "(fn pb :i64 () (ret (getppid)))\n",
            "b",
        )
        ir = lower.lower_program(
            check.check_program(resolve.program([first, second]))
        )
        text = llvm.emit(ir)
        self.assertIn("declare i64 @getpid()", text)
        self.assertIn("declare i64 @getppid()", text)
        self.assertIn("call i64 @getppid()", text)


class ImportedTypeOutsideTheUnitTest(unittest.TestCase):
    """A type's owner spells it, whichever module of the unit uses it."""

    def _modules(self):
        directory = Path(tempfile.mkdtemp())
        _parse(
            "(mod shapes)\n(type point (struct (x :i64) (y :i64)))\n",
            "shapes",
            directory,
        )
        first = _parse(
            "(mod a)\n(use shapes)\n(use b)\n"
            "(fn main :i64 ()\n"
            "  (let p point (make point 3 4))\n"
            "  (println (take p))\n"
            "  (ret 0))\n",
            "a",
            directory,
        )
        second = _parse(
            "(mod b)\n(use shapes)\n"
            "(fn take :i64 ((p point))\n"
            "  (ret (+ (get p x) (get p y))))\n",
            "b",
            directory,
        )
        return first, second

    def test_the_declaring_module_names_the_type_for_every_root(self):
        first, second = self._modules()
        text = llvm.emit(
            lower.lower_program(
                check.check_program(resolve.program([first, second]))
            )
        )
        self.assertEqual(text.count("%struct.shapes.point = type { i64, i64 }"), 1)
        self.assertIn("define internal i64 @lg.b.take(%struct.shapes.point", text)
        self.assertNotIn("%struct.a.point", text)
        self.assertNotIn("%struct.b.point", text)

    def test_a_cross_module_struct_value_links_and_prints_it(self):
        first, second = self._modules()
        ir = lower.lower_program(
            check.check_program(resolve.program([first, second]))
        )
        ll = driver.BUILD_DIR / "test-shared-type.ll"
        out = str(driver.BUILD_DIR / "test-shared-type")
        driver._link(ir, ll, out, "-O2", True, debug=False)
        done = subprocess.run([out], capture_output=True, text=True)
        self.assertEqual(done.stdout, "7\n", done.stderr)
        self.assertEqual(done.returncode, 0)


def _build_set(files: dict[str, str], root: str, level: str) -> str:
    """Write ``files`` as a build set, build ``root`` and return its output."""
    directory = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (directory / f"{name}.logos").write_text(text, encoding="utf-8")
    out = str(Path(tempfile.mkdtemp()) / root)
    driver.build_program([str(directory / f"{root}.logos")], out, opt=level)
    done = subprocess.run([out], capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError(f"{level}: {done.returncode}: {done.stderr}")
    return done.stdout


class ImportedStructFieldTypeTest(unittest.TestCase):
    """A struct's field types are spelled by the module that declares it.

    ``deep`` declares ``inner``; ``shapes`` declares ``point`` with a field of
    that type; ``program`` declares an ``inner`` of its own. The ``point`` a
    ``shapes`` function builds must keep ``deep``'s ``inner``, whatever the
    module holding the value happens to call its own field type.
    """

    DEEP = (
        "(mod deep)"
        "(type inner (struct (x :i64)))"
        "(fn make-inner inner () (ret (make inner 42)))"
    )
    SHAPES = (
        "(mod shapes)"
        "(use deep)"
        "(type point (struct (inner inner)))"
        "(fn origin point () (ret (make point (make-inner))))"
        "(fn value :i64 ((p point)) (ret (get (get p inner) x)))"
    )

    def test_a_field_type_keeps_the_declaring_modules_namespace(self):
        # The two ``inner`` types have different layouts, which is why the
        # mis-spelt field reached clang as an aggregate that disagrees.
        program = (
            "(mod program)"
            "(use shapes)"
            "(type inner (struct (y :i64) (z :i64)))"
            "(fn main :void () (let p (origin)) (println (value p)))"
        )
        files = {"deep": self.DEEP, "shapes": self.SHAPES, "program": program}
        for level in ("-O0", "-O2"):
            self.assertEqual(_build_set(files, "program", level), "42\n", level)

    def test_identical_layouts_still_keep_their_own_namespace(self):
        # Same layout on both sides: the failure was never the layout. The
        # two identified types differ, so a wrong spelling is still refused.
        program = (
            "(mod program)"
            "(use shapes)"
            "(type inner (struct (y :i64)))"
            "(fn main :void ()"
            " (let q inner (make inner 7))"
            " (println (get q y))"
            " (let p (origin))"
            " (println (value p)))"
        )
        files = {"deep": self.DEEP, "shapes": self.SHAPES, "program": program}
        for level in ("-O0", "-O2"):
            self.assertEqual(_build_set(files, "program", level), "7\n42\n", level)


class SiblingSignatureTypeTest(unittest.TestCase):
    """A signature may name a type only the declaring module's chain sees.

    ``shapes`` returns and takes ``deep``'s ``point``; ``program`` imports only
    ``shapes``. The type is two hops from the module that holds the value, so
    neither ``program`` nor ``shapes`` may be the namespace it is read in.
    """

    DEEP = (
        "(mod deep)"
        "(type point (struct (x :i64)))"
        "(fn mk point () (ret (make point 7)))"
    )
    SHAPES = (
        "(mod shapes)"
        "(use deep)"
        "(fn origin point () (ret (mk)))"
        "(fn value :i64 ((p point)) (ret (get p x)))"
    )
    PROGRAM = (
        "(mod program)"
        "(use shapes)"
        "(fn main :void () (let p (origin)) (println (value p)))"
    )

    def test_a_type_two_hops_down_lowers_and_runs(self):
        # Before the fix this was ``E0002 program/main/2: point is not lowered
        # yet`` at a ``let`` the author never wrote a type on.
        files = {"deep": self.DEEP, "shapes": self.SHAPES, "program": self.PROGRAM}
        for level in ("-O0", "-O2"):
            self.assertEqual(_build_set(files, "program", level), "7\n", level)

    def test_a_declaring_module_outside_the_build_is_named(self):
        # ``deep`` is not a root, so it is not lowered with the set; the type
        # still resolves to it, and the refusal has to say which module owns
        # the type rather than blame the expression that mentioned it. The
        # sibling here builds the value itself, so it needs no call into
        # ``deep`` and the checker accepts the pair.
        shapes = (
            "(mod shapes)"
            "(use deep)"
            "(fn origin point () (ret (make point 7)))"
            "(fn value :i64 ((p point)) (ret (get p x)))"
        )
        directory = Path(tempfile.mkdtemp())
        _parse(self.DEEP, "deep", directory)
        first = _parse(shapes, "shapes", directory)
        program = _parse(self.PROGRAM, "program", directory)
        checked = check.check_program(resolve.program([program, first]))
        with self.assertRaises(LogosError) as caught:
            lower.lower_program(checked)
        self.assertEqual(caught.exception.code, "E0002")
        self.assertIn("'point'", caught.exception.message)
        self.assertIn("'deep'", caught.exception.message)


class OneModuleTwoFilesTest(unittest.TestCase):
    """C2: one module name may only ever be answered by one file."""

    A = (
        "(mod a)"
        "(use util)"
        "(use b)"
        "(fn main :void () (println (answer)) (println (run)))"
    )
    B = "(mod b)(use util)(fn run :i64 () (ret (answer)))"
    UTIL = "(mod util)(fn answer :i64 () (ret {value}))"

    def _files(self) -> tuple[Path, Path]:
        directory = Path(tempfile.mkdtemp())
        first = directory / "dir1"
        second = directory / "dir2"
        first.mkdir()
        second.mkdir()
        (first / "util.logos").write_text(
            self.UTIL.format(value=1), encoding="utf-8"
        )
        (first / "a.logos").write_text(self.A, encoding="utf-8")
        (second / "b.logos").write_text(self.B, encoding="utf-8")
        (second / "util.logos").write_text(
            self.UTIL.format(value=2), encoding="utf-8"
        )
        return first, second

    def test_a_name_answered_by_two_files_is_e0003_naming_both(self):
        first, second = self._files()
        with self.assertRaises(LogosError) as caught:
            driver.load_program(
                [str(first / "a.logos"), str(second / "b.logos")]
            )
        self.assertEqual(caught.exception.code, "E0003")
        self.assertIn(str(first / "util.logos"), caught.exception.message)
        self.assertIn(str(second / "util.logos"), caught.exception.message)

    def test_the_refusal_does_not_depend_on_the_order_of_the_roots(self):
        first, second = self._files()
        with self.assertRaises(LogosError) as caught:
            driver.load_program(
                [str(second / "b.logos"), str(first / "a.logos")]
            )
        self.assertEqual(caught.exception.code, "E0003")
        self.assertIn(str(first / "util.logos"), caught.exception.message)
        self.assertIn(str(second / "util.logos"), caught.exception.message)


class TestEntryMainTest(unittest.TestCase):
    """The entry point is the system's to call, in a build and in a test build."""

    def test_a_call_to_a_sibling_main_is_e0108(self):
        directory = Path(tempfile.mkdtemp())
        _parse(
            "(mod util)\n(fn twice :i64 ((x :i64)) (ret (* x 2)))\n",
            "util",
            directory,
        )
        _parse(
            "(mod app)\n(use util)\n(fn main :i64 () (ret (twice 6)))\n",
            "app",
            directory,
        )
        _parse(
            "(mod lib)\n(use app)\n(fn run :i64 () (ret (main)))\n",
            "lib",
            directory,
        )
        # ``lib`` names a symbol it cannot call: the ``main`` it reaches is the
        # C entry point, which clang takes with an ``:i32`` result and no
        # arguments. The checker refuses the call, at the call.
        with self.assertRaises(LogosError) as caught:
            driver.checked_program(str(directory / "lib.logos"))
        self.assertEqual(caught.exception.code, "E0108")
        self.assertEqual(caught.exception.path, "lib/run/2/0")
        self.assertIn("entry point is not callable", caught.exception.message)

    def test_a_call_to_its_own_main_is_e0108(self):
        # The same fault within one module: it predates build sets, and it is
        # refused for the same reason.
        directory = Path(tempfile.mkdtemp())
        _parse(
            "(mod alone)\n"
            "(fn helper :i64 () (ret (main)))\n"
            "(fn main :i64 () (ret (helper)))\n",
            "alone",
            directory,
        )
        with self.assertRaises(LogosError) as caught:
            driver.checked_program(str(directory / "alone.logos"))
        self.assertEqual(caught.exception.code, "E0108")
        self.assertEqual(caught.exception.path, "alone/helper/2/0")



def _called(fn) -> list[str]:
    """Every symbol ``fn`` calls directly, in instruction order."""
    return [
        instr[2]
        for block in fn.blocks
        for instr in block.instrs
        if instr[0] == "call" and instr[2]
    ]


def _addresses(fn) -> list[str]:
    """Every symbol ``fn`` takes the address of, in instruction order."""
    return [
        instr[2]
        for block in fn.blocks
        for instr in block.instrs
        if instr[0] == "faddr"
    ]


class SiblingValueTest(unittest.TestCase):
    # Task 3 emits the thunk against the owner's symbol; these pin the
    # checker's half of that contract.
    UTIL = (
        "(mod util)"
        "(fn twice :i64 ((x :i64)) (ret (* x 2)))"
        "(fn apply :i64 ((f :(fn (:i64) :i64)) (x :i64)) (ret (f x)))"
        "(fn work :void ((n :i64)) (println n))"
    )

    def test_a_sibling_function_may_be_a_function_value(self):
        program = _parse(
            "(mod program)(use util)(fn main :i64 () (ret (apply twice 3)))",
            "program",
        )
        checked = check.check_program(
            resolve.program([program, _parse(self.UTIL, "util")])
        )
        self.assertEqual([cm.module.name for cm in checked], ["program", "util"])

    def test_a_sibling_function_may_be_spawned(self):
        program = _parse(
            "(mod program)(use util)"
            "(fn main :i64 () (let t (spawn work 1)) (join t) (ret 0))",
            "program",
        )
        checked = check.check_program(
            resolve.program([program, _parse(self.UTIL, "util")])
        )
        self.assertEqual([cm.module.name for cm in checked], ["program", "util"])
