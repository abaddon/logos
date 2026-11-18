#!/usr/bin/env bash
# Prove the tarball installs and compiles, from the tarball alone.
#
# This is the acceptance test for shipping: it unpacks the artifact into a
# scratch directory, and from the unpacked directory — with no repository, no
# `src/`, no `bootstrap/` and no git — compiles and runs a program, imports the
# standard library, refuses a program that has a type error with a diagnostic
# that carries a code, reports the version the tarball claims, and checks that
# every relative link in the shipped pages resolves inside the package. A tarball
# missing `logos/runtime/rt.c` or `src/std/str.logos`, holding a binary built
# from other sources, or carrying a `README.md` that points at a `docs/` it does
# not contain, fails here rather than on a consumer's first read.
#
# These are the things a consumer does in the first five minutes. Everything runs
# with the working directory inside the unpacked prefix, which is the layout the
# compiler resolves its runtime and standard library out of. The last check is
# the one that makes the others mean "installable": it builds the same
# standard-library program again from a directory that is *not* the prefix, with
# `LOGOS_ROOT` and `LOGOS_PATH` unset, because the compiler must decide which
# runtime and library it uses from its own path. Running from inside the prefix
# used to be the whole contract, and a tarball can satisfy that and still be
# unusable.
#
# Usage: bash tools/verify_install.sh dist/logos-<version>-x86_64-linux.tar.gz

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

TARBALL="${1:-}"
if [[ ! -f "$TARBALL" ]]; then
    echo "usage: bash tools/verify_install.sh dist/logos-<version>-x86_64-linux.tar.gz" >&2
    exit 2
fi
TARBALL="$(cd "$(dirname "$TARBALL")" && pwd)/$(basename "$TARBALL")"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/logos-install.XXXXXX")" || exit 2
trap 'rm -rf "$WORK"' EXIT

tar -xzf "$TARBALL" -C "$WORK" ||
    { printf 'verify: could not unpack %s\n' "${TARBALL#"$ROOT"/}" >&2; exit 2; }
mapfile -t DIRS < <(find "$WORK" -mindepth 1 -maxdepth 1 -type d)
if (( ${#DIRS[@]} != 1 )); then
    printf 'verify: the tarball must hold exactly one top-level directory, found %d\n' \
        "${#DIRS[@]}" >&2
    exit 2
fi
PREFIX="${DIRS[0]}"
cd "$PREFIX" || exit 2

FAILURES=0
CHECKS=0

pass() {
    CHECKS=$((CHECKS + 1))
    printf 'PASS %s\n' "$1"
}

fail() {
    CHECKS=$((CHECKS + 1))
    FAILURES=$((FAILURES + 1))
    printf 'FAIL %s: %s\n' "$1" "$2"
}

# The prefix must be the whole compiler: a binary, the runtime source clang
# links, the standard library the loader reads, and the documents it ships.
for path in bin/logosc logos/runtime/rt.c logos/runtime/rt.h \
            src/std/io.logos src/std/map.logos src/std/str.logos VERSION INSTALL.md \
            README.md CHANGELOG.md LICENSE AGENTS.md llms.txt docs/00-index.md docs/LOGOS.md \
            examples/agent-gate/README.md; do
    if [[ ! -e "$path" ]]; then
        fail "layout" "$path is missing from the tarball"
    fi
done
if (( FAILURES == 0 )); then
    pass "layout: the compiler, the runtime, the standard library and VERSION"
fi

# The documents are read offline, so every relative link in them must resolve
# inside the package: `README.md` pointing at a `docs/` that did not ship is a
# dead end the reader cannot fix.
if bash "$ROOT/tools/check_doc_links.sh" "$PREFIX" > link-check.log 2>&1; then
    pass "docs: $(tail -n 1 link-check.log)"
else
    fail "docs" "$(head -n 1 link-check.log)"
fi

# The version the tarball claims is the version the binary reports, so a
# consumer and a release page cannot disagree about what they downloaded.
CLAIMED="$(sed -n 's/^version: //p' VERSION)"
REPORTED="$(bin/logosc version 2>&1 | awk '{ print $2 }')"
if [[ -n "$CLAIMED" && "$CLAIMED" == "$REPORTED" ]]; then
    pass "version: $REPORTED"
else
    fail "version" "VERSION says '${CLAIMED:-nothing}', the binary says '${REPORTED:-nothing}'"
fi

# One program, no imports: the emitter, clang and the runtime, end to end.
printf '(mod hello)\n\n(fn main :void ()\n  (println "logos ok"))\n' > hello.logos
if bin/logosc build hello.logos -o hello 2> build.err && [[ "$(./hello)" == "logos ok" ]]; then
    pass "build: hello world compiles and prints"
else
    fail "build" "hello world did not build or print: $(head -n 1 build.err)"
fi

# One program that imports the standard library: the loader finds
# src/std/str.logos from the unpacked directory.
printf '(mod hello-std)\n\n(use str)\n\n(fn main :void ()\n  (if (string-starts-with "logos" "lo")\n    (println "std ok")\n    (println "std broken")))\n' > hello-std.logos
if bin/logosc build hello-std.logos -o hello-std 2> build.err && [[ "$(./hello-std)" == "std ok" ]]; then
    pass "stdlib: (use str) resolves and links"
else
    fail "stdlib" "a standard-library import did not build or print: $(head -n 1 build.err)"
fi

# A program with a type error is refused with a diagnostic that carries a code,
# which is the shape every tool downstream reads.
printf '(mod bad)\n\n(fn main :void ()\n  (let x :i64 "s")\n  (println x))\n' > bad.logos
if bin/logosc build bad.logos -o bad > /dev/null 2> bad.err; then
    fail "diagnostics" "a program with a type error was accepted"
elif head -n 1 bad.err | grep -Eq 'E[0-9]{4}'; then
    pass "diagnostics: $(head -n 1 bad.err)"
else
    fail "diagnostics" "no diagnostic code in: $(head -n 1 bad.err)"
fi

# The compiler must work from anywhere: same program, same binary, run from a
# directory that is not the prefix and with neither override set. This is D2/D3
# of the v1 readiness audit, and it is the difference between "unpacks" and
# "installs".
if ( cd "$WORK" && env -u LOGOS_ROOT -u LOGOS_PATH "$PREFIX/bin/logosc" \
        build "$PREFIX/hello-std.logos" -o "$WORK/hello-std" 2> "$WORK/outside.err" ) \
        && [[ "$("$WORK/hello-std")" == "std ok" ]]; then
    pass "elsewhere: builds from a directory that is not the prefix"
else
    fail "elsewhere" "a build from outside the prefix failed: $(head -n 1 "$WORK/outside.err")"
fi

if (( FAILURES > 0 )); then
    printf '\n%d/%d install checks passed, %d failed\n' \
        "$((CHECKS - FAILURES))" "$CHECKS" "$FAILURES"
    exit 1
fi
printf '\n%d/%d install checks passed\n' "$CHECKS" "$CHECKS"
