"""The sixth gate runs, and the self-hosted front end reproduces canonical source.

`tools/selfhost.sh` builds `gen2` from `src/logosc/*.logos`, compares its `fmt`
output with every file `tools/selfhost-manifest.txt` lists, then runs
`gen2 resolve` on every resolver-owned negative fixture under `tests/parse`
and compares the code with its `.expect` sidecar, then runs `gen2 check` over
`tools/selfhost-check.txt` and compares the whole diagnostic line with the
generated `.check` sidecar beside each fixture. This test is the smallest one
that proves the wiring: it runs the gate and checks the three summary lines and
the exit status, so a script that silently skipped a loop, overran the manifest
or passed over zero files cannot look green.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "selfhost.sh"

#: `selfhost: N files, M differences`, with both numbers present and M zero.
SELFHOST_LINE = re.compile(r"^selfhost: (\d+) files, (\d+) differences$")
#: `resolve: N fixtures, M differences`, the second phase's summary.
RESOLVE_LINE = re.compile(r"^resolve: (\d+) fixtures, (\d+) differences$")
#: `check: N fixtures, M differences`, the third phase's summary.
CHECK_LINE = re.compile(r"^check: (\d+) fixtures, (\d+) differences$")


class SelfhostGateTest(unittest.TestCase):
    def test_gate_formats_the_manifest_resolver_and_checker_fixtures(self):
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertGreaterEqual(len(lines), 3, "tools/selfhost.sh printed no summaries")
        self.assertIsNotNone(
            SELFHOST_LINE.match(lines[-3]),
            f"third-to-last line is not the selfhost summary: {lines[-3]!r}",
        )
        self.assertIsNotNone(
            RESOLVE_LINE.match(lines[-2]),
            f"second-to-last line is not the resolve summary: {lines[-2]!r}",
        )
        self.assertIsNotNone(
            CHECK_LINE.match(lines[-1]),
            f"last line is not the check summary: {lines[-1]!r}",
        )
        selfhost_match = SELFHOST_LINE.match(lines[-3])
        resolve_match = RESOLVE_LINE.match(lines[-2])
        check_match = CHECK_LINE.match(lines[-1])
        assert selfhost_match is not None  # for the type checker, not the test
        assert resolve_match is not None
        assert check_match is not None

        files, differences = (int(group) for group in selfhost_match.groups())
        self.assertGreaterEqual(files, 100, "the manifest is smaller than the corpus")
        self.assertEqual(differences, 0)

        fixtures, resolve_differences = (
            int(group) for group in resolve_match.groups()
        )
        self.assertGreaterEqual(fixtures, 13, "the resolver fixture set was pruned")
        self.assertEqual(resolve_differences, 0)

        checked, check_differences = (int(group) for group in check_match.groups())
        self.assertGreaterEqual(checked, 6, "the checker fixture list was pruned")
        self.assertEqual(check_differences, 0)


if __name__ == "__main__":
    unittest.main()
