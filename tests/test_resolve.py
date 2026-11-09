"""Tests for name resolution: the module index, imports, duplicates and cycles.

The resolver runs on a parsed tree and answers what a module contains, what it
imports and whether any name means two things. Expressions are not its
business: the checker owns the body vocabulary, so a form inside a ``fn`` is
never an E0002 here.
"""

import unittest
from pathlib import Path

from logos import driver
from logos.diag import LogosError
from logos.parser import parse
from logos.resolve import Module, reachable, resolve

PARSE = Path(__file__).parent / "parse"

#: Every resolver-owned negative fixture, by path under ``tests/parse``.
#:
#: The expected code is also in the fixture's ``.expect`` sidecar; the second
#: element is the node path the diagnostic must carry. ``None`` means the file
#: has no node to point at — a file that never declares a module is located by
#: its source position instead.
RESOLVER_FIXTURES = {
    "no-mod.logos": ("E0002", None),
    "nameless-mod.logos": ("E0002", "0"),
    "second-mod.logos": ("E0003", "m/n"),
    "unknown-node.logos": ("E0002", "m/0"),
    "duplicate-fn.logos": ("E0003", "m/f"),
    "duplicate-test.logos": ("E0003", "m/test/t"),
    "extern-fn-collision.logos": ("E0003", "m/get"),
    "use-no-name.logos": ("E0002", "m/0"),
    "use-two-names.logos": ("E0002", "m/0"),
    "multi-module/unknown-module.logos": ("E0005", "missing/0"),
    "multi-module/wrong-name.logos": ("E0005", "wrong-name/0"),
    "multi-module/cycle/root.logos": ("E0004", "b/0"),
    "multi-module/merge/root.logos": ("E0003", "merge/1"),
}


def resolve_src(src: str, files: dict[str, str] | None = None) -> Module:
    """Resolve ``src`` with ``files`` as the loader's store.

    The source is always named ``a.logos``, whatever its ``mod`` form says: the
    resolver never compares a file name to a module name, so ``(mod math)`` in
    ``a.logos`` is legal here. Mapping a name to the file that answers it, and
    enforcing any name-must-equal-file rule, belongs to the loader.
    """
    sources = dict(files or {})

    def loader(module: str, _asker: str):
        if module not in sources:
            raise FileNotFoundError(module)
        return parse(sources[module], f"{module}.logos")

    return resolve(parse(src, "a.logos"), loader, "a.logos")


