"""The sixth gate runs, and the self-hosted formatter reproduces the corpus.

`tools/selfhost.sh` builds `gen2` from `src/logosc/*.logos` and compares its
`fmt` output with every file `tools/selfhost-manifest.txt` lists. This test is
the smallest one that proves the wiring: it runs the gate and checks its final
line and exit status, so a script that silently skipped the loop, overran the
manifest or passed over zero files cannot look green.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "selfhost.sh"

#: `selfhost: N files, M differences`, with both numbers present and M zero.
FINAL_LINE = re.compile(r"^selfhost: (\d+) files, (\d+) differences$")


class SelfhostGateTest(unittest.TestCase):
    def test_gate_formats_every_manifest_file_byte_for_byte(self):
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertTrue(lines, "tools/selfhost.sh printed no summary line")
        match = FINAL_LINE.match(lines[-1])
        self.assertIsNotNone(
            match,
            f"last line is not the selfhost summary: {lines[-1]!r}",
        )
        assert match is not None  # for the type checker, not the test
        files, differences = (int(group) for group in match.groups())
        self.assertGreaterEqual(files, 100, "the manifest is smaller than the corpus")
        self.assertEqual(differences, 0)


if __name__ == "__main__":
    unittest.main()
