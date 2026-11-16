# Logos v1 readiness — gap register

**Audit date:** 2026-11-15 · **Commit audited:** `9194412` · **Auditor:** technical-architect
**Question:** what is missing before `logosc` can ship as v1 and be adopted by an AI that has never seen it?

> **Status note (added with the v1 doc set).** This register is the audit's
> backlog, kept verbatim as the record of what was wrong at `9194412`. Some
> rows have since been paid down by the documentation work: **B2, B3, B5, B6,
> B7, B9, D6, E2** and the consumer half of **B1** are now answered by
> [`../00-index.md`](../00-index.md), [`../quickstart.md`](../quickstart.md) and
> [`../reference/`](../reference/). The compiler, packaging and test gaps
> (`A*`, `C*`, `D1-D5`, `D7-D10`, `E1`, `E3-E10`) are untouched by a docs
> change and remain open. Read the register as the backlog, and the row's
> owner as the profile that must close it.

**Verdict: not releasable.** The compiler is functionally strong — self-hosting, 309-case corpus
green at both optimisation levels, byte-reproducible output — but it cannot leave its own
repository. There is no install artifact, the build fails outside a checkout, the standard library
resolves only from the working directory, and the project has never been tagged. Seven S1 blockers
sit between this tree and a download someone else can use.

Each gap is analysed in `02-analysis/`, and every behavioural claim about the compiler was
measured, not inferred — the commands and their output are in `03-dossiers/probe-log.md`.

**All SOURCES paths below are absolute in this worktree** (`/root/ai-language-program/.worktrees/t_7a5a4fe5`);
the repository-relative path is the same string minus that prefix.

---

## How to read this register

| Field | Values |
|---|---|
| **Severity** | `S1` blocker — v1 cannot ship · `S2` high — ships unusable for the target consumer · `S3` medium — degrades trust or ergonomics · `S4` low — polish |
| **Effort** | `S` ≤ 1 day · `M` 1–3 days · `L` 1–2 weeks · `XL` > 2 weeks |
| **Owner** | the profile that should execute it: `backend-engineer` (compiler), `technical-writer` (docs), `platform-engineer` (build/CI/publish), `qa-engineer` (tests/gates), `oss-contributor` (release), `technical-architect` (design decisions), `orchestrator`/owner (human decision) |
| **AI lens** | every gap was judged by one question: *does closing this make an AI consumer's life easier?* Machine-readable output, deterministic behaviour, structured error codes, agent-facing docs, reproducible builds are the scoring rubric — not human ergonomics. |

Counts: **7 S1 · 20 S2 · 17 S3 · 2 S4** (46 gaps).

---

## S1 — blockers. v1 cannot ship with any of these open.

| ID | Gap | Effort | Owner | Evidence |
|---|---|---|---|---|
| **D1** | **No install artifact.** `pyproject.toml`, `setup.py` and `tools/verify_install.sh` were deleted with the Python compiler; no `install` target, no tarball, no package in any registry. There is no way to obtain `logosc` except cloning the repo. | M | platform-engineer | `03-dossiers/repository-inventory.md` |
| **D2** | **The compiler cannot compile outside a checkout.** It looks for `logos/runtime/rt.c` relative to the *working directory*; from `/tmp` every build dies with `logos: runtime not found`, exit 1. An installed binary would have nothing to link. | S | backend-engineer | probe P7 |
| **D3** | **The standard library resolves from the working directory.** `(use map)` is found as `src/std/map.logos`; in an isolated directory it is `E0005: unknown module 'map'`. `(use io)` likewise. Installed, a consumer's first non-trivial program fails to resolve. | M | backend-engineer | probes P10, P11 |
| **D4** | **No release pipeline.** Zero git tags, no `release.yml`, no CHANGELOG, no artifact publication, no version anywhere but a string constant in `main.logos`. | M | platform-engineer | probe P1, `repository-inventory.md` |
| **D5** | **The repository is private.** The project's own ledger records it: *"the repository is private, so nobody finds it"*. Every claim about adoption is vacuous until this is decided. Needs the owner, not an agent. | S | orchestrator / owner | `03-dossiers/doc-contradictions.md` |
| **E1** | **No machine-readable diagnostics.** Every compiler error is one text line on stderr (`p/main/3/0: E0304: …`). The only JSON the product emits is `guide --json`. An AI consumer must regex prose-style text to learn what broke — the single largest gap against the project's own stated purpose. | M | backend-engineer | probes P5, P6 |
| **A1** | **Names are global across the whole program.** Two modules each declaring `point` is `E0003`, so every program of any size needs a hand-maintained naming discipline. The project's own design document calls it *"the thing that makes Logos hard to adopt"*; the fix is designed (`2026-11-15-module-qualified-names-design.md`) and unimplemented. | L | backend-engineer | `03-dossiers/doc-contradictions.md` |

