# L2 (b) — Documentation: what is missing, and what is false

Two different problems, often confused. **Missing** documentation costs an agent time. **False**
documentation costs it trust — it acts on a statement that is not true, and worse, an agent that
reads `README.md` and the design spec together gets two incompatible pictures of the same project.

Gap IDs: **B1-B9** (and B3/B4/B5 have direct descendants in the gate/CLI dimensions).

---

## What exists

| Artifact | Size | Quality | Audience |
|---|---|---|---|
| `docs/LOGOS.md` | 932 lines, 20 chapters + reference | **Excellent** — generated from compiler tables, every example executed by the harness at both optimisation levels, drift impossible (`guide --check` is a gate) | language user |
| `docs/manual/*.logos` | 20 chapter sources | Good — executable | contributor |
| `AGENTS.md` | 6.9 KB | **Excellent** — precise, gate list, invariants, bootstrap procedure, PR rules | contributor agent |
| `CONTRIBUTING.md` | 4.3 KB | Good, one stale command | human contributor |
| `README.md` | 12.4 KB | Strong on design and limits, **overstates status**, one dangling line | evaluator |
| `src/logosc/*.md`, `src/std/*.md` | 15 files, ~4-40 KB each | Unusually thorough per-module contracts — they encode decisions, alternatives and limits | compiler contributor |
| `docs/history/build-ledger.md` | 35 KB, 277 lines | The real architectural history: every ruling, every deferred minor, the review verdicts | maintainer |
| `docs/superpowers/plans/*.md` | 34 files | Working reports, mostly historical | maintainer |
| `docs/superpowers/specs/*.md` | 3 files | Two current-ish, one **actively contradicted** by the tree | decision maker |

This is a better-documented project than most released compilers. The gaps below are what it does
not cover, not a general criticism.

---

## B1 — No documentation index (S3, S) — *closed by this pyramid*

Before this audit, `docs/` had no entry point. 34 plan reports, 3 specs, a 35 KB ledger, 15 module
contracts and one generated manual, with no map. An agent landing in the repo had to choose between
reading `README.md` (which overstates) and `docs/LOGOS.md` (which is a language manual, not a
project guide).

`docs/00-index.md` now serves that role for this audit; a v1 should grow a proper `docs/README.md`
that indexes the manual, the specs, the module contracts and the release notes.

---

## B2 — The manual documents the language but not the tool (S2, M)

The single most consequential documentation gap. `docs/LOGOS.md` is a language manual. It contains
no chapter on:

- the eight verbs and their flags;
- exit codes (`0`/`1`/`2` with two distinct meanings of `2`);
- which stream each message goes to;
- where the IR and the binary are written (`build/<stem>.ll`, `build/<stem>`);
- what a diagnostic line looks like (`path: CODE: message` vs `file:line:col: CODE: message`);
- the corpus categories and directives;
- that two verbs (`resolve`, `check`) are absent from `--help` but work.

An AI that reads the manual end-to-end can write correct Logos and still not know how to run it,
how to interpret a failure, or how to find the IR. Meanwhile `README.md` §Usage covers ten commands
in ten lines and `main.md` — the authoritative CLI contract — is a 661-line design document for
compiler contributors, not a user manual.

**What v1 needs.** One manual chapter (21) covering the CLI: verbs, flags, exit-code table, streams,
artefact locations, diagnostic formats, and one worked error example with expected output.

---

## B3 — README overstates status, and its own claims contradict the Makefile (S2, S)

Four problems in a 241-line file:

1. **Line 40:** *"Logos v1 is complete for one target: x86_64 Linux."* It is not complete — nothing
   can be installed, the repo is private, there is no release (D1-D5). The Status section then
   lists genuinely verified execution results (309 cases, 361+81+38 suite cases, seven accept
   sections) which are *true* and are undercut by the sentence above them.
2. **Lines 49-50:** the compiler's own suites run *"each at both levels"*. The shipped target does
   not: `Makefile:17-22` says they run at `-O0` in the gate *"because every case lowers and links its
   whole module, which makes two levels a ninety-minute gate"*, and `make suites-all` is the
   two-level form. `AGENTS.md` repeats the false claim in its own words.
