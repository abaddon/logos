# L2 (c) — Tests and quality gates

The quality system here is stronger than most released compilers: six gates, a DCO precondition, a
floor on every section so deleting cases cannot turn a gate green, a baseline that refuses to compare
rather than fail open, and a stage-0 binary checked against its hash on every run. The gaps are not
"more tests" — they are **the contract the tests stopped covering when the Python implementation was
deleted**, and the one promise (`install, then compile`) that nothing tests at all.

Gap IDs: **C1-C9**, with **C2/C3** carrying the weight.

---

## What runs today

| Gate | Command | What it proves | Floor |
|---|---|---|---|
| 1 | `make test` | 24 contract tests (20 `test_contributing`, 3 `test_runtime`, 1 `test_selfhost`), then `body_test` (361 cases), `check_test` (81), `resolve_test` (38) at `-O0` | suites named explicitly, not discovered |
| 2 | `./tools/logosc.sh test tests` | 309 corpus cases across 8 categories, every case at `-O0` **and** `-O2`, the two levels compared with each other, plus the recorded baseline and leak total | baseline has an `OPTS` line; a case outside the 8 categories fails the run |
| 3 | `bash tools/accept.sh` | 7 sections: corpus, differential oracle vs gcc (3 programs × 2 levels), `wc`/`json`/`matrix` examples vs `wc`/`jq`/C reference, `fmt` idempotency over every `.logos` file, 200-function compile-speed floor | every section must examine ≥ 1 item |
| 4 | `./tools/logosc.sh guide --check` | the committed manual is byte-identical to what the compiler generates | stale ⇒ exit 1 with a diff summary |
| 5 | `logosc fmt $(git diff --name-only main...HEAD -- '*.logos')` + `fmt tests docs/manual` | no formatting drift, and the formatter is a fixed point | `git diff --exit-code` |
| 6 | `bash tools/selfhost.sh` | `gen2` built by the stage-0 is byte-identical to the binary it produces (`gen3`), IR parity over a 90-file manifest, `fmt` reproduces every tracked `.logos` file, **and** the stage-0 equals what this source produces | manifest floor + IR floor |

Plus a DCO precondition before any gate, and a `tests/summary.txt` baseline recording `LEAKS 10`,
`OPTS -O0 -O2` and one line per case. Verified during this audit: `--only regress` → 33 passed, 0
failed, 0 leaked, 0 regressions, in 3.5 s.

This is the part of the project that should be advertised rather than fixed.

---

## C1 — The documented suite run does not exist (S2, S)

`AGENTS.md`: *"`make test` runs … the compiler's own suites (`body_test`, `check_test`,
`resolve_test`) at `-O0` and `-O2`."* `README.md:49-50` says *"each at both levels"*.

`Makefile:17-22` says the opposite, deliberately:

> They run at `-O0` in the gate because every case lowers and links its whole module, which makes two
> levels a ninety-minute gate; the corpus already runs all 309 language cases at both levels, and
> `make suites-all` is the two-level form.

So the two-level form exists (`make suites-all`) and no gate runs it, and the two files that define
the contract describe the gate as if it did. **Either the docs or the gate is wrong; pick one and
make them agree.** The honest option is to document both forms and say which one the gate runs and
why — an AI reading `make test` should not believe it measured optimisation parity of the compiler's
suites.

---

## C2 — The CLI has no contract tests at all (S2, M)

Every statement about the command line — exit codes, which stream a message goes to, what
`build -h` does, the `--only` validation, the repeated `-` refusal — was pinned by Python unit tests
that were deleted with the Python compiler. What replaced them is `tests/test_contributing.py`,
which pins the *gate list*, not the CLI.

Verified behaviour that nothing asserts:

| Behaviour | Measured | Pinned by |
|---|---|---|
| `build -h` | `unrecognized arguments: -h`, exit 2 | nothing |
| unknown verb | `invalid choice: 'patch'`, exit 2 | nothing |
| no arguments | help on stdout, exit 0 | nothing |
| source error | one line on stderr, exit 2 | nothing |
| missing file | `logos: <path>: No such file or directory`, exit 1 | nothing |
| `resolve`/`check` absent from `--help` | true | nothing |

An agent that branches on exit status is relying on undocumented, untested behaviour. **C2 is the
prerequisite for E2** (the published exit-code table): a table nobody tests is a comment.

