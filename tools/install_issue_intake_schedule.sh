#!/bin/sh
# Install the hourly logos-issue-intake schedule on this host. Idempotent: run it
# again after a change (or after the branch merges into /root/ai-language-program)
# and it rewrites the same five things in place, keeping the existing token.
#
#   /etc/logos-issue-intake/env                    0600, root — the only secret
#   /var/log/logos-issue-intake.log                0640, one RUN line per run
#   /etc/logrotate.d/logos-issue-intake            daily, 14 rotations, compressed
#   $HERMES_HOME/scripts/logos-issue-intake.sh     0755, a copy of the runner
#   the Hermes cron job 'logos-issue-intake'       `0 * * * *`, --no-agent
#
# The token is read from the existing env file, else $GITHUB_TOKEN, else
# `gh auth token`, and is never printed.
set -eu

usage() {
    cat <<'EOF'
usage: install_issue_intake_schedule.sh [--repo-root PATH] [--hermes-home PATH]

  --repo-root PATH    checkout holding tools/issue_intake.py (default: this checkout)
  --hermes-home PATH  Hermes home owning the cron job (default: $HERMES_HOME, else /root/.hermes)
EOF
}

repo_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
hermes_home=${HERMES_HOME:-/root/.hermes}
env_file=/etc/logos-issue-intake/env
log_file=/var/log/logos-issue-intake.log
fail_dir=/var/lib/logos-issue-intake
code_root=/root/ai-language-program

while [ $# -gt 0 ]; do
    case $1 in
    --repo-root) repo_root=$2; shift 2 ;;
    --hermes-home) hermes_home=$2; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 64 ;;
    esac
done

[ "$(id -u)" = 0 ] || {
    echo "install_issue_intake_schedule: must run as root" >&2
    exit 77
}
[ -f "$repo_root/tools/issue_intake.py" ] || {
    printf 'install_issue_intake_schedule: %s/tools/issue_intake.py not found\n' "$repo_root" >&2
    exit 65
}
python=${PYTHON:-/usr/bin/python3}
hermes=$(command -v hermes || echo /root/.hermes/hermes-agent/.hermes/bin/hermes)

# --- the env file: the token is the only thing that needs care ---------------
token=
if [ -s "$env_file" ]; then
    token=$(sed -n 's/^GITHUB_TOKEN=//p' "$env_file" | head -n 1)
fi
if [ -z "$token" ]; then
    token=${GITHUB_TOKEN:-}
fi
if [ -z "$token" ]; then
    token=$(gh auth token 2>/dev/null || true)
fi
if [ -z "$token" ]; then
    echo "install_issue_intake_schedule: no GITHUB_TOKEN, and 'gh auth token' gave none" >&2
    exit 65
fi

install -d -m 0750 -o root -g root /etc/logos-issue-intake
tmp=$(mktemp /etc/logos-issue-intake/.env.XXXXXX)
trap 'rm -f "$tmp"' EXIT INT TERM
{
    printf 'GITHUB_TOKEN=%s\n' "$token"
    printf '# board the intake creates tasks on; it must already exist\n'
    printf 'LOGOS_INTAKE_REPO=abaddon/logos\n'
    printf 'LOGOS_INTAKE_BOARD=logos\n'
    printf 'HERMES_KANBAN_DB=%s\n' "${HERMES_KANBAN_DB:-/root/.hermes/kanban/boards/logos/kanban.db}"
    printf '# REPO_ROOT is the workspace parent for the created tasks (merged checkout)\n'
    printf 'LOGOS_INTAKE_REPO_ROOT=%s\n' "$code_root"
    printf '# the code may live in the merged checkout or, before the merge, in a worktree\n'
    printf 'LOGOS_INTAKE_CODE_ROOT=%s\n' "$code_root"
    printf 'LOGOS_INTAKE_CODE_FALLBACK=%s\n' "$repo_root"
    printf 'LOGOS_INTAKE_HERMES=%s\n' "$hermes"
    printf 'PATH=%s:/usr/local/bin:/usr/bin:/bin\n' "$(dirname -- "$hermes")"
} >"$tmp"
mv "$tmp" "$env_file"
chmod 0600 "$env_file"
chgrp root "$env_file"

# --- log, its rotation, and the failure marker directory ---------------------
install -d -m 0700 -o root -g root "$fail_dir"
[ -f "$log_file" ] || : >"$log_file"
chmod 0640 "$log_file"
chgrp adm "$log_file" 2>/dev/null || true

cat >/etc/logrotate.d/logos-issue-intake <<EOF
$log_file {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 root adm
}
EOF
chmod 0644 /etc/logrotate.d/logos-issue-intake

# --- the runner, where the cron job is allowed to load scripts from ----------
install -d -m 0700 "$hermes_home/scripts"
install -m 0755 "$repo_root/tools/issue_intake_schedule.sh" \
    "$hermes_home/scripts/logos-issue-intake.sh"

# --- the cron job: edit in place if it exists, so run history survives -------
job_id=
jobs_json=$hermes_home/cron/jobs.json
if [ -f "$jobs_json" ]; then
    job_id=$("$python" - "$jobs_json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
jobs = data if isinstance(data, list) else data.get("jobs", data)
if isinstance(jobs, dict):
    jobs = list(jobs.values())
for job in jobs:
    if job.get("name") == "logos-issue-intake":
        print(job.get("id") or "")
        break
PY
    )
fi

if [ -n "$job_id" ]; then
    "$hermes" cron edit "$job_id" --schedule '0 * * * *' --script logos-issue-intake.sh \
        --no-agent --deliver local --workdir "$code_root"
else
    "$hermes" cron create '0 * * * *' --name logos-issue-intake --no-agent \
        --script logos-issue-intake.sh --deliver local --workdir "$code_root"
fi

# --- what got installed ------------------------------------------------------
printf 'env      %s (%s)\n' "$env_file" "$(stat -c %a "$env_file")"
printf 'log      %s\n' "$log_file"
printf 'runner   %s\n' "$hermes_home/scripts/logos-issue-intake.sh"
printf 'markers  %s\n' "$fail_dir"
"$hermes" cron list
