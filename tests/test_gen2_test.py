"""`gen2 test`: discovery, the directive reader, a child's I/O, and the report.

The `test` verb is landed in seven steps (`2026-11-13-w8-harness-notes.md` §5)
and this file judges the first six: which files a run covers, what each case is
called and in what order, what a case's directives say, that the case runs with
an empty standard input, its own ten-second budget and a failure reported
rather than a panic (step 3), that each case runs at every level and the four
clauses are compared (step 4), that the levels are compared with each other
(step 5), and that the run ends with the suite's own summary line (step 6).

Two oracles, both cheap:

* The id column and its order are compared with `tests/summary.txt`, which is
  Python's own full run written by `tester.write_baseline` and gated by
  `python3 -m logos test` in the same gate — so a case that appears, moves or
  disappears moves the baseline in the same commit. Its ids are percent-encoded,
  so both sides are decoded before comparing.
* The directive sentences are compared with `tester.run_suite` over a scratch
  tree holding one malformed variant per rule. Every fixture fails inside
  `_expectation`/`_expected_diagnostic`, before a binary would be built, so the
  oracle costs no compilation.

The corpus-wide run executes every case at both levels, so its status column is
not asserted here: the port still refuses 32 `exec` cases and 2 `mem` cases in
the lowering, and those are classified in
`2026-11-14-w8-harness-steps4-6-report.md`. What this file pins is that every
case appears once in the baseline's order, that the summary line counts the
lines above it, and that the child-I/O behaviours are the runtime's.

The compiler under test is built once per run from the source set
`tools/selfhost.sh` builds `gen2` from, with Python, because a compiler is the
only way to build a compiler before one exists.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "test-gen2-test" / "gen2"

#: Sources the gate builds `gen2` from: every module plus the two the compiler's
#: tables name.
SOURCES = sorted(str(path) for path in (ROOT / "src" / "logosc").glob("*.logos")) + [
    str(ROOT / "src" / "std" / "map.logos"),
    str(ROOT / "src" / "std" / "str.logos"),
]

#: One malformed directive per rule in the reader, and nothing else: a fixture
#: here must be reachable by every earlier check, or the sentence under test is
#: never the one that fires. `(test …)` names are `t` except where the rule is
#: about the name.
MALFORMED = {
    "two-expect.logos": '(mod a)\n\n(test t\n  (expect (out "a"))\n  (expect (out "b"))\n  (println "x"))\n',
    "two-legacy.logos": '(mod a)\n\n(test t\n  (expect (out "a"))\n  (expect-leak 1)\n  (expect-leak 2)\n  (println "x"))\n',
    "atom-clause.logos": "(mod a)\n\n(test t\n  (expect x)\n  (println \"x\"))\n",
    "duplicate.logos": '(mod a)\n\n(test t\n  (expect (out "a")\n    (out "b"))\n  (println "x"))\n',
    "duplicate-arity.logos": "(mod a)\n\n(test t\n  (expect (code 1)\n    (code))\n  (println \"x\"))\n",
    "arity-two.logos": '(mod a)\n\n(test t\n  (expect (out "a" "b"))\n  (println "x"))\n',
    "arity-zero.logos": "(mod a)\n\n(test t\n  (expect (code))\n  (println \"x\"))\n",
    "out-atom.logos": "(mod a)\n\n(test t\n  (expect (out x))\n  (println \"x\"))\n",
    "err-empty.logos": '(mod a)\n\n(test t\n  (expect (err-contains ""))\n  (println "x"))\n',
    "code-float.logos": "(mod a)\n\n(test t\n  (expect (code 1.5))\n  (println \"x\"))\n",
    "leaks-atom.logos": "(mod a)\n\n(test t\n  (expect (leaks x))\n  (println \"x\"))\n",
    "unknown.logos": "(mod a)\n\n(test t\n  (expect (foo 1))\n  (println \"x\"))\n",
    "unknown-arity.logos": "(mod a)\n\n(test t\n  (expect (foo))\n  (println \"x\"))\n",
    "empty-expect.logos": "(mod a)\n\n(test t\n  (expect)\n  (println \"x\"))\n",
    "no-expect.logos": '(mod a)\n\n(test t\n  (println "x"))\n',
    "fold.logos": '(mod a)\n\n(test t\n  (expect (leaks 0))\n  (expect-leak 0)\n  (println "x"))\n',
    "legacy-int.logos": '(mod a)\n\n(test t\n  (expect (out "a"))\n  (expect-leak x)\n  (println "x"))\n',
    "legacy-arity.logos": '(mod a)\n\n(test t\n  (expect (out "a"))\n  (expect-leak 1 2)\n  (println "x"))\n',
    "error-arity.logos": "(mod a)\n\n(expect-error E0101 E0102)\n",
    "error-bad-code.logos": "(mod a)\n\n(expect-error nope)\n",
    "error-two.logos": "(mod a)\n\n(expect-error E0101)\n\n(expect-error E0102)\n",
    "error-string.logos": '(mod a)\n\n(expect-error "E0101")\n',
}

#: The fixtures that need a sibling `.expect`, and its bytes.
SIDECARS = {
    "sidecar-multiline.expect": "E0101\nE0102\n",
    "sidecar-bad.expect": "nope\n",
    "sidecar-disagree.expect": "E0102\n",
}

#: The fixtures that pair a sidecar with a module-level directive.
SIDECAR_SOURCES = {
    "sidecar-multiline.logos": "(mod a)\n\n(expect-error E0101)\n",
    "sidecar-bad.logos": "(mod a)\n\n(expect-error E0101)\n",
    "sidecar-disagree.logos": "(mod a)\n\n(expect-error E0101)\n",
}

ENV = {**os.environ, "PYTHONPATH": os.pathsep.join(
    [str(ROOT), os.environ.get("PYTHONPATH", "")]
)}


def _run(
    arguments: list[str],
    cwd: Path,
    timeout: float | None = None,
    executable: str | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=ENV,
        timeout=timeout,
        executable=executable,
    )


def _plant(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _baseline_ids() -> list[str]:
    """`tests/summary.txt`'s case ids, in order, with the two header lines gone."""
    lines = (ROOT / "tests" / "summary.txt").read_text(encoding="utf-8").splitlines()
    return [unquote(line.split(" ")[1]) for line in lines[2:] if line.strip()]


