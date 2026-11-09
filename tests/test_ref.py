"""The ``(ref (vec T))`` parameter: its argument rule and its escape refusals.

A ref is a parameter kind, not a value: the caller lends the callee the address
of its own vector descriptor, so a ``vec-push`` inside the callee grows the
caller's buffer, and nothing is copied or moved. The checker's share is exactly
that shape — the argument must be a mutable binding or another ref parameter
(E0304), and a ref may never leave the call that received it (E0305). The
lowerer's share is Task 4; here every case stops at the checker.
"""

from __future__ import annotations

import unittest

from logos import check, parser
from logos.check import CheckedModule, check_module
from logos.diag import LogosError
from logos.resolve import resolve
from logos.types import Prim, Ref, Vec


def checked(source: str) -> CheckedModule:
    """Parse and check one inline module, which imports nothing."""

    def loader(name: str, _asker: str):
        raise FileNotFoundError(name)

    return check_module(resolve(parser.parse(source, "m.logos"), loader))


def refusal(source: str) -> LogosError:
    """Check ``source`` and return the diagnostic it must raise."""
    try:
        checked(source)
    except LogosError as error:
        return error
    raise AssertionError("expected a diagnostic, but the module checked")


GOOD = """(mod r)
(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))
(fn main :i64 () (letmut v (vec :i64) (make (vec :i64))) (grow v) (vec-free v) (ret 0))
"""


class RefParameterTest(unittest.TestCase):
    """The happy path: a ref parameter and the call that fills it."""

    def test_a_ref_parameter_checks_clean(self):
        module = checked(GOOD)
        # The parameter keeps its ref type in the signature, and the callee's
        # own binding is marked as one so the container forms act through it.
        self.assertEqual(module.fn_sigs["grow"].params, (Ref(Vec(Prim("i64"))),))

    def test_passing_a_ref_to_a_ref_param_does_not_move_it(self):
        module = checked(
            "(mod r)"
            "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))"
            "(fn twice :void ((w (ref (vec :i64)))) (grow w) (grow w) (ret))"
        )
        self.assertIn("twice", module.fn_sigs)

    def test_a_ref_can_read_the_vector_it_borrows(self):
        checked(
            "(mod r)"
            "(fn inspect :i64 ((v (ref (vec :i64)))) (ret (vec-len v)))"
            "(fn first :i64 ((v (ref (vec :i64)))) (ret (vec-get v 0)))"
            "(fn fill :void ((v (ref (vec :i64)))) (vec-set v 0 1) (ret))"
            "(fn clear :void ((v (ref (vec :i64)))) (vec-free v) (ret))"
        )


class RefArgumentTest(unittest.TestCase):
    """E0304: the argument has to name a mutable binding."""

    def test_a_plain_let_argument_is_refused(self):
        error = refusal(GOOD.replace("(letmut v", "(let v"))
        self.assertEqual(error.code, "E0304")
        self.assertIn("mutable binding", error.message)
        self.assertIn("'v'", error.message)

    def test_a_temporary_argument_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))"
            "(fn f :void () (grow (make (vec :i64))) (ret))"
        )
        self.assertEqual(error.code, "E0304")

    def test_an_immutable_vector_argument_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))"
            "(fn f :void ((v (vec :i64))) (grow v) (ret))"
        )
        self.assertEqual(error.code, "E0304")


class RefEscapeTest(unittest.TestCase):
    """E0305: a ref may not leave the call, wherever it would be kept."""

    def test_a_returned_ref_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn f (ref (vec :i64)) ((v (ref (vec :i64)))) (ret v))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("a ref cannot escape the call", error.message)
        self.assertIn("returning it", error.message)
        self.assertEqual(error.path, "r/f/2")

    def test_a_captured_ref_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn f :i64 ((v (ref (vec :i64))))"
            "  (let g (fn :i64 () (vec-len v)))"
            "  (ret 0))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("a closure captures 'v'", error.message)

    def test_a_ref_pushed_into_a_vector_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn f :void ((v (ref (vec :i64))))"
            "  (letmut o (vec (vec :i64)) (make (vec (vec :i64))))"
            "  (vec-push o v)"
            "  (vec-free o)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")

    def test_a_ref_stored_in_a_field_is_refused(self):
        error = refusal(
            "(mod r)"
            "(type holder (struct (v (ref (vec :i64)))))"
            "(fn f :void ((v (ref (vec :i64)))) (letmut h (make holder v)) (ret))"
        )
        self.assertEqual(error.code, "E0305")

    def test_a_ref_passed_to_a_plain_parameter_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn take :void ((v (vec :i64))) (ret))"
            "(fn f :void ((w (ref (vec :i64)))) (take w) (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("argument 1 of 'take'", error.message)

    def test_an_allocated_ref_element_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn f :void ((n :i64))"
            "  (letmut p (own (ref (vec :i64))) (alloc (ref (vec :i64)) n))"
            "  (free p))"
        )
        self.assertEqual(error.code, "E0305")


class RefShapeTest(unittest.TestCase):
    """The parameter kinds a ref may not be, and the forms that keep refusing."""

    def test_a_ref_to_a_struct_is_e0100(self):
        error = refusal(
            "(mod r)"
            "(type point (struct (x :i64) (y :i64)))"
            "(fn g :void ((v (ref point))) (ret))"
        )
        self.assertEqual(error.code, "E0100")
        self.assertIn("a ref may name a vector only", error.message)

    def test_set_still_refuses_a_ref_parameter(self):
        error = refusal(
            "(mod r)"
            "(fn f :void ((v (ref (vec :i64)))) (set v (make (vec :i64))) (ret))"
        )
        self.assertEqual(error.code, "E0104")

    def test_set_field_still_refuses_a_ref_parameter(self):
        error = refusal(
            "(mod r)"
            "(type point (struct (x :i64) (y :i64)))"
            "(fn f :void ((v (ref (vec :i64)))) (set-field v x 1) (ret))"
        )
        self.assertEqual(error.code, "E0104")
