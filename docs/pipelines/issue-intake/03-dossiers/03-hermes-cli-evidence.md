# Dossier — the Hermes CLI, as installed

The pipeline shells out to `hermes kanban create` and is scheduled by
`hermes cron create`. Both calls are quoted from the installed CLI on this host
(`/root/.hermes/hermes-agent`, 2026-11-20), not from documentation.

## `hermes kanban create`

```
usage: hermes kanban create [-h] [--body BODY] [--body-file PATH]
                            [--assignee ASSIGNEE] [--parent PARENT]
                            [--workspace WORKSPACE] [--branch BRANCH]
                            [--project PROJECT] [--tenant TENANT]
                            [--priority PRIORITY] [--triage]
                            [--idempotency-key IDEMPOTENCY_KEY]
                            [--max-runtime MAX_RUNTIME] [--created-by CREATED_BY]
                            [--skill SKILLS] [--max-retries N] [--model MODEL_OVERRIDE]
                            [--provider PROVIDER_OVERRIDE]
                            [--completion-contract CONTRACT] [--goal]
                            [--goal-max-turns N]
                            [--initial-status {blocked,running}] [--json]
                            title
```

Three help lines the spec depends on, verbatim:

- `--body-file PATH   Read the opening post from a file ('-' = stdin), so bodies
  with embedded newlines or flag-like lines survive shell quoting.`
- `--idempotency-key IDEMPOTENCY_KEY  Dedup key. If a non-archived task with
  this key exists, its id is returned instead of creating a duplicate.`
- `--workspace WORKSPACE  scratch | worktree | worktree:<path> | dir:<path>
  (default: scratch; an explicit 'scratch' also opts out of a project-scoped
  board's project)`

The global `--board <slug>` precedes the subcommand:
`hermes kanban --board logos create …`.

### What the code does with those flags

`hermes_cli/kanban.py:364-383` (`_cmd_create`) forwards
`idempotency_key=getattr(args, "idempotency_key", None)` into `kb.create_task`,
then:

```python
if getattr(args, "json", False):
    _print_json(_task_to_dict(task))
else:
    print(f"Created {task_id}  ({task.status}, assignee={task.assignee or '-'})")
```

and `hermes_cli/kanban_output.py:16-22` fixes the JSON keys:

```python
_TASK_DICT_FIELDS = (
    "id", "title", "body", "assignee", "status", "priority", "tenant", …
)
```

so `--json` prints an object whose **`"id"`** is the task id. That is the field
the pipeline parses; there is no `task_id` key.

`hermes_cli/kanban_db.py:1176` documents the dedupe semantic the spec relies on:

```
``idempotency_key``: an existing non-archived task with the key is returned
instead of a duplicate.
```

and the lookup is `SELECT id FROM tasks WHERE idempotency_key = ? … ORDER BY
created_at DESC LIMIT 1` (`kanban_db.py:1227-1231`). Two consequences:

- an **archived** task does not block re-creation (the spec records this hole in
  `05-failure-and-idempotency.md` §5.1);
- the key is a plain column with no uniqueness constraint, so "one key, one
  issue, forever" is a discipline the pipeline keeps, not one the database
  enforces.

### The worker-context refusal

Running `hermes kanban list` from inside a `delegate_task` child on this host
prints, and exits non-zero:

```
kanban: delegate_task child contexts cannot mutate Kanban tasks or boards
```

That is why the spec installs the poller as a **cron script job** and says in
`04-task-creation.md` §4.1 that it must not be run from a dispatched worker.

## `hermes cron create`

```
usage: hermes cron create [-h] [--name NAME] [--deliver DELIVER]
                          --failure-deliver FAILURE_DELIVER] [--repeat REPEAT]
                          [--catch-up {on,off}] [--wrap-response] [--no-wrap-response]
                          [--skill SKILLS] [--script SCRIPT] [--no-agent]
                          [--monitor-script MONITOR_SCRIPT] [--monitor-url MONITOR_URL]
                          [--workdir WORKDIR] [--model MODEL] [--pin] …
                          schedule [prompt]
```

The two flags that make this a *script* job rather than an agent job, verbatim:

- `--script SCRIPT  Path to a script under ~/.hermes/scripts/. Default mode:
  script stdout is injected into the agent's prompt each run. With --no-agent:
  the script IS the job and its stdout is delivered verbatim.`
- `--no-agent  Skip the LLM entirely — run --script on schedule and deliver its
  stdout directly. Empty stdout = silent.`

"Empty stdout = silent" is exactly the no-op behaviour the spec specifies, and
it is why the run prints nothing when there is nothing new. `schedule` accepts
cron syntax (`0 * * * *`) per the usage line (`'30m'`, `'every 2h'`,
`'0 9 * * *'`).

## Dispatcher cadence

`hermes kanban create` prints, when no dispatcher is running:

> The gateway hosts an embedded dispatcher that ticks every 60 seconds by
> default (config: `kanban.dispatch_interval_seconds`). Without a running
> gateway, tasks stay in 'ready' forever.

So a task created at `HH:00:03` is claimed within about a minute — the hourly
schedule plus a 60-second tick is the whole latency budget, and no queue-draining
logic belongs in the poller.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/04-task-creation.md
 -> the invocation built from these flags, and the body template it writes
docs/pipelines/issue-intake/02-analysis/05-failure-and-idempotency.md
 -> the dedupe consequences of `idempotency_key` and the archive hole
docs/pipelines/issue-intake/02-analysis/06-config.md
 -> the cron install line and why `--no-agent` is the right mode
