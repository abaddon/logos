"""`gen2`'s CLI tail is Python's: `version`, `show`, usage, and the baseline.

The last verbs of W8 are the ones that are not about the language at all. They
are the command line a caller scripts against, and every one of them has an
oracle that is still present: `logos/cli.py`. This test judges the port at the
process boundary, running both binaries on the same tree and comparing stdout,
stderr and exit status byte for byte:

* `version` is one string (`cli.py:131`);
* `show` prints one node at the node paths the diagnostics already print, for
  a definition, a nested expression, a token, the file itself, a path that does
  not exist and a path that does not spell (`cli.py:401-497`);
* the usage block, the help and the error lines are `argparse`'s, so a missing
  argument, an unknown verb and an extra word must read exactly as Python's do
  (`cli.py:151-184`) — with the one deliberate difference that `patch` is gone,
  because a verb `logosc` keeps is not a developer convenience;
* `test --update-baseline` writes `<root>/summary.txt` (`tester.py:760-800`):
  a `LEAKS` line, an `OPTS` line, then one line per case in run order. A full
  run replaces the file; a filtered run merges into it and drops a stale line
  under the category it covered. Nothing else in the toolchain can rewrite that
  file once Python is gone, so its bytes are compared against Python's.

The comparison is byte for byte because these are the surfaces a script reads.
Where Python is still the oracle for a *scratch* suite — the baseline — both
tools write their own copy of one summary file and the two files are compared.

The compiler under test is built once per run from the source set
`tools/selfhost.sh` builds `gen2` from, with Python, because a compiler is the
only way to build a compiler before one exists. The binary is copied to a file
named `logosc` first: the usage block names the program it was invoked as
(Python's `argparse` hardcodes `logosc`), so the copy is what makes the two
helps comparable rather than merely similar.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "test-gen2-cli" / "gen2"
#: The same binary under the name the usage block prints.
CLI = BIN.parent / "logosc"

#: Sources the gate builds `gen2` from: every module plus the two the compiler's
#: tables name.
SOURCES = sorted(str(path) for path in (ROOT / "src" / "logosc").glob("*.logos")) + [
    str(ROOT / "src" / "std" / "map.logos"),
    str(ROOT / "src" / "std" / "str.logos"),
]

#: The oracle runs from a scratch directory, so the package has to come from
#: the checkout rather than from the working directory.
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join(
    [str(ROOT), os.environ.get("PYTHONPATH", "")]
)}

#: `patch` is the one verb Python has and the port does not. These are the two
#: places its name appears in the CLI's own text; removing them exactly is what
#: "identical to Python apart from the dropped verb" means.
HELP_ROW = "    patch     replace one node of a Logos file\n"
CHOICE = ", 'patch'"

HELLO = """\
(mod hello)

(test prints
  (expect (out "hi\\n") (code 0))
  (println "hi"))
"""

FINE = """\
(mod fine)

(test frees
  (expect (code 0) (leaks 0))
  (let p (alloc :i64 4))
  (free p))
"""

BROKEN_HELLO = """\
(mod hello)

(test prints
  (expect (out "expected\\n") (code 0))
  (println "hi"))
