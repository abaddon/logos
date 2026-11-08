#!/usr/bin/env bash
# Gate: every commit in a pull request carries a DCO sign-off.
#
# A commit passes when its message contains a trailer of the form
#
#     Signed-off-by: Name <email>
#
# whose email matches the commit's author email. This is the Developer
# Certificate of Origin, enforced in the repository's own gate job instead of a
# third-party app.
#
# Usage:
#   bash tools/check_dco.sh BASE HEAD
#   DCO_BASE=... DCO_HEAD=... bash tools/check_dco.sh
#   bash tools/check_dco.sh
#
# With no arguments the range is the current branch since `main` (from the
# merge base). When there is nothing to compare -- no local `main`, or no
# commits since it -- the gate skips and says so instead of failing.

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

if [[ $# -ge 2 ]]; then
    BASE="$1"
    HEAD="$2"
elif [[ -n "${DCO_BASE:-}" && -n "${DCO_HEAD:-}" ]]; then
    BASE="$DCO_BASE"
    HEAD="$DCO_HEAD"
else
    HEAD="HEAD"
    if ! git rev-parse --verify --quiet main > /dev/null; then
        echo "sign-off: no local 'main' branch; nothing to compare (create it with 'git fetch origin main:main')"
        exit 0
    fi
    BASE="main"
fi

if ! git rev-parse --verify --quiet "$BASE" > /dev/null; then
    echo "sign-off: base '$BASE' is not a commit; refusing to skip the check" >&2
    exit 1
fi
if ! git rev-parse --verify --quiet "$HEAD" > /dev/null; then
    echo "sign-off: head '$HEAD' is not a commit; refusing to skip the check" >&2
    exit 1
fi

MERGE_BASE="$(git merge-base "$BASE" "$HEAD" 2>/dev/null)" || {
    echo "sign-off: '$BASE' and '$HEAD' have no common ancestor; refusing to skip the check" >&2
    exit 1
}

COMMITS="$(git rev-list "$MERGE_BASE..$HEAD")"
if [[ -z "$COMMITS" ]]; then
    printf 'sign-off: no commits between %s and %s; nothing to compare\n' "$BASE" "$HEAD"
    exit 0
fi

FAILED=0
CHECKED=0

for sha in $COMMITS; do
    CHECKED=$((CHECKED + 1))
    author_name="$(git show -s --format='%an' "$sha")"
    author_email="$(git show -s --format='%ae' "$sha")"

    if git show -s --format='%B' "$sha" | awk -v want="$author_email" '
        {
            line = $0
            sub(/\r$/, "", line)
            if (line ~ /^[[:space:]]*Signed-off-by:[[:space:]]/) {
                if (match(line, /<[^<>]+>/)) {
                    email = substr(line, RSTART + 1, RLENGTH - 2)
                    if (tolower(email) == tolower(want)) {
                        found = 1
                    }
                }
            }
        }
        END { exit(found ? 0 : 1) }
    '; then
        continue
    fi

    FAILED=$((FAILED + 1))
    printf 'sign-off: commit %s has no Signed-off-by trailer matching its author <%s>\n' "$sha" "$author_email"
    printf 'Add exactly this line to the end of the commit message:\n'
    printf '\n    Signed-off-by: %s <%s>\n\n' "$author_name" "$author_email"
    printf 'Then amend it, or sign off the commits since the base:\n'
    printf '    git commit --amend --signoff\n'
    printf '    git rebase --signoff %s\n' "$MERGE_BASE"
done

if [[ "$FAILED" -ne 0 ]]; then
    printf 'sign-off: %d of %d commit(s) failed the DCO check\n' "$FAILED" "$CHECKED"
    exit 1
fi

printf 'sign-off: %d commit(s) carry a matching Signed-off-by trailer\n' "$CHECKED"
