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
