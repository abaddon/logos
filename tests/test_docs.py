"""The shipped documentation must link only to pages the package contains.

`tools/check_doc_links.sh` is what `tools/dist.sh` and `tools/verify_install.sh`
run on the staged tree and on the unpacked artifact. Those two are a release and
a manual step, so a pull request can break a relative link and land it; this test
is the same check on the same script at the level every pull request runs. It
also pins the two extraction rules the script's readers depend on: a link title
is not part of the path, and a link to a page that is not there is reported.

The script is addressed through bash, like the other contract tests, so the
assertion is about the checker and not about a second implementation of it.
"""

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join(ROOT, "tools", "check_doc_links.sh")


def check(tree):
    return subprocess.run(["bash", CHECKER, tree], cwd=ROOT,
                          capture_output=True, text=True)


class DocLinksTest(unittest.TestCase):
    def test_the_repository_has_no_broken_relative_link(self):
        result = check(ROOT)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(" 0 broken", result.stdout)

    def test_a_link_to_a_missing_page_fails_and_names_it(self):
        with tempfile.TemporaryDirectory() as tree:
            with open(os.path.join(tree, "README.md"), "w") as page:
                page.write("[install](docs/install.md)\n")
            result = check(tree)
        self.assertEqual(1, result.returncode)
        self.assertIn("README.md -> docs/install.md", result.stdout)

    def test_a_link_title_is_not_part_of_the_path(self):
        with tempfile.TemporaryDirectory() as tree:
            with open(os.path.join(tree, "README.md"), "w") as page:
                page.write("[install](guide.md \"Install guide\")\n")
            with open(os.path.join(tree, "guide.md"), "w") as page:
                page.write("# Guide\n")
            result = check(tree)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