## S2 — high. A v1 that ships without these is unusable or untrustworthy for an AI consumer.

| ID | Gap | Effort | Owner | Evidence |
|---|---|---|---|---|
| **A2** | **The `patch` verb is missing.** `logosc patch <path>` is specified — node-addressed editing is design goal #3, *"a change is a patch to one node, not a rewrite of the file"* — and was implemented on the Python compiler, then deliberately dropped from the Logos port. `show` is read-only, so an AI can address a node but cannot write one. | M | backend-engineer | probe P3, `doc-contradictions.md` |
| **A3** | **Float literals with no finite value are accepted.** `(println 1e999)` compiles and prints `inf`, while the integer path refuses `E0106`. A silent wrong value, one type family apart. | S | backend-engineer | `02-analysis/a-compiler-capabilities.md` |
| **A4** | **The standard library is 21 functions** (`io` 5, `str` 6, `map` 10, with `:i64` values only). No string→integer parse, no integer-keyed map, no sort, no JSON encode/decode (the JSON parser is an example, not a library), no formatting/`sprintf`, no `unlink`/`stat`/`getenv`. An AI writing a real tool hits these within an hour. | L | technical-architect + backend-engineer | `repository-inventory.md` |
| **A5** | **No way to publish or consume a third-party Logos library.** `use` searches the asking file's directory and `src/std` only; no environment variable, lockfile, registry or version constraint. Without it there is no ecosystem, only the stdlib. | L | technical-architect | `02-analysis/a-compiler-capabilities.md` |
| **B2** | **The manual documents the language but not the tool.** `docs/LOGOS.md` (932 lines, 20 chapters) has no chapter on verbs, flags, exit codes, output streams, or where the IR goes. An AI can write Logos after reading it and still not know how to drive `logosc`. | M | technical-writer | probe P4, `02-analysis/b-documentation.md` |
| **B3** | **README overstates reality in two places.** It opens Status with *"Logos v1 is complete"* while publishing is impossible; and it claims the compiler's suites run *"each at both levels"* when the shipped `make test` target runs `-O0` only (`Makefile:17-22` says so explicitly). The file also ends with a dangling `Not chosen yet.` under License. | S | technical-writer | `doc-contradictions.md` |
| **B4** | **The design spec contradicts the implementation.** It declares self-hosting a non-goal ("`logosc` is Python in v1"), promises `patch`, and promises diagnostics carry "the minimal subtree" — none true. No amendment recorded. An AI reading the spec is actively misled. | M | technical-architect | `doc-contradictions.md` |
| **B5** | **Stale references to the deleted Python compiler.** `CONTRIBUTING.md` tells contributors to run `python3 -m unittest tests.test_gen2_build` (no such file), the bug-report template's placeholder command is `python3 -m logos build`, and `make clean` still deletes `dist/ *.egg-info`. | S | technical-writer | `repository-inventory.md` |
| **B6** | **`AGENTS.md` is a contributor contract, not a consumer contract.** It is excellent on how to change the compiler and silent on how an AI that *has* the compiler should compile, run, read errors and find the IR. | M | technical-writer | `02-analysis/b-documentation.md` |
| **B7** | **No standard library API reference.** `src/std/*.md` are design rationale files; the manual contains no signature table for the 22 public functions (grep: one incidental hit). | M | technical-writer | probe P9 |
| **C2** | **No CLI contract tests.** Exit codes, output streams and per-verb behaviour were pinned by Python unit tests that were deleted with the port. `logosc build -h` is a usage error with exit 2 — correct by accident, pinned by nothing. | M | qa-engineer | probes P2, P8 |
| **C7** | **No install acceptance test.** The v1 promise — "install, then compile hello" — has no test, because there is no install. This is the gate that must exist before the release, not after. | M | qa-engineer | `02-analysis/c-tests-and-gates.md` |
| **D6** | **No install instructions and no supported-platform contract.** README's Requirements section is a developer's cut; nothing states what a consumer must have, which libc, or what is verified. | S | technical-writer | `02-analysis/d-build-packaging-ci.md` |
| **D7** | **No distribution-format decision.** Static or dynamic, glibc floor (builds on ubuntu-22.04 ⇒ glibc 2.35), one tarball or per-distro packages, checksums and signing — all undecided. | M | platform-engineer | probes P12, P13 |
| **D10** | **No `make release`, `make install` or `make dist`.** `make` has `test`, `contract`, `suites`, `suites-all`, `fmt`, `clean` only. | S | platform-engineer | `Makefile` |
| **E2** | **The exit-code contract is undocumented and unpinned.** `0`/`1`/`2` are used with real semantics (2 = source error *and* usage error; 1 = I/O), the manual states none of it, and the port deliberately changed front-end failures from 1 to 2. An AI cannot branch on status reliably. | S | technical-writer + qa-engineer | probes P5, P6, P8 |
| **E3** | **No per-verb help.** `logosc build -h` and `logosc build --frob` are both `unrecognized arguments`, exit 2. Flag discovery requires reading the source or the manual, which does not cover flags. | S | backend-engineer | probe P8 |
| **E4** | **Two verbs are hidden.** `resolve` and `check` work but appear neither in `--help` nor in the invalid-choice list — a deliberate parity choice that leaves an agent seeing six verbs where eight exist. | S | backend-engineer | probes P4, P6 |
| **E6** | **No `run` verb, no `--emit`, no IR on stdout.** Building and running is `build` then read `build/<stem>`; asking for IR only, an object, or stdout requires knowledge of a path convention instead of a flag. | M | backend-engineer | probe P4 |
| **E9** | **The one JSON surface is unversioned and undocumented.** `guide --json` emits valid JSON with seven keys, but no schema, no `schema_version`, and no statement that it is stable — so no consumer can depend on it. | S | backend-engineer + technical-writer | probe P5 |

