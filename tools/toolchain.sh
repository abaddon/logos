#!/usr/bin/env bash
# The toolchain the byte-identity claim depends on.
#
# `bootstrap/logosc` is a claim about bytes: the compiler that binary builds
# from `src/` must equal it exactly. clang embeds its own version in every
# binary it produces and its codegen changes between releases, so the claim is
# only measurable with the clang recorded in `bootstrap/toolchain.txt`. Without
# this check a different toolchain reaches the self-hosting gate looking like a
# stale stage-0, and the advice it prints there — rebuild the bootstrap — does
# not help, because rebuilding on the wrong clang produces the same mismatch.
#
# Usage:
#   tools/toolchain.sh            print the toolchain in use and the recorded one
#   tools/toolchain.sh --check    exit 1 when they differ
#   tools/toolchain.sh --install  install the recorded toolchain (needs sudo)
#
# The pull request gate runs `--check` before the six gates. A host that cannot
# reproduce the stage-0 is told so by name, before an hour of gates fail at the
# last one.

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECORD="$ROOT/bootstrap/toolchain.txt"
CLANG_MAJOR=14

usage() {
    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

recorded() {
    sed -n "s/^$1: //p" "$RECORD" 2>/dev/null | head -n 1
}

actual() {
    case "$1" in
        clang)
            command -v clang > /dev/null 2>&1 || { printf 'clang: not found on PATH\n'; return 0; }
            clang --version 2>/dev/null | head -n 1
            ;;
        ld)
            command -v ld > /dev/null 2>&1 || { printf 'ld: not found on PATH\n'; return 0; }
            ld --version 2>/dev/null | head -n 1
            ;;
    esac
}

# One file names the pin so CI, a release job and a contributor's machine cannot
# disagree about which clang the stage-0 was built with.
install_toolchain() {
    if ! command -v sudo > /dev/null 2>&1; then
        echo "toolchain: --install needs sudo (run it as root, or install clang-$CLANG_MAJOR by hand)" >&2
        return 1
    fi
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends "clang-$CLANG_MAJOR" "lld-$CLANG_MAJOR"
    # The image ships several LLVM releases and `clang` may point at another
    # one; the compiler shells out to the bare name, so the link is the pin.
    sudo update-alternatives --install /usr/bin/clang clang "/usr/lib/llvm-$CLANG_MAJOR/bin/clang" 1400
    sudo update-alternatives --set clang "/usr/lib/llvm-$CLANG_MAJOR/bin/clang"
    actual clang
}

status=0
for tool in clang ld; do
    want="$(recorded "$tool")"
    got="$(actual "$tool")"
    if [[ -z "$want" ]]; then
        printf '%s: bootstrap/toolchain.txt records nothing for %s\n' "$tool" "$tool"
        status=1
    elif [[ "$got" == "$want" ]]; then
        printf '%s: %s\n' "$tool" "$got"
    else
        printf '%s: %s\n' "$tool" "$got"
        printf '%s: recorded %s\n' "$tool" "$want"
        status=1
    fi
done

if (( status == 0 )); then
    exit 0
fi

case "${1:-}" in
    --install)
        install_toolchain || exit 1
        exit 0
        ;;
    --check)
        printf '\ntoolchain: this host cannot reproduce bootstrap/logosc.\n' >&2
        printf 'The stage-0 byte-identity gate is only measurable with the recorded\n' >&2
        printf 'toolchain. Either install it:\n\n    bash tools/toolchain.sh --install\n\n' >&2
        printf 'or rebuild the bootstrap with the toolchain you have and record it in\n' >&2
        printf 'bootstrap/toolchain.txt in the same commit:\n\n' >&2
        printf '    ./tools/logosc.sh version\n    cp build/logosc bootstrap/logosc\n' >&2
        printf '    ( cd bootstrap && sha256sum logosc > logosc.sha256 )\n' >&2
        exit 1
        ;;
    "")
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
