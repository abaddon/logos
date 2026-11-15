# QA sign-off — Logos v1

**Verdict: the quality gate is in place and green; the build is not releasable
yet.** Six of the eighteen v1 criteria are unsatisfied and two are partial, all
for reasons that predate this pass and each with a named owner. Nothing in this
pass is blocked by a defect in the compiler; what remains is language surface,
publication, and one missing machine-readable report.

Scored on the merged tree (`wt/t_5bd6660b` = `main` `ed0196b` plus the
gap-closure branch, plus this QA pass). The criteria are reproduced here because
the audit that wrote them is on an unmerged branch; each row was re-verified
against this tree, not copied.

## What this pass establishes

| Claim | Evidence |
|---|---|
| The six documented gates pass on this tree | `bash tools/pr_gate.sh`: **6/6** (see [`../03-dossiers/gate-run-log.md`](../03-dossiers/gate-run-log.md)) |
| Every negative fixture is judged by the compiler | 147 sidecars, **144 agree**, 3 disagreeing plus 1 code-level gap registered in `tools/qa-known-gaps.txt` with measurements |
| Every published diagnostic is reachable | **34 of 35** codes exercised from `tests/`; `E0201` registered as having no emitter |
| The corpus cannot silently lose cases | per-category floors and 315 cases total, enforced by `tests/test_qa.py`; baseline pins `-O0` and `-O2` |
| The compiler's own suites all run | **9 of 9** (206 cases were run by nothing before this pass) |
| Repeated runs agree | two runs of the leak-and-panic category byte-identical; two builds of one source byte-identical |
| The gate is enforced where it matters | `make test` (gate 1) → `tools/pr_gate.sh` locally → `.github/workflows/gate.yml` on every PR |

## The scorecard

Legend: **PASS** measured this pass · **PARTIAL** measured, with a named gap ·
**FAIL** measured absent · **NOT ON MAIN** the work exists on an unmerged branch.

### A. Installable

| # | Criterion | Verdict | Evidence on this tree |
|---|---|---|---|
| V1-01 | Obtainable in one command from a public artifact, no clone | **NOT ON MAIN** | `tools/dist.sh` + `tools/verify_install.sh` exist and `release.yml` runs them; nothing is published and `bootstrap/toolchain.txt` gates the build to one toolchain. Owner: release (t_7c51cf28). |
| V1-02 | `version` and `version --json` agree with the artifact | **PASS** | `tests/test_cli.py::Version` (3 tests): text form is `logos 0.1.0`, JSON carries `schema_version`, name and semver. |
| V1-03 | Compiles and runs from any working directory | **PASS** | `tests/test_cli.py::Portability::test_build_and_run_outside_the_checkout` — builds in a temp dir, runs the binary, gets `hello`. |
| V1-04 | Every stdlib module resolves from the installation | **PASS** | `tests/test_cli.py::Portability::test_stdlib_modules_resolve_from_the_installation` — `(use map)` outside the checkout, builds and prints 7. |
| V1-05 | An install self-check exists (`logosc doctor` or equivalent) | **FAIL** | No such verb. `tools/verify_install.sh` is the closest thing and is not reachable from the compiler. Owner: release/compiler. |

### B. Usable

| # | Criterion | Verdict | Evidence on this tree |
|---|---|---|---|
| V1-06 | Two modules may declare the same type name; a bare ambiguous reference is refused with both candidates | **FAIL** | Global namespace (audit gap A1). `E0003: duplicate definition 'point': qa/point and qb/point` is the measured behaviour. Owner: language (designed, unmerged). |
| V1-07 | `show` + `patch` round-trip, or the goal is withdrawn | **FAIL** | `patch` is not in the verb list and `tests/test_cli.py::Help::test_invalid_choice_names_every_verb` pins the set without it. Needs an owner ruling, not code. |
| V1-08 | Every literal with no finite value is refused with a code and a node path | **PASS** | `E0106` for `:f64` and `:f32` (`tests/regress/float-range`, `float-range-f32`), while `1e308` and `DBL_MAX` compile (`tests/regress/float-finite`). |
| V1-09 | Stdlib has string→integer parsing and an integer-keyed map | **FAIL** | 21 functions; `map` is `:str` keys and `:i64` values only; no `str`→`i64`. Owner: stdlib (audit gap A4). |