3. **Line 241:** the file ends with `Not chosen yet.` immediately after "License: MIT" — a leftover
   from the unresolved licence question (ledger: *"Deferred to Stefano: public vs private, and the
   licence"*). It makes the licence look undecided in a repo that ships `LICENSE`.
4. **Line 100-101:** *"`bootstrap/logosc` is an x86_64 Linux binary, so another platform needs a
   stage-0 built where the compiler already runs"* — correct, but it appears only under Known
   limits, not under Requirements, where a consumer looks.

**AI lens.** An agent that reads Status and believes "v1 is complete" will attempt a release
procedure that does not exist, then write its own install script — the exact wrong behaviour.

---

## B4 — The design spec contradicts the implementation (S2, M)

`docs/superpowers/specs/2026-11-06-ai-language-design.md`, status *"for approval"*, is still cited
as the design of record. Three of its statements are now false:

| Spec says | Reality |
|---|---|
| Non-goals: *"Self-hosting (`logosc` is Python in v1). It is a later project."* | The compiler has been self-hosted since the W7 cutover and reproduces itself byte for byte |
| §Compiler: *"The compiler is a Python package with one entry point, runnable as `python3 -m logos` and installed as `logosc`."* | No Python, no package, no install |
| §Addressing: *"`logosc patch <path>` accepts a replacement subtree, rewrites only that node…"* | The verb is deliberately absent (A2) |

A fourth statement is aspirational rather than false: *"Diagnostics carry: path, a code, one
sentence, and **the minimal subtree**."* The compiler never emits the subtree — and this is a good
argument for E1 (JSON diagnostics), since the spec already reserved structure the current text
format throws away.

**The fix is cheap and high-value:** an amendment section in the spec recording (i) self-hosting
achieved, (ii) packaging moved to a self-hosted binary distribution, (iii) `patch` status pending
decision, (iv) diagnostics format as implemented. Without it, every agent that reads the design
before the code builds a wrong mental model. Note the *module-qualified-names* design is a model of
how to do this well: it records decisions, accepted costs and risks explicitly.

---

## B5 — Stale references to the deleted Python compiler (S2, S)

Four files still instruct readers to run a compiler that no longer exists:

| File | Line | Text | Reality |
|---|---|---|---|
| `CONTRIBUTING.md` | 39 | `python3 -m unittest tests.test_gen2_build -v` | `tests/test_gen2_build.py` does not exist; only `test_contributing.py`, `test_runtime.py`, `test_selfhost.py` do |
| `.github/ISSUE_TEMPLATE/bug.yml` | placeholder | `python3 -m logos build repro.logos` | should be `logosc build repro.logos` |
| `Makefile` | 42 | `clean:` removes `dist *.egg-info` | no Python packaging remains; the target should clean `build/` only (it already does) |
| `README.md` | 57 | *"The suites that diffed the compiler against the Python implementation went with it."* | true, but reads as an aside — the removal deserves one line in the release notes |

Each is a one-line fix. Individually trivial; collectively they tell an agent that the removal was
not finished, which is exactly the kind of signal an agent uses to decide how much to trust
documentation.

---

## B6 — `AGENTS.md` is a contributor contract, not a consumer contract (S2, M)

`AGENTS.md` answers "how do I change this compiler safely" with exceptional precision: the six
gates, the bootstrap procedure and why byte-equality alone cannot catch a stale stage-0, the regress
requirement, the four invariants, the generated-manual rule, the PR conventions.

It does not answer "I have `logosc`; now what". There is no:

- install/verify step for a consumer;
- minimal program + build + run + exit-code example;
- diagnostic format reference (what the code, the path and the stream mean);
- statement of determinism/reproducibility guarantees (which are real and are a selling point);
- pointer to where the IR is and why an agent should read it when a program misbehaves.

Since **the stated consumer of this project is an AI**, the file whose name literally addresses
agents should be written for both roles — contributor and consumer — with a clear split.

---

## B7 — No standard library API reference (S2, M)

`src/std/*.md` are module design documents: rationale, ABI reasoning, limits, and test descriptions.
They contain API tables (e.g. `io.md` has a five-row table) but they are buried in prose and are not
reachable from the manual. Grep of `docs/LOGOS.md` for the three public module names returns one
incidental hit.

An AI needs a flat reference: module, function, signature, semantics, error/panic behaviour, one
example. Twenty-one rows today. It should be generated, not hand-maintained — `guide.logos` already
owns generated tables, so a `stdlib` section there makes the reference drift-proof by construction.

---

## B8 — No CHANGELOG, versioning policy or release notes (S3, S)

`git tag` is empty; the only version is the literal in `src/logosc/main.logos`. `main.md` says
bumping it *"means changing `main-version` and nothing else"* — which is true only because nothing
else reads a version.

**What v1 needs.** A `CHANGELOG.md` in Keep-a-Changelog form, a stated versioning policy (what makes
a breaking change in a language that refuses to break the four invariants?), and release notes that
carry the known limits and the deliberate refusals. The deliberate-refusal list is a genuine asset
in release notes: it tells a consumer what will never be "fixed".

---

## B9 — Known limits are scattered (S3, S)

`README.md` has six honest bullets. Beyond them, real limits live in ~34 plan reports and 15 module
documents: no comments (A7), the 90-second `(run)` child budget, mutex-after-thread-exit deadlock,
`(str)` never freed, an unjoined thread's allocations may be invisible to the leak report, `fmt` has
no `rglob` beyond `*.logos`-style patterns, case ids outside printable ASCII print differently,
`resolve` does not type-check, `check` reads no body, `wc` column widths depend on pipe vs file,
`strtod` conformance, the release-build quarantine caveat.

None of these are defects — all are documented somewhere. None are findable by an agent that has the
compiler and not the git history. **One page, linked from the manual, README and AGENTS.md.**

---

## Documentation work that is already right, and should not be touched

- `docs/LOGOS.md` is generated. Never hand-edit it (B-adjacent agents will try).
- The 20 chapters are executed by the harness. Adding prose without an executable example would
  weaken the guarantee — extend the chapter *and* the corpus.
- `src/logosc/*.md` contracts carry the "why" that the source cannot (no comments, A7). If comments
  are added to the language, these files become the migration target, not obsolete.
- The build ledger is the only record of *why* several rules exist. Preserve it.

---

SOURCES (LAYER 2 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Register rows B1-B9 with severity, effort and owner.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/doc-contradictions.md`
 -> The exact quoted text (file + line) for every contradiction summarised here: spec vs. tree, README vs. Makefile, CONTRIBUTING vs. tests, AGENTS vs. Makefile.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/repository-inventory.md`
 -> File inventory proving the sizes and the absence of `CHANGELOG`, `SECURITY`, `ARCHITECTURE`, a docs index and a consumer quickstart.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/LOGOS.md`
 -> The manual itself — read §Cheat sheet and §Reference to see the coverage boundary (language yes, tool no).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/history/build-ledger.md`
 -> The rulings that explain why several documented statements are deliberately what they are (licence deferral, patch removal, the one-hour gate).
