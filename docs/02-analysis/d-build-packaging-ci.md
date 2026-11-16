# L2 (d) — Build, packaging, CI and publish

This dimension holds every S1 except one. The compiler builds perfectly; there is no way for anyone
outside this checkout to obtain it, and no way for it to work even if they had it.

Gap IDs: **D1-D10**.

---

## What exists

| Piece | State |
|---|---|
| `Makefile` | `test`, `contract`, `suites`, `suites-all`, `fmt`, `clean` — a developer's inner loop, not a product's |
| `tools/logosc.sh` | the real build entry point: verifies `bootstrap/logosc` against its SHA-256, rebuilds `build/logosc` when `src/` is newer, executes it |
| `tools/selfhost.sh` | the sixth gate: gen2 == gen3 byte-identity, IR parity, `fmt` reproduction, stage-0 currency |
| `tools/accept.sh` | seven end-to-end sections with per-section floors |
| `tools/pr_gate.sh` | the six gates + DCO precondition, one PASS/FAIL line each |
| `.github/workflows/gate.yml` | one job, `ubuntu-22.04`, 90-minute budget, the same six gates |
| `bootstrap/logosc` + `.sha256` | committed 1.3 MB stage-0 binary with `-text -diff` git attributes |
| `logos/runtime/rt.c`, `rt.h` | linked into every binary the compiler produces |
| `src/std/{io,str,map}.logos` | the standard library sources |

Absent: `pyproject.toml`, `setup.py`, `setup.cfg`, `tools/verify_install.sh`, `CHANGELOG.md`,
`SECURITY.md`, `ARCHITECTURE.md`, `Dockerfile`, `.devcontainer`, any `install`/`dist`/`release`
target, any `release.yml`, any git tag. All verified.

---

## D1 — No install artifact (S1, M)

Packaging was removed on purpose and correctly: the Python package existed only to ship the Python
compiler, and AGENTS.md is explicit that a second compiler must not come back. **Nothing replaced
it.** The evidence that the removal was never finished is still in the tree: `Makefile:42` cleans
`dist *.egg-info`, and `CONTRIBUTING.md:39` runs a Python test file that no longer exists.

**What v1 needs, minimally:**

```
logos-v1.0.0-x86_64-linux/
├── bin/logosc
├── lib/logos/runtime/rt.c, rt.h
├── lib/logos/std/{io,str,map}.logos
├── LICENSE, README, CHANGELOG, docs/LOGOS.md
└── install.sh          # or a single `tar -C /usr/local` instruction
```

**Recommendation (D-1, for the architect to ratify):** resolve everything relative to the executable,
not the working directory. `/proc/self/exe` gives the binary's own path on Linux — the runtime
already reads `/proc/self/cmdline` for `(args)`, so the primitive exists in spirit — and the compiler
then looks for `<prefix>/lib/logos/runtime/rt.c` and `<prefix>/lib/logos/std/`. Two overrides:
`LOGOS_ROOT` (the prefix) and `LOGOS_PATH` (extra module directories, colon-separated). This single
decision closes D2, D3 and half of A5 at once, and it is the difference between "a checkout" and "a
tool".

Alternative considered: a fully self-contained single binary with the runtime and stdlib embedded.
More ergonomic for an agent (one file to fetch), but it needs a writable temp dir at build time to
materialise `rt.c`, which is a new failure mode and a new document. The tarball-plus-prefix is
simpler and equally scriptable. Revisit at v1.1.

---

## D2 — The compiler cannot build outside a checkout (S1, S)

Measured:

```
$ cd /tmp && /…/build/logosc build /…/examples/hello.logos -o /tmp/hh
logos: runtime not found: logos/runtime/rt.c
exit=1
```

`src/logosc/main.md` documents this as intentional: *"`gen2` names the runtime the way it names
everything else it touches: `logos/runtime/rt.c`, relative to the working directory … A build run
anywhere else says so in one line and exits 1; it does not silently link a different runtime."*

