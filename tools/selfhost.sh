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
# A second phase compares the lowering. tools/selfhost-ir.txt lists the files
# whose LLVM IR the port already reproduces: each is lowered by `gen2 build`
# and by Python's `logos build`, and the two `.ll` files must be equal byte for
# byte. The list's fixture entries are exactly the fixtures under
# src/logosc/fixtures/ir-lower — the forms B2 and B3 do not lower yet are
# excluded by name in its header — and the script refuses a list whose fixture
# entries and that directory name different sets, so a fixture cannot be added,
# deleted or swapped without the list moving in the same commit. The list also
# names files outside the directory (four example programs today): those
# are claims of their own, built and counted like any other entry, and they sit
# outside the set-equality check because the directory does not own them.
# IR_FLOOR is the same kind of floor over the whole list: a pruned list fails
# rather than passing over fewer files. The floor counts distinct paths, not
# lines: a path named twice is one file, and comparing it twice is not a bigger
# corpus. IR_FIXTURE_FLOOR is a floor on the fixture entries alone: set equality
# keeps the list and the directory moving together, but it cannot stop both from
# shrinking by one while an outside path — which the directory does not own and
# the total floor does count — takes the empty place. The two floors are separate
# because those are two different claims.
#
# That phase judges the lowering's refusals too. Every fixture under
# src/logosc/fixtures/ir-refuse pairs a `.logos` with a `.refuse` sidecar
# holding the exact stderr line `gen2 build` must print: a shape with no finite
# layout is a diagnostic with a code and a node path, never a crash, and a
# signal or a silent exit is a difference. REFUSE_FLOOR keeps the directory
# from being emptied.
#
# A third phase judges the resolver-owned negative corpus. Every
# tests/parse/**/*.expect names a fixture that must make `gen2 resolve` fail
# with that exact code; the fixtures are the repository's statement of the
# resolver's negative behaviour, and this gate is what keeps the Logos port
# agreeing with them. A fixture whose source must fail to lex or parse keeps its
# sources as `*.logos.txt` and is judged on a copy under build/, because no
# tracked `*.logos` file may be malformed; see the phase below.
# RESOLVE_FLOOR is the same kind of floor: pruning fixtures
# below it fails rather than passing over a smaller set.
#
# A fourth phase judges the checker-owned negative corpus. tools/selfhost-check.txt
# lists one fixture per line — only the cases the checker can decide: the
# declaration rules and the scalar body rules — and
# each fixture's .check names the whole line `gen2 check` must print, path, code and
# message, as the reference implementation prints it. A wrong path or a reworded
# message is a difference, not just a wrong code. tools/check_parity.py writes the
# sidecars from Python, so the expectation cannot drift from the oracle. CHECK_FLOOR
# is the same kind of floor: a pruned list fails rather than passing over fewer
# fixtures.
#
# A fifth phase judges the unit: the compiler's whole front end at once.
# `gen2 build` and Python's `logos build` lower two units and the two `.ll`
# files must be equal byte for byte: the eleven-module closure both binaries
# are built from (fmt, lex and main), and the whole source set the gate builds
# gen2 from (every src/logosc module including the `*_test` helpers, plus the
# two standard modules). The second is the one a name-keyed function index
# fails: a call in `body-test` that shares a helper name with `check-test`
# binds to the wrong module's function even though every file formats
# canonically, so the unit is where that defect shows.
#
# A unit is one file, so the phase counts units rather than a corpus; what it
# floors is that each thing compared is the unit it claims — the closure names
# three roots (UNIT_FLOOR) and the whole set names at least WHOLE_FLOOR, every
# root is on disk, and each side's output is at least UNIT_BYTES_FLOOR bytes,
# so two empty or truncated files cannot agree their way to a pass. Both sides
# remove their target before building, as phase two does, so a stale file
# cannot be compared against.
#
# Output: one line per fmt, ir, resolve, check or unit failure, then
# `selfhost: N files, M differences`, `ir: N files, M differences`,
# `resolve: N fixtures, M differences`, `check: N fixtures, M differences` and
# `unit: N files, M differences`.
# Exit 0 when every phase is clean, 1 when any file or fixture differs, 2 when
# the gate could not run at all (missing manifest or list, count mismatch, no
# binary).

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
# variant with E0600, and the four ref escapes the C2 re-review found), and the
# four C3 fix-round shapes that need the handled bit to survive a move or a
# capture (a `set` of a moved result, a copy of an owned result, a capturing
# closure handed to a callee, and a generic call whose result is never handled),
# and the C4 concurrency surface: threads with their argument, return and
# generic-target rules, channels with their element, capacity and `shared`
# marker rules, mutexes and atomics, closures with their captures and their
# result obligations, and the five ref escapes those forms used to hide (a
# capture, `send`, `spawn` and a function value built from a closure), and the
# C4 fix round's annotated-`let`/`set` capture flag, its payload constructors
# and the closure `let`-shadowing order, and the two fixtures the PR C whole-branch
# review found unlisted: `sibling-set` (E0300 behind a deferred `deref`) and
# `ref-not-mutable` (E0304 at a ref argument).
# One hundred and twenty-two today; a pruned list is a failure, not a smaller pass.
CHECK_LIST="$ROOT/tools/selfhost-check.txt"
CHECK_FLOOR=122