Note that this is not a regression in engineering — it is the predictable cost of replacing one
compiler with another, and the ledger records the deletion as deliberate (*"do not reintroduce a
second compiler to test the first"*). The gap is that nothing took over the CLI's contract.

---

## C3 — No machine-readable report from anything that judges code (S2, M)

Three separate text formats an agent must parse:

- `logosc test` → `PASS regress/recursive-enum -` per case, then `33 passed, 0 failed, 0 leaked`,
  then `baseline tests/summary.txt: 0 regression(s)`.
- `tests/summary.txt` → `LEAKS 10`, `OPTS -O0 -O2`, `PASS <id> <detail>` — a custom text baseline.
- `tools/accept.sh` → `PASS <section>` / `FAIL <section>` + a tail of the log.
- diagnostics → one prose line.

Every one of these is trivially representable as JSON and every one of them is consumed by an AI in
a pipeline. `guide --json` proves the project can emit clean JSON; it is the only place it does.
Combined with E1 this is the single largest ergonomic lever in the audit.

---

## C4 — The differential oracle is three programs (S3, M)

`tests/diff/` holds `arith`, `arrays`, `strings` — each a `.logos` file, a hand-written `.c` twin, and
both compiled and compared against gcc at `-O0` and `-O2`. Good design (gcc, not clang, so the oracle
shares no backend), thin coverage: no generics, closures, enums, optionals, results, threads, or
struct layout cases.

The corpus covers those semantics against *expectations the project wrote itself*; the oracle is what
checks the project's beliefs against another compiler. Three programs is a floor, not a corpus.
Cheap expansion: one twin per `examples/` program is already close (matrix has `matrix_ref.c`), and
enum/payload/struct-padding cases are the highest-risk untested area (C layout is a compatibility
promise).

---

## C5 — No coverage measurement (S3, M)

Nothing measures which lowering or checker paths the 309 corpus cases and 480 suite cases actually
execute. For a compiler this matters more than usual: a form the corpus does not exercise is a form
whose `-O0`/`-O2` parity and memory safety are unverified, and the project's fourth invariant (*"no
form the checker accepts may be unimplemented in the backend"*) is exactly a coverage claim.

There is no instrumentation to bolt coverage onto the Logos compiler itself (it compiles through
clang), so the practical approach is source-level: count forms emitted per corpus run, or use
`llvm-cov` on the IR-built binary. Either way the deliverable is a number that can regress.

---

## C6 — No fuzzing or property tests (S3, M)

`fmt` idempotency is checked, which is a property test over a fixed corpus. Beyond that:

- no random-program generator (the design mentions *"an optional fuzz generator"* as left to the
  builder — it was not built);
- no round-trip property (`fmt → parse → fmt` equals `fmt`) over generated input;
- no lexer/parser robustness fuzzing on malformed bytes;
- no property test that a rejected program never produces a binary, or that an accepted program
  never panics with a runtime code the corpus does not expect.

For a language whose whole premise is trustworthy machine authorship, a fuzz corpus is the cheapest
way to find the class of bug the deterministic tests structurally cannot.

---

## C7 — Nothing tests the v1 promise (S1, M)

The promise is: *a stranger obtains `logosc` and compiles a program*. No gate touches it, because
there is nothing to obtain (D1). Verified: a build outside a checkout exits 1.

**This is the gate that defines v1** and it must exist before the release, not after. Its shape:

```sh
# clean container, nothing but the artifact
<single documented install command>
logosc version                              # V1-02
cd /tmp && logosc build hello.logos -o hello && ./hello   # V1-03
cd /tmp && logosc build uses-io.logos                     # V1-04
logosc build bad.logos --json | jq -e '.diagnostics[0].code'   # V1-10
```

Every one of those lines currently fails. That is the acceptance test for the install workstream,
and it should become gate 7 in `pr_gate.sh` the moment the install path exists.

---

## C8 — The gate is one hour with no documented fast path (S3, S)

The CI job's budget is 90 minutes for six gates (the workflow says so). Locally, `pr_gate.sh` runs
everything. Meanwhile `--only regress` finishes in 3.5 seconds and `--only exec --opt -O0` is a
one-category run.

An agent iterating needs two documented loops: a **seconds-scale** loop (`test --only regress`,
`fmt`, `guide --check`) and the full gate before a PR. That is a `CONTRIBUTING.md` paragraph and an
`AGENTS.md` line, not a new tool.

Related: `make test` is the only target that runs the contract tests, and it also runs three full
suites. A `make contract` target already exists separately — say so.

---

## C9 — Uneven case ids (S4, S)

Ids like `regress/vec-foreign-struct/program/program` (directory `program/` containing
`program.logos`) read poorly in a text report and complicate a future JSON report's schema. Cosmetic
now; fix opportunistically when C3 lands.

---

## What should NOT change

- **The floors.** Every section asserting it examined ≥ 1 item is why a pruned checkout fails loudly
  instead of passing over nothing. Preserve this pattern in any new gate (especially C7).
- **The baseline's refusal to compare.** A `summary.txt` without an `OPTS` line is refused rather
  than silently ungating the leak total. Keep that semantics; add a JSON baseline alongside, never
  instead.
- **The regress requirement** (a fix ships with a case that fails before it). 33 cases today, all
  green. This is the strongest cultural norm in the repo.
- **The stage-0 currency check.** The gate compares the stage-0 with the binary it produces, because
  byte-equality alone cannot see a stale bootstrap. Any change to how the compiler is built must keep
  that check.

---

SOURCES (LAYER 2 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Register rows C1-C9 with severity, effort and owner.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/v1-acceptance-criteria.md`
 -> The criteria these gates must ultimately prove (V1-10, V1-11, V1-12, V1-15, V1-18).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> P14 (regress run, 33/33 in 3.5 s), P5-P8 (CLI behaviours nothing pins), P7 (build outside a checkout).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/doc-contradictions.md`
 -> The AGENTS.md / README text against `Makefile:17-22` that C1 is about.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/tools/pr_gate.sh`
 -> The six gates as executed, plus the DCO precondition and the ordering rule that keeps six gates documented.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/tools/accept.sh`
 -> The seven end-to-end sections and their per-section floors.
