#!/bin/sh
# logos-issue-intake — one hourly run of tools/issue_intake.py.
#
# Installed by tools/install_issue_intake_schedule.sh and run by the Hermes cron
# job 'logos-issue-intake' (`0 * * * *`, --no-agent --script). The contract:
#
#   * config and the token come from an env file (0600), never from this script,
#     the job definition, or a crontab;
#   * every run appends one RUN line, and the pipeline's own output when it has
#     any, to $LOG — so the log is the audit trail and an operator can `tail -f`;
#   * a non-zero pipeline exit increments a consecutive-failure counter in
#     $FAIL_DIR and, at $ALERT_AFTER, writes an ALERT marker file. stdout carries
#     the pipeline's error lines, so the cron job's own failure notice has them;
#   * overlap is prevented by the pipeline's lock (state.json.lock): a second run
#     started while one is live logs `ERROR locked <pid>` and does nothing. This
#     script adds no second lock — one owner of that invariant is enough.
#
# Manual trigger: `hermes cron run logos-issue-intake` (next tick), or run this
# script directly, which is what the schedule does.
set -u

ENV_FILE=${LOGOS_INTAKE_ENV_FILE:-/etc/logos-issue-intake/env}
LOG=${LOGOS_INTAKE_LOG:-/var/log/logos-issue-intake.log}
FAIL_DIR=${LOGOS_INTAKE_FAIL_DIR:-/var/lib/logos-issue-intake}
ALERT_AFTER=${LOGOS_INTAKE_ALERT_AFTER:-3}

stamp() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

if [ ! -r "$ENV_FILE" ]; then
    printf 'ERROR logos-issue-intake: env file %s is not readable\n' "$ENV_FILE"
    exit 65
fi
umask 077
# `set -a` matters: sourcing a file only sets shell variables, and the pipeline
# is a separate process. Without it the env file would be decorative.
set -a
. "$ENV_FILE"
set +a

# The code may be in the merged checkout or, until this branch merges, in the
# worktree the installer was run from. Run whichever checkout has the tool.
code_root=${LOGOS_INTAKE_CODE_ROOT:-/root/ai-language-program}
if [ ! -f "$code_root/tools/issue_intake.py" ] && [ -n "${LOGOS_INTAKE_CODE_FALLBACK:-}" ]; then
    code_root=$LOGOS_INTAKE_CODE_FALLBACK
fi
if [ ! -f "$code_root/tools/issue_intake.py" ]; then
    printf 'ERROR logos-issue-intake: %s/tools/issue_intake.py not found (log %s)\n' \
        "$code_root" "$LOG"
    exit 65
fi

mkdir -p "$FAIL_DIR" 2>/dev/null || {
    printf 'ERROR logos-issue-intake: cannot create %s\n' "$FAIL_DIR"
    exit 65
}
: >>"$LOG" 2>/dev/null || {
    printf 'ERROR logos-issue-intake: cannot write %s\n' "$LOG"
    exit 65
}

started=$(date +%s)
output=$(cd "$code_root" && python3 tools/issue_intake.py --once 2>&1)
rc=$?
duration=$(( $(date +%s) - started ))

{
    printf '%s RUN code=%s repo=%s board=%s rc=%s dur=%ss\n' "$(stamp)" \
        "$code_root" "${LOGOS_INTAKE_REPO:-abaddon/logos}" \
        "${LOGOS_INTAKE_BOARD:-logos}" "$rc" "$duration"
    [ -n "$output" ] && printf '%s\n' "$output"
} >>"$LOG"

counter=$FAIL_DIR/consecutive_failures
alert=$FAIL_DIR/ALERT
if [ "$rc" -eq 0 ]; then
    rm -f "$counter" "$alert"
else
    failures=$(( $(cat "$counter" 2>/dev/null || echo 0) + 1 ))
    printf '%s\n' "$failures" >"$counter"
    logger -t logos-issue-intake "run failed rc=$rc consecutive=$failures log=$LOG" 2>/dev/null
    if [ "$failures" -ge "$ALERT_AFTER" ]; then
        {
            printf 'logos-issue-intake: %s consecutive failed runs, last rc=%s at %s\n' \
                "$failures" "$rc" "$(stamp)"
            printf 'last output:\n%s\n' "$(printf '%s' "$output" | tail -n 5)"
            printf 'log: %s\n' "$LOG"
        } >"$alert"
        chmod 600 "$alert"
        printf '%s ALERT consecutive_failures=%s last_rc=%s see=%s\n' \
            "$(stamp)" "$failures" "$rc" "$alert" >>"$LOG"
    fi
fi

# stdout is the cron deliverable: empty on a clean no-op or a lock-skip, the
# pipeline's error lines on failure (the non-zero exit is what marks it failed).
[ -n "$output" ] && printf '%s\n' "$output"
exit "$rc"
