"""Tests for tools/issue_intake.py — no network, no live GitHub calls, no board writes.

The selection rules are pinned by docs/pipelines/issue-intake/03-dossiers/
04-selection-fixtures.json, which is loaded verbatim: its 13 cases are the
acceptance data the spec was calibrated against, and a rule change that breaks
one of them fails here. The run-level tests swap ``fetch_issues`` for a canned
list and ``HERMES_BIN`` for a shim on disk, so the create-then-write ordering,
the failure table and the idempotency key are exercised without touching the
logos board.

The one live-repository trace (scenario 8: 22 ready, picks #10+#52) is not
asserted here on purpose — it needs HTTP. ``--once --dry-run`` against the live
repo is the manual check for it, and the numbers are recorded in the spec.
"""

import contextlib
import email.message
import io
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import issue_intake as intake  # noqa: E402

FIXTURES = os.path.join(ROOT, "docs", "pipelines", "issue-intake",
                        "03-dossiers", "04-selection-fixtures.json")
REAL_FETCH = intake.fetch_issues


def load_fixtures():
    with open(FIXTURES, "r", encoding="utf-8") as handle:
        return json.load(handle)


def issue(number, title, labels=(), body="**Done when:** it works.",
          created="2026-11-20T12:00:00Z", **extra):
    payload = {
        "number": number,
        "state": "open",
        "title": title,
        "labels": list(labels),
        "body": body,
        "created_at": created,
        "updated_at": created,
        "user": {"login": "stefano"},
    }
    payload.update(extra)
    return payload


# --- the selection contract ---------------------------------------------------

class SelectionFixtureTest(unittest.TestCase):
    def test_every_shipped_fixture_case_matches(self):
        fixtures = load_fixtures()
        for case in fixtures["cases"]:
            with self.subTest(case=case["name"]):
                result = intake.select(
                    case["issues"], case.get("state") or {},
                    case.get("backlog_cutoff"),
                    case.get("include_backlog", False),
                    case.get("max_picks", fixtures["config"]["max_picks"]))
                expect = case["expect"]
                self.assertEqual(expect["fetched"], result["fetched"])
                self.assertEqual(expect["prs_skipped"], result["prs_skipped"])
                self.assertEqual(expect["unseen"], result["unseen"])
                self.assertEqual(expect["ready"], result["ready"])
                self.assertEqual(expect["picked"], result["picked_numbers"])
                self.assertEqual(expect["skipped"], result["skipped"])
                for number, profile in (expect.get("assignee") or {}).items():
                    picked = next(i for i in case["issues"]
                                  if str(i["number"]) == number)
                    self.assertEqual(profile, intake.assignee_for(picked))

    def test_picks_stay_a_subset_of_candidates_in_created_order(self):
        cases = load_fixtures()["cases"]
        for case in cases:
            with self.subTest(case=case["name"]):
                result = intake.select(case["issues"], case.get("state") or {},
                                       case.get("backlog_cutoff"),
                                       case.get("include_backlog", False),
                                       case.get("max_picks", 2))
                stamps = [intake.parse_ts(i["created_at"]) for i in result["picked"]]
                self.assertEqual(stamps, sorted(stamps))
                self.assertLessEqual(len(result["picked"]), case.get("max_picks", 2))


