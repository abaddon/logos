"""Tests for tools/issue_intake_schedule.sh — the hourly cron wrapper.

The wrapper is run against a fake checkout whose ``tools/issue_intake.py`` prints
a line and exits with a code the test chooses, so the run log, the
consecutive-failure counter, the ALERT marker and the stdout contract are all
exercised without network, without the real tool, and without a card.
"""

import os
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "tools", "issue_intake_schedule.sh")


class ScheduleRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.code = os.path.join(self.dir, "checkout")
        os.makedirs(os.path.join(self.code, "tools"))
        self.log = os.path.join(self.dir, "intake.log")
        self.markers = os.path.join(self.dir, "markers")
        self.env_file = os.path.join(self.dir, "env")

    def fake_tool(self, rc, output=""):
        path = os.path.join(self.code, "tools", "issue_intake.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("import sys\n")
            if output:
                handle.write(f"print({output!r})\n")
            handle.write(f"sys.exit({rc})\n")
        return path

    def write_env(self, **values):
        lines = ["LOGOS_INTAKE_REPO=abaddon/logos", "LOGOS_INTAKE_BOARD=logos",
                 f"LOGOS_INTAKE_CODE_ROOT={self.code}",
                 f"LOGOS_INTAKE_CODE_FALLBACK={self.code}"]
        lines += [f"{key}={value}" for key, value in values.items()]
        with open(self.env_file, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def run_runner(self, alert_after=None, env_file=None):
        env = dict(os.environ)
        env.pop("LOGOS_INTAKE_CODE_ROOT", None)
        env.pop("LOGOS_INTAKE_CODE_FALLBACK", None)
        env.update({
            "LOGOS_INTAKE_ENV_FILE": env_file or self.env_file,
            "LOGOS_INTAKE_LOG": self.log,
            "LOGOS_INTAKE_FAIL_DIR": self.markers,
            "PATH": "/usr/local/bin:/usr/bin:/bin",
        })
        if alert_after is not None:
            env["LOGOS_INTAKE_ALERT_AFTER"] = str(alert_after)
        return subprocess.run(["sh", RUNNER], capture_output=True, text=True,
                              env=env, timeout=60)

    def log_text(self):
        with open(self.log, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_missing_env_file_is_a_loud_65(self):
        proc = self.run_runner(env_file=os.path.join(self.dir, "nope"))
        self.assertEqual(proc.returncode, 65)
        self.assertIn("env file", proc.stdout)
        self.assertFalse(os.path.exists(self.log))

    def test_missing_tool_in_every_checkout_is_a_loud_65(self):
        self.write_env()
        proc = self.run_runner()
        self.assertEqual(proc.returncode, 65)
        self.assertIn("issue_intake.py not found", proc.stdout)

    def test_a_clean_run_logs_one_line_and_stays_silent_on_stdout(self):
        self.fake_tool(0, "")
        self.write_env()
        proc = self.run_runner()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        log = self.log_text()
        self.assertEqual(len(log.splitlines()), 1, log)
        self.assertIn("RUN ", log)
        self.assertIn("rc=0", log)
        self.assertFalse(os.path.exists(os.path.join(self.markers, "consecutive_failures")))

    def test_pipeline_output_reaches_the_log_and_stdout(self):
        self.fake_tool(0, "fetched=3 ready=1 picked=1 created=1")
        self.write_env()
        proc = self.run_runner()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("created=1", proc.stdout)
        self.assertIn("created=1", self.log_text())

    def test_failures_count_up_and_the_marker_lands_on_the_threshold(self):
        self.fake_tool(75, "ERROR http=503")
        self.write_env()
        first = self.run_runner(alert_after=2)
        second = self.run_runner(alert_after=2)
        self.assertEqual((first.returncode, second.returncode), (75, 75))
        self.assertIn("ERROR http=503", second.stdout)
        counter = os.path.join(self.markers, "consecutive_failures")
        with open(counter, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read().strip(), "2")
        alert = os.path.join(self.markers, "ALERT")
        self.assertTrue(os.path.exists(alert))
        with open(alert, "r", encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("2 consecutive failed runs", body)
        self.assertIn("ERROR http=503", body)
        self.assertIn("ALERT consecutive_failures=2", self.log_text())
        self.assertEqual(stat.S_IMODE(os.stat(alert).st_mode), 0o600)

    def test_one_failure_is_recorded_without_raising_an_alert(self):
        self.fake_tool(65, "ERROR auth/repo")
        self.write_env()
        proc = self.run_runner(alert_after=3)
        self.assertEqual(proc.returncode, 65)
        self.assertFalse(os.path.exists(os.path.join(self.markers, "ALERT")))

    def test_success_clears_the_counter_and_the_alert(self):
        self.fake_tool(75, "ERROR timeout")
        self.write_env()
        self.run_runner(alert_after=1)
        self.assertTrue(os.path.exists(os.path.join(self.markers, "ALERT")))
        self.fake_tool(0, "")
        proc = self.run_runner(alert_after=1)
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.markers, "ALERT")))
        self.assertFalse(os.path.exists(os.path.join(self.markers, "consecutive_failures")))

    def test_the_fallback_checkout_is_used_when_the_primary_lacks_the_tool(self):
        self.fake_tool(0, "bootstrapped")
        empty = os.path.join(self.dir, "empty")
        os.makedirs(empty)
        with open(self.env_file, "w", encoding="utf-8") as handle:
            handle.write(f"LOGOS_INTAKE_CODE_ROOT={empty}\n"
                         f"LOGOS_INTAKE_CODE_FALLBACK={self.code}\n")
        proc = self.run_runner()
        self.assertEqual(proc.returncode, 0)
        self.assertIn(f"code={self.code}", self.log_text())

    def test_env_file_values_reach_the_pipeline_process(self):
        # Sourcing an env file only sets shell variables; without `set -a` the
        # pipeline would run on defaults and the token would never be sent.
        path = os.path.join(self.code, "tools", "issue_intake.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("import os\n"
                         "print('api=' + os.environ.get('LOGOS_INTAKE_API', 'missing'))\n")
        self.write_env(LOGOS_INTAKE_API="http://127.0.0.1:9")
        proc = self.run_runner()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("api=http://127.0.0.1:9", proc.stdout)
        self.assertIn("api=http://127.0.0.1:9", self.log_text())


if __name__ == "__main__":
    unittest.main()
