"""The quality gates a v1 release is trusted against.

The repository already gates six things (see AGENTS.md) and pins the *shape* of
a negative fixture — one line, a code like `E0101`. Nothing pinned the other
half of that contract: that the compiler actually produces the code a fixture
claims. This module closes that hole and adds the measurements a release needs.

What it asserts, and why each one exists:

* **Every negative fixture is judged by the compiler.** `tests/**.logos` beside
  an `*.expect` sidecar is a claim about a diagnostic. The corpus harness
  short-circuits such a file to PASS once the sidecar is well formed
  (`src/logosc/harness.logos`, `h-file-parsed`), so before this module six of
  them were judged by no gate at all and four disagreed with the compiler while
  the corpus reported PASS. Each one is now built and the emitted code compared
  with the sidecar. `tools/qa-known-gaps.txt` names the ones that disagree,
  with the measurement, and must shrink.
* **Every published code is reachable.** `logosc guide --json` publishes the
  diagnostic table an agent branches on. A code in that table that nothing can
  emit is a promise the tool cannot keep, so every code must be emitted by a
  fixture under `tests/`.
* **The corpus baseline is a floor, not a memory.** Deleting cases must fail
  the gate, and every case must have a recorded verdict.
* **Repeated runs agree.** A flaky test is worse than no test; the leak and
  panic category is run twice and the two reports must be byte-identical.
* **The gates stay wired.** This module must be part of `make test`, which the
  pull request gate and CI both run, or none of the above is enforced.

Run it directly with `python3 -m unittest tests.test_qa -v`.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGOSC = ROOT / "tools" / "logosc.sh"
BINARY = ROOT / "build" / "logosc"
GUIDE = ROOT / "tools" / "qa-known-gaps.txt"
BASELINE = ROOT / "tests" / "summary.txt"
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "gate.yml"

#: A fixture whose source must fail to lex or parse cannot carry a `.logos`
#: suffix (the formatter and the self-host manifest both own that set), so it
#: keeps the suffix inside the name — `root.logos.txt` — and the resolver phase
#: of `tools/selfhost.sh` materializes it before judging it. Such a fixture is
#: out of this module's reach and judged there instead.
MATERIALIZED_SUFFIX = ".logos.txt"

#: The register in `tools/qa-known-gaps.txt` may shrink but not grow: a line
#: added to make a new failure green fails this suite instead.
MAX_KNOWN_GAPS = 4

#: Per-category case floors. They are the counts at the commit that introduced
#: this gate; a category that loses a case fails here before the corpus gate
#: notices. Raising a floor is expected work when a case is added deliberately.
CATEGORY_FLOORS = {
    "parse": 14,
    "type": 107,
    "exec": 140,
    "mem": 7,
    "thread": 8,
    "generics": 2,
    "regress": 55,
}

TOTAL_FLOOR = 333

DIAGNOSTIC_FIELDS = {
    "severity",
    "code",
    "message",
    "node_path",
    "file",
    "line",
    "col",
}

#: Codes pinned outside the corpus, each mapped to the file that exercises it.
#: A `.expect` sidecar is only judged when the compiler exits 2 on a source
#: error, so a fixture cannot express a fault of the *installation*: a source
#: that is fine, an exit status of 1, and a missing runtime no `.logos` file in
#: this repository can un-provide. `tests/test_install.py` drives a compiler
#: copied into a prefix that lacks its runtime, and `make test` runs it with the
#: other contract tests. The file has to name the code, so deleting the case
#: removes the coverage instead of leaving a silent hole here.
PYTHON_COVERAGE = {
    "E0800": "tests/test_install.py",
}

_CACHE = {}


def binary():
    """The compiler the gates build, built on first use."""
    if not os.access(BINARY, os.X_OK):
        subprocess.run([str(LOGOSC), "version"], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    return str(BINARY)


def run(args, cwd=None, timeout=120):
    return subprocess.run([binary()] + args, cwd=cwd or ROOT,
                          capture_output=True, text=True, timeout=timeout)


def guide_codes():
    """The published diagnostic table: `{code: meaning}`."""
    if "codes" not in _CACHE:
        done = run(["guide", "--json"])
        assert done.returncode == 0, done.stderr
        _CACHE["codes"] = json.loads(done.stdout)["codes"]
    return _CACHE["codes"]


def known_gaps():
    """`(codes, fixtures)` exempted by `tools/qa-known-gaps.txt`.

    Each entry is `kind subject reason...`; a reason is mandatory, because an
    exemption without one is a silent hole.
    """
    if "gaps" in _CACHE:
        return _CACHE["gaps"]
    codes, fixtures = set(), set()
    for number, line in enumerate(GUIDE.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        fields = text.split(None, 2)
        where = "%s:%d" % (GUIDE.name, number)
        if len(fields) < 3 or not fields[2].strip():
            raise AssertionError("%s: an entry needs a reason: %r" % (where, text))
        kind, subject = fields[0], fields[1]
        if kind == "code":
            codes.add(subject)
        elif kind == "fixture":
            fixtures.add(subject)
        else:
            raise AssertionError("%s: unknown kind %r (want code|fixture)" % (where, kind))
    _CACHE["gaps"] = (codes, fixtures)
    return _CACHE["gaps"]


def negative_fixtures():
    """Every `*.expect` sidecar beside a source, and how that source is reached.

    Returns `(runnable, materialized)` as lists of
    `(source_relative_path, expected_code)`. A source that must not carry a
    `.logos` suffix — a file whose whole point is that it does not lex or parse
    — is kept as `‹name›.logos.txt`; `materialize` below drops the suffix into a
    scratch copy before the compiler sees it, which is what the resolver phase of
    `tools/selfhost.sh` does with the same files.
    """
    runnable, materialized = [], []
    for sidecar in sorted(glob.glob(str(ROOT / "tests" / "**" / "*.expect"),
                                    recursive=True)):
        side = Path(sidecar)
        stem = side.with_suffix("")
        source = stem.with_suffix(".logos")
        want = side.read_text(encoding="utf-8").strip().split()
        if not want:
            continue
        expected = want[0]
        relative = str(source.relative_to(ROOT))
        if source.exists():
            runnable.append((relative, expected))
        elif Path(str(stem) + MATERIALIZED_SUFFIX).exists():
            materialized.append((relative, expected))
        else:
            raise AssertionError(
                "%s: a sidecar names a code but there is no %s beside it"
                % (side.relative_to(ROOT), source.name))
    return runnable, materialized


def materialize(relative):
    """A scratch copy of a fixture's directory with `.logos.txt` renamed.

    Multi-module fixtures import their siblings by name, so the whole directory
    has to travel with the root; only the suffix changes.
    """
    source = ROOT / relative
    stem = Path(str(source)[: -len(".logos")])
    real = Path(str(stem) + MATERIALIZED_SUFFIX)
    scratch = Path(tempfile.mkdtemp(prefix="qa-fixture-"))
    for entry in sorted(real.parent.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if name.endswith(".logos" + ".txt"):
            name = name[: -len(".txt")]
        shutil.copyfile(entry, scratch / name)
    return scratch / (stem.name + ".logos"), scratch


def judged(relative, materialized):
    """Build one fixture and return `(exit status, [diagnostics], [raw lines])`."""
    source = ROOT / relative
    scratch = None
    if materialized:
        source, scratch = materialize(relative)
    try:
        done = run(["build", source.name, "--json"], cwd=source.parent)
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
    documents = [line for line in done.stderr.splitlines() if line.strip()]
    diagnostics = []
    for line in documents:
        try:
            document = json.loads(line)
        except json.JSONDecodeError:
            continue
        diagnostics.extend(document["diagnostics"])
    return done.returncode, diagnostics, documents


def baseline_lines():
    return [line.rstrip("\n") for line in BASELINE.read_text(encoding="utf-8").splitlines()]


class NegativeFixtureSweep(unittest.TestCase):
    """A sidecar's code is a claim; this suite makes the compiler answer it."""

    @classmethod
    def setUpClass(cls):
        runnable, materialized = negative_fixtures()
        cls.materialized_names = {relative for relative, _ in materialized}
        cls.fixtures = runnable + materialized
        cls.exempt_codes, cls.exempt_fixtures = known_gaps()
        cls.results = {}

    def sweep(self):
        """Build every fixture once; `{relative: (expected, status, diagnostics)}`."""
        if self.results:
            return self.results
        for relative, expected in self.fixtures:
            status, diagnostics, _ = judged(relative,
                                            relative in self.materialized_names)
            self.results[relative] = (expected, status, diagnostics)
        return self.results

    def test_every_negative_fixture_is_judged_by_the_compiler(self):
        """The code in the sidecar is the code the compiler emits, exactly.

        A fixture is built with the same verb an agent would use — `build
        --json` — and must exit 2 with exactly one diagnostic: not zero
        diagnostics (accepted silently) and not a second one saying something
        else first.
        """
        failures = []
        for relative, (expected, status, diagnostics) in sorted(self.sweep().items()):
            if relative in self.exempt_fixtures:
                continue
            if status != 2:
                failures.append("%s: expected %s, build exited %d"
                                % (relative, expected, status))
                continue
            if len(diagnostics) != 1:
                failures.append("%s: expected one diagnostic, got %d"
                                % (relative, len(diagnostics)))
                continue
            if diagnostics[0]["code"] != expected:
                failures.append("%s: sidecar says %s, the compiler says %s"
                                % (relative, expected, diagnostics[0]["code"]))
        self.assertEqual([], failures, "\n".join(failures))

    def test_a_diagnostic_is_a_complete_and_locatable_document(self):
        """The seven published fields, and a place an agent can go back to.

        AGENTS.md's fourth invariant is that every diagnostic carries a code and
        a node path. A lexical or parse failure has no node path — its position
        is the locator — so the requirement is *one* of the two.
        """
        self.test_every_negative_fixture_is_judged_by_the_compiler()
        for relative, (expected, status, diagnostics) in sorted(self.sweep().items()):
            if relative in self.exempt_fixtures:
                continue
            if status != 2 or len(diagnostics) != 1:
                continue  # already reported by the sweep
            diagnostic = diagnostics[0]
            with self.subTest(fixture=relative):
                self.assertEqual(DIAGNOSTIC_FIELDS, set(diagnostic))
                self.assertEqual(diagnostic["code"], expected)
                self.assertEqual(diagnostic["severity"], "error")
                self.assertNotEqual(diagnostic["message"], "")
                self.assertTrue(diagnostic["file"].endswith(".logos")
                                or diagnostic["file"].endswith(MATERIALIZED_SUFFIX),
                                diagnostic["file"])
                self.assertGreaterEqual(diagnostic["line"], 0)
                self.assertGreaterEqual(diagnostic["col"], 0)
                self.assertTrue(diagnostic["node_path"] != "" or diagnostic["line"] > 0,
                                "neither a node path nor a source position")

    def test_the_sweep_covers_every_sidecar(self):
        """No sidecar may be decorative or skipped by a glob change."""
        runnable, materialized = negative_fixtures()
        self.assertEqual(len(self.sweep()), len(runnable) + len(materialized))
        self.assertGreaterEqual(len(self.sweep()), 140,
                                "the sidecar set was pruned")
        for relative, _ in materialized:
            stem = ROOT / relative[: -len(".logos")]
            self.assertTrue(Path(str(stem) + MATERIALIZED_SUFFIX).is_file(),
                            "%s: no materialized source" % relative)
        self.assertLessEqual(len(self.exempt_fixtures), MAX_KNOWN_GAPS)

    def test_the_known_gap_register_is_still_earned(self):
        """Every exemption must still be needed, or it is a stale hole."""
        self.sweep()
        _, exempt_fixtures = known_gaps()
        stale = []
        for relative in sorted(exempt_fixtures):
            if relative not in self.results:
                stale.append("%s: no such fixture" % relative)
                continue
            expected, status, diagnostics = self.results[relative]
            if status == 2 and [d["code"] for d in diagnostics] == [expected]:
                stale.append("%s: now emits %s; remove the exemption"
                             % (relative, expected))
        self.assertEqual([], stale, "\n".join(stale))


