"""The compiler finds the runtime and the standard library by its own location.

The defect this prevents: for one release the compiler was packaged, released
and installable, and installing it still meant *running it from the unpacked
directory*. Both lookups were resolved from the working directory, so the same
binary that worked inside the prefix failed from anywhere else:

    $ cd /tmp && /prefix/bin/logosc build /abs/greet.logos -o greet
    greet/0: E0005: unknown module 'str'

and, for a program with no imports, `logos: runtime not found:
logos/runtime/rt.c` with no diagnostic code at all — the one failure shape an
agent cannot classify.

These tests drive the compiler binary the gates test, from a working directory
that is not the prefix, which is the only place this defect is visible: a case
under `tests/` runs in the repository root, where the old cwd-relative rule
happened to be right. They pin the whole contract:

- both paths resolve from the executable's own location, with `LOGOS_ROOT`
  unset (the installed case, and the reason a symlink to the binary still
  works: `/proc/self/exe` is the resolved path);
- `LOGOS_ROOT` overrides the prefix, and `LOGOS_PATH` adds module directories;
- the working directory is still the *last* entry in the search order, because
  the repository's own gates and fixtures build with relative paths;
- a failure prints the search order, so the diagnostic says what was tried
  instead of looking like a typo in the source;
- a missing runtime is `E0800` at the file being built, with the runtime's
  usual exit status 1 and the IR it had written removed;
- with `--json`, the same fault is one JSON object per line like every other
  diagnostic, so an agent's parser does not fall over on the one code that
  arrives after lowering.

A corpus case cannot express this: `tests/` always has a runtime and a standard
library beside it, so no `.logos` file can make the lookup fail. The level that
can is a binary copied into a prefix that lacks them, which is this file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "logosc"
RUNTIME = ROOT / "logos" / "runtime"
STDLIB = ROOT / "src" / "std"

HELLO = """(mod hello)

(fn main :void ()
  (println "hello"))
"""

GREET = """(mod greet)

(use str)

(fn main :void ()
  (if (string-starts-with "logos" "lo")
    (println "std ok")
    (println "std broken")))
"""

HELPER = """(mod helper)

(fn helper-greeting :str ()
  (ret "from LOGOS_PATH"))
"""

USES_HELPER = """(mod uses-helper)

(use helper)

(fn main :void ()
  (println (helper-greeting)))
"""


def environment(**extra: str) -> dict[str, str]:
    """The test's environment with the two overrides removed, then applied.

    Inheriting LOGOS_ROOT or LOGOS_PATH from the caller would silently turn the
    "installed, nothing set" case into an override case, which is the one thing
    these tests are here to tell apart.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in {"LOGOS_ROOT", "LOGOS_PATH"}
    }
    env.update(extra)
    return env


