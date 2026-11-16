# Coverage — the measured numbers, and what they do not mean

Everything below was measured on this branch with the compiler built from
`src/` (`tools/logosc.sh` refuses to run a stale binary, so the numbers are the
source's, not the bootstrap's).

## The numbers

| Measure | Value | Gate |
|---|---|---|
| Published diagnostic codes (`logosc guide --json`) | **35** | `test_every_published_code_is_exercised` |
| Codes exercised from `tests/` | **34** | same |
| Codes with no reachable emitter | **1** (`E0201`) | registered in `tools/qa-known-gaps.txt` |
| Negative fixtures (`*.expect` sidecars) | **147** | `test_the_sweep_covers_every_sidecar` |
| Fixtures the compiler agrees with | **143** | `test_every_negative_fixture_is_judged_by_the_compiler` |
| Fixtures registered as disagreeing | **4** | same, minus the register |
| Corpus cases | **315** | `test_every_category_is_at_or_above_its_floor` |
| Corpus cases executed at both `-O0` and `-O2` | **315** (all) | gate 2 |
| Compiler suite cases (`src/logosc/*_test.logos`) | **686** across 9 files | `test_a_suite_cannot_lose_its_cases` |
| Compiler suites run by the gate | **9 of 9** (was 3 of 9) | `test_every_compiler_suite_is_run_by_the_gate` |

## The finding this pass exists for

`src/logosc/harness.logos` (`h-file-parsed`) treats a file with a `*.expect`
sidecar like this:

```logos
(let f h-found (h-expected nodes ntexts path))
(if (> (str-len (get f problem)) 0)
  (h-fail base (get f problem) totals records)
  (if (> (str-len (get f code)) 0)
    (h-pass base totals records)          ; <-- a sidecar is a PASS
    (h-tests self path cat rel nodes ntexts opts totals records))))
```

A well-formed sidecar — one line, a code matching `[ER][0-9]{4}` — is a **PASS**.
The corpus never builds the file. The judgement of those fixtures lives in
`tools/selfhost.sh` (its resolver phase for `tests/parse`, its checker phase for
the 126 fixtures in `tools/selfhost-check.txt`), which is the sixth gate, and it
runs `gen2` — a compiler built from this source — which is fine as a mechanism.

What fell out of that seam:

- **6 sidecars were judged by no gate at all**, because they are under neither
  `tests/parse/` nor `tools/selfhost-check.txt`: `tests/generics/limit.logos`,
  `tests/generics/unbound.logos`, `tests/regress/generic-vector.logos`,
  `tests/regress/owner-place-read.logos`,
  `tests/regress/struct-owner-mismatch/program.logos`, and (added by this pass)
  `tests/type/unknown-field.logos`.
- **3 of them disagree with the compiler** — see
  [`../03-dossiers/negative-fixture-audit.md`](../03-dossiers/negative-fixture-audit.md).
  One claims `E0500` and the compiler accepts the program at both levels; one
  claims `E0402` and gets `E0104`; one claims `E0402` and gets nothing from
  `check`.
- **`E0201` is published and unreachable.** `logosc guide --json` lists it as
  "field type mismatch", and no code in `src/` emits it: a struct field type
  mismatch is reported as `E0100` (measured:
  `(make point "not a number")` → `E0100: field 'x' of 'point' expects :i64,
  found :str`). An agent that branches on `E0201` is branching on a string that
  cannot occur.
- **6 of the compiler's 9 unit suites were run by nothing.** `tree_test`,
  `types_test`, `emit_test`, `fmt_test`, `harness_test` and `lex_test` — 206
  cases, all passing — existed in the repository and appeared in no Makefile
  target, no script and no workflow. `make test` ran body/check/resolve only.

## What changed

1. `tests/test_qa.py` builds **every** negative fixture with `build --json` and
   compares the emitted code with the sidecar. That is the missing negative
   suite, and it runs in seconds.
2. `make test` now runs **all nine** compiler suites. `tests/test_qa.py` fails
   when a tracked `src/logosc/*_test.logos` is missing from `LOGOS_SUITES`, so a
   tenth suite cannot be added and forgotten.
3. Three fixtures and one code are registered rather than silently tolerated,
   each with its
   measurement and a rule that the register may shrink but not grow.
4. `E0201` is registered as a code-level gap. Fixing it is a compiler change
   (either emit it or unpublish it) and is not part of this pass.

## What these numbers do not mean

- **34/35 is not "the checker is 97% tested."** It is "every published code is
  reached by at least one case". A single case per code is a floor, not a
  corpus; the count of cases per code ranges from 1 (`E0401`) to 25 (`E0305`).
- **The corpus floor is a count, not a strength measure.** It catches deletion,
  which is the failure mode that matters (a case removed to make a gate green).
- **There is no line-coverage number.** The compiler emits IR and shells out to
  clang; instrumenting *it* would mean maintaining a second build system to
  measure a proxy. The three measurable contracts above were chosen instead —
  see [`quality-gates.md`](quality-gates.md) for why.
- **The differential suite is 3 programs.** `tests/diff/` checks this compiler
  against gcc for arithmetic, arrays and strings. Ownership, results, optionals,
  closures, enums and threads are checked only against expectations this project
  wrote. That is the largest remaining epistemic gap in the suite, and it is a
  design decision (the C twins are hand-written), not an oversight.

SOURCES (LAYER 2 — NAVIGATION)

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/03-dossiers/negative-fixture-audit.md
 -> The per-fixture table: what each disagreeing case claims, what the compiler
    emits, and the command that produced it.

/root/ai-language-program/.worktrees/t_5bd6660b/docs/qa/03-dossiers/gate-run-log.md
 -> Raw output of the corpus, contract, acceptance and self-hosting runs this
    pass rests on.

/root/ai-language-program/.worktrees/t_5bd6660b/src/logosc/harness.logos
 -> `h-file-parsed`, the four lines that turn a sidecar into a PASS.

/root/ai-language-program/.worktrees/t_5bd6660b/tools/selfhost.sh
 -> The resolver phase (lines ~500-560), which is where parse-error fixtures are
    materialized and judged, and the checker phase.