# The lowering parity list: the files whose IR the port already reproduces.
# Fifty today — the forty-six fixtures under src/logosc/fixtures/ir-lower,
# in the order B2, its fix round, B3 and B4 proved them, plus the four example
# programs. A pruned list is a failure, not a smaller pass; the fixture entries
# must equal the fixture directory exactly (see the check below), while a path
# outside it is a claim of its own and is only counted.
IR_LIST="$ROOT/tools/selfhost-ir.txt"
IR_FLOOR=50
# The fixture entries alone, so an outside path cannot pad the total while a
# fixture leaves the directory. Forty-six today; lowering this number is a
# deliberate act, not a side effect of a pruned fixture set.
IR_FIXTURE_FLOOR=46
# The lowering's refusal fixtures: each pairs a `.logos` with a `.refuse`
# sidecar naming the exact diagnostic line `gen2 build` must print. One today;
# emptying the directory is a failure, not a smaller pass.
REFUSE_FLOOR=1

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

# Phase two: every listed file's IR from `gen2 build` must equal Python's.
# Both drivers keep the IR at build/<stem>.ll and name the binary with `-o`
# (`driver.py:164-171`), so each side is asked for a binary and the text the
# comparison reads is the `.ll` beside the sources. gen2's `.ll` is moved under
# build/selfhost/ir/ before Python's build takes the same path, and both are
# removed before the run, so a file that was not just written cannot be read as
# agreement. A build that exits 0 and writes no `.ll` is a difference on both
# sides.
if [[ ! -f "$IR_LIST" ]]; then
    printf 'ir: missing list: %s\n' "${IR_LIST#"$ROOT"/}" >&2
    exit 2
