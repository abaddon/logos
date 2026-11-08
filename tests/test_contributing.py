"""The contributor contract must be enforced, not merely described.

AGENTS.md tells an agent what done means, tools/pr_gate.sh runs it locally and
.github/workflows/gate.yml runs it on every pull request. If the three drift,
an agent can be told a change is finished while CI rejects it, or CI can stop
checking a gate the local script still claims to check. These tests keep the
three copies of the five-gate list in agreement, keep the DCO sign-off a
precondition that runs before the gates rather than a sixth gate, and keep
CODEOWNERS covering the paths whose owner must review a change.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GATES = [
    "make test",
    "python3 -m logos test",
    "bash tools/accept.sh",
    "python3 -m logos guide --check",
    "python3 -m logos fmt $(git diff --name-only main...HEAD -- '*.logos')",
]

# The sign-off is a precondition, not a gate: it runs before GATES and is not
# in the documented list in AGENTS.md.
SIGN_OFF_COMMAND = "bash tools/check_dco.sh"

HIGH_RISK_CODEOWNERS = [
    "/logos/check.py",
    "/logos/lower.py",
    "/logos/types.py",
    "/docs/LOGOS.md",
    "/docs/manual/",
    "/tests/regress/",
    "/logos/runtime/",
    "/.github/",
]

WORKFLOW = ROOT / ".github" / "workflows" / "gate.yml"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
ISSUE_TEMPLATE = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
PR_GATE = ROOT / "tools" / "pr_gate.sh"
DCO_SCRIPT = ROOT / "tools" / "check_dco.sh"
README = ROOT / "README.md"


def stripped_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]


def fenced_block(path: Path) -> list[str]:
    """The non-empty lines of the first ```sh block in a document."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("```sh")
    except ValueError:
        return []
    block = []
    for line in lines[start + 1 :]:
        if line.strip() == "```":
            break
        if line.strip():
            block.append(line.strip())
    return block


