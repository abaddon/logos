"""`gen2 fmt` is Python's `fmt`: in place, several paths, directories, stdin.

The port printed one file's canonical text to stdout for exactly one path
(`main.logos:71-73`). Python's verb rewrites each file and prints nothing,
walks a directory's `*.logos` files in sorted order, reads `-` from stdin at
most once, and reports a path it cannot read as `logos: <path>: <strerror>`
with exit 1 (`cli.py:330-379`). This test judges the verb at the command line,
where a caller sees it.

The oracle is the same binary Python ships, so the parity case formats two
copies of one tree — one with `gen2` and one with `python3 -m logos` — and
requires every byte to agree. The order case uses three broken files in nested
directories: a formatter that prints nothing on success is only observable
through its diagnostics, and Python's walk is sorted by path components rather
than by the whole path as a string (`PurePath.__lt__`), so `b/x.logos` comes
before `b.logos` even though `b.logos` sorts first byte-wise.

stderr's *text* is not compared: `logos/diag.py` renders `CODE file:line:col`
while the port renders `file:line:col: CODE`, a difference `main.md` records as
deliberate. What is compared is the sequence of files, the exit status and the
stdout bytes — everything a caller scripts against.

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

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "test-gen2-fmt" / "gen2"

#: Sources the gate builds `gen2` from: every module plus the two the compiler's
#: tables name. Sorted, so the first stem is `body_test` exactly as the shell's
#: `src/logosc/*.logos` glob orders it.
SOURCES = sorted(str(path) for path in (ROOT / "src" / "logosc").glob("*.logos")) + [
    str(ROOT / "src" / "std" / "map.logos"),
    str(ROOT / "src" / "std" / "str.logos"),
]

#: One file per shape the walk has to handle: a top-level file, a nested file,
#: and a file whose name sorts after a directory of the same prefix.
TREE = {
    "a.logos": "(mod a)\n(println   1)\n",
    "b.logos": "(mod b)\n\n(fn f :i64 ()\n  (ret  3))\n",
    "b/x.logos": "(mod bx)\n(println 2)\n",
    "sub/deep/c.logos": "(mod c)\n(fn g :i64 ((n :i64)) (ret (+ n 1)))\n",
    "ignore.txt": "(mod no)\n(println 3)\n",
}

#: Three files the lexer refuses, in an order only a component-wise sort gives:
#: `b/x` before `b.logos` (because `b` < `b.logos`), then `bb/y`, then `bc/x`.
BROKEN = {
    "b.logos": "(mod b)\n(println 1)\n",
    "b/x.logos": '(mod bx)\n(println "z)\n',
    "bb/y.logos": '(mod bb)\n(println "x)\n',
    "bc/x.logos": '(mod bc)\n(println "y)\n',
}

PATH_AT = re.compile(r"[^\s:]+\.logos:\d+:\d+")


#: The oracle runs from a scratch directory, so the package has to come from
#: the checkout rather than from the working directory.
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join(
    [str(ROOT), os.environ.get("PYTHONPATH", "")]
)}


def _run(arguments: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        arguments, cwd=cwd, capture_output=True, text=True, input=stdin, env=ENV
    )


def _plant(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class Gen2FmtTest(unittest.TestCase):
    """The `fmt` verb's file-system contract, judged through the binary."""

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)], ROOT)
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gen2-fmt-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # -- in place ---------------------------------------------------------

    def test_fmt_rewrites_files_in_place_and_prints_nothing(self):
        _plant(self.tmp, TREE)
        done = _run([str(BIN), "fmt", "a.logos", "b/x.logos"], self.tmp)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "", "fmt prints nothing when it writes")
        self.assertEqual(done.stderr, "")
        self.assertEqual((self.tmp / "a.logos").read_text(), "(mod a)\n\n(println 1)\n")
        self.assertEqual(
            (self.tmp / "b/x.logos").read_text(), "(mod bx)\n\n(println 2)\n"
        )

    def test_a_directory_is_walked_and_matches_python_byte_for_byte(self):
        theirs = self.tmp / "python"
        mine = self.tmp / "port"
        _plant(mine, TREE)
        _plant(theirs, TREE)
        done = _run([str(BIN), "fmt", "."], mine)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "")
        oracle = _run([sys.executable, "-m", "logos", "fmt", "."], theirs)
        self.assertEqual(oracle.returncode, 0, oracle.stderr)
        for name in sorted(TREE):
            with self.subTest(name=name):
                self.assertEqual((mine / name).read_bytes(), (theirs / name).read_bytes())
        # A non-source file is not a source: the walk matches `*.logos` only.
        self.assertEqual((mine / "ignore.txt").read_text(), TREE["ignore.txt"])

    def test_stdin_is_formatted_to_stdout(self):
        source = "(mod s)\n(println   1)\n"
        done = _run([str(BIN), "fmt", "-"], self.tmp, stdin=source)
        oracle = _run([sys.executable, "-m", "logos", "fmt", "-"], self.tmp, stdin=source)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(oracle.returncode, 0, oracle.stderr)
        self.assertEqual(done.stdout, oracle.stdout)
        self.assertEqual(done.stdout, "(mod s)\n\n(println 1)\n")

    def test_stdin_and_files_may_be_mixed(self):
        _plant(self.tmp, TREE)
        done = _run([str(BIN), "fmt", "a.logos", "-"], self.tmp, stdin="(mod s)\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "(mod s)\n")
        self.assertEqual((self.tmp / "a.logos").read_text(), "(mod a)\n\n(println 1)\n")

    # -- order ------------------------------------------------------------

    def test_the_walk_order_matches_python(self):
        mine = self.tmp / "port"
        theirs = self.tmp / "python"
        _plant(mine, BROKEN)
        _plant(theirs, BROKEN)
        done = _run([str(BIN), "fmt", "."], mine)
        oracle = _run([sys.executable, "-m", "logos", "fmt", "."], theirs)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(oracle.returncode, 1, oracle.stderr)
        ours = [PATH_AT.search(line).group(0) for line in done.stderr.splitlines() if PATH_AT.search(line)]
        pins = [PATH_AT.search(line).group(0) for line in oracle.stderr.splitlines() if PATH_AT.search(line)]
        # The port names the argument-relative path; Python drops a leading "./".
        self.assertEqual([path[2:] if path.startswith("./") else path for path in ours], pins)
        self.assertEqual(
            [p.split(":")[0] for p in pins],
            ["b/x.logos", "bb/y.logos", "bc/x.logos"],
        )
        # Every good file is still formatted after the failures.
        self.assertEqual((mine / "b.logos").read_text(), "(mod b)\n\n(println 1)\n")

    # -- failures ---------------------------------------------------------

    def test_a_missing_path_is_one_line_and_exit_one(self):
        done = _run([str(BIN), "fmt", "nope.logos"], self.tmp)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(
            done.stderr, "logos: nope.logos: No such file or directory\n"
        )
        oracle = _run([sys.executable, "-m", "logos", "fmt", "nope.logos"], self.tmp)
        self.assertEqual(oracle.returncode, 1)
        self.assertEqual(done.stderr, oracle.stderr)

    def test_a_broken_file_is_reported_and_left_untouched(self):
        _plant(self.tmp, {"broken.logos": "(mod x))", "good.logos": "(mod g)\n"})
        done = _run([str(BIN), "fmt", "broken.logos", "good.logos"], self.tmp)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual((self.tmp / "broken.logos").read_text(), "(mod x))")
        self.assertEqual((self.tmp / "good.logos").read_text(), "(mod g)\n")
        self.assertIn("E0001", done.stderr)

    def test_a_repeated_dash_is_refused_before_anything_is_written(self):
        _plant(self.tmp, TREE)
        done = _run([str(BIN), "fmt", "a.logos", "-", "-"], self.tmp, stdin="(mod s)\n")
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "logos: fmt: '-' may be given at most once\n")
        self.assertEqual((self.tmp / "a.logos").read_text(), TREE["a.logos"])

    def test_a_command_line_with_no_path_is_usage(self):
        done = _run([str(BIN), "fmt"], self.tmp)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, "")
        self.assertTrue(done.stderr.startswith("usage: gen2"))


if __name__ == "__main__":
    unittest.main()