### C. Machine-readable

| # | Criterion | Verdict | Evidence on this tree |
|---|---|---|---|
| V1-10 | Every compiler failure can be emitted as JSON, with a published schema | **PASS** | **144 of 147 fixtures** built with `build --json`, each producing exactly one diagnostic with the seven published fields (`tests/test_qa.py::NegativeFixtureSweep`; the other 3 are registered), plus one probe per phase in `tests/test_cli.py::JsonDiagnostics`. Schemas in `docs/schemas/`. |
| V1-11 | The exit-code contract is published as a table and tested | **PASS** | `docs/CLI.md` publishes 0/1/2; `tests/test_cli.py::ExitCodes` has a test per row, including a missing file and a directory for every reading verb. |
| V1-12 | `logosc test --json` with per-case results and totals | **FAIL** | `logosc test` prints `PASS ‹id› ‹detail›` only; `test -h` has no `--json`. This is audit gap C3 and it is a compiler change (`src/logosc/harness.logos`), deliberately left to a compiler owner: this pass's boundary is tests and gates. |
| V1-13 | `guide --json` carries a `schema_version` | **PASS** | `tests/test_cli.py::Guide::test_manifest_is_versioned` — `schema_version: 1` plus the seven keys. |

### D. Trustworthy

| # | Criterion | Verdict | Evidence on this tree |
|---|---|---|---|
| V1-14 | Bit-reproducible builds, published hash, cross-host claim | **PARTIAL** | Same-host: `tests/test_cli.py::Determinism` builds twice and compares bytes. Cross-host: the self-hosting gate strips the two linker-owned sections and requires every other section equal, and `release.yml` compares digests on a second runner. Nothing is published as a release hash yet. |
| V1-15 | All six gates pass from a clean container within a documented budget | **PASS** | `bash tools/pr_gate.sh` 6/6 locally on this tree; CI runs the same six steps on `ubuntu-22.04` with a 90-minute budget. Wall time and per-gate logs in the gate-run dossier. |
| V1-16 | The known limits are published in one page and linked from README/AGENTS | **NOT ON MAIN** | `docs/reference/limits.md` exists on the unmerged docs branch (t_bd94ddc5). On this tree the limits are still scattered. |

### E. Publishable

| # | Criterion | Verdict | Evidence on this tree |
|---|---|---|---|
| V1-17 | A tagged release with CHANGELOG, checksums, notes, MIT, public repo | **FAIL** | `git tag --list 'v*'` is empty; no CHANGELOG; `release.yml` is ready and unexercised. Owner: release (t_7c51cf28). |
| V1-18 | The quickstart is executed end to end on a clean machine | **NOT ON MAIN** | `docs/quickstart.md` and the consumer doc set are on the unmerged docs branch; this tree has README bullets only. |

## Summary

| Verdict | Count | Criteria |
|---|---|---|
| PASS | 8 | V1-02, 03, 04, 08, 10, 11, 13, 15 |
| PARTIAL | 1 | V1-14 |
| NOT ON MAIN | 3 | V1-01, V1-16, V1-18 |
| FAIL | 6 | V1-05, 06, 07, 09, 12, 17 |

**What must happen before a v1 tag**, in the order that unblocks the most:

1. **Merge the branches.** Three of the four "not on main" rows are already
   written and measured on unmerged branches (`docs/reference/*`,
   `docs/quickstart.md`, the audit register). This pass's branch also carries the
   gap closure, which reverts the release pipeline if it lands without `main`
   merged in — see the note below.
2. **One compiler change for V1-12** (`logosc test --json`): per-case JSON plus
   totals, so one agent can gate another agent's PR without parsing text. The
   schema can follow `docs/schemas/diagnostic-v1.schema.json`.
3. **Debug the fixture, don't edit the corpus.** The three registered fixture
   disagreements are cases that never reached what they meant to test; each needs
   its fixture fixed so it exercises its intent, not its sidecar relaxed.