class DiagnosticCoverage(unittest.TestCase):
    """The published table is a contract; an unreachable code is a broken one."""

    def test_every_published_code_is_exercised(self):
        codes = guide_codes()
        self.assertGreaterEqual(len(codes), 30, "the diagnostic table shrank")
        exempt_codes, _ = known_gaps()
        exercised = set()
        for relative, expected in negative_fixtures()[0]:
            exercised.add(expected)
        for relative, expected in negative_fixtures()[1]:
            exercised.add(expected)
        # Runtime codes are panics, not compile diagnostics: they are named by
        # an `(err-contains "R0007: ...")` clause in a `tests/exec` case, which
        # the corpus runs, so the mention is the coverage.
        for path in glob.glob(str(ROOT / "tests" / "**" / "*.logos"), recursive=True):
            text = Path(path).read_text(encoding="utf-8")
            for code in codes:
                if code in text:
                    exercised.add(code)
        # A code whose only expressible failure is an installation one cannot be
        # reached from the corpus; its case lives in Python and has to name it.
        for code, path in PYTHON_COVERAGE.items():
            if code in (ROOT / path).read_text(encoding="utf-8"):
                exercised.add(code)
        missing = sorted(set(codes) - exercised - exempt_codes)
        self.assertEqual([], missing,
                         "published but never exercised: %s" % ", ".join(missing))
        unknown = sorted(exercised - set(codes))
        self.assertEqual([], unknown,
                         "exercised but not in the published table: %s" % ", ".join(unknown))

    def test_the_known_gap_register_does_not_grow(self):
        exempt_codes, exempt_fixtures = known_gaps()
        self.assertLessEqual(len(exempt_codes) + len(exempt_fixtures), MAX_KNOWN_GAPS)
        self.assertTrue(set(exempt_codes) <= set(guide_codes()),
                        "the register names a code the table does not publish")

    def test_a_code_exemption_is_still_uncovered(self):
        """A code exemption must disappear the moment a fixture covers it."""
        exempt_codes, _ = known_gaps()
        exercised = {want for _, want in negative_fixtures()[0]}
        exercised |= {want for _, want in negative_fixtures()[1]}
        for path in glob.glob(str(ROOT / "tests" / "**" / "*.logos"), recursive=True):
            text = Path(path).read_text(encoding="utf-8")
            for code in exempt_codes:
                if code in text:
                    exercised.add(code)
        self.assertEqual(sorted(exempt_codes & exercised), [],
                         "these codes are exercised now; remove the exemption")


