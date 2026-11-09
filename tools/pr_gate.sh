#!/usr/bin/env bash
# Run every gate a pull request must pass.
#
# This is the local twin of .github/workflows/gate.yml: the same six gates, in
# the same order, one PASS or FAIL line each, then a summary. On failure it
# prints the tail of that gate's log. Build output goes under build/pr_gate/,
# which is ignored.
#
# Sign-off is a precondition, not one of the gates: every commit must carry a
# Signed-off-by trailer matching its author (see CONTRIBUTING.md).
# tools/check_dco.sh runs first; if it fails the script prints FAIL sign-off
# and exits non-zero without running the rest. AGENTS.md therefore keeps the
# documented list at six commands. tests/test_contributing.py pins six gates
# plus this ordering, so the precondition cannot drift down the script.

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/pr_gate"

cd "$ROOT" || exit 2
mkdir -p "$OUT"

FAILURES=0
RAN=0

gate_make_test() {
    make test
}

gate_logos_test() {
    python3 -m logos test
}

gate_accept() {
    bash tools/accept.sh
}

gate_guide() {
    python3 -m logos guide --check
}

gate_fmt() {
    if ! git rev-parse --verify --quiet main > /dev/null; then
        echo "fmt: no local 'main' branch; create it with 'git fetch origin main:main'" >&2
        return 1
    fi
    if [[ -n "$(git diff --name-only main...HEAD -- '*.logos')" ]]; then
        python3 -m logos fmt $(git diff --name-only main...HEAD -- '*.logos')
    fi
    # The manual and the corpus are generated or canonical by contract. Format
    # them in place, then fail if formatting changed a tracked file.
    python3 -m logos fmt tests docs/manual
    git diff --exit-code -- '*.logos'
}

gate_selfhost() {
    bash tools/selfhost.sh
}

run_gate() {
    local name="$1"
    local fn="$2"
    local slug="${name// /-}"
    local log="$OUT/${slug}.log"
    RAN=$((RAN + 1))
    if "$fn" > "$log" 2>&1; then
        printf 'PASS %s\n' "$name"
    else
        FAILURES=$((FAILURES + 1))
        printf 'FAIL %s  (log: %s)\n' "$name" "${log#"$ROOT"/}"
        tail -n 25 "$log" | sed 's/^/    /'
    fi
}

# Precondition, not a gate: the gates below describe what the code must do, the
# sign-off describes who stands behind the commit. Check it first and stop, so
# an unsigned branch never reaches the slow gates and never reports them as
# passed. The range is the branch since main, as in check_dco.sh.
DCO_LOG="$OUT/sign-off.log"
if bash tools/check_dco.sh > "$DCO_LOG" 2>&1; then
    printf 'PASS sign-off (precondition)\n'
else
    printf 'FAIL sign-off (precondition)  (log: %s)\n' "${DCO_LOG#"$ROOT"/}"
    tail -n 25 "$DCO_LOG" | sed 's/^/    /'
    printf '\nThe six gates were not run: every commit must carry a Signed-off-by trailer\n'
    printf 'matching its author. Sign the commits since main and try again:\n'
    printf '    git rebase --signoff main\n'
    exit 1
fi

run_gate "unit tests" gate_make_test
run_gate "corpus" gate_logos_test
run_gate "acceptance" gate_accept
run_gate "manual drift" gate_guide
run_gate "formatting" gate_fmt
run_gate "self-hosting" gate_selfhost

if [[ "$FAILURES" -eq 0 ]]; then
    printf '\n%d/%d gates passed\n' "$RAN" "$RAN"
    exit 0
fi
printf '\n%d/%d gates passed, %d failed\n' "$((RAN - FAILURES))" "$RAN" "$FAILURES"
exit 1