fi
mapfile -t IR_FILES < <(grep -v '^[[:space:]]*#' "$IR_LIST" | grep -v '^[[:space:]]*$')
IR_COUNT=${#IR_FILES[@]}
if (( IR_COUNT < IR_FLOOR )); then
    printf 'ir: list names %d files, below the floor of %d\n' "$IR_COUNT" "$IR_FLOOR" >&2
    exit 2
fi
# Counted, not assumed: seven lines naming one path are one file, and comparing
# it seven times would report a corpus the run never read. Two paths that share
# a stem are refused for the same reason — both sides write `<stem>.ll`, so one
# entry would overwrite the other and be compared against it.
IR_DISTINCT=$(printf '%s\n' "${IR_FILES[@]}" | sort -u | wc -l)
if (( IR_DISTINCT != IR_COUNT )); then
    printf 'ir: list names %d lines but %d distinct files; a repeated path is not a bigger corpus\n' \
        "$IR_COUNT" "$IR_DISTINCT" >&2
    exit 2
fi
IR_STEMS=$(printf '%s\n' "${IR_FILES[@]}" | while read -r p; do basename "$p" .logos; done | sort -u | wc -l)
if (( IR_STEMS != IR_COUNT )); then
    printf 'ir: list names %d files but %d stems; two entries share a .ll and would be compared against each other\n' \
        "$IR_COUNT" "$IR_STEMS" >&2
    exit 2
fi
# The list's fixture entries and the directory must name the same set. Counting
# alone catches a fixture deleted and delisted (one fewer) but not a compensating
# swap that leaves the number where it was, and a list that names a file the
# directory does not hold claims a parity nothing measured. Set equality makes
# any addition or deletion move both sides in the same commit. The check is over
# the listed paths inside the directory only: an entry outside it (an example
# program) is a claim the directory does not own, so it neither hides a missing
# fixture nor has to exist on disk there.
#
# Set equality still lets the *directory and the list shrink together* while an
# outside path takes the freed slot in the total, which IR_FLOOR counts. So the
# fixture entries carry a floor of their own: a fixture cannot leave the corpus
# even when something outside the directory is added in the same commit.
shopt -s nullglob
IR_DISK=(src/logosc/fixtures/ir-lower/*.logos)
shopt -u nullglob
if (( ${#IR_DISK[@]} == 0 )); then
    printf 'ir: %s holds no fixtures; the list cannot be measured against an empty directory\n' \
        "src/logosc/fixtures/ir-lower" >&2
    exit 2
fi
if (( ${#IR_DISK[@]} < IR_FIXTURE_FLOOR )); then
    printf 'ir: %s holds %d fixtures, below the fixture floor of %d; an outside path cannot stand in for one\n' \
        "src/logosc/fixtures/ir-lower" "${#IR_DISK[@]}" "$IR_FIXTURE_FLOOR" >&2
    exit 2
fi
IR_LISTED_FIXTURES=$(printf '%s\n' "${IR_FILES[@]}" | grep '^src/logosc/fixtures/ir-lower/' | sort)
if [[ -z "$IR_LISTED_FIXTURES" ]]; then
    printf 'ir: tools/selfhost-ir.txt names no fixture under src/logosc/fixtures/ir-lower\n' >&2
    exit 2
fi
IR_ONDISK=$(printf '%s\n' "${IR_DISK[@]}" | sort)
if [[ "$IR_LISTED_FIXTURES" != "$IR_ONDISK" ]]; then
    printf 'ir: the fixtures in tools/selfhost-ir.txt and src/logosc/fixtures/ir-lower name different sets:\n' >&2
    comm -3 <(printf '%s\n' "$IR_LISTED_FIXTURES") <(printf '%s\n' "$IR_ONDISK") |
        awk '{ if (substr($0, 1, 1) == "\t") print "    only on disk: " substr($0, 2);
               else print "    only in the list: " $0 }' >&2
    exit 2
fi
mkdir -p "$OUT/ir"

IDIFFS=0
for path in "${IR_FILES[@]}"; do
    stem="$(basename "$path" .logos)"
    mine="$OUT/ir/$stem.ll"
    if [[ ! -f "$path" ]]; then
        printf 'ir: %s: missing file\n' "$path"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    rm -f "$mine" "build/$stem.ll"
    if ! "$BIN" build "$path" -o "$OUT/ir/$stem.bin" > "$STDOUT" 2> "$STDERR"; then
        printf 'ir: %s: gen2 build failed: %s\n' "$path" "$(head -n 1 "$STDERR")"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    if [[ ! -f "build/$stem.ll" ]]; then
        printf 'ir: %s: gen2 wrote no build/%s.ll\n' "$path" "$stem"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    mv "build/$stem.ll" "$mine"
    if ! python3 -m logos build "$path" -o "$OUT/ir/$stem.bin" > "$OUT/ir/$stem.log" 2>&1; then
        printf 'ir: %s: python build failed (log: %s)\n' "$path" "${OUT#"$ROOT"/}/ir/$stem.log"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    if [[ ! -f "build/$stem.ll" ]]; then
        printf 'ir: %s: python wrote no build/%s.ll\n' "$path" "$stem"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    if ! cmp -s "$mine" "build/$stem.ll"; then
        printf 'ir: %s: output differs\n' "$path"
        IDIFFS=$((IDIFFS + 1))
    fi
done

printf 'ir: %d files, %d differences\n' "$IR_COUNT" "$IDIFFS"

# Still phase two, the other half of the lowering's contract: a shape the port
# cannot spell must *refuse*, with a code and a node path, and never crash. A
# `gen2 build` that exits on a signal, exits 0, or prints another line is a
# difference like any other and counts in the same total. Each fixture under
# src/logosc/fixtures/ir-refuse pairs a `.logos` with a `.refuse` sidecar
# holding the exact first line of stderr, the way `.check` pairs with the
# checker's list. The directory is the list; REFUSE_FLOOR keeps it from being
# emptied, and the count moves with every add or delete.
shopt -s nullglob
REFUSED=(src/logosc/fixtures/ir-refuse/*.logos)
shopt -u nullglob
REFUSE_COUNT=${#REFUSED[@]}
if (( REFUSE_COUNT < REFUSE_FLOOR )); then
    printf 'refuse: found %d fixtures, below the floor of %d\n' "$REFUSE_COUNT" "$REFUSE_FLOOR" >&2
    exit 2
fi
for path in "${REFUSED[@]}"; do
    sidecar="${path%.logos}.refuse"
    if [[ ! -f "$sidecar" ]]; then
        printf 'refuse: %s: missing %s\n' "$path" "${sidecar##*/}"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    want="$(head -n 1 "$sidecar")"
    "$BIN" build "$path" -o "$OUT/ir/$(basename "$path" .logos).refused" \
        > "$STDOUT" 2> "$STDERR"
    status=$?
    if (( status == 0 )); then
        printf 'refuse: %s: expected %s, gen2 build exited 0\n' "$path" "$want"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    if (( status >= 128 )); then
        printf 'refuse: %s: expected %s, gen2 build died on signal %d\n' \
            "$path" "$want" "$((status - 128))"
        IDIFFS=$((IDIFFS + 1))
        continue
    fi
    got="$(head -n 1 "$STDERR")"
    if [[ "$got" != "$want" ]]; then
        printf 'refuse: %s: expected %s, got %s\n' "$path" "$want" "${got:-nothing}"
        IDIFFS=$((IDIFFS + 1))
    fi
done

# Phase three: every resolver-owned negative fixture must make `gen2 resolve`
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

# Phase four: every checker-owned fixture must make `gen2 check` print exactly
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

# Phase five: the unit. The phases above judge files one at a time; this one
# judges the compiler's whole front end at once, twice. `gen2 build` and
# Python's `logos build` lower the eleven-module closure the compiler is built
# from (fmt, lex and main) and the whole source set the gate builds gen2 from
# (every src/logosc module, the shared test helpers included, plus the two
# standard modules), and each pair of `.ll` files must be equal byte for byte.
# It is the fixed point's first half: the port's own lowering reproduces the
# oracle on the sources both are built from.
#
# The whole set is not redundant with the closure: the closure's modules do not
# share helper names, while the test modules do (`body-test` and `check-test`
# each define `show-check-fail`, `dump-tree` and so on). A function index keyed
# by name alone binds those calls to whichever module was scanned last, which
# is invisible to the fmt phase and to the closure, and which this comparison
# catches.
#
# A unit is one file, so there is no corpus to count and no count to floor:
# each comparison asserts equality. What a floor can still hold is that the
# thing compared is the unit it claims — the closure names three modules
# (UNIT_FLOOR), the whole set names at least WHOLE_FLOOR, each root is on disk,
# and each side's output is at least UNIT_BYTES_FLOOR bytes, so two empty or
# truncated files cannot agree their way to a pass. Both sides remove their
# target before building, as phase two does, so a stale file cannot be
# compared against.
UNIT_ROOTS=(src/logosc/fmt.logos src/logosc/lex.logos src/logosc/main.logos)
UNIT_FLOOR=3
# Every module under src/logosc plus map and str: twenty today, and a pruned
# tree must fail rather than compare a smaller unit.
WHOLE_SOURCES=("${SOURCES[@]}")
WHOLE_FLOOR=20
# The closure is 15.5 MB of IR and the whole set 17.5 MB today. Below a
# megabyte neither is the unit it claims, whatever the two sides agree on.
UNIT_BYTES_FLOOR=1000000

if (( ${#UNIT_ROOTS[@]} < UNIT_FLOOR )); then
    printf 'unit: %d roots, below the floor of %d\n' "${#UNIT_ROOTS[@]}" "$UNIT_FLOOR" >&2
    exit 2
fi
if (( ${#WHOLE_SOURCES[@]} < WHOLE_FLOOR )); then
    printf 'unit: whole source set names %d files, below the floor of %d\n' \
        "${#WHOLE_SOURCES[@]}" "$WHOLE_FLOOR" >&2
    exit 2
fi
for path in "${UNIT_ROOTS[@]}" "${WHOLE_SOURCES[@]}"; do
    if [[ ! -f "$path" ]]; then
        printf 'unit: %s: missing root\n' "$path" >&2
        exit 2
    fi
done

mkdir -p "$OUT/unit"
UDIFFS=0
UNIT_COUNT=0

# Compare one unit: gen2's IR for the roots against Python's. Both drivers
# spell the IR after the first root's stem (`driver.py:116-118`) and write it to
# `build/<first stem>.ll`; `-o` names each side's binary. gen2's text is moved
# out of that path before Python writes its own, and both sides remove their
# target first so a stale file cannot be read as agreement.
unit_compare() {
    local tag="$1"
    shift
    local mine="$OUT/unit/$tag.gen2.ll"
    local pyll="build/$(basename "$1" .logos).ll"
    UNIT_COUNT=$((UNIT_COUNT + 1))
    rm -f "$mine" "$pyll"
    if ! "$BIN" build "$@" -o "$OUT/unit/$tag.gen2.bin" > "$STDOUT" 2> "$STDERR"; then
        printf 'unit: %s: gen2 build failed: %s\n' "$tag" "$(head -n 1 "$STDERR")"
        UDIFFS=$((UDIFFS + 1))
        return
    fi
    if [[ ! -f "$pyll" ]]; then
        printf 'unit: %s: gen2 wrote no %s\n' "$tag" "$pyll"
        UDIFFS=$((UDIFFS + 1))
        return
    fi
    mv "$pyll" "$mine"
    if (( $(wc -c < "$mine") < UNIT_BYTES_FLOOR )); then
        printf 'unit: %s: gen2 wrote %d bytes, below the floor of %d\n' \
            "$tag" "$(wc -c < "$mine")" "$UNIT_BYTES_FLOOR"
        UDIFFS=$((UDIFFS + 1))
        return
    fi
    if ! python3 -m logos build "$@" -o "$OUT/unit/$tag.python" > "$OUT/unit/$tag.python.log" 2>&1; then
        printf 'unit: %s: python build failed (log: %s)\n' \
            "$tag" "${OUT#"$ROOT"/}/unit/$tag.python.log"
        UDIFFS=$((UDIFFS + 1))
        return
    fi
    if [[ ! -f "$pyll" ]]; then
        printf 'unit: %s: python wrote no %s\n' "$tag" "$pyll"
        UDIFFS=$((UDIFFS + 1))
        return
    fi
    if (( $(wc -c < "$pyll") < UNIT_BYTES_FLOOR )); then
        printf 'unit: %s: python wrote %d bytes, below the floor of %d\n' \
            "$tag" "$(wc -c < "$pyll")" "$UNIT_BYTES_FLOOR"
        UDIFFS=$((UDIFFS + 1))
        return
    fi
    if ! cmp -s "$mine" "$pyll"; then
        printf 'unit: %s: output differs\n' "$tag"
        UDIFFS=$((UDIFFS + 1))
    fi
}

unit_compare closure "${UNIT_ROOTS[@]}"
unit_compare whole "${WHOLE_SOURCES[@]}"

printf 'unit: %d files, %d differences\n' "$UNIT_COUNT" "$UDIFFS"
if (( DIFFS > 0 || IDIFFS > 0 || RDIFTS > 0 || CDIFFS > 0 || UDIFFS > 0 )); then
    exit 1
fi
exit 0
