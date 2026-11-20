# Dossier — the schedule, as installed

Everything below was run on this host on 2026-11-20 (Europe/London) and is
quoted from the command output. This is the evidence for
`02-analysis/08-operations.md`; where the two disagree, the host is right.

## 1. What is on disk, and with which mode

```
750 root:root /etc/logos-issue-intake
600 root:root /etc/logos-issue-intake/env
640 root:adm  /var/log/logos-issue-intake.log
700 root:root /var/lib/logos-issue-intake
755 root:root /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
644 root:root /etc/logrotate.d/logos-issue-intake
700 root:root /root/.local/state/logos-issue-intake
600 root:root /root/.local/state/logos-issue-intake/state.json
```

The env file's keys, values hidden — the token is the only secret, and it is one
line:

```
GITHUB_TOKEN=…
# board the intake creates tasks on; it must already exist
LOGOS_INTAKE_REPO=abaddon/logos
LOGOS_INTAKE_BOARD=logos
HERMES_KANBAN_DB=/root/.hermes/kanban/boards/logos/kanban.db
# REPO_ROOT is the workspace parent for the created tasks (merged checkout)
LOGOS_INTAKE_REPO_ROOT=/root/ai-language-program
# the code may live in the merged checkout or, before the merge, in a worktree
LOGOS_INTAKE_CODE_ROOT=/root/ai-language-program
LOGOS_INTAKE_CODE_FALLBACK=/root/ai-language-program/.worktrees/t_759f141f
LOGOS_INTAKE_HERMES=/root/.hermes/hermes-agent/.hermes/bin/hermes
PATH=/root/.hermes/hermes-agent/.hermes/bin:/usr/local/bin:/usr/bin:/bin
```

`HERMES_KANBAN_DB` is pinned deliberately. The cron script runs with the
scheduler's sanitized environment, not a worker's, and `kanban create` would
otherwise resolve the board database from whatever `HERMES_HOME` the gateway
happens to hand it. The pinned path is the one every other worker on this host
writes to.

## 2. The install, as run

```
$ bash tools/install_issue_intake_schedule.sh
Created job: 33a81bc1bb13
  Name: logos-issue-intake
  Schedule: 0 * * * *
  Script: logos-issue-intake.sh
  Mode: no-agent (script stdout delivered directly)
  Workdir: /root/ai-language-program
  Next run: 2026-11-20T13:00:00+00:00
env      /etc/logos-issue-intake/env (600)
log      /var/log/logos-issue-intake.log
runner   /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
markers  /var/lib/logos-issue-intake
```

Running it a second time edits the same job (same id, run history kept) instead
of creating a second one:

```
  33a81bc1bb13 [active]
    Name:      logos-issue-intake
    Schedule:  0 * * * *
    Next run:  2026-11-20T13:00:00+00:00
    Deliver:   local
    Last run:  2026-11-20T12:37:21.341151+00:00  ok
    Dispatch:  on time (scheduled 2026-11-20T12:37:11.669648+00:00)
    Execution: completed  4b9b03391f4e4e5aa31664e982e8d664
```

## 3. The first real run bootstraps and creates nothing

```
$ /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
logos-issue-intake 2026-11-20T12:32:38Z bootstrap seeded=38 picked=0 backlog_cutoff=2026-11-20T12:32:38Z
$ echo $?
0
```

and the log file, which is the audit trail of the same event:

```
2026-11-20T12:32:39Z RUN code=/root/ai-language-program/.worktrees/t_759f141f repo=abaddon/logos board=logos rc=0 dur=1s
logos-issue-intake 2026-11-20T12:32:38Z bootstrap seeded=38 picked=0 backlog_cutoff=2026-11-20T12:32:38Z
```

The next run has nothing to say, so it says nothing on stdout and writes one
line to the log:

```
$ /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
$                     # empty stdout: the scheduler treats this as a silent run
2026-11-20T12:32:55Z RUN code=/root/ai-language-program/.worktrees/t_759f141f repo=abaddon/logos board=logos rc=0 dur=0s
```

