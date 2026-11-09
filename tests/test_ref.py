"""The ``(ref (vec T))`` parameter: its argument rule and its escape refusals.

A ref is a parameter kind, not a value: the caller lends the callee the address
of its own vector descriptor, so a ``vec-push`` inside the callee grows the
caller's buffer, and nothing is copied or moved. The checker's share is exactly
that shape — the argument must be a mutable binding or another ref parameter
(E0304), and a ref may never leave the call that received it (E0305). The
lowerer's share is the IR at the bottom of this file: the parameter is a
pointer, the call passes the address of the caller's slot, and every vector
form reads and writes the descriptor the pointer names.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

from logos import check, driver, llvm, lower, parser
from logos.check import CheckedModule, check_module
from logos.diag import LogosError
from logos.resolve import program, resolve
from logos.types import Prim, Ref, Vec

ROOT = Path(__file__).resolve().parents[1]


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


def emitted(source: str) -> str:
    """Lower one inline module and return its LLVM text."""
    return llvm.emit(lower.lower_module(checked(source)))


def build_and_run(name: str, source: str, opt: str) -> subprocess.CompletedProcess:
    """Build ``source`` at ``opt`` into ``build/`` and run it once.

    A debug build, so a block still live at exit lands on stderr and the test
    can see it rather than a silent pass.
    """
    path = ROOT / "build" / f"{name}.logos"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    out = str(ROOT / "build" / f"{name}{opt[1:]}")
    driver.build(str(path), out, opt=opt, debug=True)
    return subprocess.run([out], capture_output=True, text=True)


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
        # The diagnostic sits at the call, never at the parameter: a token
        # argument has no sub-path of its own.
        self.assertEqual(error.path, "r/main/3")

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

    # -- the two paths C1 found open --------------------------------------

    def test_a_channel_of_refs_is_refused(self):
        # The ring copies its elements into a thread and outlives the call
        # that lent the ref, so no value of this type could ever be sent.
        error = refusal(
            "(mod r)"
            "(fn f :void ((c (shared (chan (ref (vec :i64)))))) (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("a ref cannot escape the call", error.message)
        self.assertIn("channel", error.message)
        self.assertEqual(error.path, "r/f/1/0/0")

    def test_a_channel_of_a_struct_holding_a_ref_is_refused(self):
        # The element walk descends named aggregates: a struct field is not a
        # place the channel type can see, so spelling the struct must not hide
        # the ref inside it.
        error = refusal(
            "(mod r)"
            "(type holder (struct (v (ref (vec :i64)))))"
            "(fn f :void ((c (shared (chan holder)))) (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("channel", error.message)

    def test_a_ref_sent_on_a_channel_is_refused(self):
        # The reviewer's program. The declaration now refuses it before the
        # send can be reached; ``_send`` states the same rule for the value.
        error = refusal(
            "(mod r)"
            "(fn f :void ((v (ref (vec :i64))))"
            "  (letmut c (chan (ref (vec :i64)) 2))"
            "  (send c v)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("channel", error.message)
        self.assertEqual(error.path, "r/f/2/1")

    def test_a_ref_spawn_argument_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))"
            "(fn mid :void ((w (ref (vec :i64))))"
            "  (letmut t :thread (spawn grow w))"
            "  (join t)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("a ref cannot escape the call", error.message)
        self.assertEqual(error.path, "r/mid/2/2")

    def test_a_copied_ref_spawn_argument_is_refused(self):
        # The copy between the parameter and the spawn is legal — it names the
        # same descriptor — but the thread boundary is not: the copy is still a
        # ref and the thread outlives the caller's frame.
        error = refusal(
            "(mod r)"
            "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))"
            "(fn mid :void ((w (ref (vec :i64))))"
            "  (letmut x w)"
            "  (letmut t :thread (spawn grow x))"
            "  (join t)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertEqual(error.path, "r/mid/3/2")

    def test_a_ref_passed_to_a_function_value_is_refused(self):
        # A named callee cannot keep its argument; a function value can be
        # stored and called after the ref's frame is gone.
        error = refusal(
            "(mod r)"
            "(fn mid :void ((w (ref (vec :i64))))"
            "  (letmut g (fn :void ((p (ref (vec :i64)))) (vec-push p 1)))"
            "  (g w)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("function value", error.message)
        self.assertEqual(error.path, "r/mid/3")

    def test_a_ref_passed_to_a_named_function_binding_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))"
            "(fn mid :void ((w (ref (vec :i64))))"
            "  (letmut g grow)"
            "  (g w)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("function value", error.message)


class RefStorageTest(unittest.TestCase):
    """E0305 at each storage site a ref may not be written to."""

    def test_a_ref_written_into_a_vector_element_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn f :void ((v (ref (vec :i64))))"
            "  (letmut o (vec (ref (vec :i64))) (make (vec (ref (vec :i64)))))"
            "  (vec-set o 0 v)"
            "  (vec-free o)"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("vector element", error.message)
        self.assertEqual(error.path, "r/f/3")

    def test_a_ref_written_into_an_array_element_is_refused(self):
        error = refusal(
            "(mod r)"
            "(fn f :void ((v (ref (vec :i64))))"
            "  (letmut a (make (arr (ref (vec :i64)) 1) v))"
            "  (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("array element", error.message)
        self.assertEqual(error.path, "r/f/2/1")

    def test_a_ref_carried_in_an_enum_payload_is_refused(self):
        error = refusal(
            "(mod r)"
            "(type box (enum (of (ref (vec :i64)))))"
            "(fn f :void ((v (ref (vec :i64)))) (letmut b (of v)) (ret))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("enum 'box'", error.message)
        self.assertEqual(error.path, "r/f/2/1")

    def test_a_ref_carried_in_a_result_slot_is_refused(self):
        error = refusal(
            "(mod r)"
            "(type bad (enum (nope)))"
            "(fn f (res (ref (vec :i64)) bad) ((v (ref (vec :i64)))) (ret (ok v)))"
        )
        self.assertEqual(error.code, "E0305")
        self.assertIn("a result", error.message)
        self.assertEqual(error.path, "r/f/2/0")


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


TWO_REFS = """(mod two)

