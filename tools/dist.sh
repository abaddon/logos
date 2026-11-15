#!/usr/bin/env bash
# Assemble the installable tarball for one version.
#
# The layout is the contract, not a convention: the compiler resolves its
# runtime at `logos/runtime/rt.c` and its standard library at
# `src/std/<name>.logos` relative to the *working directory*, so the tarball
# ships those two paths spelled exactly as the repository spells them and
# `docs/install.md` says to run the compiler from the unpacked directory.
# Resolving them relative to the executable is the D2/D3 compiler change; until
# it lands, mirroring the repository's paths is what makes an install work
# outside a checkout. When that change lands, this layout stays valid: it is the
# same two paths, only found by a different rule.
#
# The tarball is deterministic. File order, ownership and mtime are fixed, the
# commit date is the timestamp (never the wall clock), gzip compression is
# filename- and time-free (`-n`), and the recorded toolchain — not the host's —
# is what goes into VERSION. Two runs on the same commit therefore produce the
# same bytes and the same SHA-256, which is the property `tools/release.sh`
# checks by building it twice and the release workflow checks on a second
# runner.
#
# Outputs:
#   dist/logos-<version>-x86_64-linux.tar.gz
#   dist/SHA256SUMS
#
# Usage: bash tools/dist.sh [VERSION=x.y.z]

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

OUT="$ROOT/dist"
VERSION="${VERSION:-}"
if [[ -z "$VERSION" ]]; then
    VERSION="$(./tools/logosc.sh version | awk '{ print $2 }')" || exit 2
fi
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'dist: the compiler reported no x.y.z version (%s)\n' "${VERSION:-nothing}" >&2
    exit 2
fi

# The binary that ships is the one the gates test: `tools/logosc.sh` rebuilds it
# from src/ when the source is newer, and the self-hosting gate proves that
# binary and the committed stage-0 are the same compiler.
BIN="$ROOT/build/logosc"
if [[ ! -x "$BIN" ]]; then
    echo "dist: no compiler at build/logosc; run ./tools/logosc.sh version first" >&2
    exit 2
fi

NAME="logos-$VERSION-x86_64-linux"
STAGE="$OUT/$NAME"
EPOCH="$(git log -1 --format=%ct 2>/dev/null || echo 0)"

rm -rf "$STAGE"
mkdir -p "$STAGE/bin" "$STAGE/logos/runtime" "$STAGE/src/std" "$STAGE/share/doc" ||
    { echo "dist: could not create the staging tree" >&2; exit 2; }

install -m 755 "$BIN" "$STAGE/bin/logosc"
install -m 644 logos/runtime/rt.c logos/runtime/rt.h "$STAGE/logos/runtime/"
for module in io map str; do
    install -m 644 "src/std/$module.logos" "$STAGE/src/std/$module.logos" ||
        { echo "dist: missing src/std/$module.logos" >&2; exit 2; }
done
install -m 644 LICENSE "$STAGE/share/doc/LICENSE"
install -m 644 README.md "$STAGE/share/doc/README.md"
install -m 644 docs/LOGOS.md "$STAGE/share/doc/LOGOS.md"
install -m 644 docs/install.md "$STAGE/INSTALL.md"
if [[ -f CHANGELOG.md ]]; then
    install -m 644 CHANGELOG.md "$STAGE/share/doc/CHANGELOG.md"
fi

# Provenance the consumer can read without git, and the release workflow can
# compare: the commit, and the toolchain the stage-0 was built with. Recorded
# values, not the host's, so the file does not make the tarball host-dependent.
{
    printf 'version: %s\n' "$VERSION"
    printf 'commit: %s\n' "$(git rev-parse HEAD 2>/dev/null || echo unknown)"
    printf 'clang: %s\n' "$(sed -n 's/^clang: //p' bootstrap/toolchain.txt)"
    printf 'ld: %s\n' "$(sed -n 's/^ld: //p' bootstrap/toolchain.txt)"
} > "$STAGE/VERSION"

TARBALL="$OUT/$NAME.tar.gz"
( cd "$OUT" && tar --sort=name --owner=0 --group=0 --numeric-owner \
      --mtime="@$EPOCH" --format=gnu -cf - "$NAME" | gzip -9 -n ) > "$TARBALL" ||
    { echo "dist: could not write $TARBALL" >&2; exit 2; }

( cd "$OUT" && sha256sum "$NAME.tar.gz" > SHA256SUMS ) ||
    { echo "dist: could not write $OUT/SHA256SUMS" >&2; exit 2; }

printf 'dist: %s (%s bytes)\n' "${TARBALL#"$ROOT"/}" "$(stat -c %s "$TARBALL")"
printf 'dist: %s\n' "$(cat "$OUT/SHA256SUMS")"
