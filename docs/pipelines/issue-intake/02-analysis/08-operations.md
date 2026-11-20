# 8 — Operations: the installed hourly schedule

`02-analysis/06-config.md` §6.3-6.5 specifies the entrypoint and says the hourly
schedule belongs to cron. This chapter is what was actually installed on this
host on 2026-11-20, how to read it when it misbehaves, and how to remove it.

Everything below is as it exists on the host right now, not as designed:
`03-dossiers/05-installed-schedule.md` carries the commands and their real
output.

## 8.1 Why Hermes cron, not systemd or `/etc/cron.d`

This host runs recurring jobs three ways, so the choice was made against real
precedent rather than taste:

| Mechanism | On this host | Fits here? |
|---|---|---|
| Hermes cron (`hermes cron`, `$HERMES_HOME/cron/jobs.json`) | `companion-report.py` daily, `email-to-companion.py` every 15 min, both `--no-agent` script jobs | **chosen** |
| systemd timer | `hermes-backup.timer` (`OnCalendar=*-*-* 00/6:17:00`) | no |
| root crontab / `/etc/cron.d` | empty (`crontab -l`: no crontab for root) | no |

Hermes cron wins on three counts a shell cron entry cannot match:

1. **`--no-agent` is exactly this job's shape.** The script *is* the job; its
   stdout is the deliverable verbatim, and empty stdout is a silent run. That is
   the "nothing new this hour" case producing no notification at all.
2. **A non-zero exit already means something.** The scheduler records a failed
   run, delivers a `⚠ cron watchdog ... script failed` notice carrying the
   script's stderr/stdout, and files it in `hermes cron incidents`. Failure
   visibility is a property of the scheduler, not something the poller has to
   invent.
3. **The scheduler is already running** — the host gateway (one process) ticks
   the cron of every profile it serves, this one included, every 60 seconds.

A systemd timer would work and is the right answer for a job that must fire
even with Hermes down. This one must not: its only side effect is
`hermes kanban create`, so a fire with the gateway down could only fail.

## 8.2 What is installed

| Piece | Path | Mode | Owns |
|---|---|---|---|
| env file | `/etc/logos-issue-intake/env` | `0600 root:root` (dir `0750`) | `GITHUB_TOKEN`, repo, board, Kanban DB, code roots, `PATH` |
| runner | `$HERMES_HOME/scripts/logos-issue-intake.sh` | `0755` | one run: log line, failure counter, alert marker |
| runner source | `tools/issue_intake_schedule.sh` (this repo) | `0755` | the version-controlled copy the installer deploys |
| log | `/var/log/logos-issue-intake.log` | `0640 root:adm` | one `RUN` line per run plus the pipeline's output |
| rotation | `/etc/logrotate.d/logos-issue-intake` | `0644` | daily, 14 kept, compressed |
| failure state | `/var/lib/logos-issue-intake/` | `0700` | `consecutive_failures`, `ALERT` |
| cron job | `hermes cron`, name `logos-issue-intake` | — | `0 * * * *`, `--no-agent`, `--deliver local` |

`$HERMES_HOME` is the Hermes home that owns the job: on this host
`/root/.hermes/profiles/platform-engineer`, whose scheduler the host gateway
ticks. The scheduler only loads scripts from inside `<home>/scripts/`, which is
why the runner is deployed there instead of being invoked from the checkout.

The cron job runs with `--workdir /root/ai-language-program`, so the process
starts in the merged checkout even when the code being executed is resolved
elsewhere (see §8.5).

## 8.3 The run, line by line

```sh
# what the schedule does every hour, and the manual trigger for one run
/root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh

# the same thing on demand
# (runs immediately, in this shell's environment; the schedule is unaffected)
hermes cron run 33a81bc1bb13

# what happened, newest first
hermes cron runs 33a81bc1bb13 --limit 10
tail -n 20 /var/log/logos-issue-intake.log
```

The runner does five things, in this order:

1. reads `/etc/logos-issue-intake/env` with `set -a` so the pipeline process
   actually inherits the token (a sourced file without `set -a` sets shell
   variables only — the poller then runs unauthenticated and looks healthy);
2. picks a code root that contains `tools/issue_intake.py` (§8.5);
3. runs `python3 tools/issue_intake.py --once` from it, capturing stdout/stderr
   and the exit code;
4. appends one line — `RUN code=… repo=… board=… rc=… dur=…s` — plus the
   pipeline's output when it printed any, to the log;
5. on success clears `consecutive_failures` and `ALERT`; on failure increments
   the counter, writes syslog, and at 3 consecutive failures writes `ALERT`.

stdout of the runner is the cron deliverable: empty for a clean no-op or a
lock-skip, the pipeline's own `ERROR ...` lines for a failure.

`hermes cron run <id>` is **not** a scheduler tick — it runs the job right there,
in the process that asks and with that process's environment. From a plain root
shell that is indistinguishable from the hourly fire. From inside a dispatched
Kanban worker it inherits `HERMES_DELEGATED_CHILD_CONTEXT`, and the create step
comes back `ERROR create failed issue=#n rc=1` / exit 75 — a harness artifact, not
a pipeline bug (`04-task-creation.md` §4.1). The hourly fire itself runs from the
gateway, whose script environment is clean: no delegate marker, no session or
task pins. Both environments are dumped side by side in
`03-dossiers/05-installed-schedule.md` §12.

