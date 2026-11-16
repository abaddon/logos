# L1 — Logos v1 release acceptance criteria

**Definition of shipped.** Sixteen criteria, each with the command that proves it and its status at
commit `9194412`. A v1 release is cut when all sixteen pass on a machine that is not this one.

Status legend: **PASS** (verified during this audit) · **FAIL** (verified absent/broken) ·
**N/A** (cannot be tested because a prerequisite is missing) · **DECISION** (needs an owner ruling
before it can be tested at all).

Gap IDs refer to [`gap-register.md`](gap-register.md).

---

## A. Installable — an AI with no repository has a working compiler

| # | Criterion | Verification | Status | Gaps |
|---|---|---|---|---|
| **V1-01** | `logosc` is obtainable in one command from a public artifact (tarball or package) on a clean x86_64 Linux host with no repository clone, no network access to the source tree, and no environment variables set. | On a fresh container: run the single documented install command, then `command -v logosc`. | **FAIL** — no artifact exists | D1, D7 |
| **V1-02** | The installed tool reports its own identity: `logosc version` exits 0 and prints a version that matches the artifact name, the release tag and the manifest field (`version --json` or `--version`). | `logosc version`; `logosc version --json \| jq -r .version`; compare with tag. | **FAIL** — prints `logos 0.1.0` from a source constant, no JSON form | E5, D4 |
| **V1-03** | Compiling and running a program works from **any** working directory, with the source outside any checkout. No `logos/runtime/rt.c` lookup can depend on cwd. | `cd /tmp && logosc build ~/hello.logos -o /tmp/hello && /tmp/hello` → prints `hello`, exit 0. | **FAIL** — `logos: runtime not found: logos/runtime/rt.c`, exit 1 | D2 |
| **V1-04** | Every standard-library module resolves from the **installation**, not the cwd: `(use map)`, `(use str)`, `(use io)` all resolve outside a checkout. | `cd /tmp/x && logosc build uses-io.logos` for each of the three modules. | **FAIL** — `E0005: unknown module 'map'` outside a checkout | D3 |
| **V1-05** | An install self-check exists and is used by the install test: one command that verifies compiler, runtime and stdlib are mutually consistent (version, hash, resolvable modules) and exits non-zero with a JSON diagnostic when they are not. | `logosc doctor` (or documented equivalent) on the installed tree. | **FAIL** — no such command | D1, C7 |

## B. Usable — a real program is possible

| # | Criterion | Verification | Status | Gaps |
|---|---|---|---|---|
| **V1-06** | A multi-module program in which two modules declare the **same type name** compiles and runs with each type getting its own layout; an ambiguous bare reference is refused with a code, a node path and both candidates named. | Two-module fixture from the qualified-names design's acceptance §1-2; `logosc build` then run. | **FAIL** — `E0003: duplicate definition 'point': qa/point and qb/point` | A1 |
| **V1-07** | Node-addressed editing round-trips: `logosc show FILE PATH` prints one node; `logosc patch FILE PATH` (replacement on stdin) rewrites only that node, then formats the file canonically, and every other node keeps its path. **Or** the design goal is formally withdrawn in the spec and this criterion is deleted. | show → patch → fmt → `git diff` limited to one node; second `fmt` is a no-op. | **DECISION** — `patch` returns, or the goal is withdrawn | A2, E10 |
| **V1-08** | Every numeric literal with no finite value in its type is refused with a code and a node path — `:f64` and `:f32` alike — while a large but finite literal is accepted. | `(println 1e999)` → `E0106` + node path, exit 2; `(println 1e308)` → compiles. | **FAIL** — `1e999` compiles and prints `inf` | A3 |
| **V1-09** | The standard library documented for v1 includes string→integer parsing and an integer-keyed map, has a signature reference, and every public function has at least one corpus case. | Reference table in the manual; `logosc guide --json` lists them; corpus case per function. | **FAIL** — 21 functions, no `str`→`i64`, `map` values are `:i64` with `:str` keys only | A4, B7 |

## C. Machine-readable — an AI can consume the output without parsing prose

