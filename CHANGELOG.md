# Changelog

All notable changes to the Logos compiler, its runtime and its standard
library. The version is `logos <version>` from `logosc version`, and a release
tag is `v<version>`; there is no other place a version lives.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).
Pre-1.0 the minor number carries features and the patch number carries fixes.

## 0.2.1 — 2026-11-16

A packaging fix. The compiler is unchanged; the tarball is not, which is why
this is a patch release and not a rebuild of 0.2.0 under the digest that release
already published.

### Fixed

- **The documentation in the tarball is self-contained.** 0.2.0 shipped
  `share/doc/README.md` — the repository's front page — while the `docs/` tree
  every one of its links pointed into was not in the artifact. Twelve `docs/…`
  links, plus the `AGENTS.md`, `CONTRIBUTING.md` and `CHANGELOG.md` links beside
  them, resolved to nothing for anyone who unpacked it; `INSTALL.md` told the
  reader to consult `AGENTS.md` and `docs/release.md`, neither of which shipped.
  The documentation now ships where the links point: `README.md`,
  `CHANGELOG.md`, `LICENSE`, `AGENTS.md`, `CONTRIBUTING.md` and the `docs/` tree
  at the prefix root, with `INSTALL.md` beside them, so a page that links
  `docs/reference/cli.md` finds it offline and without a checkout.
- **`tools/check_doc_links.sh`** walks every `*.md` in a tree, resolves each
  relative link against the page that holds it, and reports what does not
  resolve. `tools/dist.sh` runs it on the staging tree before writing the
  tarball and refuses to build on a broken link; `tools/verify_install.sh` runs
  it on the unpacked artifact, and now also requires the shipped pages
  (`README.md`, `CHANGELOG.md`, `LICENSE`, `AGENTS.md`, `docs/00-index.md`,
  `docs/LOGOS.md`) by name. The artifact stays byte-reproducible: the pages are
  copied from the git index in a fixed order, and two builds of one commit still
  produce one SHA-256.

## 0.2.0 — 2026-11-16

The first published release. The compiler is self-hosting: `src/logosc/*.logos`
is the whole compiler, `bootstrap/logosc` is the stage-0 that builds it, and CI
requires the binary built by the stage-0 and the binary that binary builds to be
byte-identical before it will cut a release.

**Pre-1.0.** Five of the eighteen v1 acceptance criteria are still open — the
global namespace, `logosc test --json`, an install self-check, a `patch` verb
and two standard-library gaps. They are listed under *Known limits* below and
tracked in [`docs/reference/limits.md`](docs/reference/limits.md). Pin the
version you test against.

### Added

- **An installable artifact.** `logos-0.2.0-x86_64-linux.tar.gz` plus
  `SHA256SUMS`, built by `tools/dist.sh`, byte-reproducible from the tag: file
  order, ownership, mtime (the commit date) and gzip header are all fixed, and
  the release workflow rebuilds it on a second runner and requires the two
  SHA-256 sums to agree. `tools/verify_install.sh` proves the tarball alone can
  compile, link and run a program.
- **Machine-readable diagnostics.** `--json` on `build`, `check`, `resolve`,
  `fmt` and `show` emits one JSON object per line on stderr — `schema_version`,
  then `diagnostics[]` of `{severity, code, message, node_path, file, line,
  col}`. Published schema: `docs/schemas/diagnostic-v1.schema.json`.
- **Versioned JSON documents.** `logosc version --json` and a `schema_version`
  key on `logosc guide --json`, so a consumer can detect a breaking change.
- **Per-verb help.** Every verb answers `-h` on stdout with exit 0, and
  `resolve` and `check` are no longer hidden from the verb list.
- **A real exit-code contract,** pinned one test per row: `0` success, `2` a
  source or usage error, `1` an I/O or toolchain failure.
- **Running from an installation.** The runtime and the standard library are
  resolved from the compiler's own location (`/proc/self/exe`) instead of the
  working directory, so `cd /tmp && logosc build hello.logos` works and
  `(use map)` resolves.
- **A QA gate** (`tests/test_qa.py`, inside `make test`, so every workflow
  enforces it): all 147 negative fixtures are built through `build --json` and
  judged by the compiler, diagnostic shape and locatability are checked,
  published-code coverage and corpus floors are enforced, and repeated runs are
  compared. Nine compiler suites run in the gate — six of them (lexer, tree,
  types, emitter, formatter, harness; 206 cases) were run by no target before.
- **Documentation for consumers:** `docs/install.md`, `docs/quickstart.md`,
  `docs/00-index.md`, and references for the CLI, diagnostics, the language,
  the standard library, the limits and the agent contract.
- **A release pipeline** (`.github/workflows/release.yml`): the six gates, the
  build, a second-runner digest comparison, and `gh release create --verify-tag`
  on a `v*` tag; `tools/release.sh` rehearses the same steps locally.
- `tests/test_cli.py` (34 tests) and `tests/test_qa.py` (14 tests).

### Fixed

- `fmt` exited 0 on a file that does not lex; it now reports the source error
  and exits 2.
- The float range check counted leading zeros as magnitude, refusing the
  finite literal `0.0001e312`; exponents now subtract the leading zeros.
- An unreadable file, or a directory passed as a source, crashed the compiler
  with its own `R0007` panic and an internal node path. Every verb now prints
  `logos: <path>: <reason>` and exits 1.
- Non-finite float literals (`1e400`, `nan`, `inf`) are refused with `E0106`
  instead of silently becoming a different number.
- A wrong-arity form is refused in every root set, not only in function bodies.
- The emitter suite read its fixtures through an absolute path belonging to one
  machine, so it could only pass there; it now uses a relative path.
- The self-hosting gate compared two linker-owned ELF sections (`.comment` and
  `.note.gnu.build-id`) that record the distribution's GCC point release, so
  two correct hosts disagreed by 24 bytes; it now strips those two and requires
  every other section to be byte-identical.

### Changed

- The Python implementation of the compiler is gone: `src/logosc/*.logos` is
  the compiler, and a Python driver is no longer needed to build or run it.
- `make test` runs the contract tests and all nine compiler suites; `make fast`
  is the seconds-scale loop, and `make release` rehearses a publish.

### Known limits

- Names are global across a whole program: two modules cannot both declare
  `point` (designed, not implemented).
- `logosc test` prints text only — there is no `test --json` (the machine
  surface is `build|check|resolve|fmt --json`).
- No `logosc doctor`, and no `patch` verb.
- The standard library is 21 functions: no `str` → integer parsing, and `map`
  is `:str` keys with `:i64` values only.
- x86_64 Linux only, glibc 2.35 or newer, and `clang` 14 is required at build
  time of every program, not only of the compiler.
- The stage-0's provenance is recorded, not proven: `bootstrap/logosc.sha256`
  proves integrity, and the toolchain is pinned in `bootstrap/toolchain.txt`.

### Verify

```sh
gh release download --repo abaddon/logos --pattern 'logos-0.2.0-*' --pattern SHA256SUMS
sha256sum -c SHA256SUMS
tar -xzf logos-0.2.0-x86_64-linux.tar.gz
cd logos-0.2.0-x86_64-linux
./bin/logosc version                       # logos 0.2.0
printf '(mod hello)\n\n(fn main :void ()\n  (println "hello from logos"))\n' > hello.logos
./bin/logosc build hello.logos -o hello && ./hello
```