## S3 — medium. Ship-with-it-documented, or fix in v1.1.

| ID | Gap | Effort | Owner | Evidence |
|---|---|---|---|---|
| **A6** | arm64 and Darwin untested; the stage-0 binary is x86_64 Linux, so another platform needs a bootstrap built where the compiler already runs. Target triple is already a flag. | L | backend-engineer | `README.md` Known limits |
| **A7** | **The language has no comments and no doc form.** Rationale lives in a sibling `.md` (`src/std/io.md`: *"Logos has no comments and no doc form, so this file is the header documentation"*). For AI-authored code, that removes in-source intent — a v1 decision that should be recorded as deliberate, not omitted. | M | technical-architect | `doc-contradictions.md` |
| **A8** | Compiler rebuild from source takes ~6 minutes (measured); no incremental or parallel path. Slow loop for an agent iterating on the compiler. | L | backend-engineer | probe P0 |
| **B1** | No documentation index. **Closed by [`docs/00-index.md`](../00-index.md)** (this register lived there before the v1 doc set landed). | S | technical-writer | — |
| **B8** | No CHANGELOG, no versioning policy, no release notes; `version` is a constant in `main.logos` with no documented bump procedure. | S | oss-contributor | `02-analysis/b-documentation.md` |
| **B9** | Known limits are scattered across ~40 plan reports; no single page an AI can read before trusting the tool. | S | technical-writer | `repository-inventory.md` |
| **C1** | The documented two-level suite run does not exist in the gate: `make test` runs `-O0`; the two-level form is the undocumented `make suites-all`. Either the claim or the gate is wrong, and AGENTS.md repeats the claim. | S | qa-engineer | `doc-contradictions.md` |
| **C3** | No machine-readable test report. `logosc test` prints `PASS id -` lines; the baseline is text. Gating a PR programmatically means parsing text. | M | qa-engineer | probe P14 |
| **C4** | The differential oracle is three programs (`arith`, `arrays`, `strings`) against gcc. Thin for generics, closures, enums, threads, optionals. | M | qa-engineer | `repository-inventory.md` |
| **C5** | No coverage measurement anywhere — not for the corpus, not for the compiler's own suites. | M | qa-engineer | `02-analysis/c-tests-and-gates.md` |
| **C6** | No fuzzing or property tests beyond `fmt` idempotency; the lexer, parser and printer are exercised only by fixed cases. | M | qa-engineer | `02-analysis/c-tests-and-gates.md` |
| **C8** | The full gate is ~1 hour with no documented fast subset (`--only regress` is 3.5 s and works — nobody says so). | S | qa-engineer | probe P14 |
| **D8** | No CI matrix and no recorded toolchain provenance for a release; the gate pins `ubuntu-22.04` + clang 14 implicitly. | M | platform-engineer | `.github/workflows/gate.yml` |
| **E5** | `version` is a source constant and a bare verb: no `--version` flag and no machine-readable version (`version --json`). Version-bump automation has nothing to read. | S | backend-engineer | probe P1 |
| **E7** | No stdin input for `build`/`check`, while `fmt -` supports it — an inconsistency an agent hits when piping generated source. | S | backend-engineer | probe P9 |
| **E8** | `build` writes IR and binary into `build/` **relative to the working directory**, not beside the source or in a caller-named place — unexpected side effects in a consumer's tree. | S | backend-engineer | `src/logosc/main.md` |
| **E10** | **Diagnostic text is a byte-for-byte contract with a deleted implementation.** The port reproduces Python's `argparse` strings exactly and calls that the contract. For an AI consumer, stable codes and a stable schema beat byte parity with a dead tool — this is a decision to revisit, not a bug. | M | technical-architect | `doc-contradictions.md` |

