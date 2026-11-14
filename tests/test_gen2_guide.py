"""`gen2 guide` is Python's `guide`: the manual, the manifest, and the drift check.

`guide` is the last verb W8 ports, and it is the one verb whose output is
byte-compared with a committed file: `docs/LOGOS.md` is generated, never
edited, and `guide --check` is the gate's manual-drift phase. The port builds
that file from the tables the compiler itself uses — the code table in
`diag.py`, the primitive and type-form lists in `types.py`, the reserved names
in `check.py`, the categories in `tester.py` — plus the editorial tables only
the manual needs (the ten rules, the arities and meanings, the chapter titles)
and the twenty chapters under `docs/manual/`, each rendered by the same printer
`fmt` uses.

This test judges the verb at the command line, against Python on the same tree:

* `guide` must print the same bytes as `python3 -m logos guide`;
* `guide --json` must print the same bytes as `python3 -m logos guide --json`,
  which is the 18 KB manifest with seven keys;
* `guide --check` must accept the committed manual and print one line, and must
  reject an edited chapter. The stale case runs in a scratch directory holding
  a copy of `docs/manual/` and `docs/LOGOS.md`, because the port resolves both
  against the working directory and a test must not write to the tree it is
  judging. The port renders a chapter through `fmt` into `build/` and reads it
  back, so the copy gets its own `build/` too.

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

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "test-gen2-guide" / "gen2"

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

#: The chapter whose expected output the stale case edits. It is the first
#: chapter in file order, so a diff that numbers lines is stable.
EDITED = "01-values-and-literals.logos"


def _run(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, env=ENV)


class Gen2GuideTest(unittest.TestCase):
    """The `guide` verb, judged through the binary against Python."""

    @classmethod
    def setUpClass(cls) -> None:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        done = _run([sys.executable, "-m", "logos", "build", *SOURCES, "-o", str(BIN)], ROOT)
        if done.returncode != 0 or not BIN.is_file():
            raise AssertionError(f"could not build gen2: {done.stdout}{done.stderr}")

    # -- the manual ------------------------------------------------------

    def test_markdown_is_byte_identical_to_python(self):
        mine = _run([str(BIN), "guide"], ROOT)
        oracle = _run([sys.executable, "-m", "logos", "guide"], ROOT)
        self.assertEqual(oracle.returncode, 0, oracle.stderr)
        self.assertEqual(mine.returncode, 0, mine.stderr)
        self.assertEqual(mine.stdout, oracle.stdout)
        self.assertEqual(mine.stderr, "")
        self.assertEqual(mine.stdout.encode(), (ROOT / "docs" / "LOGOS.md").read_bytes())

    # -- the manifest ----------------------------------------------------

    def test_manifest_is_byte_identical_to_python(self):
        mine = _run([str(BIN), "guide", "--json"], ROOT)
        oracle = _run([sys.executable, "-m", "logos", "guide", "--json"], ROOT)
        self.assertEqual(oracle.returncode, 0, oracle.stderr)
        self.assertEqual(mine.returncode, 0, mine.stderr)
        self.assertEqual(mine.stdout, oracle.stdout)
        self.assertEqual(mine.stdout.count('"'), oracle.stdout.count('"'))

    # -- the drift check -------------------------------------------------

    def test_check_accepts_the_committed_manual(self):
        done = _run([str(BIN), "guide", "--check"], ROOT)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "guide: docs/LOGOS.md is current\n")
        self.assertEqual(done.stderr, "")

    def _tree(self) -> Path:
        """A scratch checkout holding just what `guide --check` reads."""
        root = Path(tempfile.mkdtemp(prefix="gen2-guide-"))
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(ROOT / "docs" / "manual", root / "docs" / "manual")
        (root / "docs" / "LOGOS.md").write_bytes((ROOT / "docs" / "LOGOS.md").read_bytes())
        (root / "build").mkdir()
        return root

    def test_check_passes_on_a_copy(self):
        done = _run([str(BIN), "guide", "--check"], self._tree())
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_check_fails_when_a_chapter_is_edited(self):
        root = self._tree()
        chapter = root / "docs" / "manual" / EDITED
        text = chapter.read_text(encoding="utf-8")
        changed = text.replace('-7\\n', '-8\\n', 1)
        self.assertNotEqual(changed, text, "the fixture must change the chapter")
        chapter.write_text(changed, encoding="utf-8")
        done = _run([str(BIN), "guide", "--check"], root)
        self.assertEqual(done.returncode, 1)
        self.assertIn("docs/LOGOS.md is stale", done.stderr)
        self.assertIn("logosc guide > docs/LOGOS.md", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_check_reports_a_missing_manual(self):
        root = self._tree()
        (root / "docs" / "LOGOS.md").unlink()
        done = _run([str(BIN), "guide", "--check"], root)
        self.assertEqual(done.returncode, 1)
        self.assertIn("docs/LOGOS.md is missing", done.stderr)


if __name__ == "__main__":
    unittest.main()
