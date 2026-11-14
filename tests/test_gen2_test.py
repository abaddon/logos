"""`gen2 test` discovery, ids and the directive reader — Python is the oracle.

The `test` verb is landed in seven steps (`2026-11-13-w8-harness-notes.md` §5)
and this file judges the first two, which are pure: which files a run covers,
what each case is called and in what order, and what a case's directives say.
Nothing here builds or runs a case, so every case prints `PASS <id> -` and only
a malformed directive prints `FAIL <id> <detail>`.

Two oracles, both cheap:

* The id column and its order are compared with `tests/summary.txt`, which is
  Python's own full run written by `tester.write_baseline` and gated by
  `python3 -m logos test` in the same gate — so a case that appears, moves or
  disappears moves the baseline in the same commit. Its ids are
  percent-encoded, so both sides are decoded before comparing.
* The directive sentences are compared with `tester.run_suite` over a scratch
  tree holding one malformed variant per rule. Every fixture fails inside
  `_expectation`/`_expected_diagnostic`, before a binary would be built, so the
  oracle costs no compilation.

The compiler under test is built once per run from the source set
`tools/selfhost.sh` builds `gen2` from, with Python, because a compiler is the
only way to build a compiler before one exists.
"""

from __future__ import annotations

import os
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


def _run(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, env=ENV)


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
        done = _run([str(BIN), "test", "tests"], ROOT)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
        expected = _baseline_ids()
        self.assertEqual(_ids(done), expected)
        # One line per case, and every case is a PASS: the reader refuses nothing
        # in the corpus, and nothing has run yet.
        self.assertEqual(len(done.stdout.splitlines()), len(expected))
        self.assertTrue(all(line.startswith("PASS ") and line.endswith(" -")
                            for line in done.stdout.splitlines()))

    def test_the_category_order_is_the_suites_not_the_alphabet(self):
        expected = _baseline_ids()
        categories = [case.split("/")[0] for case in expected]
        order = ["parse", "type", "exec", "mem", "thread", "generics", "regress", "diff"]
        self.assertEqual(categories, sorted(categories, key=order.index))
        # `parse` before `type` is the documented walk, and `p` < `t` hides it;
        # the pair that only the category list gives is `type` before `exec`.
        self.assertLess(categories.index("type"), categories.index("exec"))

    def test_only_narrows_the_run_to_one_category(self):
        done = _run([str(BIN), "test", "tests", "--only", "mem"], ROOT)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        expected = [case for case in _baseline_ids() if case.startswith("mem/")]
        self.assertEqual(_ids(done), expected)
        self.assertEqual(len(expected), 7)

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
        done = _run([str(BIN), "test", str(tree)], self.tmp)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        # The oracle fails these in the reader, so it compiles nothing.
        summary = tester.run_suite(str(tree), opts=["-O0"])
        pins = [f"{case.status} {case.id} {case.detail}" for case in summary.cases]
        self.assertEqual(done.stdout.splitlines(), pins)
        self.assertEqual(len(pins), 25)

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