class ModuleTest(unittest.TestCase):
    def test_module_indexes_its_definitions(self):
        module = resolve_src(
            "(mod math)"
            "(type point (struct (x :i64)))"
            "(fn add :i64 ((a :i64) (b :i64)) (ret a))"
            "(test add (expect (code 0)))"
        )
        self.assertIsInstance(module, Module)
        self.assertEqual(module.name, "math")
        self.assertEqual(list(module.types), ["point"])
        self.assertEqual(list(module.fns), ["add"])
        self.assertEqual(list(module.tests), ["add"])
        self.assertEqual(module.fns["add"].path, "math/add")
        self.assertEqual(module.tests["add"].path, "math/test/add")
        self.assertEqual(module.imports, {})

    def test_a_test_and_a_fn_may_share_a_name(self):
        module = resolve_src("(mod m)(fn f :i64 () (ret 0))(test f (expect (code 0)))")
        self.assertEqual(list(module.fns), ["f"])
        self.assertEqual(list(module.tests), ["f"])

    def test_a_module_form_must_exist(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(fn f :i64 () (ret 0))")
        self.assertEqual(caught.exception.code, "E0002")
        self.assertIn("mod", caught.exception.message)

    def test_a_missing_module_form_is_located_by_file(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(fn f :i64 () (ret 0))")
        error = caught.exception
        # No node stands for the absent form, so the location is the source's.
        self.assertEqual(error.path, "")
        self.assertEqual(error.location, "a.logos:1:1")
        self.assertEqual(
            error.render(), "E0002 a.logos:1:1: missing (mod ...) form"
        )

    def test_a_missing_module_form_without_a_file_name_has_no_location(self):
        # Backward compatibility: the two-argument call is still supported and
        # simply has no source to point at.
        def loader(name: str, _asker: str):
            raise FileNotFoundError(name)

        with self.assertRaises(LogosError) as caught:
            resolve(parse("(fn f :i64 () (ret 0))", "a.logos"), loader)
        self.assertEqual(caught.exception.render(), "E0002: missing (mod ...) form")

    def test_a_module_form_needs_a_name(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod)(fn f :i64 () (ret 0))")
        self.assertEqual(caught.exception.code, "E0002")
        self.assertIn("name", caught.exception.message)

    def test_a_second_module_form_is_a_duplicate(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(mod n)")
        self.assertEqual(caught.exception.code, "E0003")

    def test_expect_error_is_a_module_level_directive(self):
        module = resolve_src("(mod m)(expect-error E0002)")
        self.assertEqual((module.types, module.fns, module.tests), ({}, {}, {}))


class DuplicateTest(unittest.TestCase):
    def test_duplicate_fn_reports_the_second_path(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(fn f :i64 () (ret 0))(fn f :i64 () (ret 1))")
        error = caught.exception
        self.assertEqual(error.code, "E0003")
        self.assertEqual(error.path, "m/f")
        self.assertEqual(error.render(), "E0003 m/f: duplicate definition 'f'")

    def test_duplicate_type_reports_the_second_path(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(type p (struct))(type p (struct))")
        self.assertEqual(caught.exception.code, "E0003")
        self.assertEqual(caught.exception.path, "m/p")

    def test_a_duplicate_through_an_import_names_both_paths(self):
        # The module's own ``f`` and the one the import brought in are two
        # declarations; the message has to say which, or a reader cannot tell
        # which one to rename.
        other = {"other": "(mod other)(fn f :i64 () (ret 1))"}
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(use other)(fn f :i64 () (ret 0))", other)
        error = caught.exception
        self.assertEqual(error.code, "E0003")
        self.assertEqual(error.path, "m/f")
        self.assertIn("other/f", error.message)
        self.assertIn("m/f", error.message)

    def test_a_duplicate_through_an_import_names_both_paths_in_either_order(self):
        other = {"other": "(mod other)(fn f :i64 () (ret 1))"}
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(fn f :i64 () (ret 0))(use other)", other)
        error = caught.exception
        self.assertEqual(error.code, "E0003")
        self.assertIn("other/f", error.message)
        self.assertIn("m/f", error.message)

    def test_a_fn_and_a_type_may_not_share_a_name(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(type p (struct))(fn p :i64 () (ret 0))")
        self.assertEqual(caught.exception.code, "E0003")
        self.assertEqual(caught.exception.path, "m/p")

    def test_duplicate_test_reports_its_path(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(test t (expect (code 0)))(test t (expect (code 1)))")
        self.assertEqual(caught.exception.code, "E0003")
        self.assertEqual(caught.exception.path, "m/test/t")

    def test_a_local_definition_may_not_repeat_an_imported_name(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src(
                "(mod a)(fn f :i64 () (ret 0))(use b)",
                {"b": "(mod b)(fn f :i64 () (ret 1))"},
            )
        self.assertEqual(caught.exception.code, "E0003")
        self.assertEqual(caught.exception.path, "a/1")

    def test_a_definition_after_an_import_is_the_duplicate(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src(
                "(mod a)(use b)(fn f :i64 () (ret 0))",
                {"b": "(mod b)(fn f :i64 () (ret 1))"},
            )
        self.assertEqual(caught.exception.code, "E0003")
        self.assertEqual(caught.exception.path, "a/f")


class ImportTest(unittest.TestCase):
    def test_an_import_is_resolved_and_recorded(self):
        module = resolve_src(
            "(mod a)(use b)(fn f :i64 () (ret 0))",
            {"b": "(mod b)(fn g :i64 () (ret 0))"},
        )
        self.assertEqual(list(module.imports), ["b"])
        imported = module.imports["b"]
        self.assertEqual(imported.name, "b")
        self.assertEqual(list(imported.fns), ["g"])
        # Imports are recorded, not copied: ``fns`` holds this module's own.
        self.assertEqual(list(module.fns), ["f"])

    def test_imports_are_not_transitive(self):
        module = resolve_src(
            "(mod a)(use b)",
            {
                "b": "(mod b)(use c)",
                "c": "(mod c)(fn h :i64 () (ret 0))",
            },
        )
        self.assertEqual(list(module.imports), ["b"])
        self.assertEqual(list(module.imports["b"].imports), ["c"])
        self.assertEqual(module.fns, {})

    def test_a_diamond_loads_each_module_once(self):
        loaded: list[str] = []
        sources = {
            "b": "(mod b)(use d)",
            "c": "(mod c)(use d)",
            "d": "(mod d)(fn h :i64 () (ret 0))",
        }

        def loader(name: str, _asker: str):
            loaded.append(name)
            return parse(sources[name], f"{name}.logos")

        module = resolve(parse("(mod a)(use b)(use c)", "a.logos"), loader)
        self.assertEqual(loaded, ["b", "d", "c"])
        self.assertIs(module.imports["b"].imports["d"], module.imports["c"].imports["d"])

    def test_the_same_import_twice_is_one_import(self):
        module = resolve_src(
            "(mod a)(use b)(use b)",
            {"b": "(mod b)(fn g :i64 () (ret 0))"},
        )
        self.assertEqual(list(module.imports), ["b"])

    def test_use_needs_one_module_name(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(use)")
        self.assertEqual(caught.exception.code, "E0002")
        self.assertEqual(caught.exception.path, "m/0")

    def test_an_unknown_module_is_a_name_not_found(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod a)(use b)")
        error = caught.exception
        self.assertEqual(error.code, "E0005")
        self.assertEqual(error.path, "a/0")
        self.assertIn("b", error.message)

    def test_a_module_that_declares_another_name_is_not_found(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod a)(use b)", {"b": "(mod c)"})
        self.assertEqual(caught.exception.code, "E0005")
        self.assertEqual(caught.exception.path, "a/0")

    def test_a_use_name_that_differs_from_the_declared_name_is_not_found(self):
        """The resolver's whole contract: the tree must declare the name asked for.

        The loader supplies ``c.logos`` for ``c``, so the file name agrees with
        the request; the tree inside declares ``d``. The resolver has no file
        names to compare, so it reports the mismatch at the ``use`` that asked
        for ``c``. Enforcing that a file is named after its module is the
        loader's rule, not this pass's.
        """
        with self.assertRaises(LogosError) as caught:
            resolve_src(
                "(mod a)(use b)",
                {"b": "(mod b)(use c)", "c": "(mod d)"},
            )
        error = caught.exception
        self.assertEqual(error.code, "E0005")
        self.assertEqual(error.path, "b/0")
        self.assertIn("'c'", error.message)
        self.assertIn("'d'", error.message)


class CycleTest(unittest.TestCase):
    def test_circular_import_lists_the_cycle(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod a)(use b)", files={"b": "(mod b)(use a)"})
        error = caught.exception
        self.assertEqual(error.code, "E0004")
        self.assertIn("a -> b -> a", error.message)
        self.assertEqual(error.path, "b/0")

    def test_a_self_import_is_a_cycle(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod a)(use a)")
        error = caught.exception
        self.assertEqual(error.code, "E0004")
        self.assertIn("a -> a", error.message)

    def test_a_cycle_is_reported_from_its_first_module(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src(
                "(mod a)(use b)",
                {"b": "(mod b)(use c)", "c": "(mod c)(use b)"},
            )
        self.assertIn("b -> c -> b", caught.exception.message)


class ReachableTest(unittest.TestCase):
    """The import closure a build set lowers, root first and each name once."""

    def test_a_root_and_a_two_hop_chain_are_each_answered_once(self):
        root = resolve_src(
            "(mod a)(use b)(fn fa :i64 () (ret 1))",
            {
                "b": "(mod b)(use c)(fn fb :i64 () (ret 2))",
                "c": "(mod c)(fn fc :i64 () (ret 3))",
            },
        )
        modules = reachable([root])
        self.assertEqual([module.name for module in modules], ["a", "b", "c"])
        self.assertEqual(len(modules), len({module.name for module in modules}))

    def test_two_roots_share_one_answer_for_a_diamond(self):
        left = resolve_src("(mod left)(use base)", {"base": "(mod base)"})
        right = resolve_src("(mod right)(use base)", {"base": "(mod base)"})
        modules = reachable([left, right])
        self.assertEqual([module.name for module in modules], ["left", "base", "right"])


class UnknownNodeTest(unittest.TestCase):
    def test_an_unknown_module_level_form_is_E0002(self):
        with self.assertRaises(LogosError) as caught:
            resolve_src("(mod m)(wat 1)")
        error = caught.exception
        self.assertEqual(error.code, "E0002")
        self.assertEqual(error.path, "m/0")
        self.assertEqual(error.render(), "E0002 m/0: unknown node 'wat'")

    def test_the_negative_corpus_case_matches_its_expect_file(self):
        source = (PARSE / "unknown-node.logos").read_text(encoding="utf-8")
        expected = (PARSE / "unknown-node.expect").read_text(encoding="utf-8").strip()
        with self.assertRaises(LogosError) as caught:
            resolve_src(source)
        self.assertEqual(caught.exception.code, expected)


class ResolverFixturesTest(unittest.TestCase):
    """The resolver-owned negative corpus, judged as the compiler judges it.

    Each fixture is loaded through the driver, so the test sees the same
    loader, standard-library path and import walk a build does. The expected
    code is read from the sidecar rather than restated, and the table above
    must cover every ``.expect`` under ``tests/parse`` — a new fixture that
    nobody wired into the table fails instead of sitting unread.
    """

    def test_the_table_covers_every_negative_fixture(self):
        found = {
            path.relative_to(PARSE).as_posix()
            for path in PARSE.rglob("*.expect")
        }
        declared = {
            key.removesuffix(".logos") + ".expect" for key in RESOLVER_FIXTURES
        }
        self.assertEqual(found, declared)

    def test_each_fixture_agrees_with_its_expect_file(self):
        for relative, (code, path) in RESOLVER_FIXTURES.items():
            with self.subTest(fixture=relative):
                fixture = PARSE / relative
                expected = fixture.with_suffix(".expect").read_text(
                    encoding="utf-8"
                ).strip()
                self.assertEqual(expected, code)
                with self.assertRaises(LogosError) as caught:
                    driver.load_program([str(fixture)])
                error = caught.exception
                self.assertEqual(error.code, expected)
                if path is None:
                    # No node stands for an absent ``(mod ...)``. The source
                    # position is the only location that can exist, and the
                    # error must carry it rather than an empty message.
                    self.assertEqual(error.path, "")
                    self.assertEqual(error.file, str(fixture))
                    self.assertEqual(error.location, f"{fixture}:1:1")
                else:
                    self.assertEqual(error.path, path)

    def test_the_cycle_fixture_lists_the_whole_cycle(self):
        with self.assertRaises(LogosError) as caught:
            driver.load_program(
                [str(PARSE / "multi-module" / "cycle" / "root.logos")]
            )
        self.assertEqual(caught.exception.code, "E0004")
        self.assertIn("a -> b -> a", caught.exception.message)

    def test_the_merge_fixture_names_both_sides(self):
        # A collision through a ``use`` is only actionable when the message
        # says which local definition and which imported one collided.
        with self.assertRaises(LogosError) as caught:
            driver.load_program(
                [str(PARSE / "multi-module" / "merge" / "root.logos")]
            )
        error = caught.exception
        self.assertEqual(error.code, "E0003")
        self.assertIn("merge/f", error.message)
        self.assertIn("other/f", error.message)


if __name__ == "__main__":
    unittest.main()
