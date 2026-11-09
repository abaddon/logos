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
# Output: one line per failure, then `selfhost: N files, M differences`.
# Exit 0 when there are none, 1 when a file differs, 2 when the gate could not
# run at all (missing manifest, count mismatch, no binary).

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/selfhost"
MANIFEST="$ROOT/tools/selfhost-manifest.txt"
BIN="$OUT/gen2"
# Below this many files the manifest is not the corpus it claims to be. The
# repository has held more than this since W4; lowering the number is a
# deliberate act, not a side effect of a pruned tree.
FLOOR=100

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
[[ "$DIFFS" -eq 0 ]] || exit 1
exit 0
