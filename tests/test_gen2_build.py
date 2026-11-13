"""`gen2 build` is a compiler driver: it links, and it fails in one line.

The port emitted LLVM IR and stopped (`main-spit`); Python's `build` writes the
same text and then runs clang over it and the C runtime (`driver.py:225-265`).
This test judges the difference at the command line, where a caller sees it: the
default output, the `--opt` pass-through, the exit status and the single
`logos: …` line a failed link prints. The self-hosted gate (`tools/selfhost.sh`)
compares the IR that `gen2 build` writes; nothing else compared the binary, so
the parity case below builds one program both ways and requires the two
executables to be equal byte for byte. They can be: clang embeds the IR file's
basename and nothing else about the path, and both drivers keep the text at
`build/<stem>.ll`, which is why the driver has a fixed IR path instead of
`-o`.

The compiler under test is built once per run from the same source set
`tools/selfhost.sh` builds `gen2` from, with Python, because a compiler is the
only way to build a compiler before one exists.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "test-gen2" / "gen2"

#: Sources the gate builds `gen2` from: every module plus the two the compiler's
#: tables name. Sorted, so the first stem is `body_test` exactly as the shell's
#: `src/logosc/*.logos` glob orders it.
SOURCES = sorted(str(path) for path in (ROOT / "src" / "logosc").glob("*.logos")) + [
    str(ROOT / "src" / "std" / "map.logos"),
    str(ROOT / "src" / "std" / "str.logos"),
]

#: A program whose whole binary is one call to `println`.
PROGRAM = """(mod gen2cli)

(fn main :i64 ()
  (println "hi")
  (ret 0))
"""

#: A second root, so the first file's stem is the one the default output uses.
EXTRA = """(mod gen2cli-extra)

(fn twice :i64 ((n :i64))
  (ret (+ n n)))
"""


def _run(arguments: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    """Run the compiler and capture both streams as text."""
    return subprocess.run(arguments, cwd=cwd, capture_output=True, text=True)


class Gen2BuildTest(unittest.TestCase):
    """The `build` verb's process contract, judged through the binary."""

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)])
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")

    def setUp(self) -> None:
        self.work = ROOT / "build" / "test-gen2"
        self.work.mkdir(parents=True, exist_ok=True)
        self.source = self.work / "gen2cli.logos"
        self.source.write_text(PROGRAM, encoding="utf-8")
        self.extra = self.work / "gen2cli-extra.logos"
        self.extra.write_text(EXTRA, encoding="utf-8")
        for name in ("gen2cli", "gen2cli.ll", "gen2cli-early", "gen2cli-python"):
            self.addCleanup(self._remove, ROOT / "build" / name)

    @staticmethod
    def _remove(path: Path) -> None:
        """Remove a build artefact, if the test got as far as writing one."""
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def test_build_links_by_default_at_the_first_stems_name(self):
        """No `-o`: the binary is `build/<first stem>` and it runs."""
        done = _run([str(BIN), "build", str(self.source), str(self.extra)])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "")
        binary = ROOT / "build" / "gen2cli"
        self.assertTrue(binary.is_file(), "the default output is build/<first stem>")
        self.assertTrue((ROOT / "build" / "gen2cli.ll").is_file())
        ran = _run([str(binary)])
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, "hi\n")

    def test_the_binary_is_pythons_byte_for_byte(self):
        """Same flags and same IR path, so the executable cannot differ."""
        mine = self.work / "port-binary"
        self.addCleanup(self._remove, mine)
        done = _run([str(BIN), "build", str(self.source), "-o", str(mine)])
        self.assertEqual(done.returncode, 0, done.stderr)
        port_ll = (ROOT / "build" / "gen2cli.ll").read_bytes()
        theirs = ROOT / "build" / "gen2cli-python"
        done = _run(
            [sys.executable, "-m", "logos", "build", str(self.source), "-o", str(theirs)]
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((ROOT / "build" / "gen2cli.ll").read_bytes(), port_ll)
        self.assertEqual(mine.read_bytes(), theirs.read_bytes())

    def test_opt_is_passed_to_clang(self):
        """A flag clang rejects proves `--opt` reaches it, and fails as one line.

        The failure is the point: no traceback, no panic line, no signal — the
        exit status is 1 and stderr starts with the command that was run.
        """
        out = self.work / "gen2cli-clang"
        done = _run(
            [str(BIN), "build", str(self.source), "--opt", "-fno-such-option", "-o", str(out)]
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        first, _, rest = done.stderr.partition("\n")
        self.assertEqual(
            first,
            "logos: clang failed: clang -fno-such-option -target "
            "x86_64-unknown-linux-gnu build/gen2cli.ll logos/runtime/rt.c "
            f"-o {out} -lpthread -lm",
        )
        self.assertIn("-fno-such-option", rest)
        self.assertFalse(out.exists(), "a failed link leaves no binary")
        self.assertFalse(
            (ROOT / "build" / "gen2cli.ll").exists(),
            "a failed link leaves no IR",
        )

    def test_a_missing_runtime_is_one_line_and_exit_one(self):
        """A compiler that cannot find its runtime says so; it does not panic.

        The runtime is named relative to the working directory, so a build run
        from a directory without `logos/runtime/rt.c` is the one way to make it
        absent without moving the checkout.
        """
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp)
            (here / "build").mkdir()
            shutil.copy(self.source, here / "gen2cli.logos")
            done = _run([str(BIN), "build", "gen2cli.logos"], cwd=here)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertEqual(
                done.stderr, "logos: runtime not found: logos/runtime/rt.c\n"
            )
            self.assertEqual(list((here / "build").iterdir()), [])

    def test_attached_opt_and_keep_ir_are_accepted(self):
        """`--opt=-O0` and `--keep-ir` parse; the IR is always kept anyway."""
        out = self.work / "gen2cli-attached"
        done = _run(
            [
                str(BIN),
                "build",
                str(self.source),
                "--opt=-O0",
                "--keep-ir",
                "-o",
                str(out),
            ]
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        ran = _run([str(out)])
        self.assertEqual((ran.returncode, ran.stdout), (0, "hi\n"))
        self.assertTrue((ROOT / "build" / "gen2cli.ll").is_file())
        self.addCleanup(self._remove, out)

    def test_the_output_flag_may_come_before_the_files(self):
        """The flag is a flag, not the fifth word on the line."""
        out = ROOT / "build" / "gen2cli-early"
        done = _run([str(BIN), "build", "-o", str(out), str(self.source)])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(out.is_file())

    def test_a_command_line_with_no_file_is_usage(self):
        """Nothing to build is a usage error, not a link with an empty set."""
        done = _run([str(BIN), "build", "-o", "build/gen2cli-nothing"])
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, "")
        self.assertTrue(done.stderr.startswith("usage: gen2"))

    def test_an_unknown_flag_is_usage(self):
        """A flag the driver does not know is refused before any lowering."""
        done = _run([str(BIN), "build", str(self.source), "--bogus"])
        self.assertEqual(done.returncode, 2)
        self.assertTrue(done.stderr.startswith("usage: gen2"))


if __name__ == "__main__":
    unittest.main()
