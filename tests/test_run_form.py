"""``(run prog args)`` and the three readers of its ``:run`` handle.

A child process is one opaque handle: ``(run "sh" argv)`` starts it, and
``(run-status r)``, ``(run-out r)`` and ``(run-err r)`` read what it did. The
handle is a primitive, not a struct, so the only operations on it are the
three the compiler knows — a ``:run`` cannot be built, copied from a struct or
inspected.

The arguments are the interesting part: the vector is **moved** into the call
and the form releases it, because the runtime copies every string it needs
before it returns. The tests pin that transfer (a second use is E0300), the
gathering and freeing order in the IR, and the two corpus runs, including the
chatty child from Review Focus 3.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from logos import driver, ir, lower, types
from logos.check import CheckedModule, check_module
from logos.diag import LogosError
from logos.parser import parse
from logos.resolve import resolve
from logos.types import Prim, Ptr, Vec

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


def calls(fn: ir.IrFn, callee: str) -> list[tuple]:
    return [i for b in fn.blocks for i in b.instrs if i[0] == "call" and i[2] == callee]


def flat(fn: ir.IrFn) -> list[tuple]:
    return [i for b in fn.blocks for i in b.instrs]


def main_of(module: ir.IrModule) -> ir.IrFn:
    return next(fn for fn in module.functions if fn.name.endswith("main"))


def declares(module: ir.IrModule) -> dict[str, tuple[tuple, object]]:
    return {decl.name: (decl.params, decl.ret) for decl in module.declares}


VECTOR = "(letmut a (vec :str) (make (vec :str)))(vec-push a \"-c\")"


class RunIsAPrimitiveTest(unittest.TestCase):
    def test_run_is_a_primitive_beside_the_other_handles(self):
        self.assertIn("run", types.PRIMITIVES)
        # ``INTEGERS`` is the first eight and must not move.
        self.assertEqual(types.PRIMITIVES[:8], types.INTEGERS)
        self.assertEqual(types.PRIMITIVES[-1], "run")
        self.assertIn("mutex", types.PRIMITIVES)

    def test_a_run_is_not_a_thread(self):
        error = fail_on("(mod m)(fn f :run ((t :thread)) (ret t))")
        self.assertEqual(error.code, "E0100")

    def test_a_run_parameter_is_usable(self):
        cm = checked(
            "(mod m)(fn f :i64 ((r :run)) (ret (run-status r)))"
        )
        self.assertEqual(type_of(cm, "run-status"), Prim("i64"))


class RunCheckTest(unittest.TestCase):
    """``(run prog args)``: a ``:str`` and a moved ``(vec :str)``."""

    def test_run_is_a_run(self):
        cm = checked(
            f'(mod m)(fn main :void () {VECTOR} (let r (run "sh" a))'
            " (println (run-status r)))"
        )
        self.assertEqual(type_of(cm, "run"), Prim("run"))

    def test_the_program_must_be_a_str(self):
        error = fail_on("(mod m)(fn f :run () (ret (run 5 (make (vec :str)))))")
        self.assertEqual(error.code, "E0100")
        self.assertEqual(error.message, "'run' takes a :str, found :i64")

    def test_the_arguments_must_be_a_name(self):
        error = fail_on(
            '(mod m)(fn f :run () (ret (run "sh" (make (vec :str)))))'
        )
        self.assertEqual(error.code, "E0100")
        self.assertEqual(
            error.message, "'run' needs the name of a (vec :str) to pass"
        )

    def test_the_arguments_must_be_a_vector_of_str(self):
        error = fail_on(
            '(mod m)(fn f :run () (letmut a (vec :i64) (make (vec :i64)))'
            ' (ret (run "sh" a)))'
        )
        self.assertEqual(error.code, "E0100")
        self.assertEqual(
            error.message, "'run' takes a (vec :str) of arguments, found (vec :i64)"
        )

    def test_the_arguments_are_moved(self):
        # A second use of the vector is a use after move: the form released
        # it, and there is no second vector to hand on.
        error = fail_on(
            f'(mod m)(fn main :void () {VECTOR} (let r (run "sh" a))'
            ' (let s (run "sh" a)))'
        )
        self.assertEqual(error.code, "E0300")
        self.assertIn("use after move of 'a'", error.message)

    def test_the_arguments_cannot_be_read_after_the_call(self):
        error = fail_on(
            f'(mod m)(fn main :void () {VECTOR} (let r (run "sh" a))'
            " (println (vec-len a)))"
        )
        self.assertEqual(error.code, "E0300")

    def test_run_takes_two_arguments(self):
        error = fail_on('(mod m)(fn f :run () (ret (run "sh")))')
        self.assertEqual(error.code, "E0102")
        self.assertEqual(error.message, "'run' takes a program and an argument vector")


class RunReadersCheckTest(unittest.TestCase):
    """The three accessors, each taking exactly one ``:run``."""

    def test_the_status_is_an_i64(self):
        cm = checked(
            '(mod m)(fn f :i64 () (letmut a (vec :str) (make (vec :str)))'
            ' (let r (run "sh" a)) (ret (run-status r)))'
        )
        self.assertEqual(type_of(cm, "run-status"), Prim("i64"))

    def test_out_is_a_str(self):
        cm = checked(
            '(mod m)(fn f :str () (letmut a (vec :str) (make (vec :str)))'
            ' (let r (run "sh" a)) (ret (run-out r)))'
        )
        self.assertEqual(type_of(cm, "run-out"), Prim("str"))

    def test_err_is_a_str(self):
        cm = checked(
            '(mod m)(fn f :str () (letmut a (vec :str) (make (vec :str)))'
            ' (let r (run "sh" a)) (ret (run-err r)))'
        )
        self.assertEqual(type_of(cm, "run-err"), Prim("str"))

    def test_a_non_run_argument_is_e0100_at_the_argument(self):
        for kind in ("run-status", "run-out", "run-err"):
            with self.subTest(kind=kind):
                error = fail_on(f"(mod m)(fn f :i64 () (ret ({kind} 5)))")
                self.assertEqual(error.code, "E0100")
                self.assertEqual(
                    error.message, f"'{kind}' takes a :run, found :i64"
                )

    def test_a_run_value_cannot_stand_in_for_a_thread(self):
        error = fail_on(
            '(mod m)(fn f :i64 () (letmut a (vec :str) (make (vec :str)))'
            ' (let r (run "sh" a)) (ret (join r)))'
        )
        self.assertEqual(error.code, "E0100")

    def test_each_reader_takes_one_argument(self):
        for kind in ("run-status", "run-out", "run-err"):
            with self.subTest(kind=kind):
                error = fail_on(f"(mod m)(fn f :i64 () (ret ({kind} 1 2)))")
                self.assertEqual(error.code, "E0102")
                self.assertEqual(error.message, f"'{kind}' takes a :run")


class RunReservedNameTest(unittest.TestCase):
    FORMS = ("run", "run-status", "run-out", "run-err")

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


class RunLoweringTest(unittest.TestCase):
    SOURCE = (
        '(mod m)(fn main :void () (letmut a (vec :str) (make (vec :str)))'
        ' (vec-push a "-c") (let r (run "sh" a)) (println (run-status r)))'
    )

    def test_the_lowering_calls_the_runtime(self):
        module = lowered(self.SOURCE)
        names = call_names(main_of(module))
        for callee in ("rt_run_start", "rt_run_status"):
            self.assertIn(callee, names)
        params, ret = declares(module)["rt_run_start"]
        self.assertEqual(len(params), 6)
        self.assertEqual(ret, Ptr(Prim("u8")))

    def test_the_two_arrays_are_gathered_and_all_three_buffers_freed_after(self):
        fn = main_of(lowered(self.SOURCE))
        instrs = flat(fn)
        start = next(
            i
            for i, instr in enumerate(instrs)
            if instr[0] == "call" and instr[2] == "rt_run_start"
        )
        allocs = [
            i for i, instr in enumerate(instrs)
            if instr[0] == "call" and instr[2] == "rt_alloc"
        ]
        frees = [
            i for i, instr in enumerate(instrs)
            if instr[0] == "call" and instr[2] == "rt_free"
        ]
        # The vector's own push allocates once; the gather adds two buffers
        # (one pointer array and one length array).
        allocs_before = [i for i in allocs if i < start]
        self.assertEqual(len(allocs_before), 3, instrs)
        # The runtime copies every argument, so nothing may be released before
        # it returns: the two gathered buffers and the vector's own buffer go
        # afterwards, and the push released its old (empty) buffer earlier.
        frees_after = [i for i in frees if i > start]
        self.assertEqual(len(frees_after), 3, instrs)

    def test_the_vector_slot_is_zeroed_after_the_release(self):
        # The form released the vector's own descriptor buffer, so the frame
        # must hold no second name for it: the slot the descriptor was read
        # from is zeroed once, after all three frees, exactly as `vec-free`
        # zeroes it. Harmless today because a second use is E0300; cheap to
        # keep true if that rule ever loosens.
        fn = main_of(lowered(self.SOURCE))
        instrs = flat(fn)
        zeroed = [
            i for i, instr in enumerate(instrs)
            if instr[0] == "store" and instr[2] == "zeroinitializer"
        ]
        self.assertEqual(len(zeroed), 1, instrs)
        at = zeroed[0]
        ty, slot = instrs[at][1], instrs[at][3]
        self.assertEqual(ty, Vec(Prim("str")))
        # It is the slot the run form loaded the descriptor from.
        start = next(
            i
            for i, instr in enumerate(instrs)
            if instr[0] == "call" and instr[2] == "rt_run_start"
        )
        descriptor_reads = [
            i
            for i, instr in enumerate(instrs[:start])
            if instr[0] == "load" and instr[2] == Vec(Prim("str"))
        ]
        self.assertTrue(descriptor_reads, instrs)
        self.assertEqual(instrs[descriptor_reads[-1]][3], slot, instrs)
        # And the zeroing follows every release.
        last_free = max(
            i
            for i, instr in enumerate(instrs)
            if instr[0] == "call" and instr[2] == "rt_free"
        )
        self.assertGreater(at, last_free, instrs)

    def test_the_node_path_is_the_call_s_own(self):
        cm = checked(self.SOURCE)
        module = lower.lower_module(cm)
        path = path_of(cm, "run")
        self.assertIn(
            (path + "\x00").encode(), [g.data for g in module.globals]
        )

    def test_the_readers_call_their_runtime_functions(self):
        source = (
            '(mod m)(fn main :void () (letmut a (vec :str) (make (vec :str)))'
            ' (let r (run "sh" a)) (println (run-status r))'
            " (print (run-out r)) (print (run-err r)))"
        )
        module = lowered(source)
        names = call_names(main_of(module))
        for callee in ("rt_run_status", "rt_run_out", "rt_run_err"):
            self.assertIn(callee, names)
            self.assertIn(callee, declares(module))
        params, ret = declares(module)["rt_run_out"]
        self.assertEqual(len(params), 2)
        self.assertEqual(ret, Ptr(Prim("u8")))


class RunExecTest(unittest.TestCase):
    """``tests/exec/run.logos`` and the chatty child, at both levels."""

    def build(self, stem: str, case: str, opt: str) -> str:
        BUILD.mkdir(parents=True, exist_ok=True)
        out = str(BUILD / f"run-form-{stem}-{case}-{opt[1:]}")
        driver.run_test(str(EXEC / f"{stem}.logos"), case, out, opt=opt)
        return out

    def test_the_corpus_case_runs_a_child_and_reads_both_streams(self):
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                done = subprocess.run(
                    [self.build("run", "run", opt)],
                    capture_output=True,
                    timeout=60,
                )
                self.assertEqual(done.stdout, b"0\nhi\n0\noops\n", done.stderr)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn(b"LEAK", done.stderr)

    def test_a_program_that_cannot_start_panics_r0006_at_the_call(self):
        source = BUILD / "run-spawn.logos"
        BUILD.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "(mod spawn)\n"
            "(fn main :void ()\n"
            "  (letmut a (vec :str) (make (vec :str)))\n"
            '  (let r (run "definitely-not-a-program-xyz" a))\n'
            "  (println (run-status r)))\n",
            encoding="utf-8",
        )
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                binary = driver.build(
                    str(source), str(BUILD / f"run-spawn-{opt[1:]}"), opt=opt
                )
                done = subprocess.run([binary], capture_output=True, timeout=60)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertEqual(done.stdout, b"", done.stderr)
                self.assertIn(
                    b"R0006: could not start definitely-not-a-program-xyz",
                    done.stderr,
                )
                # The location is the `run` node, not the runtime: the path is
                # the one the lowerer emitted for the call.
                self.assertIn(b"spawn/main/3/1: R0006", done.stderr)

    def test_a_nonzero_and_a_signalled_status_are_reported(self):
        # Both are the child's status, not the test process's: only pinning
        # `0` would let a reader that always returned 0 stay green.
        for case, expected in (
            ("nonzero-status", b"7\n"),
            ("signalled-status", b"143\n"),
        ):
            for opt in ("-O0", "-O2"):
                with self.subTest(case=case, opt=opt):
                    done = subprocess.run(
                        [self.build("run", case, opt)],
                        capture_output=True,
                        timeout=60,
                    )
                    self.assertEqual(done.stdout, expected, done.stderr)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertNotIn(b"LEAK", done.stderr)

    def test_a_run_handle_crosses_a_thread_boundary(self):
        # The handle is written once and never mutated, so it is copyable
        # across a thread like any scalar; the runtime's handle is
        # process-lifetime, so the copy stays valid.
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                done = subprocess.run(
                    [self.build("run", "run-across-a-thread", opt)],
                    capture_output=True,
                    timeout=60,
                )
                self.assertEqual(done.stdout, b"5\n", done.stderr)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn(b"LEAK", done.stderr)

    def test_a_child_writing_200_kib_on_both_streams_does_not_deadlock(self):
        source = BUILD / "run-chatty.logos"
        BUILD.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "(mod chatty)\n"
            "(fn main :void ()\n"
            "  (letmut a (vec :str) (make (vec :str)))\n"
            '  (vec-push a "-c")\n'
            '  (vec-push a "yes x | head -c 204800; yes y | head -c 204800 1>&2")\n'
            '  (let r (run "sh" a))\n'
            "  (println (run-status r))\n"
            "  (println (str-len (run-out r)))\n"
            "  (println (str-len (run-err r))))\n",
            encoding="utf-8",
        )
        for opt in ("-O0", "-O2"):
            with self.subTest(opt=opt):
                binary = driver.build(
                    str(source), str(BUILD / f"run-chatty-{opt[1:]}"), opt=opt
                )
                done = subprocess.run([binary], capture_output=True, timeout=60)
                self.assertEqual(
                    done.stdout, b"0\n204800\n204800\n", done.stderr
                )
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn(b"LEAK", done.stderr)


if __name__ == "__main__":
    unittest.main()