## 4. The manual trigger

```
$ hermes cron run 33a81bc1bb13
Triggered job: logos-issue-intake (33a81bc1bb13)
  Next run: 2026-11-20T13:00:00+00:00
  Ran now: succeeded.

$ hermes cron runs 33a81bc1bb13 --limit 3
d3fcb470aafc473aaa9729e74e58dfba  completed  job=33a81bc1bb13  source=direct  2026-11-20T12:32:54.574673+00:00
```

`source=direct` is the manual trigger; the log line at `12:32:55` is its run. The
trigger is immediate and in-process: `hermes cron run` executed the script inside
the CLI that asked for it, with that shell's environment, and left the hourly
schedule alone (`Next run: 13:00:00` before and after). It is *not* a scheduler
tick — a ticked run is `source=builtin`, which is §11.

## 5. The scheduler fires it on its own

Proving the schedule is not just a stored string: the job was temporarily set to
`1m`, left alone, and fired by the gateway's own tick — no human command — then
restored to `0 * * * *`.

```
$ hermes cron edit 33a81bc1bb13 --schedule '1m'
$ sleep 145
$ hermes cron runs 33a81bc1bb13 --limit 4
4b9b03391f4e4e5aa31664e982e8d664  completed  job=33a81bc1bb13  source=builtin  2026-11-20T12:37:15.553230+00:00
d3fcb470aafc473aaa9729e74e58dfba  completed  job=33a81bc1bb13  source=direct   2026-11-20T12:32:54.574673+00:00
$ tail -1 /var/log/logos-issue-intake.log
2026-11-20T12:37:21Z RUN code=/root/ai-language-program/.worktrees/t_759f141f repo=abaddon/logos board=logos rc=0 dur=1s
$ hermes cron edit 33a81bc1bb13 --schedule '0 * * * *'
```