class ContributorFilesTest(unittest.TestCase):
    """Every document a contributor is told to read or fill in exists."""

    def test_required_files_exist(self):
        for path in (
            AGENTS,
            CONTRIBUTING,
            PR_TEMPLATE,
            ISSUE_TEMPLATE,
            WORKFLOW,
            CODEOWNERS,
            PR_GATE,
            DCO_SCRIPT,
        ):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file(), f"{path} is missing")

    def test_agents_points_at_the_manual_first(self):
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("docs/LOGOS.md", text)
        self.assertIn("Read `docs/LOGOS.md` first", text)

    def test_readme_has_a_contribute_section(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("## Contribute", text)
        for pointer in ("AGENTS.md", "CONTRIBUTING.md", "tools/pr_gate.sh"):
            with self.subTest(pointer=pointer):
                self.assertIn(pointer, text)
        self.assertIn("AI agents", text)

    def test_pr_gate_is_executable_and_parses(self):
        self.assertTrue(os.access(PR_GATE, os.X_OK), "tools/pr_gate.sh is not executable")
        first = PR_GATE.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "#!/usr/bin/env bash")
        result = subprocess.run(
            ["bash", "-n", str(PR_GATE)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class GateListAgreementTest(unittest.TestCase):
    """AGENTS.md, the local gate script and CI name the same five commands."""

    def test_agents_names_the_five_gates_in_order(self):
        lines = stripped_lines(AGENTS)
        positions = []
        for command in GATES:
            with self.subTest(command=command):
                self.assertIn(command, lines)
                positions.append(lines.index(command))
        self.assertEqual(positions, sorted(positions), "AGENTS.md gates are out of order")

    def test_agents_documents_five_gates_and_the_sign_off_precondition(self):
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("five commands", text)
        self.assertNotIn("six gates", text)
        self.assertNotIn("six commands", text)
        self.assertEqual(
            fenced_block(AGENTS),
            GATES,
            "the command block in AGENTS.md must hold exactly the five gates",
        )
        self.assertIn("Signed-off-by", text, "AGENTS.md must state the sign-off precondition")
        self.assertIn(SIGN_OFF_COMMAND, text, "AGENTS.md must name the sign-off check")
        self.assertNotIn(
            SIGN_OFF_COMMAND,
            fenced_block(AGENTS),
            "sign-off is a precondition, not a gate",
        )

    def test_pr_gate_runs_the_five_gates(self):
        lines = stripped_lines(PR_GATE)
        for command in GATES:
            with self.subTest(command=command):
                self.assertIn(command, lines)
        self.assertNotIn('run_gate "sign-off"', lines, "sign-off is not a gate")

    def test_pr_gate_checks_sign_off_before_the_first_gate(self):
        lines = stripped_lines(PR_GATE)
        dco = [index for index, line in enumerate(lines) if SIGN_OFF_COMMAND in line]
        self.assertTrue(dco, "tools/pr_gate.sh never runs tools/check_dco.sh")
        calls = [index for index, line in enumerate(lines) if line.startswith("run_gate ")]
        self.assertEqual(len(calls), len(GATES), "pr_gate.sh must invoke exactly five gates")
        first_gate = calls[0]
        self.assertLess(dco[0], first_gate, "sign-off must run before the first gate")
        text = PR_GATE.read_text(encoding="utf-8")
        self.assertIn("FAIL sign-off", text)
        self.assertIn("The five gates were not run", text)

    def test_workflow_runs_the_five_gates(self):
        lines = stripped_lines(WORKFLOW)
        for command in GATES:
            with self.subTest(command=command):
                self.assertIn(command, lines)

    def test_workflow_is_the_required_job(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("name: gate", text)
        self.assertIn("runs-on: ubuntu-22.04", text)
        self.assertIn("pull_request", text)
        self.assertIn("branches: [main]", text)
        for package in ("clang", "lld", "gcc", "jq", "python3"):
            with self.subTest(package=package):
                self.assertIn(package, text)
        self.assertNotIn("continue-on-error", text, "a failing gate must stop the job")

    def test_workflow_sign_off_step_precedes_the_gates_and_is_pr_only(self):
        lines = stripped_lines(WORKFLOW)
        self.assertIn("- name: sign-off", lines)
        sign_off = lines.index("- name: sign-off")
        first_gate = lines.index("- name: unit tests")
        self.assertLess(sign_off, first_gate, "sign-off must run before the first gate")
        # The step ends at the next "- name:" line; its condition and event
        # SHAs must live inside it, not on some later step.
        end = next(
            (index for index in range(sign_off + 1, len(lines))
             if lines[index].startswith("- name:")),
            len(lines),
        )
        step = "\n".join(lines[sign_off:end])
        self.assertIn("if: github.event_name == 'pull_request'", step)
        self.assertIn("github.event.pull_request.base.sha", step)
        self.assertIn("github.event.pull_request.head.sha", step)
        self.assertNotIn(
            "if: github.event_name == 'push'",
            step,
            "sign-off must not run for a push to main",
        )

    def test_dco_script_can_check_and_skip(self):
        self.assertTrue(os.access(DCO_SCRIPT, os.X_OK), "tools/check_dco.sh is not executable")
        text = DCO_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Signed-off-by:", text)
        self.assertIn("nothing to compare", text)
        result = subprocess.run(["bash", "-n", str(DCO_SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class CodeownersTest(unittest.TestCase):
    """The high-risk paths have a named owner, not only a default."""

    def test_codeowners_names_abaddon(self):
        lines = stripped_lines(CODEOWNERS)
        self.assertIn("* @abaddon", lines, "CODEOWNERS needs a default owner")

    def test_codeowners_covers_every_high_risk_path(self):
        lines = stripped_lines(CODEOWNERS)
        for path in HIGH_RISK_CODEOWNERS:
            with self.subTest(path=path):
                matches = [line for line in lines if line.split()[:1] == [path]]
                self.assertTrue(matches, f"{path} is not in CODEOWNERS")
                for line in matches:
                    self.assertTrue(
                        re.search(r"@abaddon\b", line),
                        f"{path} must be owned by @abaddon",
                    )


class TemplatesTest(unittest.TestCase):
    """The templates ask for the evidence the gates require."""

    def test_pull_request_template_mirrors_the_gates(self):
        text = PR_TEMPLATE.read_text(encoding="utf-8")
        for command in GATES:
            with self.subTest(command=command):
                self.assertIn(command, text)
        for required in (
            "regress",
            "failed before the fix",
            "summary.txt",
            "never",
            "invariants",
            "unrelated reformatting",
            "feat/",
            "fix/",
            "docs/",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_pull_request_template_treats_sign_off_as_a_precondition(self):
        text = PR_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Signed-off-by:", text)
        self.assertIn("git commit --signoff", text)
        self.assertIn("precondition", text)
        self.assertNotIn(f"| sign-off | `{SIGN_OFF_COMMAND}` |", text)

    def test_contributing_treats_sign_off_as_a_precondition(self):
        text = CONTRIBUTING.read_text(encoding="utf-8")
        self.assertIn("## The five gates", text)
        self.assertNotIn("## The six gates", text)
        self.assertIn("precondition", text)
        self.assertIn(SIGN_OFF_COMMAND, text)

    def test_bug_form_asks_for_a_reproduction(self):
        text = ISSUE_TEMPLATE.read_text(encoding="utf-8")
        for required in (
            "Minimal Logos program",
            "Command",
            "Expected output",
            "Actual output or diagnostic code",
            '\"-O0\"',
            '\"-O2\"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