| # | Criterion | Verification | Status | Gaps |
|---|---|---|---|---|
| **V1-10** | Every compiler failure can be emitted as JSON: one object per diagnostic on stderr with a published schema carrying at least `code`, `severity`, `message`, `node_path`, `file`, `line`, `col`, and a `schema_version`. Human text remains the default; the exit code is unchanged by the flag. | `logosc build bad.logos --json \| jq -e '.diagnostics[0].code'` for a lexer, parser, resolver, checker and lowering failure (five probes). | **FAIL** — text only | E1 |
| **V1-11** | The exit-code contract is published as a table and tested: `0` success, `2` a source/usage error, `1` an environment/IO failure — with any deviation (e.g. link failure) stated explicitly. Each row has a test. | Table in the manual + one corpus case per row asserting the status. | **FAIL** — semantics exist, undocumented and unpinned | E2, C2 |
| **V1-12** | `logosc test` can emit a machine-readable report: per-case `{id, level, passed, failed, leaked, diagnostic}` plus suite totals and the baseline verdict, so one agent can gate another agent's PR without text parsing. | `logosc test tests --json \| jq -e '.totals.failed == 0'`. | **FAIL** — `PASS id -` text only | C3 |
| **V1-13** | `logosc guide --json` carries a `schema_version` and is documented as a stable contract; a breaking change to it is a version bump. | `logosc guide --json \| jq -r .schema_version`; schema file in the repo. | **FAIL** — valid JSON, seven keys, unversioned | E9 |

## D. Trustworthy — the guarantees are published and reproducible

| # | Criterion | Verification | Status | Gaps |
|---|---|---|---|---|
| **V1-14** | Builds are bit-reproducible and the claim is published: the same source compiled twice, on two different hosts, yields identical binary and identical IR bytes, and the release publishes a hash. | Build twice on host A and once on host B, `sha256sum` all three, compare with the published hash. | **PARTIAL — PASS for same-host determinism** (verified identical), untested cross-host, unpublished | D7, D8, B6 |
| **V1-15** | All six gates pass from a clean container using documented commands, within a documented time budget, and the self-hosting fixed point holds (stage-0 reproduces itself byte for byte). | `bash tools/pr_gate.sh` from a fresh `ubuntu-22.04` container; record wall time. | **PASS (by project record; not re-run in this audit)** — CI + ledger report 6/6 | C8 |
| **V1-16** | The known limits are published in one page and linked from `README.md` and `AGENTS.md`: one target, `:str` lifetime, no comments, closure confinement, mutex-after-thread-exit, `(run)` 90 s budget, no data-race detection. | Page exists; both files link it; each limit names the diagnostic or the reason. | **FAIL** — limits scattered across ~40 plan reports and README bullets | B9, A7 |

## E. Publishable — the release itself

| # | Criterion | Verification | Status | Gaps |
|---|---|---|---|---|
| **V1-17** | A tagged release exists with: version in the artifact and in `version` output, a CHANGELOG entry, published checksums, release notes stating the v1 scope and the known limits, MIT licence in force, and a **public** repository. | `git tag --list 'v*'`; release page; `sha256sum -c`; repo visibility. | **FAIL** — no tags, no CHANGELOG, private repo, dangling `Not chosen yet.` in README | D4, D5, B8, B3 |
| **V1-18** | The quickstart in the docs is executed end-to-end by a person or agent with no prior context, on a clean machine, and every command in it produces the documented output — including the error case, which must show a structured diagnostic. | Follow `AGENTS.md`/README quickstart verbatim on a fresh container; diff each output. | **FAIL** — no consumer quickstart exists | B2, B6, D6 |

---

## Notes on scope

- **Criteria 1-5 are one workstream.** They cannot be split usefully: the runtime path, the stdlib
  path and the install layout are the same decision, and V1-05 is the test that proves all four.
- **V1-07 is a ruling, not necessarily work.** The spec promises `patch`; the port refuses the verb
  on purpose. Both positions are defensible; shipping with the text and the tool disagreeing is not.
- **V1-14 is already true and merely unpublished.** Same-host determinism was measured in this
  audit. Cross-host equality is the claim to establish; it is the cheapest trust win available.
- **V1-15 is the only criterion resting on the project's own record rather than a probe in this
  audit.** The full gate list takes ~1 hour and was out of scope here; `--only regress` was run and
  is green (33/33, 3.5 s).

---

SOURCES (LAYER 1 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> The gaps cited in the last column, with severity, effort and owner.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/findings.md`
 -> Why these criteria and this order; the AI-for-AI reasoning behind each group.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> The probes that produced every FAIL status in this table (P0-P16).