def _ids(done: subprocess.CompletedProcess) -> list[str]:
    return [line.split(" ")[1] for line in done.stdout.splitlines() if line.startswith(("PASS ", "FAIL "))]


SUMMARY = re.compile(r"^(\d+) passed, (\d+) failed, (\d+) leaked$")


def _totals(done: subprocess.CompletedProcess) -> tuple[int, int, int]:
    """The run's three numbers, from the line `cli._test` prints last."""
    match = SUMMARY.match(done.stdout.splitlines()[-1])
    if match is None:
        raise AssertionError(f"no summary line in {done.stdout!r}")
    passed, failed, leaks = match.groups()
    return int(passed), int(failed), int(leaks)


class Gen2TestTest(unittest.TestCase):
    """The `test` verb's discovery, id and directive contract, through the binary."""

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)], ROOT)
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gen2-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # -- ids and order ----------------------------------------------------

    def test_the_whole_corpus_ids_and_order_match_the_baseline(self):
        # Every case is built and run at both levels now, so the run costs
        # minutes and reports the port's known refusals; what it must still do
        # is name each case once, in the baseline's order, and end with a
        # summary whose numbers count the lines above it.
        done = _run([str(BIN), "test", "tests"], ROOT, timeout=1800)
        self.assertEqual(done.stderr, "")
        expected = _baseline_ids()
        self.assertEqual(_ids(done), expected)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), len(expected) + 1)
        passed, failed, _ = _totals(done)
        self.assertEqual(passed + failed, len(expected))
        self.assertEqual(passed, sum(1 for line in lines if line.startswith("PASS ")))
        self.assertEqual(done.returncode, 1 if failed else 0)

    def test_the_category_order_is_the_suites_not_the_alphabet(self):
        expected = _baseline_ids()
        categories = [case.split("/")[0] for case in expected]
        order = ["parse", "type", "exec", "mem", "thread", "generics", "regress", "diff"]
        self.assertEqual(categories, sorted(categories, key=order.index))
        # `parse` before `type` is the documented walk, and `p` < `t` hides it;
        # the pair that only the category list gives is `type` before `exec`.
        self.assertLess(categories.index("type"), categories.index("exec"))

    def test_only_narrows_the_run_to_one_category(self):
        done = _run([str(BIN), "test", "tests", "--only", "mem"], ROOT, timeout=600)
        expected = [case for case in _baseline_ids() if case.startswith("mem/")]
        self.assertEqual(_ids(done), expected)
        self.assertEqual(len(expected), 7)
        # Two of the seven do not build yet (the port's lowering refuses a
        # `match` used as a call argument), so the exit status is not this
        # test's claim; the id set, its order and the leak total are. Python's
        # run at both levels reports `7 passed, 0 failed, 6 leaked`.
        self.assertEqual(done.stderr, "")
        passed, failed, leaks = _totals(done)
        self.assertEqual(passed + failed, 7)
        self.assertEqual(leaks, 6)

    def test_a_file_root_is_the_whole_set(self):
        done = _run([str(BIN), "test", "tests/exec/hello.logos"], ROOT)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(_ids(done), ["exec/hello/hello"])

    # -- the directive reader --------------------------------------------

    def test_malformed_directives_are_reported_in_python_s_words(self):
        from logos import tester

        tree = self.tmp / "cases"
        tree.mkdir()
        _plant(tree, {**MALFORMED, **SIDECAR_SOURCES, **SIDECARS})
        # One level, because every one of these fails in the reader before a
        # child would start: the sentences are the claim, and the summary is
        # the oracle's own count.
        done = _run([str(BIN), "test", str(tree), "--opt", "-O0"], self.tmp)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        summary = tester.run_suite(str(tree), opts=["-O0"])
        pins = [f"{case.status} {case.id} {case.detail}" for case in summary.cases]
        lines = done.stdout.splitlines()
        self.assertEqual(len(pins), 25)
        self.assertEqual(lines[:-1], pins)
        self.assertEqual(
            lines[-1],
            f"{summary.passed} passed, {summary.failed} failed, {summary.leaks} leaked",
        )

    def test_a_missing_root_is_one_line_and_exit_one(self):
        done = _run([str(BIN), "test", "nope"], self.tmp)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "logos: test: nope: no such file or directory\n")

    def test_an_unknown_category_is_a_usage_error(self):
        done = _run([str(BIN), "test", "tests", "--only", "bogus"], ROOT)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "logos: test: unknown test category 'bogus'\n")

    def test_a_second_path_is_a_usage_error(self):
        done = _run([str(BIN), "test", "tests", "tests/exec"], ROOT)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, "")
        self.assertIn("usage: gen2", done.stderr)