class CorpusBaseline(unittest.TestCase):
    """`tests/summary.txt` is the floor that stops a case vanishing."""

    def test_the_baseline_pins_both_optimisation_levels(self):
        lines = baseline_lines()
        self.assertIn("LEAKS", " ".join(lines))
        options = [line for line in lines if line.startswith("OPTS")]
        self.assertEqual(len(options), 1, "the baseline needs exactly one OPTS line")
        for level in ("-O0", "-O2"):
            self.assertIn(level, options[0],
                          "the baseline does not pin %s" % level)

    def test_every_category_is_at_or_above_its_floor(self):
        counts, verdicts = {}, {}
        for line in baseline_lines():
            fields = line.split()
            if not fields or fields[0] not in ("PASS", "FAIL"):
                continue
            category = fields[1].split("/")[0]
            counts[category] = counts.get(category, 0) + 1
            verdicts[category] = verdicts.get(category, 0) + (fields[0] == "FAIL")
        for category, floor in sorted(CATEGORY_FLOORS.items()):
            with self.subTest(category=category):
                self.assertIn(category, counts, "the baseline has no %s case" % category)
                self.assertGreaterEqual(counts[category], floor,
                                        "%s lost cases: %d < %d"
                                        % (category, counts[category], floor))
        self.assertGreaterEqual(sum(counts.values()), TOTAL_FLOOR,
                                "the baseline is smaller than the corpus contract")
        self.assertEqual({}, {c: n for c, n in verdicts.items() if n},
                         "the committed baseline records a failing case")

    def test_the_baseline_has_a_verdict_for_every_case(self):
        """A fixture that is not in the baseline is a case nobody recorded."""
        recorded = set()
        for line in baseline_lines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] in ("PASS", "FAIL"):
                recorded.add(fields[1])
        runnable, _ = negative_fixtures()
        missing = []
        for relative, _ in runnable:
            identifier = relative[len("tests/"):-len(".logos")]
            if identifier not in recorded:
                missing.append(identifier)
        self.assertEqual([], missing,
                         "run `logosc test tests --opt -O0 --opt -O2 --update-baseline`")