## 8.4 The failure ladder

| Run outcome | Log | stdout (cron) | Marker |
|---|---|---|---|
| `rc=0`, nothing new | one `RUN ... rc=0` line | empty → silent run | cleared |
| `rc=0`, lock held by a live run | `RUN ... rc=0` + `ERROR locked <pid>` | the `ERROR locked` line | not touched |
| `rc=65` auth/repo/corrupt state | `RUN ... rc=65` + `ERROR auth/repo` | `ERROR ...` → run recorded failed | counter `1` |
| `rc=75` rate limit, 5xx, timeout, create failure | `RUN ... rc=75` + `ERROR ...` | `ERROR ...` → run recorded failed | counter `n+1` |
| 3rd consecutive failure | `ALERT consecutive_failures=3 last_rc=… see=…` | the `ERROR` line | `ALERT` (0600) holds the last rc, the last output, the log path |

Three surfaces, so no single one has to be watched: the log file (`tail -f`),
syslog (`journalctl -t logos-issue-intake`), and the scheduler
(`hermes cron runs`, `hermes cron incidents`). The marker file is the one a
monitor can poll without parsing text: its existence means "three failed runs in
a row, nobody has looked yet". A successful run removes it.

`--deliver local` keeps the hourly no-op silent: nothing is pushed to a chat.
To have failures pushed instead, without touching the job's success path:

```sh
hermes cron edit 33a81bc1bb13 --failure-deliver <chat-target>
```

## 8.5 Two checks that are not secrets, but are load-bearing

**Which checkout ran.** `LOGOS_INTAKE_CODE_ROOT` (the merged checkout,
`/root/ai-language-program`) is tried first; if it has no
`tools/issue_intake.py`, `LOGOS_INTAKE_CODE_FALLBACK` is used. The fallback
exists because the branch carrying the pipeline had not merged when the schedule
was installed, and it is what makes the schedule work *today* without pointing at
a path that will be deleted. Once the merge lands the first path wins, the log's
`code=` field shows it, and the fallback line can be deleted from the env file.
If neither checkout has the tool the run exits 65 and says so — it does not
silently succeed.

**Which token was sent.** An expired token is *not* caught while the repo is
quiet: GitHub answers a conditional request (`If-None-Match` from the state's
`last_etag`) with `304` before it objects to the credential, and a 304 writes no
state and exits 0. The bad token is caught on the first run whose repo content
changed — `401` → `ERROR auth/repo` → `rc=65` → counter → alert. Recorded, not
defended: the pipeline's own `05-failure-and-idempotency.md` §5.4 keeps the
failure lines free of the token, which is why the log shows a status code and a
URL, nothing else.

## 8.6 Overlap

The pipeline already holds a lock: `os.open(state.json.lock, O_EXCL)` before any
fetch, released in a `finally` (`02-state.md`). The runner adds **no** second
lock — two owners of one invariant is how you get a lock that is held forever.

A run that starts while another is live prints

```
ERROR locked pid=<pid> age=<seconds>
```

and exits 0 without fetching, creating, or writing state. A lock older than
`LOCK_STALE_S = 600` is reclaimed with `WARN stale-lock reclaimed`, so a killed
run cannot wedge the schedule for more than ten minutes.

Consequence for the schedule: overlapping fires are safe and boring. Even if the
scheduler fired twice in the same minute (it does not — one tick per minute,
`--repeat ∞`, one run per due occurrence), the second fire would log one line and
do nothing.

## 8.7 Install, verify, remove

```sh
# install or re-install (idempotent: keeps the existing token, edits the same job)
bash tools/install_issue_intake_schedule.sh
bash tools/install_issue_intake_schedule.sh --repo-root /root/ai-language-program

# verify
hermes cron list                 # schedule, next run on the hour, last run
stat -c '%a %U:%G' /etc/logos-issue-intake/env     # 600 root:root
ls -l /var/lib/logos-issue-intake/                 # no ALERT = no open failure streak
hermes cron run 33a81bc1bb13 && sleep 70 && hermes cron runs 33a81bc1bb13 --limit 3

# remove
hermes cron remove 33a81bc1bb13
```

The installer rewrites `/etc/logos-issue-intake/env`, the log's rotation, the
runner copy and the job definition; it never prints the token and never creates a
second job with the same name (it looks the job up by name and edits it, so run
history survives a reinstall).

**Do not trigger it by hand from inside a dispatched Kanban worker.** The CLI
refuses board mutations from a delegate child (`04-task-creation.md` §4.1), and
`hermes cron run` inherits the caller's environment, so a run started there fails
at the create step with `rc=75` — a failure that looks like a pipeline bug and is
really a test harness. Trigger it from a plain root shell; the hourly fire is
unaffected either way.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/06-config.md
 -> the entrypoint and exit codes this chapter schedules
docs/pipelines/issue-intake/02-analysis/02-state.md
 -> the lock the schedule relies on for overlap safety
docs/pipelines/issue-intake/02-analysis/05-failure-and-idempotency.md
 -> the failure table a failed run lands in
docs/pipelines/issue-intake/03-dossiers/05-installed-schedule.md
 -> the install as run, with its real output
