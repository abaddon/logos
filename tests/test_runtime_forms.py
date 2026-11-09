"""The five runtime access forms: files, arguments and one string's bytes.

``(read-file p)``, ``(args)``, ``(str-byte s i)``, ``(str-from-i64 v)`` and
``(f64-bits v)`` are the small half of the self-hosted compiler's runtime
surface: the C functions exist (``rt_read_file``, ``rt_args``,
``rt_str_from_i64``) and nothing in the language could reach them.

Each form is pinned at the three layers the string surface already uses: the
type the checker gives it, the diagnostic a wrong program gets, and the call
the lowerer makes. The corpus cases in ``tests/exec`` carry the end-to-end
expectations in their ``(expect ...)`` directives; the last class restates them
here so a regression names the form rather than a corpus line.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from logos import driver, ir, lower
from logos.check import CheckedModule, check_module
from logos.diag import LogosError
from logos.parser import parse
from logos.resolve import resolve
from logos.types import Prim, Vec

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "tests" / "exec"
BUILD = ROOT / "build"


def checked(source: str) -> CheckedModule:
    """Parse and check one inline module, which imports nothing."""

    def loader(name: str, _asker: str):
        raise FileNotFoundError(name)

    return check_module(resolve(parse(source, "m.logos"), loader))


def path_of(cm: CheckedModule, kind: str) -> str:
    """The node path of the first node of ``kind`` in ``cm``."""
    for node in cm.module.root.walk():
        if node.kind == kind:
            return node.path
    raise AssertionError(f"no '{kind}' node in the module")


def type_of(cm: CheckedModule, kind: str):
    return cm.expr_types[path_of(cm, kind)]


def fail_on(source: str) -> LogosError:
    """The checker diagnostic ``source`` raises; fails if it checks."""
    try:
        checked(source)
    except LogosError as error:
        return error
    raise AssertionError(f"expected a diagnostic, but this checked: {source}")


def lowered(source: str) -> ir.IrModule:
    return lower.lower_module(checked(source))


def call_names(fn: ir.IrFn) -> list[str]:
    return [i[2] for b in fn.blocks for i in b.instrs if i[0] == "call"]


def ops(fn: ir.IrFn, opcode: str) -> list[tuple]:
    return [i for b in fn.blocks for i in b.instrs if i[0] == opcode]


def main_of(module: ir.IrModule) -> ir.IrFn:
    return next(fn for fn in module.functions if fn.name.endswith("main"))


def declares(module: ir.IrModule) -> dict[str, tuple[tuple, object]]:
    return {decl.name: (decl.params, decl.ret) for decl in module.declares}


class ReadFileCheckTest(unittest.TestCase):
    """``(read-file p)``: the whole file as a ``:str``."""

    def test_read_file_is_a_str(self):
        cm = checked('(mod m)(fn f :str () (ret (read-file "/dev/null")))')
        self.assertEqual(type_of(cm, "read-file"), Prim("str"))

    def test_read_file_takes_a_str(self):
        error = fail_on("(mod m)(fn f :str () (ret (read-file 5)))")
        self.assertEqual(error.code, "E0100")
        self.assertEqual(error.message, "'read-file' takes a :str, found :i64")

    def test_the_diagnostic_names_the_argument_node(self):
        error = fail_on("(mod m)(fn f :str ((s :str)) (ret (read-file (str-len s))))")
        self.assertEqual(error.code, "E0100")
        # The operand is a node, so the diagnostic is at that node rather than
        # at the form.
        self.assertEqual(error.path, "m/f/2/0/0")

    def test_read_file_takes_one_argument(self):
        error = fail_on('(mod m)(fn f :str () (ret (read-file "a" "b")))')
        self.assertEqual(error.code, "E0102")
        self.assertEqual(error.message, "'read-file' takes a :str")


class ArgsCheckTest(unittest.TestCase):
    """``(args)``: the command line as a tracked ``(vec :str)``."""

    def test_args_is_a_vector_of_str(self):
        cm = checked(
            "(mod m)(fn f :i64 () (letmut a (args)) (ret (vec-len a)))"
        )
        self.assertEqual(type_of(cm, "args"), Vec(Prim("str")))

    def test_args_takes_nothing(self):
        error = fail_on("(mod m)(fn f :i64 () (letmut a (args 1)) (ret 0))")
        self.assertEqual(error.code, "E0102")
        self.assertEqual(error.message, "'args' takes no arguments")


class StrByteCheckTest(unittest.TestCase):
    """``(str-byte s i)``: one byte, as ``:u8``."""

    def test_str_byte_is_a_u8(self):
        cm = checked('(mod m)(fn f :u8 () (ret (str-byte "abc" 1)))')
        self.assertEqual(type_of(cm, "str-byte"), Prim("u8"))

    def test_the_string_operand_must_be_a_str(self):
        error = fail_on("(mod m)(fn f :u8 () (ret (str-byte 1 0)))")
        self.assertEqual(error.code, "E0100")
        self.assertEqual(error.message, "'str-byte' takes a :str, found :i64")

    def test_the_index_must_be_an_integer(self):
        error = fail_on('(mod m)(fn f :u8 () (ret (str-byte "abc" "x")))')
        self.assertEqual(error.code, "E0100")
        self.assertEqual(
            error.message, "'str-byte' needs an integer index, found :str"
        )

    def test_str_byte_takes_two_arguments(self):
        error = fail_on('(mod m)(fn f :u8 () (ret (str-byte "abc")))')
        self.assertEqual(error.code, "E0102")
        self.assertEqual(error.message, "'str-byte' takes a :str and an index")


class StrFromI64CheckTest(unittest.TestCase):
    """``(str-from-i64 v)``: an integer written in decimal, as ``:str``."""

    def test_str_from_i64_is_a_str(self):
        cm = checked("(mod m)(fn f :str () (ret (str-from-i64 -42)))")
        self.assertEqual(type_of(cm, "str-from-i64"), Prim("str"))

    def test_every_integer_width_is_accepted(self):
        for param in ("a :i8", "b :u64"):
            with self.subTest(param=param):
                name = param.split()[0]
                cm = checked(
                    f"(mod m)(fn f :str (({param})) (ret (str-from-i64 {name})))"
                )
                self.assertEqual(type_of(cm, "str-from-i64"), Prim("str"))

    def test_the_operand_must_be_an_integer(self):
        error = fail_on('(mod m)(fn f :str () (ret (str-from-i64 "1.5")))')
        self.assertEqual(error.code, "E0100")
        self.assertEqual(
            error.message, "'str-from-i64' needs an integer, found :str"
        )

    def test_str_from_i64_takes_one_argument(self):
        error = fail_on("(mod m)(fn f :str () (ret (str-from-i64 1 2)))")
        self.assertEqual(error.code, "E0102")
        self.assertEqual(error.message, "'str-from-i64' takes an integer")


class F64BitsCheckTest(unittest.TestCase):
    """``(f64-bits v)``: the binary64 pattern as ``:i64``."""

    def test_f64_bits_is_an_i64(self):
        cm = checked("(mod m)(fn f :i64 () (ret (f64-bits 1.5)))")
        self.assertEqual(type_of(cm, "f64-bits"), Prim("i64"))

    def test_the_operand_must_be_an_f64(self):
        error = fail_on("(mod m)(fn f :i64 ((b :bool)) (ret (f64-bits b)))")
        self.assertEqual(error.code, "E0100")
        self.assertEqual(error.message, "'f64-bits' takes a :f64, found :bool")

    def test_f64_bits_takes_one_argument(self):
        error = fail_on("(mod m)(fn f :i64 () (ret (f64-bits 1.5 2.5)))")
        self.assertEqual(error.code, "E0102")
        self.assertEqual(error.message, "'f64-bits' takes a :f64")


class ReservedNameTest(unittest.TestCase):
    """A definition of a form's name could never be called (E0003)."""

    FORMS = ("read-file", "args", "str-byte", "str-from-i64", "f64-bits")

    def test_a_function_may_not_spell_a_form(self):
        for name in self.FORMS:
            with self.subTest(name=name):
                error = fail_on(f"(mod m)(fn {name} :i64 () (ret 0))")
                self.assertEqual(error.code, "E0003")
                self.assertEqual(error.message, "reserved form name")

    def test_a_type_may_not_spell_a_form(self):
        for name in self.FORMS:
            with self.subTest(name=name):
                error = fail_on(f"(mod m)(type {name} (struct (x :i64)))")
                self.assertEqual(error.code, "E0003")
                self.assertEqual(error.message, "reserved form name")