class Flakiness(unittest.TestCase):
    """A test that fails nondeterministically teaches the team to ignore it."""

    #: The leak and panic category: every case allocates, panics or counts
    #: leaks, which is where nondeterminism shows up first. It is small on
    #: purpose — two runs cost a few seconds, so the gate can afford them.
    CATEGORY = "mem"
    REPEATS = 2

    def test_repeated_runs_agree_byte_for_byte(self):
        reports = []
        for _ in range(self.REPEATS):
            done = run(["test", "tests", "--only", self.CATEGORY])
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            reports.append((done.stdout, done.stderr))
        first_out, first_err = reports[0]
        for index, (out, err) in enumerate(reports[1:], 2):
            with self.subTest(run=index):
                self.assertEqual(out, first_out, "stdout differs between runs")
                self.assertEqual(err, first_err, "stderr differs between runs")
        self.assertNotEqual(first_out.strip(), "", "the category reported nothing")


class GateWiring(unittest.TestCase):
    """The gates above are only real if the gate list runs them."""

    #: Case floors per compiler suite file. A suite that is in the gate but
    #: loses half its cases still reports "0 failed", so the count is pinned
    #: here. Raise a floor when a case is added deliberately.
    SUITE_FLOORS = {
        "body_test": 361,
        "check_test": 81,
        "resolve_test": 38,
        "lex_test": 24,
        "tree_test": 14,
        "types_test": 112,
        "emit_test": 24,
        "fmt_test": 20,
        "harness_test": 12,
    }

    def test_make_test_runs_this_module(self):
        text = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("tests.test_qa", text,
                      "tests/test_qa.py is not in CONTRACT_TESTS")

    def test_every_compiler_suite_is_run_by_the_gate(self):
        """A suite in the repository that no target runs cannot fail.

        `git ls-files` is the source of truth, so a ninth suite added tomorrow
        fails here until it is listed in LOGOS_SUITES.
        """
        result = subprocess.run(["git", "ls-files", "src/logosc/*_test.logos"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        tracked = sorted(result.stdout.split())
        self.assertGreaterEqual(len(tracked), 9, "the suite set shrank")
        text = MAKEFILE.read_text(encoding="utf-8")
        missing = [path for path in tracked if path not in text]
        self.assertEqual([], missing,
                         "these suites are tracked but no target runs them: %s"
                         % ", ".join(missing))

    def test_a_suite_cannot_lose_its_cases(self):
        for name, floor in sorted(self.SUITE_FLOORS.items()):
            path = ROOT / "src" / "logosc" / (name + ".logos")
            with self.subTest(suite=name):
                self.assertTrue(path.is_file(), "%s is missing" % path.name)
                cases = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                            if line.startswith("(test "))
                self.assertGreaterEqual(cases, floor,
                                        "%s has %d cases, floor is %d"
                                        % (path.name, cases, floor))

    def test_ci_runs_the_target_that_holds_it(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("make test", text,
                      "CI no longer runs the target that holds the QA suite")

    def test_the_register_is_tracked(self):
        result = subprocess.run(["git", "ls-files", "--error-unmatch",
                                 str(GUIDE.relative_to(ROOT))],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         "tools/qa-known-gaps.txt is not committed")


class DifferentialOracle(unittest.TestCase):
    """The only codegen oracle that does not share clang's optimiser (issue #5).

    Its corpus size is a promise, not a preference, and three places encode it:
    `tests/diff/manifest.txt` names the cases, `tests/diff/run_diff.sh` floors
    them with `MIN_CASES`, and `tools/accept.sh` repeats that floor as
    `MIN_DIFF_CASES`. Tying both floors to the manifest is what stops the
    corpus shrinking and the two floors drifting apart; that is how issue #5
    asks for the twelve cases, nine of which PR #11 already carries.
    """

    FLOOR = 12

    def manifest(self):
        text = (ROOT / "tests" / "diff" / "manifest.txt").read_text(encoding="utf-8")
        names = [line.split("#")[0].strip() for line in text.splitlines()]
        return [name for name in names if name]

    def floor_of(self, name):
        sources = (ROOT / "tests" / "diff" / "run_diff.sh", ROOT / "tools" / "accept.sh")
        for source in sources:
            found = re.search(r"^%s=(\d+)$" % name,
                              source.read_text(encoding="utf-8"), re.MULTILINE)
            if found:
                return int(found.group(1))
        self.fail("%s is declared in neither run_diff.sh nor accept.sh" % name)

    def test_the_manifest_names_at_least_twelve_cases(self):
        self.assertGreaterEqual(len(self.manifest()), self.FLOOR,
                                "tests/diff/manifest.txt names %d case(s), the "
                                "issue asks for %d" % (len(self.manifest()), self.FLOOR))

    def test_both_floors_match_the_manifest(self):
        count = len(self.manifest())
        self.assertEqual(self.floor_of("MIN_CASES"), count,
                         "tests/diff/run_diff.sh: MIN_CASES is not the manifest length")
        self.assertEqual(self.floor_of("MIN_DIFF_CASES"), count,
                         "tools/accept.sh: MIN_DIFF_CASES is not the manifest length")


if __name__ == "__main__":
    unittest.main()
