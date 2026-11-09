#!/usr/bin/env bash
# The sixth gate: the self-hosted front end must reproduce canonical source.
#
# Build gen2 from src/logosc/*.logos plus the two standard modules gen2 may
# use: map and str. Only those two, not the whole src/std directory — the
# stdlib's `_test` files carry `(test …)` forms and are not modules gen2 needs.
# Then run `gen2 fmt <file>` for every path in tools/selfhost-manifest.txt and
# compare its stdout with the file, byte for byte. Every tracked .logos file is
# canonical (tools/accept.sh proves the Python formatter is a fixed point), so
# any difference is either a printer bug in the Logos port or a file that is no
# longer canonical.
#
# The floor: the manifest must list every tracked .logos file and at least
# FLOOR of them, and the build must produce an executable. A pruned checkout, a
# stale manifest or a failed build must fail loudly rather than pass over zero
# files.
#
# A second phase judges the resolver-owned negative corpus. Every
# tests/parse/**/*.expect names a fixture that must make `gen2 resolve` fail
# with that exact code; the fixtures are the repository's statement of the
# resolver's negative behaviour, and this gate is what keeps the Logos port
# agreeing with them. RESOLVE_FLOOR is the same kind of floor: pruning fixtures
# below it fails rather than passing over a smaller set.
#
# Output: one line per fmt or resolve failure, then
# `selfhost: N files, M differences` and `resolve: N fixtures, M differences`.
# Exit 0 when both phases are clean, 1 when any file or fixture differs, 2 when
# the gate could not run at all (missing manifest, count mismatch, no binary).

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/selfhost"
MANIFEST="$ROOT/tools/selfhost-manifest.txt"
BIN="$OUT/gen2"
# Below this many files the manifest is not the corpus it claims to be. The
# repository has held more than this since W4; lowering the number is a
# deliberate act, not a side effect of a pruned tree.
FLOOR=100
# Every resolver-owned negative fixture has a sidecar; the count may grow but
# must not silently shrink.
RESOLVE_FLOOR=13

cd "$ROOT" || exit 2
mkdir -p "$OUT"

if [[ ! -f "$MANIFEST" ]]; then
    echo "selfhost: missing manifest: ${MANIFEST#"$ROOT"/}" >&2
    exit 2
fi

mapfile -t FILES < <(grep -v '^[[:space:]]*$' "$MANIFEST")
COUNT=${#FILES[@]}
TRACKED=$(git ls-files '*.logos' | wc -l)

if (( COUNT < FLOOR )); then
    echo "selfhost: manifest lists $COUNT files, below the floor of $FLOOR" >&2
    exit 2
fi
if (( COUNT != TRACKED )); then
    if (( COUNT < TRACKED )); then
        echo "selfhost: manifest lists $COUNT files but git tracks $TRACKED; regenerate tools/selfhost-manifest.txt" >&2
    else
        echo "selfhost: manifest lists $COUNT files but git tracks $TRACKED; remove stale entries from tools/selfhost-manifest.txt" >&2
    fi
    exit 2
fi

shopt -s nullglob
SOURCES=(src/logosc/*.logos src/std/map.logos src/std/str.logos)
shopt -u nullglob
if (( ${#SOURCES[@]} == 0 )); then
    echo "selfhost: no sources under src/logosc; cannot build gen2" >&2
    exit 2
fi

BUILD_LOG="$OUT/build.log"
if ! python3 -m logos build "${SOURCES[@]}" -o "$BIN" > "$BUILD_LOG" 2>&1; then
    echo "selfhost: gen2 build failed (log: ${BUILD_LOG#"$ROOT"/})" >&2
    tail -n 25 "$BUILD_LOG" | sed 's/^/    /' >&2
    exit 2
fi
if [[ ! -x "$BIN" ]]; then
    echo "selfhost: gen2 build produced no executable at ${BIN#"$ROOT"/}" >&2
    exit 2
fi

DIFFS=0
STDOUT="$OUT/current.out"
STDERR="$OUT/current.err"
for path in "${FILES[@]}"; do
    if [[ ! -f "$path" ]]; then
        printf 'selfhost: %s: missing file\n' "$path"
        DIFFS=$((DIFFS + 1))
        continue
    fi
    if ! "$BIN" fmt "$path" > "$STDOUT" 2> "$STDERR"; then
        printf 'selfhost: %s: gen2 fmt failed: %s\n' "$path" "$(head -n 1 "$STDERR")"
        DIFFS=$((DIFFS + 1))
        continue
    fi
    if ! cmp -s "$STDOUT" "$path"; then
        printf 'selfhost: %s: output differs\n' "$path"
        DIFFS=$((DIFFS + 1))
    fi
done

printf 'selfhost: %d files, %d differences\n' "$COUNT" "$DIFFS"

# Phase two: every resolver-owned negative fixture must make `gen2 resolve`
# print the code its sidecar demands. A fixture that resolves cleanly, prints
# no code, or prints another code is one difference.
mapfile -t EXPECTS < <(find tests/parse -type f -name '*.expect' | sort)
RESOLVE_COUNT=${#EXPECTS[@]}
if (( RESOLVE_COUNT < RESOLVE_FLOOR )); then
    printf 'resolve: found %d fixtures, below the floor of %d\n' \
        "$RESOLVE_COUNT" "$RESOLVE_FLOOR" >&2
    exit 2
fi

RDIFTS=0
for expect in "${EXPECTS[@]}"; do
    fixture="${expect%.expect}.logos"
    want="$(tr -d '[:space:]' < "$expect")"
    if [[ ! -f "$fixture" ]]; then
        printf 'resolve: %s: missing fixture\n' "$fixture"
        RDIFTS=$((RDIFTS + 1))
        continue
    fi
    if "$BIN" resolve "$fixture" > "$STDOUT" 2> "$STDERR"; then
        printf 'resolve: %s: expected %s, gen2 resolve exited 0\n' "$fixture" "$want"
        RDIFTS=$((RDIFTS + 1))
        continue
    fi
    got="$(sed -n 's/.*\(E[0-9]\{4\}\).*/\1/p; q' "$STDERR")"
    if [[ -z "$got" ]]; then
        printf 'resolve: %s: expected %s, no code printed\n' "$fixture" "$want"
        RDIFTS=$((RDIFTS + 1))
    elif [[ "$got" != "$want" ]]; then
        printf 'resolve: %s: expected %s, got %s\n' "$fixture" "$want" "$got"
        RDIFTS=$((RDIFTS + 1))
    fi
done

printf 'resolve: %d fixtures, %d differences\n' "$RESOLVE_COUNT" "$RDIFTS"
if (( DIFFS > 0 || RDIFTS > 0 )); then
    exit 1
fi
exit 0