class ReadFileLoweringTest(unittest.TestCase):
    def test_the_lowering_calls_the_runtime(self):
        module = lowered(
            '(mod m)(fn main :void () (println (str-len (read-file "/dev/null"))))'
        )
        fn = main_of(module)
        self.assertIn("rt_read_file", call_names(fn))
        params, ret = declares(module)["rt_read_file"]
        self.assertEqual(ret, Prim("i64"))
        self.assertEqual(len(params), 4)

    def test_the_node_path_is_the_call_s_own(self):
        module = lowered('(mod m)(fn main :void () (println (str-len (read-file "/x"))))')
        pat = [g.data for g in module.globals if g.data == b"m/main/2/0/0\x00"]
        self.assertEqual(pat, [b"m/main/2/0/0\x00"])


class ArgsLoweringTest(unittest.TestCase):
    def test_the_lowering_builds_a_tracked_vector(self):
        module = lowered(
            "(mod m)(fn main :void () (letmut a (args)) (vec-free a))"
        )
        fn = main_of(module)
        names = call_names(fn)
        self.assertIn("rt_args", names)
        # The pairs are copied into a buffer the caller owns, so the copy is
        # tracked and ``vec-free`` can release it.
        self.assertIn("rt_alloc", names)
        self.assertIn("memcpy", names)
        self.assertIn("rt_free", names)


