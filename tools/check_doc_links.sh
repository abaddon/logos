#!/usr/bin/env bash
# Prove that every relative markdown link in a tree of pages resolves inside it.
#
# The tarball is read offline, so a link that only works in a git checkout is a
# dead end for the person who installed it: `README.md` in the package pointed
# at `docs/install.md` while the package shipped no `docs/`. This walks every
# `*.md` under the directory it is given, extracts each `](target)` link,
# ignores absolute URLs, mail links and same-page anchors, strips a `#fragment`,
# and requires what is left to exist relative to the page that holds it.
#
# Two callers, one rule: `tools/dist.sh` runs it on the staging tree, so a page
# with a broken link fails the build rather than the reader, and
# `tools/verify_install.sh` runs it on the unpacked artifact, so the claim is
# measured on the thing that ships.
#
# Usage: bash tools/check_doc_links.sh [DIR]    (default: the repository root)

set -u -o pipefail

TREE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
if [[ ! -d "$TREE" ]]; then
    printf 'check_doc_links: no such directory: %s\n' "$TREE" >&2
    exit 2
fi

FILES=0
LINKS=0
BROKEN=0

while IFS= read -r -d '' page; do
    FILES=$((FILES + 1))
    dir="$(dirname "$page")"
    while IFS= read -r target; do
        case "$target" in
            *://* | mailto:* | '#'*) continue ;;
        esac
        path="${target%%#*}"
        [[ -z "$path" ]] && continue
        LINKS=$((LINKS + 1))
        if [[ ! -e "$dir/$path" ]]; then
            BROKEN=$((BROKEN + 1))
            printf 'broken: %s -> %s\n' "${page#"$TREE"/}" "$target"
        fi
    done < <(grep -oE '\]\([^)]*\)' "$page" | sed -e 's/^](//' -e 's/)$//')
done < <(find "$TREE" -type f -name '*.md' -print0 | sort -z)

printf '%d files, %d relative links, %d broken\n' "$FILES" "$LINKS" "$BROKEN"
(( BROKEN == 0 ))
