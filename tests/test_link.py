import tempfile
import unittest
from pathlib import Path

from logos import check, parser, resolve
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


class ImportOutsideTheSetTest(unittest.TestCase):
    def test_a_shared_plain_name_does_not_make_an_unbuilt_import_legal(self):
        # ``m1`` is loaded from disk, so nothing emits its symbol; ``b``'s
        # ``helper`` is in the build set but it is not the body the call
        # reached.
        directory = Path(tempfile.mkdtemp())
        _parse("(mod m1)(fn helper :i64 ((v :i64)) (ret 7))", "m1", directory)
        a = _parse(
            "(mod a)(use m1)(fn main :i64 () (ret (helper 1)))", "a", directory
        )
        b = _parse("(mod b)(fn helper :i64 ((v :i64)) (ret 2))", "b", directory)
        modules = resolve.program([a, b])
        with self.assertRaises(LogosError) as caught:
            check.check_program(modules)
        self.assertEqual(caught.exception.code, "E0103")
        self.assertIn("helper", caught.exception.message)


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
