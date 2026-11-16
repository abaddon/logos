"""The CLI contract: verbs, flags, streams, exit codes, and JSON output.

Every assertion here is a promise the compiler makes to an agent that drives
it. The compiler is addressed through `build/logosc`, the binary the gates
build from `src/`, not through `tools/logosc.sh` — the wrapper changes the
working directory to the repository root, and two of these tests exist
precisely because the compiler must not need that.

Exit codes (see docs/reference/cli.md):
  0  success
  2  a source error, a usage error, or a failed `guide --check`
  1  an I/O or toolchain failure
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGOSC = os.path.join(ROOT, "tools", "logosc.sh")
BINARY = os.path.join(ROOT, "build", "logosc")

# One program per failing phase: the lexer, the parser, the resolver, the
# checker and the lowerer must each be able to say what went wrong in JSON.
PHASES = [
    ("lex", '  (println "oops)\n', "E0006"),
    ("parse", "  (println (+ 1 2)\n", "E0001"),
    ("check", '  (println (+ 1 "x"))\n', "E0100"),
    ("lower", "  (break)\n", "E0002"),
]

RESOLVE_SOURCE = "(mod resolve)\n\n(use nomod)\n\n(fn main :i64 ()\n  (ret 0))\n"

DIAGNOSTIC_FIELDS = {
    "severity",
    "code",
    "message",
    "node_path",
    "file",
    "line",
    "col",
}


def binary():
    """The compiler the gates build, built on first use."""
    if not os.access(BINARY, os.X_OK):
        subprocess.run([LOGOSC, "version"], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    return BINARY


def run(args, cwd=None, stdin=None):
    return subprocess.run([binary()] + args, cwd=cwd or ROOT, input=stdin,
                          capture_output=True, text=True, timeout=120)


def program(mod, body):
    return "(mod %s)\n\n(fn main :i64 ()\n%s  (ret 0))\n" % (mod, body)


def write(directory, name, text):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def last_json(stderr):
    """The last non-empty line of stderr, parsed as one JSON object."""
    lines = [line for line in stderr.splitlines() if line.strip()]
    return json.loads(lines[-1])


class Version(unittest.TestCase):
    def test_text_form_is_stable(self):
        done = run(["version"])
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "logos 0.2.0\n")

    def test_json_form_is_machine_readable(self):
        done = run(["version", "--json"])
        self.assertEqual(done.returncode, 0)
        report = json.loads(done.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["name"], "logos")
        self.assertRegex(report["version"], r"^\d+\.\d+\.\d+$")

    def test_version_flag_matches_the_verb(self):
        self.assertEqual(run(["--version"]).stdout, run(["version"]).stdout)


class ExitCodes(unittest.TestCase):
    def test_success_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "ok.logos", program("ok", ""))
            done = run(["check", "ok.logos"], cwd=tmp)
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stdout, "")
            self.assertEqual(done.stderr, "")

    def test_source_error_is_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "bad.logos", program("bad", '  (println (+ 1 "x"))\n'))
            self.assertEqual(run(["build", "bad.logos"], cwd=tmp).returncode, 2)

    def test_usage_error_is_two(self):
        done = run(["build", "--frobnicate"])
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments", done.stderr)

    def test_missing_file_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(["build", "gone.logos"], cwd=tmp).returncode, 1)

    def test_every_reading_verb_reports_a_missing_file_the_same_way(self):
        """An unreadable input is an I/O failure for every verb, never a panic."""
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "here.logos", program("here", ""))
            calls = [
                ["build", "gone.logos"],
                ["check", "gone.logos"],
                ["resolve", "gone.logos"],
                ["fmt", "gone.logos"],
                ["show", "gone.logos", "here/0"],
            ]
            for args in calls:
                with self.subTest(verb=args[0]):
                    done = run(args, cwd=tmp)
                    self.assertEqual(done.returncode, 1, done.stderr)
                    self.assertTrue(done.stderr.startswith("logos: "), done.stderr)
                    self.assertIn("gone.logos", done.stderr)
                    self.assertNotIn("R0007", done.stderr)

    def test_multi_file_resolve_reports_a_missing_file_as_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "here.logos", program("here", ""))
            done = run(["resolve", "here.logos", "gone.logos"], cwd=tmp)
            self.assertEqual(done.returncode, 1, done.stderr)
            self.assertTrue(done.stderr.startswith("logos: "), done.stderr)
            self.assertIn("gone.logos", done.stderr)

    def test_a_directory_argument_is_an_io_failure_not_a_panic(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "adir"))
            for args in (["build", "adir"], ["check", "adir"], ["resolve", "adir"]):
                with self.subTest(verb=args[0]):
                    done = run(args, cwd=tmp)
                    self.assertEqual(done.returncode, 1, done.stderr)
                    self.assertTrue(done.stderr.startswith("logos: "), done.stderr)
                    self.assertNotIn("R0007", done.stderr)

    def test_fmt_source_error_is_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.logos",
                         '(mod bad)\n\n(fn main :i64 ()\n  (println "oops)\n')
            self.assertEqual(run(["fmt", path]).returncode, 2)


class JsonDiagnostics(unittest.TestCase):
    def test_every_phase_reports_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [(name, program(name, body), code) for name, body, code in PHASES]
            cases.append(("resolve", RESOLVE_SOURCE, "E0005"))
            for name, source, code in cases:
                with self.subTest(phase=name):
                    path = write(tmp, name + ".logos", source)
                    done = run(["build", path, "--json"])
                    self.assertEqual(done.returncode, 2, done.stderr)
                    report = last_json(done.stderr)
                    self.assertEqual(report["schema_version"], 1)
                    self.assertEqual(len(report["diagnostics"]), 1)
                    diag = report["diagnostics"][0]
                    self.assertEqual(DIAGNOSTIC_FIELDS, set(diag))
                    self.assertEqual(diag["severity"], "error")
                    self.assertEqual(diag["code"], code)
                    self.assertRegex(diag["code"], r"^[ER]\d{4}$")
                    self.assertNotEqual(diag["message"], "")
                    self.assertIn(diag["file"], (name + ".logos", path))
                    self.assertGreaterEqual(diag["line"], 0)
                    self.assertGreaterEqual(diag["col"], 0)
                    if name in ("lex", "parse"):
                        self.assertGreater(diag["line"], 0)
                    else:
                        self.assertNotEqual(diag["node_path"], "")

    def test_the_flag_may_precede_the_verb(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.logos", program("bad", '  (println (+ 1 "x"))\n'))
            before = run(["--json", "build", path]).stderr
            after = run(["build", path, "--json"]).stderr
            self.assertEqual(before, after)
            self.assertEqual(last_json(before)["diagnostics"][0]["code"], "E0100")

    def test_human_text_remains_the_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.logos", program("bad", '  (println (+ 1 "x"))\n'))
            done = run(["build", path])
            self.assertEqual(done.returncode, 2)
            self.assertNotIn("{", done.stderr)
            self.assertRegex(done.stderr, r"^bad/main/2/0: E0100: .+\n$")

    def test_a_json_line_is_a_complete_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.logos", program("bad", "  (break)\n"))
            for line in run(["build", path, "--json"]).stderr.splitlines():
                if line.strip():
                    json.loads(line)

    def test_lexer_positions_survive_into_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "lex.logos", program("lex", '  (println "oops)\n'))
            diag = last_json(run(["build", path, "--json"]).stderr)["diagnostics"][0]
            self.assertEqual(diag["code"], "E0006")
            self.assertEqual((diag["line"], diag["col"]), (4, 12))


class Help(unittest.TestCase):
    def test_every_verb_has_its_own_help(self):
        for verb in ["build", "check", "fmt", "guide", "resolve", "show",
                     "test", "version"]:
            with self.subTest(verb=verb):
                done = run([verb, "-h"])
                self.assertEqual(done.returncode, 0, verb)
                self.assertTrue(done.stdout.startswith("usage: logosc " + verb),
                                done.stdout)

    def test_top_level_help_lists_every_verb(self):
        done = run(["-h"])
        self.assertEqual(done.returncode, 0)
        for verb in ["build", "check", "fmt", "guide", "resolve", "show",
                     "test", "version"]:
            self.assertIn("    " + verb, done.stdout)

    def test_invalid_choice_names_every_verb(self):
        done = run(["nope"])
        self.assertEqual(done.returncode, 2)
        self.assertIn("'resolve'", done.stderr)


class Portability(unittest.TestCase):
    """The compiler must work from any working directory, and find its own
    runtime and standard library from where it is installed."""

    def test_build_and_run_outside_the_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "hello.logos", program("hello", '  (println "hello")\n'))
            done = run(["build", "hello.logos"], cwd=tmp)
            self.assertEqual(done.returncode, 0, done.stderr)
            built = subprocess.run([os.path.join(tmp, "build", "hello")],
                                   capture_output=True, text=True)
            self.assertEqual(built.stdout, "hello\n")
            self.assertEqual(built.returncode, 0)

    def test_stdlib_modules_resolve_from_the_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = ("(mod usesmap)\n\n(use map)\n\n(fn main :i64 ()\n"
                      "  (letmut keys (vec :str)\n    (make (vec :str)))\n"
                      "  (letmut vals (vec :i64)\n    (make (vec :i64)))\n"
                      "  (letmut slots (vec :i64)\n    (make (vec :i64)))\n"
                      "  (map-init slots 16)\n"
                      '  (map-put keys vals slots "a" 7)\n'
                      '  (println (map-get keys vals slots "a"))\n'
                      "  (vec-free keys)\n  (vec-free vals)\n  (vec-free slots)\n"
                      "  (ret 0))\n")
            write(tmp, "usesmap.logos", source)
            done = run(["build", "usesmap.logos"], cwd=tmp)
            self.assertEqual(done.returncode, 0, done.stderr)
            built = subprocess.run([os.path.join(tmp, "build", "usesmap")],
                                   capture_output=True, text=True)
            self.assertEqual(built.stdout, "7\n")


class Determinism(unittest.TestCase):
    def test_two_builds_of_one_source_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "twice.logos",
                         program("twice", '  (println "same")\n'))
            first = os.path.join(tmp, "first")
            second = os.path.join(tmp, "second")
            self.assertEqual(run(["build", path, "-o", first]).returncode, 0)
            self.assertEqual(run(["build", path, "-o", second]).returncode, 0)
            with open(first, "rb") as one, open(second, "rb") as two:
                self.assertEqual(one.read(), two.read())


class FloatLiterals(unittest.TestCase):
    def test_a_literal_with_no_finite_value_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "too.logos", program("too", "  (println 1e999)\n"))
            done = run(["build", path, "--json"])
            self.assertEqual(done.returncode, 2)
            diag = last_json(done.stderr)["diagnostics"][0]
            self.assertEqual(diag["code"], "E0106")
            self.assertIn(":f64", diag["message"])

    def test_a_large_but_finite_literal_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "max.logos", program("max", "  (println 1e308)\n"))
            self.assertEqual(run(["build", path], cwd=tmp).returncode, 0)


class Guide(unittest.TestCase):
    def test_manifest_is_versioned(self):
        done = run(["guide", "--json"])
        self.assertEqual(done.returncode, 0)
        manifest = json.loads(done.stdout)
        self.assertEqual(manifest["schema_version"], 1)
        for key in ["forms", "types", "operators", "builtins", "reserved",
                    "codes", "categories"]:
            self.assertIn(key, manifest)


class JsonSchemas(unittest.TestCase):
    """The published schemas must describe what the compiler actually emits."""

    def test_schemas_are_valid_json_and_cover_the_emitted_keys(self):
        for name in ["diagnostic-v1.schema.json", "version-v1.schema.json"]:
            with self.subTest(schema=name):
                path = os.path.join(ROOT, "docs", "schemas", name)
                with open(path, encoding="utf-8") as handle:
                    schema = json.load(handle)
                self.assertEqual(schema["$schema"],
                                 "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("schema_version", json.dumps(schema))


class Targets(unittest.TestCase):
    """The target triple is a flag, not a constant (issue #2).

    `docs/superpowers/specs/2026-11-06-ai-language-design.md:38` promises that
    "target triple is a compiler flag, so arm64 and Darwin remain one flag".
    The flag did not exist: `build --help` did not list it, and both the IR
    header (`src/logosc/lower.logos` -> `src/logosc/emit.logos`) and clang's
    `-target` (`src/logosc/main.logos`) took a hard-coded x86_64 literal.

    These tests hold the plumbing: the flag is parsed in both spellings, its
    value reaches the IR *and* clang, the default is unchanged, and a triple
    this compiler cannot emit is refused as a usage error rather than handed
    to clang. What they do not hold is arm64 codegen (issue #10).
    """

    HOST = "x86_64-unknown-linux-gnu"

    def build_with(self, args, name="host"):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        write(tmp, name + ".logos", program(name, '  (println "hi")\n'))
        done = run(["build", name + ".logos"] + args, cwd=tmp)
        return done, tmp

    def ir(self, tmp, name="host"):
        with open(os.path.join(tmp, "build", name + ".ll"),
                  encoding="utf-8") as handle:
            return handle.read()

    def test_build_help_lists_the_target_flag(self):
        done = run(["build", "--help"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("--target", done.stdout)

    def test_an_explicit_host_triple_reaches_the_ir(self):
        done, tmp = self.build_with(["--target", self.HOST, "--keep-ir"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('target triple = "%s"' % self.HOST, self.ir(tmp))

    def test_the_attached_spelling_is_equivalent(self):
        done, tmp = self.build_with(["--target=" + self.HOST])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('target triple = "%s"' % self.HOST, self.ir(tmp))

    def test_the_default_is_still_the_host_triple(self):
        done, tmp = self.build_with([])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('target triple = "%s"' % self.HOST, self.ir(tmp))

    def test_an_unsupported_triple_is_a_usage_error(self):
        """Refused by the driver, naming the target — not a clang crash.

        The backend and the runtime still assume this host (issue #10), so a
        triple it cannot honour must exit 2 with the offending value in the
        message. A clang failure would be exit 1 and would say nothing about
        the flag the user typed.
        """
        triple = "aarch64-unknown-linux-gnu"
        done, _ = self.build_with(["--target", triple])
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn(triple, done.stderr)
        self.assertIn("usage:", done.stderr)

    def test_a_missing_target_value_is_a_usage_error(self):
        done = run(["build", "x.logos", "--target"])
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("--target", done.stderr)
        self.assertIn("expected one argument", done.stderr)


if __name__ == "__main__":
    unittest.main()