## S4 — low. Polish.

| ID | Gap | Effort | Owner |
|---|---|---|---|
| **D9** | No container image or devcontainer for a reproducible build environment (only add if distribution needs it). | S | platform-engineer |
| **C9** | Corpus naming is uneven (`tests/regress/program/program`), which makes ids noisy in reports an agent must parse. | S | qa-engineer |

---

## What v1 means, precisely

The release criteria are in one place, each with the command that proves it:
**[`v1-acceptance-criteria.md`](v1-acceptance-criteria.md)** — 18 criteria,
grouped as *installable*, *usable*, *machine-readable*, *trustworthy*, *publishable*.

Read it before starting any gap above: it defines the stopping condition, and several gaps
(A2, A7, E10) are decisions inside it rather than obvious defects.

## Recommended sequence

1. **Decide (owner, no code):** D5 private-vs-public, D7 distribution format, A2 patch in v1,
   A7 comments, E10 diagnostic-text contract. These are cheap now and expensive later.
2. **Make it installable:** D1 → D2 → D3 → D10 → D6 → C7. This unblocks every other dimension and
   produces the first end-to-end proof that v1 is possible.
3. **Make it machine-readable:** E1 → E9 → E2 → C2 → C3. This is the differentiator; the compiler
   is already deterministic and structured internally, it just refuses to say so in JSON.
4. **Fix the language blockers:** A1 → A2 → A3 → A4. A1 is designed and quoted, not speculative.
5. **Publish:** D4 → B8 → D8 → D7 → release.
6. **Correct the record in parallel:** B2 → B3 → B4 → B5 → B6 → B7 → B9 (technical-writer can run
   alongside steps 2-4; B4 must land before the spec is cited by anyone else).

---

SOURCES (LAYER 0 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/findings.md`
 -> The audit in one page: why v1 is blocked, the seven S1s in context, and what the AI-for-AI lens changes about priorities.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/v1-acceptance-criteria.md`
 -> The 18 testable criteria that define "v1 shipped", each with the exact command that proves it.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/02-analysis/a-compiler-capabilities.md`
 -> Dimension (a): language and compiler capability vs. what v1 needs — namespaces, patch, literals, stdlib, distribution model, targets, build latency.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/02-analysis/b-documentation.md`
 -> Dimension (b): missing and wrong documentation, file by file, with the specific sentence that is false.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/02-analysis/c-tests-and-gates.md`
 -> Dimension (c): what the six gates do and do not cover, missing contract/install/JSON-report tests, coverage and fuzzing.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/02-analysis/d-build-packaging-ci.md`
 -> Dimension (d): build, packaging, CI and publish — the install gap traced to its three root causes.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/02-analysis/e-cli-api-contract.md`
 -> Dimension (e): CLI surface, exit codes, streams, JSON schema, hidden verbs, the patch and run verbs.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> Every measured behaviour: 16 probes (P0-P16) with the exact command, output and exit code. This is the grounding for every factual claim in the register.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/repository-inventory.md`
 -> What exists: file counts, surfaces, stdlib function list, packaging files (absent), git state, toolchain.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/doc-contradictions.md`
 -> Quoted contradictions between spec/README/AGENTS/CONTRIBUTING and the implementation, with file and line.
