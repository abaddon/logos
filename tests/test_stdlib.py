"""The Logos standard library is part of the build, not a side project.

``src/std`` holds the compiler's own tables and tools, written in Logos and
tested in Logos. This module keeps them inside ``make test``: without it the
library's cases would only run when somebody remembered the path.
"""

import pathlib
import unittest

from logos import tester

STD = pathlib.Path(__file__).resolve().parent.parent / "src" / "std"
FLOOR = 25


class StdlibTest(unittest.TestCase):
    def test_every_library_case_passes_at_both_levels(self):
        summary = tester.run_suite(str(STD), opts=["-O0", "-O2"])
        failures = [
            f"{case.id} {case.detail}"
            for case in summary.cases
            if case.status != "PASS"
        ]
        self.assertEqual(failures, [])
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.leaks, 0)
        # The floor stops a pruned tree or a broken glob from reporting PASS
        # over no cases. New cases raise the count without editing this line.
        self.assertGreaterEqual(summary.total, FLOOR)
