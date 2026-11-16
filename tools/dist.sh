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
# The documentation ships laid out exactly as the repository lays it out:
# `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and `LICENSE` at
# the prefix root with `docs/` beside them, so a relative link in a shipped page
# means in the package what it meant in the checkout. The README points at
# `docs/00-index.md`, `docs/reference/cli.md` and `AGENTS.md` by those paths;
# mirroring the tree keeps all of them, and keeps the pages honest offline,
# where rewriting them to github.com URLs would not. `INSTALL.md` is the same
# root-level spelling of `docs/install.md`. `tools/check_doc_links.sh` then
# proves the staged tree has no relative link the package cannot answer, so a
# page that points outside the artifact fails the build here and not on a
# consumer's first read.
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
mkdir -p "$STAGE/bin" "$STAGE/logos/runtime" "$STAGE/src/std" ||
    { echo "dist: could not create the staging tree" >&2; exit 2; }

install -m 755 "$BIN" "$STAGE/bin/logosc"
install -m 644 logos/runtime/rt.c logos/runtime/rt.h "$STAGE/logos/runtime/"
for module in io map str; do
    install -m 644 "src/std/$module.logos" "$STAGE/src/std/$module.logos" ||
        { echo "dist: missing src/std/$module.logos" >&2; exit 2; }
done

# The pages go in at the paths they link to each other by. The file list is the
# index's, not a `cp -R` of the working tree, so an untracked file cannot make
# one build differ from the next.
install -m 644 LICENSE README.md CHANGELOG.md AGENTS.md CONTRIBUTING.md "$STAGE/" ||
    { echo "dist: could not install the root documentation" >&2; exit 2; }
while IFS= read -r -d '' page; do
    install -D -m 644 "$page" "$STAGE/$page" ||
        { echo "dist: could not install $page" >&2; exit 2; }
done < <(git ls-files -z docs)
install -m 644 docs/install.md "$STAGE/INSTALL.md"

if ! bash "$ROOT/tools/check_doc_links.sh" "$STAGE"; then
    echo "dist: a shipped page links to something the package does not contain" >&2
    exit 2
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