(fn bump :void ((a (ref (vec :i64))) (b (ref (vec :i64))))
  (vec-push a 1)
  (vec-push b 2)
  (vec-set a 0 7))

(fn main :i64 ()
  (letmut a (vec :i64) (make (vec :i64)))
  (letmut b (vec :i64) (make (vec :i64)))
  (bump a b)
  (println (vec-len a))
  (println (vec-len b))
  (println (vec-get a 0))
  (println (vec-get b 0))
  (vec-free a)
  (vec-free b)
  (ret 0))
"""

FREE_THROUGH_REF = """(mod ref-free)

(fn clear :void ((v (ref (vec :i64))))
  (vec-free v))

(fn main :i64 ()
  (letmut v (vec :i64) (make (vec :i64)))
  (vec-push v 1)
  (clear v)
  (println (vec-len v))
  (vec-free v)
  (ret 0))
"""

FORWARD = """(mod fwd)

(fn inner :void ((v (ref (vec :i64))))
  (vec-push v 1))

(fn outer :void ((v (ref (vec :i64))))
  (inner v)
  (inner v))

(fn main :i64 ()
  (letmut v (vec :i64) (make (vec :i64)))
  (outer v)
  (println (vec-len v))
  (vec-free v)
  (ret 0))
"""

GROW_THROUGH_REF = """(mod ref-grow)

(fn fill :void ((v (ref (vec :i64))))
  (vec-push v 10)
  (vec-push v 11)
  (vec-push v 12)
  (vec-push v 13)
  (vec-push v 14))

(fn main :i64 ()
  (letmut v (vec :i64) (make (vec :i64)))
  (fill v)
  (println (vec-len v))
  (println (vec-get v 0))
  (println (vec-get v 4))
  (vec-free v)
  (ret 0))