def ensure_compiler() -> None:
    """Build the compiler the gates test, once, from the repository root.

    tools/logosc.sh checks the stage-0 against its recorded hash and rebuilds
    build/logosc from src/ when the source is newer. It runs from the
    repository root, which is why every test below copies the binary out of the
    build directory instead of invoking the wrapper.
    """
    result = subprocess.run(
        [str(ROOT / "tools" / "logosc.sh"), "version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not BIN.is_file():
        raise unittest.SkipTest(
            "no compiler at build/logosc to test: " + result.stdout + result.stderr
        )


class InstallLayoutTest(unittest.TestCase):
    """A build from a directory that is not the prefix."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_compiler()

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="logos-install-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prefix = self.tmp / "prefix"
        (self.prefix / "bin").mkdir(parents=True)
        shutil.copy2(BIN, self.prefix / "bin" / "logosc")
        # The shipped layout: the runtime and the library sit at the prefix, in
        # the paths the repository spells them, which is what tools/dist.sh
        # stages.
        (self.prefix / "logos" / "runtime").mkdir(parents=True)
        for name in ("rt.c", "rt.h"):
            shutil.copy2(RUNTIME / name, self.prefix / "logos" / "runtime" / name)
        (self.prefix / "src" / "std").mkdir(parents=True)
        for module in STDLIB.glob("*.logos"):
            shutil.copy2(module, self.prefix / "src" / "std" / module.name)
        self.elsewhere = self.tmp / "elsewhere"
        self.elsewhere.mkdir()
        self.compiler = self.prefix / "bin" / "logosc"

    def build(self, source: str, name: str, **extra: str) -> subprocess.CompletedProcess:
        path = self.elsewhere / name
        path.write_text(source)
        return subprocess.run(
            [str(self.compiler), "build", str(path), "-o", str(self.elsewhere / Path(name).stem)],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(**extra),
        )

    def test_a_program_with_no_imports_builds_and_runs_from_any_directory(self):
        result = self.build(HELLO, "hello.logos")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        run = subprocess.run(
            [str(self.elsewhere / "hello")], capture_output=True, text=True
        )
        self.assertEqual(run.stdout, "hello\n")

    def test_the_standard_library_resolves_without_logos_root(self):
        result = self.build(GREET, "greet.logos")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run = subprocess.run(
            [str(self.elsewhere / "greet")], capture_output=True, text=True
        )
        self.assertEqual(run.stdout, "std ok\n")

    def test_logos_root_overrides_the_prefix(self):
        # The binary does not sit in a prefix of its own any more, so the only
        # way to find the shipped files is the override.
        moved = self.tmp / "moved"
        moved.mkdir()
        bare = moved / "logosc"
        shutil.copy2(self.compiler, bare)
        path = self.elsewhere / "greet.logos"
        path.write_text(GREET)
        result = subprocess.run(
            [str(bare), "build", str(path), "-o", str(self.elsewhere / "greet")],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(LOGOS_ROOT=str(self.prefix)),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_logos_path_adds_a_module_directory(self):
        modules = self.tmp / "modules"
        modules.mkdir()
        (modules / "helper.logos").write_text(HELPER)
        result = self.build(
            USES_HELPER, "uses-helper.logos", LOGOS_PATH=str(modules)
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run = subprocess.run(
            [str(self.elsewhere / "uses-helper")], capture_output=True, text=True
        )
        self.assertEqual(run.stdout, "from LOGOS_PATH\n")

    def test_the_working_directory_is_still_the_last_entry(self):
        # A compiler with no prefix of its own, and the two paths beside the
        # program being built instead of beside the compiler: the rule the
        # repository's own fixtures rely on.
        bare_dir = self.tmp / "bare"
        (bare_dir / "bin").mkdir(parents=True)
        shutil.copy2(self.compiler, bare_dir / "bin" / "logosc")
        (self.elsewhere / "logos" / "runtime").mkdir(parents=True)
        for name in ("rt.c", "rt.h"):
            shutil.copy2(
                RUNTIME / name, self.elsewhere / "logos" / "runtime" / name
            )
        (self.elsewhere / "src" / "std").mkdir(parents=True)
        for module in STDLIB.glob("*.logos"):
            shutil.copy2(module, self.elsewhere / "src" / "std" / module.name)
        path = self.elsewhere / "greet.logos"
        path.write_text(GREET)
        result = subprocess.run(
            [str(bare_dir / "bin" / "logosc"), "build", str(path), "-o", str(self.elsewhere / "greet")],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_symlinked_compiler_resolves_to_its_real_prefix(self):
        links = self.tmp / "links"
        links.mkdir()
        os.symlink(self.compiler, links / "logosc")
        path = self.elsewhere / "greet.logos"
        path.write_text(GREET)
        result = subprocess.run(
            [str(links / "logosc"), "build", str(path), "-o", str(self.elsewhere / "greet")],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class DiagnosticTest(unittest.TestCase):
    """What a failure prints, which is what an agent has to act on."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_compiler()

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="logos-diag-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prefix = self.tmp / "prefix"
        (self.prefix / "bin").mkdir(parents=True)
        shutil.copy2(BIN, self.prefix / "bin" / "logosc")
        self.elsewhere = self.tmp / "elsewhere"
        self.elsewhere.mkdir()
        self.compiler = self.prefix / "bin" / "logosc"

    def test_a_missing_module_names_every_directory_it_searched(self):
        path = self.elsewhere / "greet.logos"
        path.write_text(GREET)
        result = subprocess.run(
            [str(self.compiler), "build", str(path), "-o", str(self.elsewhere / "greet")],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("greet/0: E0005: unknown module 'str'; searched: ", result.stderr)
        # The asking file's own directory first, the working directory last.
        self.assertIn(str(self.elsewhere / "str.logos"), result.stderr)
        first = result.stderr.splitlines()[0]
        self.assertTrue(first.endswith(", src/std/str.logos"), result.stderr)
        # And the node the path names follows, indented four spaces.
        self.assertEqual(result.stderr.splitlines()[1], "    (use str)")

    def test_a_missing_runtime_is_a_classified_diagnostic(self):
        path = self.elsewhere / "hello.logos"
        path.write_text(HELLO)
        out = self.elsewhere / "hello"
        result = subprocess.run(
            [str(self.compiler), "build", str(path), "-o", str(out)],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(LOGOS_ROOT=str(self.tmp / "nowhere")),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{path}: E0800: runtime not found; searched: ", result.stderr)
        self.assertIn(str(self.tmp / "nowhere" / "logos" / "runtime" / "rt.c"), result.stderr)
        self.assertIn("logos/runtime/rt.c", result.stderr)
        # Nothing half-built is left behind: no binary, and the IR the compiler
        # had written is removed with the failure.
        self.assertFalse(out.exists())
        self.assertFalse((self.elsewhere / "build" / "hello.ll").exists())

    def test_a_missing_runtime_is_json_when_json_is_asked_for(self):
        path = self.elsewhere / "hello.logos"
        path.write_text(HELLO)
        result = subprocess.run(
            [str(self.compiler), "build", str(path),
             "-o", str(self.elsewhere / "hello"), "--json"],
            cwd=self.elsewhere,
            capture_output=True,
            text=True,
            env=environment(LOGOS_ROOT=str(self.tmp / "nowhere")),
        )
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stderr)
        self.assertEqual(1, report["schema_version"])
        (diagnostic,) = report["diagnostics"]
        self.assertEqual("E0800", diagnostic["code"])
        self.assertEqual(str(path), diagnostic["file"])
        self.assertEqual("", diagnostic["node_path"])
        self.assertIn("runtime not found; searched: ", diagnostic["message"])


if __name__ == "__main__":
    unittest.main()