class ChildIoTest(unittest.TestCase):
    """Step 3: the child's standard input, its budget, and a spawn that fails.

    Three different waits, kept apart: a build keeps the runtime's 90-second
    guard, one test case gets Python's ten seconds, and a child that could not
    be started is a case detail instead of a panic that kills the run.
    """

    FIXTURES = ROOT / "src" / "logosc" / "fixtures" / "harness"

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)], ROOT)
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gen2-child-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_read_runs_both_cases_and_terminates(self):
        # A full run used to hang here: `read-all` in the child inherited this
        # process's standard input. With `/dev/null` both cases read end of
        # file at once and the run ends.
        done = _run([str(BIN), "test", "tests/exec/read.logos"], ROOT, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
        self.assertEqual(
            done.stdout,
            "PASS exec/read/empty-standard-input -\n"
            "PASS exec/read/reading-is-not-a-leak -\n"
            "2 passed, 0 failed, 0 leaked\n",
        )

    def test_a_twenty_second_case_is_killed_at_ten(self):
        # Python's budget for one case is 10 s, not the runtime's 90 s build
        # guard. The sentence is Python's, and the case is the only failure, so
        # the run ends with exit 1 instead of hanging for twenty seconds.
        done = _run(
            [str(BIN), "test", str(self.FIXTURES / "sleep.logos")], ROOT, timeout=60
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        # Both levels run, so the budget is spent twice and the detail carries
        # one clause per level.
        self.assertEqual(
            done.stdout,
            "FAIL exec/sleep/sleeps-past-its-budget -O0: timed out after 10s; "
            "-O2: timed out after 10s\n"
            "0 passed, 1 failed, 0 leaked\n",
        )
        self.assertEqual(done.stderr, "")

    def test_a_child_that_cannot_start_is_a_detail_not_a_panic(self):
        # The case builds, and the binary is gone by the time it is run: the
        # harness is started under a wrapper's *name* (argv[0]), stands it in
        # for the compiler, and the wrapper removes what it produced. The only
        # failure left is the spawn, which is reported; a panic would exit 2
        # with R0006 on stderr.
        wrapper = self.tmp / "compiler.sh"
        wrapper.write_text(
            "#!/bin/sh\n"
            f'{BIN} "$@" || exit $?\n'
            'prev=""\n'
            'for arg in "$@"; do\n'
            '  if [ "$prev" = "-o" ]; then rm -f "$arg"; fi\n'
            '  prev="$arg"\n'
            "done\n"
            "exit 0\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        done = _run(
            [str(wrapper), "test", str(self.FIXTURES / "missing.logos")],
            ROOT,
            timeout=120,
            executable=str(BIN),
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
        prefix = "FAIL exec/missing/cannot-be-started -O0: could not run: "
        self.assertTrue(done.stdout.startswith(prefix), done.stdout)
        self.assertIn("No such file or directory", done.stdout)


class ReportTest(unittest.TestCase):
    """Steps 4-6: the level loop, the cross-level comparison and the report.

    Every fixture here is a scratch tree inside the repository's `build/`,
    because a test binary is linked against `logos/runtime/rt.c` relative to the
    working directory. The trees are small: each case is one build per level,
    so the whole class costs a few seconds.
    """

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)], ROOT)
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")

    def setUp(self) -> None:
        (ROOT / "build").mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="gen2-report-", dir=ROOT / "build"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.rel = self.tmp.relative_to(ROOT)

    def _tree(self, name: str, files: dict[str, str]) -> str:
        root = self.tmp / name
        _plant(root, files)
        return str((self.rel / name))

    def test_a_case_runs_at_both_levels_and_the_clauses_are_compared(self):
        # The two cases differ only in what they print, so the failure detail
        # is `_compare`'s sentence once per level, joined by `"; "` in the
        # order the levels ran. A summary counts the lines above it.
        tree = self._tree(
            "cases",
            {
                "exec/levels.logos": (
                    "(mod levels)\n\n"
                    "(test passes\n  (expect (out \"one\\n\"))\n  (println \"one\"))\n\n"
                    "(test fails\n  (expect (out \"two\\n\"))\n  (println \"three\"))\n"
                )
            },
        )
        done = _run([str(BIN), "test", tree], ROOT, timeout=300)
        self.assertEqual(
            done.stdout,
            "PASS exec/levels/passes -\n"
            "FAIL exec/levels/fails -O0: stdout: expected 'two\\n', got 'three\\n'; "
            "-O2: stdout: expected 'two\\n', got 'three\\n'\n"
            "1 passed, 1 failed, 0 leaked\n",
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
        # Both levels really ran, at Python's paths.
        harness = ROOT / "build" / "harness" / "exec" / "levels"
        self.assertTrue((harness / "00-passes.O0.bin").is_file())
        self.assertTrue((harness / "00-passes.O2.bin").is_file())

    def test_opt_selects_the_levels(self):
        tree = self._tree(
            "only",
            {
                "exec/only.logos": (
                    "(mod only)\n\n(test solo\n  (expect (out \"a\\n\"))\n  (println \"a\"))\n"
                )
            },
        )
        done = _run([str(BIN), "test", tree, "--opt", "-O0"], ROOT, timeout=300)
        self.assertEqual(
            done.stdout,
            "PASS exec/only/solo -\n1 passed, 0 failed, 0 leaked\n",
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        harness = ROOT / "build" / "harness" / "exec" / "only"
        self.assertTrue((harness / "00-solo.O0.bin").is_file())
        self.assertFalse((harness / "00-solo.O2.bin").is_file())
        # `--opt=-O0` is argparse's other spelling of the same flag, and the
        # level it names is the level that runs.
        attached = _run([str(BIN), "test", tree, "--opt=-O0"], ROOT, timeout=300)
        self.assertEqual(attached.stdout, done.stdout)
        self.assertEqual(attached.returncode, 0, attached.stdout + attached.stderr)

    def test_two_levels_that_agree_are_not_a_disagreement(self):
        # The same level twice is two observations with nothing between them:
        # the comparison must stay silent rather than invent a difference.
        tree = self._tree(
            "same",
            {
                "exec/same.logos": (
                    "(mod same)\n\n(test twice\n  (expect (out \"a\\n\"))\n  (println \"a\"))\n"
                )
            },
        )
        done = _run([str(BIN), "test", tree, "--opt", "-O0", "-O0"], ROOT, timeout=300)
        self.assertEqual(
            done.stdout,
            "PASS exec/same/twice -\n1 passed, 0 failed, 0 leaked\n",
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_file_outside_the_categories_is_skipped_and_fails_the_run(self):
        tree = self._tree(
            "skip",
            {
                "exec/skip.logos": (
                    "(mod skip)\n\n(test one\n  (expect (out \"a\\n\"))\n  (println \"a\"))\n"
                ),
                "stray.logos": "(mod stray)\n",
            },
        )
        done = _run([str(BIN), "test", tree], ROOT, timeout=300)
        self.assertEqual(
            done.stdout,
            "PASS exec/skip/one -\n"
            f"SKIP {tree}/stray.logos\n"
            "1 passed, 0 failed, 0 leaked\n",
        )
        self.assertEqual(
            done.stderr,
            "logos: test: 1 file(s) outside the known categories were skipped\n",
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_an_empty_run_says_so_and_fails(self):
        tree = self._tree("empty", {"exec/none.logos": "(mod none)\n"})
        done = _run([str(BIN), "test", tree], ROOT, timeout=120)
        self.assertEqual(
            done.stdout,
            f"0 passed, 0 failed, 0 leaked\ntest: no cases found in {tree}\n",
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
