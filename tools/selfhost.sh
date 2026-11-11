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
# agreeing with them. A fixture whose source must fail to lex or parse keeps its
# sources as `*.logos.txt` and is judged on a copy under build/, because no
# tracked `*.logos` file may be malformed; see the phase below.
# RESOLVE_FLOOR is the same kind of floor: pruning fixtures
# below it fails rather than passing over a smaller set.
#
# A third phase judges the checker-owned negative corpus. tools/selfhost-check.txt
# lists one fixture per line — only the cases the checker can decide: the
# declaration rules and the scalar body rules — and
# each fixture's .check names the whole line `gen2 check` must print, path, code and
# message, as the reference implementation prints it. A wrong path or a reworded
# message is a difference, not just a wrong code. tools/check_parity.py writes the
# sidecars from Python, so the expectation cannot drift from the oracle. CHECK_FLOOR
# is the same kind of floor: a pruned list fails rather than passing over fewer
# fixtures.
#
# Output: one line per fmt, resolve or check failure, then
# `selfhost: N files, M differences`, `resolve: N fixtures, M differences` and
# `check: N fixtures, M differences`. Exit 0 when every phase is clean, 1 when
# any file or fixture differs, 2 when the gate could not run at all (missing
# manifest or list, count mismatch, no binary).

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
# must not silently shrink. Fourteen today: the twelve resolver cases and the
# checker case, plus `bad-lex`, whose sources are `*.logos.txt` because the
# imported file must fail to lex.
RESOLVE_FLOOR=14
# The checker's list names exactly the corpus cases the checker decides: the
# declaration cases, the scalar and control-flow body cases, the calls,
# containers, strings and memory forms the W6 B3 pass reads, the ownership
# rules of W6 C1 (moves, frees, E0302/E0303, E0402, E0005) and the narrowed
# E0107 deferral, the ref rules of W6 C2 (E0304 at the argument shape and
# E0305 at every escape site, plus the ref payloads of `some`/`ok`, the E0107
# deferral keyed on that payload, E0304's mutability rule, and the nested payload
# rule that walks a ref through `some`/`ok`/`err` however deeply it is carried),
# and the results and optionals of W6 C3 (a typed `some`/`none`/`ok`/`err`,
# `try` with E0601, result obligations with E0602, matches that must name every
# variant with E0600, and the four ref escapes the C2 re-review found).
# Eighty-three today; a pruned list is a failure, not a smaller pass.
CHECK_LIST="$ROOT/tools/selfhost-check.txt"
CHECK_FLOOR=83

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
#
# A fixture whose source must fail to lex or parse cannot be a *.logos file in
# the tree: `tools/accept.sh` formats every one of them and this gate
# reproduces every tracked one, so a malformed source has no legal name. Such a
# fixture therefore keeps its sources as `*.logos.txt` — invisible to both
# formatters and to `git ls-files '*.logos'` — and is judged on a copy under
# build/ where the suffix is dropped. `‹fixture›.expect` stays beside the
# sources, so the count below still counts it, and the copy is rebuilt on every
# run so an edited source is never masked by a stale one.
mapfile -t EXPECTS < <(find tests/parse -type f -name '*.expect' | sort)
RESOLVE_COUNT=${#EXPECTS[@]}
if (( RESOLVE_COUNT < RESOLVE_FLOOR )); then
    printf 'resolve: found %d fixtures, below the floor of %d\n' \
        "$RESOLVE_COUNT" "$RESOLVE_FLOOR" >&2
    exit 2
fi

# Materialize the fixture whose stem is <stem> (a path without `.logos` or
# `.expect`) under build/ and print the root's path there. Every `*.logos.txt`
# in the fixture's directory becomes `*.logos`; nothing else is copied, so the
# copy holds exactly the sources the fixture declares.
materialize() {
    local dir at name
    dir="$(dirname "$1")"
    at="$OUT/parse/${dir#tests/parse/}"
    rm -rf "$at"
    mkdir -p "$at"
    for name in "$dir"/*.logos.txt; do
        cp "$name" "$at/"
    done
    for name in "$at"/*.logos.txt; do
        mv "$name" "${name%.txt}"
    done
    printf '%s/%s.logos' "$at" "$(basename "$1")"
}

RDIFTS=0
for expect in "${EXPECTS[@]}"; do
    fixture="${expect%.expect}.logos"
    want="$(tr -d '[:space:]' < "$expect")"
    if [[ ! -f "$fixture" && -f "${fixture}.txt" ]]; then
        fixture="$(materialize "${expect%.expect}")"
    fi
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

# Phase three: every checker-owned fixture must make `gen2 check` print exactly
# the line its sidecar demands. A fixture the pass accepts, one with another
# line, and one without a sidecar are each one difference.
if [[ ! -f "$CHECK_LIST" ]]; then
    printf 'check: missing list: %s\n' "$CHECK_LIST" >&2
    exit 2
fi
mapfile -t CHECKED < <(grep -v '^[[:space:]]*$' "$CHECK_LIST")
CHECK_COUNT=${#CHECKED[@]}
if (( CHECK_COUNT < CHECK_FLOOR )); then
    printf 'check: list names %d fixtures, below the floor of %d\n' \
        "$CHECK_COUNT" "$CHECK_FLOOR" >&2
    exit 2
fi

CDIFFS=0
for fixture in "${CHECKED[@]}"; do
    sidecar="${fixture%.logos}.check"
    if [[ ! -f "$fixture" ]]; then
        printf 'check: %s: missing fixture\n' "$fixture"
        CDIFFS=$((CDIFFS + 1))
        continue
    fi
    if [[ ! -f "$sidecar" ]]; then
        printf 'check: %s: missing %s\n' "$fixture" "${sidecar##*/}"
        CDIFFS=$((CDIFFS + 1))
        continue
    fi
    want="$(head -n 1 "$sidecar")"
    if "$BIN" check "$fixture" > "$STDOUT" 2> "$STDERR"; then
        printf 'check: %s: expected %s, gen2 check exited 0\n' "$fixture" "$want"
        CDIFFS=$((CDIFFS + 1))
        continue
    fi
    got="$(head -n 1 "$STDERR")"
    if [[ "$got" != "$want" ]]; then
        printf 'check: %s: expected %s, got %s\n' "$fixture" "$want" "$got"
        CDIFFS=$((CDIFFS + 1))
    fi
done

printf 'check: %d fixtures, %d differences\n' "$CHECK_COUNT" "$CDIFFS"
if (( DIFFS > 0 || RDIFTS > 0 || CDIFFS > 0 )); then
    exit 1
fi
exit 0