class SelectionRuleTest(unittest.TestCase):
    def test_a_structural_phrase_without_an_issue_number_is_not_a_blocker(self):
        # The live issue #86 says "the contract that depends on passing a budget".
        body = ("**Impact.** A consumer that depends on passing a budget is stuck.\n\n"
                "**Done when:** both rows state what the compiler does.")
        subject = issue(86, "docs: a budget is a parameter", body=body)
        self.assertEqual(set(), intake.structural_refs(subject))
        self.assertFalse(intake.blocked(subject, {86, 52}))

    def test_a_closed_blocker_stops_blocking(self):
        subject = issue(111, "tooling: exit codes", body="**Blocked by:** #110 — one contract.")
        self.assertTrue(intake.blocked(subject, {110, 111}))
        self.assertFalse(intake.blocked(subject, {111}))

    def test_blocked_line_is_read_one_line_at_a_time(self):
        subject = issue(96, "docs: link limits.md",
                        body="A note on #52.\n\n- **Sequenced after:** #52, #78, #86\n")
        self.assertEqual({52, 78, 86}, intake.structural_refs(subject))

    def test_independence_is_symmetric_and_subsystem_aware(self):
        a = issue(1, "compiler: one")
        b = issue(2, "compiler: two")
        c = issue(3, "docs: three", body="")
        self.assertFalse(intake.independent(a, b))      # same area, no mutual ref
        self.assertEqual({"compiler"}, intake.subsystem(a) & intake.subsystem(b))
        self.assertTrue(intake.independent(a, c))
        citing = issue(4, "docs: four", body="See #1 for the scheme.")
        self.assertFalse(intake.independent(a, citing))
        self.assertFalse(intake.independent(citing, a))  # one-way citation is enough

    def test_unclassified_collides_with_unclassified(self):
        a = issue(1, "add a container image", labels=["enhancement"])
        b = issue(2, "changelog entries", labels=["enhancement"])
        self.assertEqual({"unclassified"}, intake.subsystem(a))
        self.assertFalse(intake.independent(a, b))

    def test_umbrella_threshold_is_eight_open_references(self):
        seven = issue(1, "compiler: work", body=" ".join(f"#{n}" for n in range(10, 17)))
        eight = issue(2, "compiler: index", body=" ".join(f"#{n}" for n in range(10, 18)))
        open_numbers = set(range(10, 18)) | {1, 2}
        self.assertFalse(intake.umbrella(seven, open_numbers))
        self.assertTrue(intake.umbrella(eight, open_numbers))

    def test_umbrella_by_first_body_line(self):
        subject = issue(41, "Compiler label sweep: end state",
                        body="Tracking issue for the `compiler` sweep.\n\nSee #10.")
        self.assertTrue(intake.umbrella(subject, {41, 10}))

    def test_never_relaxes_independence_to_reach_two_picks(self):
        issues = [issue(n, "docs: page %d" % n, labels=["docs"]) for n in (1, 2, 3)]
        result = intake.select(issues, {}, "2026-11-01T00:00:00Z")
        self.assertEqual([1], result["picked_numbers"])
        self.assertEqual({"subsystem-collision"}, set(result["skipped"].values()))

    def test_first_run_picks_nothing_without_a_cutoff_override(self):
        issues = [issue(1, "docs: one", created="2026-11-19T00:00:00Z")]
        result = intake.select(issues, {}, "2026-11-20T00:00:00Z")
        self.assertEqual(0, result["unseen"])
        self.assertEqual([], result["picked_numbers"])

    def test_max_picks_zero_is_honoured(self):
        issues = [issue(1, "docs: one"), issue(2, "compiler: two")]
        result = intake.select(issues, {}, "2026-11-01T00:00:00Z", max_picks_value=0)
        self.assertEqual([], result["picked_numbers"])
        self.assertEqual({"cap"}, set(result["skipped"].values()))


# --- the task card ------------------------------------------------------------

