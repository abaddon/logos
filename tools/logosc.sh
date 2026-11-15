#!/usr/bin/env bash
# The compiler the gates test: built from the current source, not shipped.
#
# `bootstrap/logosc` is a stage-0 binary — it exists only to build the compiler
# from `src/`, and it is replaced by its own output on every self-hosting run.
# A gate that ran the bootstrap directly would test last release's compiler and
# would keep passing after a change broke the source, so this wrapper rebuilds
# `build/logosc` whenever `src/` is newer than it, then runs that.
#
# Usage: tools/logosc.sh <verb> [args...]

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOT="$ROOT/bootstrap/logosc"
BIN="$ROOT/build/logosc"
SOURCES=("$ROOT"/src/logosc/*.logos "$ROOT"/src/std/map.logos "$ROOT"/src/std/str.logos)

cd "$ROOT" || exit 2

# The checksum is the only thing standing between a corrupted bootstrap and a
# silently different compiler, so it is checked before every build, not once.
if ! ( cd "$ROOT/bootstrap" && sha256sum -c --status logosc.sha256 ); then
    echo "logosc: bootstrap/logosc does not match bootstrap/logosc.sha256" >&2
    echo "logosc: rebuild it from a compiler whose output you trust, and record the new hash" >&2
    exit 2
fi

needs_build() {
    [[ ! -x "$BIN" ]] && return 0
    local newer
    newer=$(find "${SOURCES[@]}" -newer "$BIN" -print -quit 2>/dev/null)
    [[ -n "$newer" ]]
}

if needs_build; then
    mkdir -p "$ROOT/build"
    tmp="$BIN.$$"
    if ! "$BOOT" build "${SOURCES[@]}" -o "$tmp" > "$ROOT/build/logosc-build.log" 2>&1; then
        echo "logosc: the bootstrap could not build the compiler from src/:" >&2
        tail -n 20 "$ROOT/build/logosc-build.log" | sed 's/^/    /' >&2
        rm -f "$tmp"
        exit 2
    fi
    mv -f "$tmp" "$BIN"
fi

exec "$BIN" "$@"