"""


def _run(arguments: list[str], cwd: Path = ROOT, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        arguments, cwd=cwd, input=stdin, capture_output=True, text=True, env=ENV
    )


def _python(arguments: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return _run([sys.executable, "-m", "logos", *arguments], cwd)


def _port(arguments: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return _run([str(CLI), *arguments], cwd)


def _plant(root: Path, category: str, name: str, text: str) -> Path:
    path = root / category / name / f"{name}.logos"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Gen2CliTest(unittest.TestCase):
    """`version`, `show`, the usage block and the baseline, against Python."""

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)])
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")
        shutil.copyfile(BIN, CLI)
        CLI.chmod(0o755)

    def same(self, arguments: list[str], cwd: Path = ROOT, stdin: str = "") -> None:
        """Both binaries must agree on stdout, stderr and the exit status."""
        mine = _run([str(CLI), *arguments], cwd, stdin)
        oracle = _run([sys.executable, "-m", "logos", *arguments], cwd)
        self.assertEqual(oracle.returncode, mine.returncode, mine.stderr)
        self.assertEqual(mine.stdout, oracle.stdout)
        self.assertEqual(mine.stderr, oracle.stderr)

    # -- version ---------------------------------------------------------

    def test_version_is_one_line_and_zero(self):
        done = _port(["version"])
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "logos 0.1.0\n")
        self.assertEqual(done.stderr, "")
        self.same(["version"])

    # -- show ------------------------------------------------------------

    def test_show_a_definition(self):
        self.same(["show", "examples/hello.logos", "hello/main"])
        done = _port(["show", "examples/hello.logos", "hello/main"])
        self.assertEqual(done.stdout, '(fn main :void ()\n  (println "hello"))\n')

    def test_show_a_nested_expression(self):
        self.same(["show", "examples/hello.logos", "hello/main/2"])
        done = _port(["show", "examples/hello.logos", "hello/main/2"])
        self.assertEqual(done.stdout, '(println "hello")\n')

    def test_show_a_token_and_a_bare_list(self):
        # A return type is a token and a parameter list is a bare form; both
        # hold a position, and a token has no path of its own, so the walk has
        # to mirror `assign_paths` rather than read the stored path.
        self.same(["show", "examples/hello.logos", "hello/main/0"])
        self.same(["show", "examples/hello.logos", "hello/main/1"])
        self.assertEqual(_port(["show", "examples/hello.logos", "hello/main/1"]).stdout, "()\n")

    def test_show_the_file_itself(self):
        self.same(["show", "examples/hello.logos", ""])
        done = _port(["show", "examples/hello.logos", ""])
        self.assertEqual(done.stdout, (ROOT / "examples" / "hello.logos").read_text())

    def test_show_every_path_of_a_file(self):
        """Every node path Python assigns is a path the port can address."""
        from logos.nodes import assign_paths
        from logos.parser import parse

        for name in ("examples/hello.logos", "src/std/map.logos",
                     "tests/exec/closures.logos"):
            root = parse((ROOT / name).read_text(encoding="utf-8"), name)
            assign_paths(root)
            for node in root.walk():
                self.same(["show", name, node.path])

    def test_show_a_path_that_does_not_exist(self):
        done = _port(["show", "examples/hello.logos", "hello/main/9"])
        self.assertEqual(done.returncode, 1)
        self.assertEqual(
            done.stderr,
            "logos: show: no node at path 'hello/main/9' in examples/hello.logos\n",
        )
        self.same(["show", "examples/hello.logos", "hello/main/9"])

    def test_show_a_path_that_does_not_spell_every_miss(self):
        for path in ("hello", "/hello/main", "hello//main", "hello/main/1/0", "x/1/2"):
            self.same(["show", "examples/hello.logos", path])

    def test_show_a_file_that_does_not_exist(self):
        done = _port(["show", "/nope.logos", "/x"])
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stderr, "logos: /nope.logos: No such file or directory\n")
        self.same(["show", "/nope.logos", "/x"])

    # -- the usage block and the exit codes ------------------------------

    def test_no_argument_prints_the_help_and_exits_zero(self):
        done = _port([])
        oracle = _python([])
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stderr, "")
        self.assertEqual(done.stdout, oracle.stdout.replace(HELP_ROW, ""))

    def test_the_help_names_no_patch(self):
        self.assertNotIn("patch", _port([]).stdout)

    def test_an_unknown_verb_is_argparse_s_invalid_choice(self):
        done = _port(["frobnicate"])
        oracle = _python(["frobnicate"])
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, oracle.stderr.replace(CHOICE, ""))

    def test_patch_is_unknown(self):
        done = _port(["patch", "examples/hello.logos", "hello/main"])
        self.assertEqual(done.returncode, 2)
        self.assertIn("invalid choice: 'patch'", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_a_missing_required_argument(self):
        for arguments in (["show"], ["show", "examples/hello.logos"],
                          ["fmt"], ["build"]):
            self.same(arguments)

    def test_an_extra_word_is_unrecognized(self):
        for arguments in (["show", "examples/hello.logos", "hello/main", "x"],
                          ["version", "extra"], ["guide", "--bogus"],
                          ["guide", "--json", "--check"]):
            self.same(arguments)

    def test_a_path_that_does_not_exist(self):
        for arguments in (["fmt", "/nope.logos"], ["build", "/nope.logos"],
                          ["test", "/nope"]):
            self.same(arguments)

    # -- test --update-baseline ------------------------------------------

    def _suite(self) -> Path:
        """A scratch directory holding one suite root, `suite`.

        It lives under `build/` rather than in the system temporary directory
        because the run happens with the repository as the working directory:
        a case is built by this compiler, and the link needs the runtime beside
        the tree (`rt.c`). It also keeps the root *relative*, which is what
        makes the baseline line's path comparable — Python shortens a path
        against the working directory and the port prints the root as given.
        """
        root = Path(tempfile.mkdtemp(prefix="suite-", dir=BIN.parent))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "suite").mkdir()
        return root

    def _rel(self, scratch: Path) -> str:
        return str((scratch / "suite").relative_to(ROOT))

    def baseline(self, scratch: Path, arguments: list[str]) -> tuple[
        subprocess.CompletedProcess, subprocess.CompletedProcess, bytes | None, bytes | None
    ]:
        """Run both binaries and compare the baseline each one writes."""
        root = scratch / "suite"
        rel = self._rel(scratch)
        before = (root / "summary.txt").read_bytes() if (root / "summary.txt").is_file() else None

        oracle = _python(["test", rel, *arguments])
        after_python = (root / "summary.txt").read_bytes() if (root / "summary.txt").is_file() else None
        (root / "summary.txt").unlink()
        if before is not None:
            (root / "summary.txt").write_bytes(before)

        mine = _port(["test", rel, *arguments])
        after_port = (root / "summary.txt").read_bytes() if (root / "summary.txt").is_file() else None
        return oracle, mine, after_python, after_port

    def test_full_update_writes_python_s_baseline(self):
        scratch = self._suite()
        _plant(scratch / "suite", "exec", "hello", HELLO)
        _plant(scratch / "suite", "mem", "fine", FINE)
        oracle, mine, want, got = self.baseline(scratch, ["--opt", "-O0", "--update-baseline"])
        self.assertEqual(mine.returncode, oracle.returncode)
        self.assertEqual(mine.stdout, oracle.stdout)
        self.assertEqual(mine.stderr, oracle.stderr)
        self.assertEqual(got, want)
        self.assertEqual(
            got.decode(),
            "LEAKS 0\n"
            "OPTS -O0\n"
            "PASS exec/hello/hello/prints -\n"
            "PASS mem/fine/fine/frees -\n",
        )

    def test_a_full_update_rewrites_even_when_nothing_changed(self):
        scratch = self._suite()
        _plant(scratch / "suite", "exec", "hello", HELLO)
        _, _, want, got = self.baseline(scratch, ["--opt", "-O0", "--update-baseline"])
        self.assertEqual(got, want)
        # The file is the same bytes; the second run must still have written it.
        path = scratch / "suite" / "summary.txt"
        before = path.stat().st_mtime_ns
        _port(["test", self._rel(scratch), "--opt", "-O0", "--update-baseline"])
        self.assertEqual(path.read_bytes(), got)
        self.assertGreaterEqual(path.stat().st_mtime_ns, before)

    def test_a_filtered_update_merges_and_drops_the_stale_line(self):
        scratch = self._suite()
        suite = scratch / "suite"
        _plant(suite, "exec", "hello", HELLO)
        _plant(suite, "mem", "fine", FINE)
        gone = _plant(suite, "exec", "gone",
                      '(mod gone)\n\n(test prints\n  (expect (out "bye\\\\n") (code 0))\n  (println "bye"))\n')
        _port(["test", self._rel(scratch), "--opt", "-O0", "--update-baseline"])
        self.assertIn("exec/gone/gone/prints", (suite / "summary.txt").read_text())

        gone.unlink()
        oracle, mine, want, got = self.baseline(
            scratch, ["--only", "exec", "--opt", "-O0", "--update-baseline"]
        )
        self.assertEqual(mine.returncode, oracle.returncode)
        self.assertEqual(mine.stdout, oracle.stdout)
        self.assertEqual(got, want)
        self.assertNotIn(b"exec/gone/gone/prints", got or b"")
        self.assertIn(b"PASS exec/hello/hello/prints -", got or b"")
        self.assertIn(b"PASS mem/fine/fine/frees -", got or b"")

    def test_a_failing_filtered_update_records_fail_and_exits_one(self):
        scratch = self._suite()
        suite = scratch / "suite"
        _plant(suite, "exec", "hello", HELLO)
        _plant(suite, "mem", "fine", FINE)
        _port(["test", self._rel(scratch), "--opt", "-O0", "--update-baseline"])
        _plant(suite, "exec", "hello", BROKEN_HELLO)
        oracle, mine, want, got = self.baseline(
            scratch, ["--only", "exec", "--opt", "-O0", "--update-baseline"]
        )
        self.assertEqual(oracle.returncode, 1)
        self.assertEqual(mine.returncode, 1)
        self.assertEqual(mine.stdout, oracle.stdout)
        self.assertEqual(got, want)
        self.assertIn(b"FAIL exec/hello/hello/prints -O0: stdout:", got or b"")

    def test_a_fresh_filtered_update_has_no_headers(self):
        """With no baseline to merge into, Python writes only what it ran."""
        scratch = self._suite()
        _plant(scratch / "suite", "exec", "hello", HELLO)
        oracle, mine, want, got = self.baseline(
            scratch, ["--only", "exec", "--opt", "-O0", "--update-baseline"]
        )
        self.assertEqual(mine.returncode, oracle.returncode)
        self.assertEqual(got, want)
        self.assertEqual(got, b"PASS exec/hello/hello/prints -\n")

    def test_update_baseline_refuses_a_file_and_a_category_directory(self):
        scratch = self._suite()
        _plant(scratch / "suite", "exec", "hello", HELLO)
        rel = self._rel(scratch)
        for target in (f"{rel}/exec/hello/hello.logos", f"{rel}/exec",
                       f"{rel}/exec/hello", "nope"):
            mine = _port(["test", target, "--opt", "-O0", "--update-baseline"])
            oracle = _python(["test", target, "--opt", "-O0", "--update-baseline"])
            self.assertEqual(mine.returncode, 2, target)
            self.assertEqual(mine.stderr, oracle.stderr, target)
            self.assertEqual(mine.stdout, "")


if __name__ == "__main__":
    unittest.main()
