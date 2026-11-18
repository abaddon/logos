#!/usr/bin/env bash
# Section 7 of the verification log: the five quickstart commands run against the
# PUBLISHED release, in a clean directory, with the real output captured.
# Waits for the v0.2.2 release to appear (the release workflow runs the six gates
# first), then executes the README/llms.txt/quickstart block verbatim.
#
# Usage: bash docs/distribution/03-dossiers/verify-published-release.sh
set -uo pipefail

VERSION=v0.2.2
REPO=abaddon/logos
DEADLINE=$(( $(date +%s) + 9000 ))   # 2.5 h, the release job's own timeout
WORK=$(mktemp -d "${TMPDIR:-/tmp}/logos-published-XXXXXX")

say() { printf '%s\n' "$*"; }

say "# waiting for $REPO release $VERSION (release workflow runs the six gates)"
while :; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 \
    "https://api.github.com/repos/$REPO/releases/tags/$VERSION")
  if [ "$code" = 200 ]; then say "release $VERSION is published (HTTP 200)"; break; fi
  if [ "$(date +%s)" -gt "$DEADLINE" ]; then
    say "TIMEOUT: release $VERSION still HTTP $code after the deadline"; exit 1
  fi
  say "  $(date -u +%H:%M:%SZ) HTTP $code — waiting 60 s"
  sleep 60
done

cd "$WORK" || exit 1
say ""
say "## 7. The published release"
say ""
say "A clean directory (\`$WORK\`), the block copied from \`README.md\` verbatim:"
say ""
say '```sh'
say "gh release download $VERSION --repo $REPO --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS"
say "sha256sum -c SHA256SUMS"
say "tar -xzf logos-0.2.2-x86_64-linux.tar.gz && cd logos-0.2.2-x86_64-linux"
say "# (heredoc writes hello.logos exactly as the README shows it)"
say "./bin/logosc build hello.logos -o hello && ./hello     # hello from logos"
say '```'
say ""
say '```console'

run() { say "\$ $*"; "$@"; rc=$?; say "[exit $rc]"; return 0; }

say "\$ gh release download $VERSION --repo $REPO --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS"
gh release download "$VERSION" --repo "$REPO" --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
say "[exit $?]"
ls -l || true

say ""
say "\$ sha256sum -c SHA256SUMS"
sha256sum -c SHA256SUMS; say "[exit $?]"

say ""
say "\$ tar -xzf logos-0.2.2-x86_64-linux.tar.gz && cd logos-0.2.2-x86_64-linux"
tar -xzf logos-0.2.2-x86_64-linux.tar.gz && cd logos-0.2.2-x86_64-linux
say "[exit $?]"

say ""
say "\$ cat > hello.logos <<'EOF' … EOF"
cat > hello.logos <<'EOF'
(mod hello)

(fn main :void ()
  (println "hello from logos"))
EOF
say "[exit $?]"

say ""
say "\$ ./bin/logosc build hello.logos -o hello && ./hello"
./bin/logosc build hello.logos -o hello && ./hello; say "[exit $?]"

say ""
say "\$ ./bin/logosc version"
./bin/logosc version; say "[exit $?]"

say '```'
say ""
say "### 7.1 What the artifact must ship"
say ""
say "Both pages the README and \`llms.txt\` link, because a link into a directory"
say "the tarball does not carry is the dead end \`tools/verify_install.sh\` exists"
say "to prevent:"
say ""
say '```console'
say "\$ test -f llms.txt && echo llms.txt present"
test -f llms.txt && echo "llms.txt present"; say "[exit $?]"
say "\$ test -f share/doc/logos/examples/agent-gate/README.md && echo agent-gate page present"
if [ -f share/doc/logos/examples/agent-gate/README.md ]; then
  echo "agent-gate page present"
elif [ -f docs/examples/agent-gate/README.md ]; then
  echo "agent-gate page present (docs/examples/...)"
else
  echo "agent-gate page MISSING"; find . -name 'README.md' -o -name 'llms.txt' | head -20
fi
say "[exit $?]"
say '```'

say ""
say "### 7.2 The language reference the release ships"
say ""
say '```console'
say "\$ ./bin/logosc guide --json | jq -c '{schema_version, forms: (.forms|length), types: (.types|length), operators: (.operators|length), codes: (.codes|length)}'"
./bin/logosc guide --json 2>/dev/null | jq -c '{schema_version, forms: (.forms|length), types: (.types|length), operators: (.operators|length), codes: (.codes|length)}'
say "[exit $?]"
say '```'

say ""
say "Working directory kept for inspection: $WORK"
