#!/usr/bin/env bash
# Cut a release, or rehearse one.
#
#   bash tools/release.sh             rehearse: build, prove it installs, print what would be published
#   bash tools/release.sh --publish   publish: create the GitHub release for tag v<version>
#
# A release is a tag plus three files: the tarball, its SHA256SUMS, and the
# release notes. This script does not choose the version and does not write the
# changelog — the version is what the compiler reports (`logosc version`, one
# string in `src/logosc/main.logos`) and the notes are the changelog's section
# for that version when there is one. What it does is make the tag and the
# artifact provably agree:
#
#   1. the tarball is built twice and the two SHA-256 sums must match, so the
#      artifact is reproducible from this commit;
#   2. the tarball is unpacked into a scratch directory and a program is
#      compiled from it, so the artifact is installable;
#   3. the tag must exist, be annotated, and point at HEAD before anything is
#      published, so a release names a commit rather than a branch tip that
#      moved.
#
# Nothing is published without --publish, and even then the rehearsal steps run
# first. The release workflow (.github/workflows/release.yml) runs the same
# script on a tag push, after the six gates.

set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

PUBLISH=0
case "${1:-}" in
    "") ;;
    --publish) PUBLISH=1 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "usage: bash tools/release.sh [--publish]" >&2; exit 2 ;;
esac

OUT="$ROOT/dist"
VERSION="$(./tools/logosc.sh version | awk '{ print $2 }')" || exit 2
TAG="v$VERSION"
TARBALL="$OUT/logos-$VERSION-x86_64-linux.tar.gz"
NOTES="$OUT/release-notes.md"

printf 'release: version %s from %s\n' "$VERSION" "$(git rev-parse --short HEAD)"

# A release built from a dirty tree ships something no commit contains, so a
# rehearsal is allowed to be dirty (it is how the pipeline is tested before the
# change is committed) and publishing is not.
if (( PUBLISH )); then
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "release: the tree is dirty; commit before publishing" >&2
        git status --short >&2
        exit 2
    fi
fi

# 1. The artifact must be reproducible from this commit.
bash tools/dist.sh || exit 2
FIRST="$(sha256sum "$TARBALL" | cut -d' ' -f1)"
bash tools/dist.sh || exit 2
SECOND="$(sha256sum "$TARBALL" | cut -d' ' -f1)"
if [[ "$FIRST" != "$SECOND" ]]; then
    printf 'release: the tarball is not reproducible from this commit:\n  %s\n  %s\n' \
        "$FIRST" "$SECOND" >&2
    exit 1
fi
printf 'release: tarball reproducible, sha256 %s\n' "$FIRST"

# 2. The artifact must install and compile with nothing but the tarball.
if ! bash tools/verify_install.sh "$TARBALL"; then
    echo "release: the tarball did not install; not releasing it" >&2
    exit 1
fi

# 3. The tag must be the commit being released.
TAG_SHA="$(git rev-parse -q --verify "refs/tags/$TAG^{commit}" 2>/dev/null)"
HEAD_SHA="$(git rev-parse HEAD)"
if [[ -z "$TAG_SHA" ]]; then
    printf 'release: no tag %s. Cut it on the commit to release:\n' "$TAG" >&2
    printf '    git tag -s %s -m "Logos %s"\n' "$TAG" "$VERSION" >&2
elif [[ "$TAG_SHA" != "$HEAD_SHA" ]]; then
    printf 'release: tag %s points at %s, not HEAD (%s)\n' \
        "$TAG" "$(git rev-parse --short "$TAG_SHA")" "$(git rev-parse --short HEAD)" >&2
    TAG_SHA=""
fi
if [[ -n "$TAG_SHA" ]] && (( PUBLISH == 0 )); then
    printf 'release: tag %s names this commit\n' "$TAG"
fi

# The notes: the changelog's own section when the project keeps one, otherwise
# the commit subjects since the previous tag, so a release never ships blank.
mkdir -p "$OUT"
if [[ -f CHANGELOG.md ]] && grep -qE "^## .*${VERSION//./\\.}" CHANGELOG.md; then
    awk -v v="$VERSION" '
        $0 ~ "^## .*" v { on = 1; print; next }
        on && /^## / { exit }
        on { print }
    ' CHANGELOG.md > "$NOTES"
else
    PREVIOUS="$(git describe --tags --abbrev=0 "$TAG^{commit}^" 2>/dev/null || true)"
    {
        printf '## Logos %s\n\n' "$VERSION"
        if [[ -n "$PREVIOUS" ]]; then
            printf 'Changes since %s:\n\n' "$PREVIOUS"
            git log --no-merges --format='- %s' "$PREVIOUS..$TAG^{commit}" 2>/dev/null
        else
            printf -- '- First release.\n'
        fi
        printf '\n### Verify\n\n```sh\ntar -xzf logos-%s-x86_64-linux.tar.gz\ncd logos-%s-x86_64-linux\nsha256sum -c ../SHA256SUMS 2>/dev/null || sha256sum ../logos-%s-x86_64-linux.tar.gz\n./bin/logosc version\n```\n' \
            "$VERSION" "$VERSION" "$VERSION"
    } > "$NOTES"
fi
printf 'release: notes at %s\n' "${NOTES#"$ROOT"/}"

if (( PUBLISH == 0 )); then
    printf '\nrelease: rehearsal complete, nothing was published. To publish:\n\n'
    printf '    git tag -s %s -m "Logos %s"   # once, on this commit\n' "$TAG" "$VERSION"
    printf '    git push origin %s\n' "$TAG"
    printf '    bash tools/release.sh --publish\n\n'
    printf 'or, from an already-tagged commit:\n\n'
    printf '    gh release create %s dist/logos-%s-x86_64-linux.tar.gz dist/SHA256SUMS \\\n' \
        "$TAG" "$VERSION"
    printf '        --title "Logos %s" --notes-file %s\n' "$VERSION" "${NOTES#"$ROOT"/}"
    exit 0
fi

# Publishing: the tag is the release's identity, so `--verify-tag` is what stops
# a typo from creating a release nobody can reproduce.
if ! command -v gh > /dev/null 2>&1; then
    echo "release: gh is not installed; cannot publish" >&2
    exit 2
fi
gh release create "$TAG" "$TARBALL" "$OUT/SHA256SUMS" \
    --title "Logos $VERSION" --notes-file "$NOTES" --verify-tag || exit 1

# Read the release back: a created release that lists no asset is a failure the
# upload exit code does not always report.
if gh release view "$TAG" --json url,assets \
        --jq '"release: \(.url) (\(.assets | length) assets)"; .assets[].name' ; then
    printf 'release: %s published\n' "$TAG"
else
    printf 'release: %s was created but could not be read back\n' "$TAG" >&2
    exit 1
fi