class StrToolsLoweringTest(unittest.TestCase):
    def test_str_byte_loads_one_byte_after_a_bounds_check(self):
        module = lowered('(mod m)(fn main :void () (println (str-byte "abc" 1)))')
        fn = main_of(module)
        loads = [i for i in ops(fn, "load") if i[2] == Prim("u8")]
        self.assertTrue(loads, "str-byte must load one u8")
        paths = [g.data for g in module.globals]
        self.assertIn(b"byte index out of bounds\x00", paths)
        self.assertIn("rt_panic", call_names(fn))

    def test_str_from_i64_calls_the_runtime(self):
        module = lowered("(mod m)(fn main :void () (println (str-from-i64 -42)))")
        self.assertIn("rt_str_from_i64", call_names(main_of(module)))
        self.assertIn("rt_str_from_i64", declares(module))

    def test_f64_bits_is_a_bitcast(self):
        module = lowered("(mod m)(fn main :void () (println (f64-bits 1.5)))")
        casts = [
            i
            for i in ops(main_of(module), "bitcast")
            if i[2] == Prim("f64") and i[3] == Prim("i64")
        ]
        self.assertTrue(casts, "f64-bits must bitcast double to i64")


class RuntimeFormsExecTest(unittest.TestCase):
    """The three corpus cases, at both optimisation levels."""

    def build(self, stem: str, case: str, opt: str) -> str:
        BUILD.mkdir(parents=True, exist_ok=True)
        out = str(BUILD / f"runtime-forms-{stem}-{opt[1:]}")
        driver.run_test(str(EXEC / f"{stem}.logos"), case, out, opt=opt)
        return out

    def run_case(self, stem: str, case: str, opt: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.build(stem, case, opt)], capture_output=True, timeout=60
        )

    def test_str_tools_prints_a_byte_an_integer_and_a_bit_pattern(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                done = self.run_case("str-tools", "str-tools", opt)
                self.assertEqual(done.stdout, b"98\n-42\n4609434218613702656\n", done.stderr)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn(b"LEAK", done.stderr)

    def test_read_file_reads_dev_null_and_panics_on_a_missing_path(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                done = self.run_case("read-file", "read-file", opt)
                self.assertEqual(done.stdout, b"0\n", done.stderr)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn(
                    b"R0007: could not read /nonexistent/logos-w2/read-file.logos",
                    done.stderr,
                )
                # The panic names the call's node path, not the runtime.
                self.assertIn(b"read-file/test/read-file/", done.stderr)

    def test_args_holds_at_least_the_program(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                done = self.run_case("args", "args", opt)
                self.assertEqual(done.stdout, b"true\n", done.stderr)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn(b"LEAK", done.stderr)