4. **E0201 is a one-line decision:** emit it for field type mismatches, or drop
   it from the table. Today an agent can branch on a code that cannot occur.
5. **V1-06 (global namespace) is the only large piece of language work left**
   and it is designed (`docs/superpowers/specs/2026-11-15-module-qualified-names-design.md`).

## Appendix — every gap closed upstream, and the test that pins it

The gap-closure work merged into this branch closed ten audit gaps and fixed
three defects it found on the way. A gap without a test is a gap that reopens,
so each row names the check that fails if the behaviour goes away.

| Gap | Closed by | Pinned by |
|---|---|---|
| E1 — JSON diagnostics + schema | `build/check/resolve/fmt --json` | `tests/test_cli.py::JsonDiagnostics` (5 tests) and **144 fixtures** through `tests/test_qa.py::NegativeFixtureSweep` |
| D2 — runtime found from the executable | `/proc/self/exe` lookup | `test_cli.Portability::test_build_and_run_outside_the_checkout` |
| D3 — stdlib resolved from the installation | same | `test_cli.Portability::test_stdlib_modules_resolve_from_the_installation` |
| E2 — exit-code table | `docs/CLI.md` + one test per row | `test_cli.ExitCodes` (8 tests) |
| E3 — per-verb help | every verb has `-h` | `test_cli.Help::test_every_verb_has_its_own_help` |
| E4 — `resolve`/`check` unhidden | verb list | `test_cli.Help::test_invalid_choice_names_every_verb` |
| E5 — `version --json` | `schema_version` + name + semver | `test_cli.Version` (3 tests) |
| E9 — `guide --json` schema_version | manifest version | `test_cli.Guide::test_manifest_is_versioned` |
| A3 — non-finite float literals | `E0106` for `:f64` and `:f32` | `test_cli.FloatLiterals`, `tests/regress/float-range`, `float-range-f32`, `float-finite` |
| B2 — a CLI reference | `docs/CLI.md` | not a test; see the merge note about the duplicate `docs/reference/cli.md` |

| Defect found while closing them | Pinned by |
|---|---|
| `fmt` exited 0 on a file that does not lex | `test_cli.ExitCodes::test_fmt_source_error_is_two` |
| The float range check counted leading zeros as magnitude, refusing `0.0001e312` | `tests/regress/float-leading-zeros` |
| An unreadable file or a directory made the compiler panic with its own `R0007` and internal node path | `test_cli.ExitCodes::test_every_reading_verb_reports_a_missing_file_the_same_way`, `::test_a_directory_argument_is_an_io_failure_not_a_panic` |

## Notes for whoever merges this

- This branch is `main` **plus** a merge of `origin/fix/v1-gap-closure`, because
  the tests here exercise JSON diagnostics and the exit-code contract that the
  gap-closure branch adds. That branch was cut before the release pipeline
  landed; merged as a plain pull request it would delete `tools/dist.sh`,
  `tools/release.sh`, `tools/verify_install.sh`, `docs/install.md`,
  `docs/release.md` and `.github/workflows/release.yml`. **Merge `main` into the
  gap-closure branch (or take this branch, which has already done it) before
  merging either.** This is the largest merge hazard in the v1 release.
- `docs/CLI.md` (gap closure) and `docs/reference/cli.md` (docs branch) are two
  CLI references. One must survive.
- `AGENTS.md` still says `make test` runs the compiler's suites "at `-O0` and
  `-O2`" and names three of them. The gate has always run one level, and now
  runs nine suites. The file is protected from agent edits; the sentence needs a
  human-approved change (`make suites-all` is the two-level form).

SOURCES (LAYER 1 — NAVIGATION)

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/02-analysis/quality-gates.md
 -> Every threshold the verdicts above rest on, with its failure mode.

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/02-analysis/coverage.md
 -> The measured coverage numbers and the four registered holes.

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/03-dossiers/negative-fixture-audit.md
 -> Per-fixture evidence for the four registered gaps.

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/03-dossiers/gate-run-log.md
 -> Raw output of the gate run this sign-off is based on.

/root/ai-language-program/.worktrees/t_5bd6660b/tests/test_qa.py
 -> The enforced gate: run it to re-derive every number in this document.