class TaskBodyTest(unittest.TestCase):
    def test_title_prefix_is_never_truncated(self):
        subject = issue(52, "docs: " + "very long " * 40)
        title = intake.task_title(subject)
        self.assertTrue(title.startswith("[logos#52] docs:"))
        self.assertLessEqual(len(title), intake.MAX_TITLE_CHARS)
        self.assertTrue(title.endswith("..."))

    def test_body_carries_the_url_labels_subsystem_and_done_when(self):
        subject = issue(52, "docs: limits.md says inf",
                        labels=["good first issue", "docs"],
                        body="Preamble.\n\n**Done when:** both rows state `E0106`.\n\n"
                             "**Impact.** none\n")
        body = intake.build_body(subject, intake.now())
        self.assertIn("https://github.com/abaddon/logos/issues/52", body)
        self.assertIn("- **Labels:** good first issue, docs", body)
        self.assertIn("- **Subsystem:** docs", body)
        self.assertIn("**Done when:** both rows state `E0106`.", body)
        self.assertNotIn("**Impact.**", body.split("## Acceptance")[1].split("## ")[0])
        self.assertIn("bash tools/pr_gate.sh", body)
        self.assertIn("- **Opened by:** stefano", body)

    def test_body_truncates_at_6000_characters_on_a_line_boundary(self):
        body = "\n".join("line %04d" % n for n in range(1200))
        cut = intake.truncate(body)
        self.assertLess(len(cut), len(body))
        self.assertIn("characters omitted; read the full issue at the URL above", cut)
        head = cut.split("\n\n…[truncated")[0]
        for line in head.splitlines():
            self.assertRegex(line, r"^line \d{4}$")

    def test_acceptance_falls_back_when_the_issue_has_none(self):
        self.assertEqual(intake.FALLBACK_DONE, intake.acceptance_criteria("Just prose."))

    def test_acceptance_takes_a_task_list(self):
        body = "Some context.\n\n- [ ] first\n- [x] second\n\nAfter."
        self.assertEqual("- [ ] first\n- [x] second", intake.acceptance_criteria(body))

    def test_acceptance_takes_a_heading_section(self):
        body = "## Acceptance criteria\n\nThe corpus case passes.\n\n## Next\n\nOther."
        self.assertEqual("## Acceptance criteria\n\nThe corpus case passes.",
                         intake.acceptance_criteria(body))


# --- run level: shim on PATH, canned fetch, temp state ------------------------

SHIM = '''#!{python}
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ["SHIM_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
counter = os.environ["SHIM_COUNT"]
seen = int(open(counter).read()) if os.path.exists(counter) else 0
seen += 1
with open(counter, "w", encoding="utf-8") as handle:
    handle.write(str(seen))
if seen == int(os.environ.get("SHIM_FAIL_AT", "0")):
    sys.exit(1)
created = int(os.environ.get("SHIM_CREATED_AT", time.time()))
print(json.dumps({{"id": "t_shim_" + str(created), "created_at": created}}))
'''


class RunTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="issue-intake-test-")
        self.state_path = os.path.join(self.dir, "state.json")
        self.shim = os.path.join(self.dir, "hermes-shim")
        with open(self.shim, "w", encoding="utf-8") as handle:
            handle.write(SHIM.format(python=sys.executable))
        os.chmod(self.shim, 0o755)
        self.log = os.path.join(self.dir, "argv.log")
        self.counter = os.path.join(self.dir, "shim-count")
        os.environ["SHIM_LOG"] = self.log
        os.environ["SHIM_COUNT"] = self.counter
        self.addCleanup(os.environ.pop, "SHIM_LOG", None)
        self.addCleanup(os.environ.pop, "SHIM_COUNT", None)
        self.addCleanup(os.environ.pop, "SHIM_FAIL_AT", None)
        self.addCleanup(os.environ.pop, "SHIM_CREATED_AT", None)

        self.saved = (intake.STATE_PATH, intake.HERMES_BIN)
        intake.STATE_PATH = self.state_path
        intake.HERMES_BIN = self.shim
        self.addCleanup(self.restore)

    def restore(self):
        intake.STATE_PATH, intake.HERMES_BIN = self.saved
        intake.fetch_issues = REAL_FETCH

    # helpers
    def canned(self, issues, etag='"etag-1"'):
        def fetch(state):
            return list(issues), sum(1 for i in issues if "pull_request" in i), etag, False
        intake.fetch_issues = fetch

    def run_main(self, *argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = intake.main(list(argv))
        return code, buffer.getvalue()

    def write_state(self, issues_map, cutoff="2026-11-20T00:00:00Z"):
        state = intake.new_state(intake.parse_ts(cutoff))
        state["issues"] = issues_map
        intake.atomic_write(self.state_path, state)
        return state

    def read_state(self):
        with open(self.state_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def sample(self):
        return [
            issue(102, "compiler: generic arity is not checked", labels=["compiler"],
                  created="2026-11-20T12:10:00Z"),
            issue(103, "runtime: vec-free on a zero-length buffer", labels=["bug", "runtime"],
                  created="2026-11-20T12:20:00Z"),
            issue(104, "docs: the stdlib page lists 21 functions", labels=["docs"],
                  created="2026-11-20T12:30:00Z"),
        ]

    # first run -------------------------------------------------------------
    def test_bootstrap_picks_nothing_and_records_the_cutoff(self):
        self.canned(self.sample())
        code, out = self.run_main("--once")
        state = self.read_state()
        self.assertEqual(0, code)
        self.assertEqual([], self.calls())
        self.assertIn("bootstrap seeded=3 picked=0", out)
        self.assertEqual({"seeded"}, {e["outcome"] for e in state["issues"].values()})
        self.assertEqual(state["backlog_cutoff"], state["last_run_at"])
        self.assertEqual(0o600, os.stat(self.state_path).st_mode & 0o777)

    # the happy path --------------------------------------------------------
    def test_creates_one_task_per_pick_with_the_specified_argv(self):
        self.write_state({})
        self.canned(self.sample())
        code, out = self.run_main("--once")
        calls = self.calls()
        self.assertEqual(0, code)
        self.assertEqual(2, len(calls))
        state = self.read_state()

        first = calls[0]
        self.assertIn("[logos#102] compiler: generic arity is not checked", first)
        self.assertIn("--assignee", first)
        self.assertEqual("backend-engineer", first[first.index("--assignee") + 1])
        self.assertEqual("logos", first[first.index("--board") + 1])
        self.assertEqual("logos-issue-102", first[first.index("--idempotency-key") + 1])
        self.assertEqual("wt/gh-102", first[first.index("--branch") + 1])
        self.assertIn("worktree:", first[first.index("--workspace") + 1])
        self.assertEqual("logos-issue-intake", first[first.index("--created-by") + 1])
        self.assertIn("--json", first)
        self.assertEqual(intake.REPO_ROOT + "/.worktrees/gh-102",
                         first[first.index("--workspace") + 1].split(":", 1)[1])

        self.assertEqual("picked", state["issues"]["102"]["outcome"])
        self.assertTrue(state["issues"]["102"]["task_id"].startswith("t_shim_"))
        self.assertEqual("skipped", state["issues"]["104"]["outcome"])
        self.assertEqual("cap", state["issues"]["104"]["skip_reason"])
        self.assertEqual({"created": 2, "picked": 2, "unseen": 3, "ready": 3},
                         {k: state["last_run"][k] for k in ("created", "picked", "unseen", "ready")})
        self.assertIn("picks=#102", out)
        self.assertIn("skipped=#104:cap", out)

    def test_a_same_subsystem_issue_never_gets_the_second_slot(self):
        self.write_state({})
        self.canned([self.sample()[0], issue(105, "compiler: another", labels=["compiler"],
                                             created="2026-11-20T12:40:00Z")])
        code, out = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertEqual(1, len(self.calls()))
        self.assertIn("skipped=#105:subsystem-collision", out)

    # idempotency -----------------------------------------------------------
    def test_second_run_is_silent_and_calls_no_create(self):
        self.write_state({})
        self.canned(self.sample()[:2])
        self.run_main("--once")
        first = len(self.calls())
        code, out = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertEqual(first, len(self.calls()))
        self.assertEqual("", out)
        state = self.read_state()
        self.assertEqual({"picked"}, {state["issues"][n]["outcome"] for n in ("102", "103")})

    def test_a_skipped_issue_is_reconsidered_the_next_hour(self):
        # Scenario 3: the third candidate was only excluded by the cap, so it is
        # picked alone on the next run — the cap costs latency, never an issue.
        self.write_state({})
        self.canned(self.sample())
        self.run_main("--once")
        code, out = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertIn("picks=#104", out)
        self.assertEqual(3, len(self.calls()))

    def test_an_existing_task_under_the_key_is_success_not_a_duplicate(self):
        self.write_state({})
        os.environ["SHIM_CREATED_AT"] = "1"          # task predates this run
        self.canned(self.sample()[:1])
        code, out = self.run_main("--once")
        state = self.read_state()
        self.assertEqual(0, code)
        self.assertEqual(0, state["last_run"]["created"])
        self.assertIn("existing=#102", out)
        self.assertEqual("picked", state["issues"]["102"]["outcome"])

    def test_a_retry_after_a_lost_state_write_reuses_the_same_key(self):
        self.write_state({})
        os.environ["SHIM_CREATED_AT"] = "1"
        self.canned(self.sample()[:1])
        self.run_main("--once")
        # Simulate the crash: the board has the task, the state file does not.
        self.write_state({})
        self.run_main("--once")
        keys = [c[c.index("--idempotency-key") + 1] for c in self.calls()]
        self.assertEqual(["logos-issue-102", "logos-issue-102"], keys)

    # partial run -----------------------------------------------------------
    def test_create_failure_stops_the_run_and_keeps_the_first_pick(self):
        self.write_state({})
        os.environ["SHIM_FAIL_AT"] = "2"          # #102 lands, #103 fails
        self.canned(self.sample())
        code, out = self.run_main("--once")
        state = self.read_state()
        self.assertEqual(75, code)
        self.assertIn("ERROR create failed issue=#103 rc=1", out)
        self.assertEqual("picked", state["issues"]["102"]["outcome"])
        self.assertNotEqual("picked", state["issues"].get("103", {}).get("outcome"))
        self.assertEqual(1, state["last_run"]["created"])
        self.assertEqual(1, state["last_run"]["failed"])
        self.assertIn("failed=1", out)
        self.assertEqual(2, len(self.calls()))     # the run stopped; #104 untouched

    def test_the_failed_pick_is_retried_the_next_hour(self):
        self.write_state({})
        os.environ["SHIM_FAIL_AT"] = "1"
        self.canned(self.sample()[:1])
        self.assertEqual(75, self.run_main("--once")[0])
        code, _ = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertEqual("picked", self.read_state()["issues"]["102"]["outcome"])

    # failure table ---------------------------------------------------------
    def http_error(self, code, headers=None):
        message = email.message.Message()
        for key, value in (headers or {}).items():
            message[key] = value
        return urllib.error.HTTPError("https://api.github.com/x", code, "err", message, None)

    def test_rate_limit_exits_75_and_leaves_state_byte_identical(self):
        self.write_state({"52": {"outcome": "seeded"}})
        with open(self.state_path, "rb") as handle:
            before = handle.read()
        error = self.http_error(403, {"x-ratelimit-remaining": "0",
                                      "x-ratelimit-reset": "1795178421"})
        with mock.patch("urllib.request.urlopen", side_effect=error):
            code, out = self.run_main("--once")
        with open(self.state_path, "rb") as handle:
            self.assertEqual(before, handle.read())
        self.assertEqual(75, code)
        self.assertIn("ERROR rate-limited remaining=0 reset=", out)
        self.assertEqual([], self.calls())

    def test_a_bad_token_exits_65(self):
        self.write_state({})
        with mock.patch("urllib.request.urlopen", side_effect=self.http_error(401)):
            code, out = self.run_main("--once")
        self.assertEqual(65, code)
        self.assertIn("ERROR auth/repo status=401", out)

    def test_not_modified_is_a_quiet_run(self):
        self.write_state({"52": {"outcome": "seeded"}})
        with mock.patch("urllib.request.urlopen", side_effect=self.http_error(304)):
            code, out = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertEqual("", out)

    def test_a_corrupt_state_file_is_quarantined_not_reseeded(self):
        with open(self.state_path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        code, out = self.run_main("--once")
        self.assertEqual(65, code)
        self.assertIn("ERROR state-corrupt path=", out)
        self.assertEqual([], [n for n in os.listdir(self.dir) if n == "state.json"])

    def test_a_fresh_lock_skips_without_fetching(self):
        self.write_state({})
        lock = self.state_path + ".lock"
        with open(lock, "w", encoding="utf-8") as handle:
            handle.write("pid=999 started=now\n")
        fetched = []
        intake.fetch_issues = lambda state: fetched.append(state) or ([], 0, None, False)
        code, out = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertIn("ERROR locked pid=999", out)
        self.assertEqual([], fetched)
        self.assertTrue(os.path.exists(lock))

    def test_a_stale_lock_is_reclaimed(self):
        self.write_state({})
        lock = self.state_path + ".lock"
        with open(lock, "w", encoding="utf-8") as handle:
            handle.write("pid=999 started=old\n")
        old = time.time() - intake.LOCK_STALE_S - 60
        os.utime(lock, (old, old))
        self.canned(self.sample())
        code, out = self.run_main("--once")
        self.assertEqual(0, code)
        self.assertIn("WARN stale-lock reclaimed", out)
        self.assertFalse(os.path.exists(lock))

    # polling ---------------------------------------------------------------
    def test_pagination_follows_the_link_header(self):
        page_one = json.dumps([issue(1, "docs: one")])
        page_two = json.dumps([issue(2, "compiler: two")])

        class Response:
            def __init__(self, status, body, headers):
                self.status, self.body, self.headers = status, body, headers

            def read(self):
                return self.body.encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        answers = [
            Response(200, page_one, {"Link": '<https://api.github.com/x?page=2>; rel="next"',
                                     "etag": '"one"'}),
            Response(200, page_two, {"etag": '"one"'}),
        ]
        with mock.patch("urllib.request.urlopen", side_effect=answers):
            issues, prs, etag, not_modified = intake.fetch_issues(None)
        self.assertEqual([1, 2], [i["number"] for i in issues])
        self.assertEqual('"one"', etag)
        self.assertFalse(not_modified)

    def test_pagination_cap_is_unrecoverable(self):
        links = {"Link": '<https://api.github.com/x?page=%d>; rel="next"'}
        body = json.dumps([issue(1, "docs: one")])

        class Response:
            def __init__(self):
                self.status, self.headers = 200, links

            def read(self):
                return body.encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with mock.patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(intake.Fatal) as raised:
                intake.fetch_issues(None)
        self.assertEqual(65, raised.exception.code)
        self.assertIn("pagination-cap", raised.exception.message)

    # dry run ---------------------------------------------------------------
    def test_dry_run_writes_nothing_and_creates_nothing(self):
        self.write_state({})
        with open(self.state_path, "rb") as handle:
            before = handle.read()
        self.canned(self.sample())
        code, out = self.run_main("--once", "--dry-run")
        with open(self.state_path, "rb") as handle:
            self.assertEqual(before, handle.read())
        self.assertEqual(0, code)
        self.assertEqual([], self.calls())
        self.assertIn("DRY RUN", out)
        self.assertIn("pick   #102", out)
        self.assertIn("create 0 (dry run, state untouched)", out)

    def test_dry_run_on_a_first_run_reports_a_bootstrap_and_stays_inert(self):
        self.canned(self.sample())
        code, out = self.run_main("--once", "--dry-run")
        self.assertEqual(0, code)
        self.assertFalse(os.path.exists(self.state_path))
        self.assertEqual([], self.calls())
        self.assertIn("would-bootstrap seeded=3 picked=0", out)

    # forget ----------------------------------------------------------------
    def test_forget_makes_an_issue_pickable_again(self):
        self.write_state({"102": {"outcome": "picked", "task_id": "t_x"}})
        code, out = self.run_main("--forget", "102")
        self.assertEqual(0, code)
        self.assertIn("forgot issue=#102", out)
        self.assertEqual({}, self.read_state()["issues"])


class EntrypointTest(unittest.TestCase):
    def test_once_is_required(self):
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stderr(io.StringIO()):
                intake.main([])
        self.assertEqual(2, raised.exception.code)

    def test_the_module_runs_as_a_command(self):
        proc = __import__("subprocess").run(
            [sys.executable, os.path.join(ROOT, "tools", "issue_intake.py"), "--help"],
            capture_output=True, text=True)
        self.assertEqual(0, proc.returncode)
        self.assertIn("--once", proc.stdout)


if __name__ == "__main__":
    unittest.main()