"""


class RefLoweringTest(unittest.TestCase):
    """The IR shape: a pointer slot, a slot address at the call, two loads."""

    def test_a_ref_parameter_is_a_pointer_to_the_descriptor(self):
        text = emitted(GOOD)
        # Pinned from the emitted text: the parameter is one pointer to the
        # three-word descriptor, never the descriptor itself.
        self.assertIn(
            "define internal void @lg.r.grow({ i64*, i64, i64 }* %v.0) {", text
        )

    def test_the_caller_passes_the_address_of_its_slot(self):
        text = emitted(GOOD)
        # ``%v.0.addr`` is the caller's own slot: the address is lent, so no
        # descriptor is copied and none is cleared.
        self.assertIn(
            "call void @lg.r.grow({ i64*, i64, i64 }* %v.0.addr)", text
        )

    def test_a_push_loads_the_pointer_then_the_descriptor(self):
        text = emitted(GOOD)
        self.assertIn(
            "  %t1 = load { i64*, i64, i64 }*, { i64*, i64, i64 }** %v.0.addr",
            text,
        )
        self.assertIn(
            "  %t2 = load { i64*, i64, i64 }, { i64*, i64, i64 }* %t1", text
        )
        # And the rewritten descriptor goes back through the same pointer, so
        # the caller's length and capacity move with the buffer. The rewritten
        # value is a temp whose number depends on allocation order elsewhere, so
        # pin the destination (``%t1``), not that index.
        self.assertRegex(
            text,
            r"  store \{ i64\*, i64, i64 \} %t\d+, \{ i64\*, i64, i64 \}\* %t1\n",
        )

    def test_forwarding_a_ref_loads_its_pointer_instead_of_the_slot_address(self):
        # ``(inner v)`` where ``v`` is itself a ref parameter: the callee wants
        # the descriptor's address, which is the pointer ``v`` already holds.
        # Taking the address of ``v``'s slot instead would hand it a pointer to
        # a pointer.
        text = emitted(FORWARD)
        start = text.index("define internal void @lg.fwd.outer")
        body = text[start : text.index("\n}\n", start)]
        calls = [line for line in body.splitlines() if "@lg.fwd.inner" in line]
        self.assertEqual(len(calls), 2)
        for line in calls:
            self.assertNotIn(".addr", line)
        loads = set(
            re.findall(
                r"  (%t\d+) = load \{ i64\*, i64, i64 \}\*, "
                r"\{ i64\*, i64, i64 \}\*\* %v\.0\.addr",
                body,
            )
        )
        self.assertTrue(loads)
        for line in calls:
            match = re.search(r"\(\{ i64\*, i64, i64 \}\* (%t\d+)\)", line)
            if match is None:
                self.fail(f"not a pointer argument: {line}")
            # The argument is one of the pointers loaded out of the ref's slot.
            self.assertIn(match.group(1), loads, line)

    def test_two_ref_parameters_are_two_pointers(self):
        text = emitted(TWO_REFS)
        self.assertIn(
            "define internal void @lg.two.bump({ i64*, i64, i64 }* %v.0, "
            "{ i64*, i64, i64 }* %v.1) {",
            text,
        )

    def test_a_ref_in_an_imported_signature_keeps_its_pointer(self):
        # A build set of two modules qualifies every type in a sibling's
        # signature: the ref must survive that walk as the same pointer.
        checked = check.check_program(
            program(
                [
                    parser.parse(
                        "(mod prog)\n(use util)\n"
                        "(fn main :i64 ()"
                        " (letmut v (vec :i64) (make (vec :i64)))"
                        " (grow v) (vec-free v) (ret 0))",
                        "prog.logos",
                    ),
                    parser.parse(
                        "(mod util)\n"
                        "(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))",
                        "util.logos",
                    ),
                ]
            )
        )
        text = llvm.emit(lower.lower_program(checked))
        self.assertIn(
            "define internal void @lg.util.grow({ i64*, i64, i64 }* %v.0)", text
        )
        self.assertIn(
            "call void @lg.util.grow({ i64*, i64, i64 }* %v.0.addr)", text
        )


class RefRuntimeTest(unittest.TestCase):
    """The caller's descriptor, observed after the callee returns."""

    def test_each_of_two_refs_grows_its_own_descriptor(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                result = build_and_run("test-ref-two", TWO_REFS, opt)
                self.assertEqual(result.returncode, 0, result.stderr)
                # Each length grew by its own push; the set through ``a`` did
                # not reach ``b``.
                self.assertEqual(result.stdout, "1\n1\n7\n2\n")
                self.assertEqual(result.stderr, "")

    def test_vec_free_through_a_ref_zeroes_the_callers_descriptor(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                result = build_and_run("test-ref-free", FREE_THROUGH_REF, opt)
                self.assertEqual(result.returncode, 0, result.stderr)
                # The callee released the buffer and zeroed the descriptor the
                # pointer names, so the caller reads length 0 and its own
                # ``vec-free`` is a harmless free(NULL). No block leaks.
                self.assertEqual(result.stdout, "0\n")
                self.assertEqual(result.stderr, "")

    def test_a_ref_forwarded_to_another_ref_grows_the_callers_vector(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                result = build_and_run("test-ref-forward", FORWARD, opt)
                self.assertEqual(result.returncode, 0, result.stderr)
                # Both pushes happened through ``outer``'s ref and landed in
                # the descriptor ``main`` owns.
                self.assertEqual(result.stdout, "2\n")
                self.assertEqual(result.stderr, "")

    def test_five_pushes_through_a_ref_grow_a_live_buffer(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                result = build_and_run("test-ref-grow", GROW_THROUGH_REF, opt)
                self.assertEqual(result.returncode, 0, result.stderr)
                # Five pushes grow 0 -> 4 -> 12. The second growth copies the
                # four live elements through the ref and releases the old
                # block; the caller still reads 10 first and 14 last.
                self.assertEqual(result.stdout, "5\n10\n14\n")
                self.assertEqual(result.stderr, "")