`source=builtin` is the scheduler; `source=direct` was §4. The gateway ticks the
cron of every profile it serves (`hermes cron status`: "serving profiles default,
…, platform-engineer, …"), and its heartbeat file for this profile updates once
a minute, which is why the job lives here rather than in a root crontab.

## 6. A failed run, end to end

Failure was forced the way a real one arrives — the endpoint answers nothing:

```
$ LOGOS_INTAKE_ENV_FILE=<env with LOGOS_INTAKE_API=http://127.0.0.1:9> \
    /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
ERROR http-error URLError url=http://127.0.0.1:9/repos/abaddon/logos/issues?…
$ echo $?
75
```

Three of those in a row, and the marker appears:

```
$ cat /var/lib/logos-issue-intake/consecutive_failures
3
$ ls -l /var/lib/logos-issue-intake
-rw------- 1 root root 259 … ALERT
-rw------- 1 root root   2 … consecutive_failures
$ cat /var/lib/logos-issue-intake/ALERT
logos-issue-intake: 3 consecutive failed runs, last rc=75 at 2026-11-20T12:39:58Z
last output:
ERROR http-error URLError url=http://127.0.0.1:9/repos/abaddon/logos/issues?…
log: /var/log/logos-issue-intake.log
```

The log carries the same streak, and a success clears both files:

```
2026-11-20T12:39:58Z RUN … rc=75 dur=0s
ERROR http-error URLError …
2026-11-20T12:39:58Z ALERT consecutive_failures=3 last_rc=75 see=/var/lib/logos-issue-intake/ALERT
$ /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh   # success
$ ls /var/lib/logos-issue-intake
                                           # empty: counter and marker cleared
```

A bad exit is also loud on stdout, which is what the scheduler quotes in its
failure notice — the run is not silent just because it wrote a marker.

## 7. The token really is sent

A fresh state path plus a bogus token removes every other explanation (no
`If-None-Match`, no cached 304):

```
$ LOGOS_INTAKE_ENV_FILE=<env with GITHUB_TOKEN=ghp_invalid… LOGOS_INTAKE_STATE=<fresh>> \
    /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
ERROR auth/repo status=401 url=https://api.github.com/repos/abaddon/logos/issues?…
$ echo $?
65
```

This test earned its keep: the first version of the runner sourced the env file
without `set -a`, so the pipeline inherited nothing, ran unauthenticated against
a public repo, and exited 0 — a green log line for a poller that was not sending
its credential. `tests/test_issue_intake_schedule.py`
(`test_env_file_values_reach_the_pipeline_process`) now pins it.

## 8. Overlap: the second run refuses

The pipeline's own lock, held by a live run:

```
$ printf 'pid=999999 started=…' > /root/.local/state/logos-issue-intake/state.json.lock
$ /root/.hermes/profiles/platform-engineer/scripts/logos-issue-intake.sh
ERROR locked pid=999999 started=2026-11-20T12:42:00Z age=0
$ echo $?
0
$ # state.json last_run_at before and after: 2026-11-20T12:40:15Z both times
```

and the real thing, two processes 50 ms apart (the first one's create step was
refused for an unrelated reason — see §10 — while the second was refused by the
lock):

```
A rc=75 'ERROR create failed issue=#101 rc=1\n… fetched=39 unseen=1 ready=1 picked=1 created=0 failed=1'
B rc=0  'ERROR locked pid=2482594 started=2026-11-20T12:40:28Z age=0'
```

One run in flight, one line for the second, one state write. The runner holds no
second lock; `08-operations.md` §8.6 explains why.

## 9. The scheduler's own failure lane

A throwaway job (`zz-intake-selftest`, a script that exits 3) was fired to prove
the lane the real job relies on, then removed. This one went through the CLI's
`run` path (`source=direct`), which records a run row and files an incident
exactly as a scheduled run does:

```
$ hermes cron run 96164318314a
  Ran now: failed.

$ hermes cron runs 96164318314a --limit 3
bb51f7b159c84907a9e11ae7570ad1f8  failed  job=96164318314a  source=direct  …
    Script exited with code 3
stdout:
selftest: deliberate failure

$ hermes cron incidents
  961643_5e38724d4791  detected
    Type:       script
    Error:      Script exited with code 3 stdout: selftest: deliberate failure
    Output:     /root/.hermes/profiles/platform-engineer/cron/output/96164318314a/2026-11-20_12-42-45.md

$ hermes cron remove 96164318314a
Removed job: zz-intake-selftest (96164318314a)
$ hermes cron incidents ack 961643_5e38724d4791
✓ Incident 961643_5e38724d4791 acknowledged (closed).
```

So a failed hourly run is visible in three places without the log file: the run
row, the incident, and (when `--deliver`/`--failure-deliver` names a chat) the
delivered `⚠ cron watchdog` notice.

## 10. Two things the host taught the schedule

**A run started from inside a dispatched Kanban worker cannot create tasks.**
Issue #101 opened during this work and the probe run picked it, then:

```
ERROR create failed issue=#101 rc=1
logos-issue-intake … fetched=39 prs=0 unseen=1 ready=1 picked=1 created=0 failed=1
```

The CLI refuses board mutations from a delegate child (`04-task-creation.md`
§4.1), and `hermes cron run` executes the job in the calling process, so the
worker's environment came with it. The pipeline stayed correct — no state entry
was written for #101, so a later run retries it with the same idempotency key —
but the failure is a harness artifact, not a pipeline bug: the scheduled run has
a clean environment and no such problem (§12).

**A quiet repo hides an expired token.** GitHub answers a conditional request
(`If-None-Match` from the state's `last_etag`) with `304` before it objects to the
credential. The first attempt at §6 used a bad token and got `rc=0`: `304`,
nothing new, nothing to report. The token is checked on the first run whose repo
content changed. Recorded in `08-operations.md` §8.5.

## 11. The first hourly fire, on the hour

Nothing was touched between 12:40 and 13:00. The gateway fired the job by itself:

```
$ hermes cron runs 33a81bc1bb13 --limit 3
addda231c53d40e3bf594acc4994509e  completed  job=33a81bc1bb13  source=builtin  2026-11-20T13:00:20.311210+00:00
4b9b03391f4e4e5aa31664e982e8d664  completed  job=33a81bc1bb13  source=builtin  2026-11-20T12:37:15.553230+00:00
d3fcb470aafc473aaa9729e74e58dfba  completed  job=33a81bc1bb13  source=direct   2026-11-20T12:32:54.574673+00:00

$ hermes cron list | grep -E 'Next run|Last run|Dispatch'
    Next run:  2026-11-20T14:00:00+00:00
    Last run:  2026-11-20T13:00:30.285904+00:00  ok
    Dispatch:  on time (scheduled 2026-11-20T13:00:00+00:00)

$ tail -1 /var/log/logos-issue-intake.log
2026-11-20T13:00:30Z RUN code=/root/ai-language-program/.worktrees/t_759f141f repo=abaddon/logos board=logos rc=0 dur=1s
```

`source=builtin`, `Dispatch: on time (scheduled 2026-11-20T13:00:00)`, a log line
ten seconds later, and the next occurrence booked for 14:00. The run was a silent
no-op — `rc=0`, no output — because nothing on the repo had changed since 12:40,
so GitHub answered the conditional fetch with `304` (§10). That is the intended
hourly behaviour: the schedule proves itself most quietly when there is nothing
to do.

Issue #101 (a QA probe opened at 12:40:25) is unseen in the state file and will
be picked by the first run whose repo content changes, which is what the
`last_etag` mechanism is for.

## 12. What environment the scheduler hands the script

The installation's whole side effect is `hermes kanban create`, so the question
worth answering is not "did the schedule fire" but "does the environment the
scheduler hands the script have a board it can write to". The ticked run in §11
proves the script ran; it cannot prove the create path because it never reached
it.

`hermes cron run` cannot answer that question — it executes the job in the process
that asks, so it inherits that process's environment. The same probe script, run
both ways, shows the difference. Fired by the tick (`source=builtin`):

```
HERMES_AGENT=true
HERMES_HOME=/root/.hermes/profiles/platform-engineer
HERMES_QUIET=1
HERMES_REAL_HOME=/root
HOME=/root
USER=root
                                    # no delegate marker, no session, no board pins
```

run through `hermes cron run` from inside a dispatched Kanban worker
(`source=direct`):

```
HERMES_DELEGATED_CHILD_CONTEXT=/root/.hermes
HERMES_KANBAN_BOARD=logos
HERMES_KANBAN_DB=/root/.hermes/kanban/boards/logos/kanban.db
HERMES_KANBAN_BRANCH=wt/t_759f141f
HERMES_KANBAN_WORKSPACE=/root/ai-language-program/.worktrees/t_759f141f
HERMES_SESSION_ID=local-1c08c240…
```

The marker in the second dump is exactly what §10's `create failed … rc=1` met.
With the probe job left on a one-minute schedule, the ticked run created and
withdrew a real task using the pipeline's own flags:

```
created: {
  "id": "t_4bd996ce",
  "title": "[probe] scheduled create",
  "assignee": "oss-contributor",
  "status": "blocked",
  "created_by": "logos-issue-intake",
  …
}
Archived t_4bd996ce
```

(`--initial-status blocked` in the probe, so the dispatcher could not claim it
between create and archive; the intake itself creates `ready` tasks.) The probe
job and its script were removed afterwards — `hermes cron list` shows the
`logos-issue-intake` job and nothing else.

SOURCES (LAYER 3 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/08-operations.md
 -> the operational chapter this dossier evidences
docs/pipelines/issue-intake/02-analysis/06-config.md
 -> the env file, exit codes and cron install the install script implements
docs/pipelines/issue-intake/03-dossiers/03-hermes-cli-evidence.md
 -> the `cron create` / `kanban create` surfaces quoted from the installed CLI