The reasoning is sound (never link an unexpected runtime) and the conclusion is wrong for a shipped
tool: it makes cwd part of the tool's contract. The fix is D-1's prefix resolution plus a search
order that is **explicit and printed on failure** — e.g. `LOGOS_ROOT`, then the executable's prefix,
then cwd (kept last for the repository's own gates, which rely on it). The error line must name every
location tried, in JSON form when E1 lands.

Note the cost of the current design is not only portability: the error is a `logos: …` line with no
code, so it is also the one failure shape in the whole product that an AI cannot classify (E1/E2).

---

## D3 — The standard library resolves from the working directory (S1, M)

Measured in an isolated directory:

```
$ (use map) → E0005: unknown module 'map'
$ (use io)  → E0005: unknown module 'io'
```

Inside a checkout both resolve, because `src/std/<name>.logos` is a literal relative path
(`resolve.md`: *"the `src/std` spelling is relative to…"*). First run of a stranger's first program
that imports anything therefore fails with a resolver error that looks like a typo.

Same fix as D1 (prefix-relative stdlib root + `LOGOS_PATH`). The loader also needs one more thing a
consumer will hit immediately: **the stdlib must be versioned with the compiler**, because a stdlib
module from a different release could describe signatures the checker does not implement. A single
`schema_version`/`stdlib_version` in the install layout, checked at startup, is cheap.

---

## D4 — No release pipeline (S1, M)

- `git tag -l` → empty. The project has 104 commits, a completed v1 feature set, and no tag.
- `.github/workflows/` contains `gate.yml` only: no `release.yml`, no artifact upload, no registry
  publish, no container build.
- Version exists as `logos 0.1.0` inside `src/logosc/main.logos` (`main.md`: bumping it *"means
  changing `main-version` and nothing else"* — true only because nothing reads a version).
- No CHANGELOG (B8).

**What v1 needs.** A tag-triggered workflow that (1) builds on a pinned container, (2) runs the full
gate, (3) assembles the tarball from D1, (4) writes a `SHA256SUMS`, (5) attaches it to the GitHub
release with notes, and (6) on a second runner re-runs the V1-14 reproducibility check and compares
hashes. Publishing to a package registry is optional for v1; a release page with a verifiable
checksum is sufficient and much cheaper.

---

## D5 — The repository is private (S1, S, needs the owner)

From the project ledger, unambiguously:

> Hard truth recorded: the repository is private, so nobody finds it; GitHub also requires an account,
> so an agent acts through its operator's credentials. Enforcement therefore means a public-or-shared
> repo plus gates that block a bad merge, not a README request.
> Deferred to Stefano: public vs private, and the licence.

The licence has since been resolved (MIT, `LICENSE` present) but the README still ends with
`Not chosen yet.` (B3). Visibility is the one item on this list no agent can close. Everything in the
"adoption" premise — an AI discovers the repo, reads it, opens a PR — is blocked on it.

Worth stating plainly for the owner: a public repo changes the threat model (contributions from
untrusted agents), but the six gates plus DCO plus CODEOWNERS are already the right shape for that,
and the project's own ledger says so.

---

## D6 — No install instructions or supported-platform contract (S2, S)

`README.md` §Requirements is a *developer's* cut: Ubuntu 22.04, clang 14 and lld, gcc, jq, make,
Python 3.10+ "for the contract tests only". A consumer needs a different page:

| Consumer needs | README says |
|---|---|
| what to download and where | nothing |
| minimum glibc / distro | nothing (implied ubuntu-22.04 ⇒ glibc 2.35) |
| that clang is required **at build time** of every program | "clang 14 and lld" under Requirements, as a dev dependency |
| that Python is not required to use the compiler | says it is for contract tests only, in a bullet |
| how to verify the download | nothing |

The clang-at-runtime requirement is the most important and least visible fact: `logosc` is a driver
that shells out to clang for every program it builds. That is a legitimate design (documented in
`main.md`, `-O2` by default, `-lpthread -lm` unconditional), but it must be a headline of the install
docs, not a bullet in a dev section.

---

## D7 — No distribution-format decision (S2, M)

Facts that constrain it:

- `build/logosc` is `ELF 64-bit LSB pie, dynamically linked`, interpreter `/lib64/ld-linux-x86-64.so.2`,
  against `libc.so.6` and `libm.so.6`, **not stripped**; 1,366,624 bytes.
- It shells out to `clang` at run time, so a consumer needs clang regardless of how the compiler is
  packaged.
- Output binaries link `logos/runtime/rt.c` plus `-lpthread -lm`.

Options:

| Option | Cost | Verdict |
|---|---|---|
| Tarball per platform + `install.sh` | low | **recommended for v1** — one fetch, prefix layout, no package manager, debuggable since the runtime source travels with it |
| Single self-contained binary (embedded runtime + stdlib, materialised to temp) | medium | best ergonomics, new failure modes; v1.1 |
| Static musl build | medium | removes the glibc floor for the compiler, not for the programmes it links; partial win, revisit if glibc 2.35 bites |
| `.deb`/`.rpm` | high | needs maintainers per distro; wrong first move |
| Container image | low | useful for CI reproduction, not a substitute for an installable compiler (D9) |

Whichever is chosen, v1 needs: `SHA256SUMS`, an install path with no root requirement (`~/.local`),
and a documented uninstall (delete the directory).

---

## D8 — CI has no matrix and no release provenance (S3, M)

`gate.yml` is clean and honest (explicit toolchain install, 90-min budget with a reason, fetch-depth
for the format diff, DCO scoped to pull requests). What it does not do:

- **no matrix**: one OS, one clang. The compiler's output depends on clang 14's behaviour
  (`main.md` notes typed pointers `i8*` because clang 14 does not enable opaque pointers), so a
  newer clang is untested — and a user with clang 15+ is the likely first bug report.
- **no caching**: the 90-minute budget is dominated by rebuilding the compiler from source
  repeatedly. A `actions/cache` on `build/` keyed by source hash would cut it substantially.
- **no `make suites-all`**: the two-level suite parity is documented (falsely, C1) as part of the
  gate and is not run anywhere in CI.
- **no provenance for the checked-in stage-0**: `bootstrap/logosc` is a 1.3 MB binary trusted via a
  hash stored in the same commit. That is the classic bootstrapping trust question — the hash proves
  integrity, not origin, and a public release makes it a supply-chain question. Mitigations worth
  documenting rather than solving: state which commit and compiler produced it, and publish the
  recipe. (Diverse double-compiling is the rigorous answer; it is out of scope for v1 but should be
  named in the release notes as a known limitation.)

---

## D9 — No reproducible dev environment (S4, S)

No container or devcontainer. The README's Requirements list is reproducible in practice
(`apt-get install clang lld gcc jq python3 make` on 22.04), but nothing pins it. A 20-line
`Dockerfile` + a `docker run` line would make "run the gates exactly as CI does" one command — worth
it only if the release workflow needs it (per D4's pinned-container step, it probably does).

---

## D10 — No release targets in the Makefile (S2, S)

`make` offers nothing a release needs. Minimum additions:

```make
install:  # prefix-relative layout into $(PREFIX) ($(HOME)/.local by default)
dist:     # assemble the tarball from an existing build, with SHA256SUMS
release:  # dist + tag verification + dry-run of the publish steps
```

`release` should be **dry-runnable** (`make release DRY=1`) so an agent can verify the pipeline
without publishing — the acceptance for the build workstream asks exactly that.

---

## Build-system detail worth keeping

- `tools/logosc.sh` verifies the bootstrap hash **before every build**, not once: a corrupted stage-0
  cannot silently produce a different compiler. Keep it in any new entry point.
- The compiler binary is named after the *first* source's stem only for the IR file (`build/body_test.ll`
  when the set starts with `body_test.logos`); `-o` names the binary. Harmless, but a v1 installer
  should pass an explicit `-o` and an explicit IR location so no consumer sees `body_test.ll`.
- Determinism: two builds of the same input yield identical bytes (verified). `main.md` explains why
  (clang embeds the IR file's basename and nothing else about the path). Any change to where the IR is
  written risks that guarantee — the reproducibility test (V1-14) belongs in the release workflow for
  exactly this reason.

---

SOURCES (LAYER 2 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Register rows D1-D10 with severity, effort and owner.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/v1-acceptance-criteria.md`
 -> Criteria V1-01…V1-05 (installable) and V1-14/V1-17 (reproducibility, release).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/repository-inventory.md`
 -> The absence evidence: file listing, `git tag` output, binary `file`/`ldd` output, Makefile targets.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> P7 (runtime not found outside a checkout), P10-P11 (stdlib E0005), P12 (binary type), P13 (identical hashes).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/src/logosc/main.md`
 -> §"Finding the runtime" (why the path is cwd-relative today) and §"Building it" (the clang command line, `-O2` default, unconditional `-lpthread -lm`).
