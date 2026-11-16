# L3 — Documentation contradictions

Every written statement in the repository that the tree contradicts, quoted with file and line, plus
a verdict on which side is wrong. Documentation that is merely thin belongs in
`02-analysis/b-documentation.md`; this file is only for statements that are **false**.

Why it matters more for this project than for most: the stated consumer is an AI, and an AI reads the
spec first and the tree second. A false statement in `README.md` or the design spec does not annoy a
reader — it produces confidently wrong work.

---

## 1. "Logos v1 is complete"

> `README.md:40` — "Logos v1 is complete for one target: x86_64 Linux. The language, the compiler and
> the test harness are built, reviewed, and green."

**Contradicted by:** D1-D5. There is no install artifact, no tag, no release, and the repository is
private. The *language and compiler* are complete; the *product* is not, and the sentence says "v1".

**Which side is wrong:** the README. The following four paragraphs (309 corpus cases, 361/81/38 suite
cases, seven accept sections, 24 contract tests, the fixed point) are all true and verified. Delete
the word "complete", state the seven blockers, and the section becomes the strongest part of the
file.

---

## 2. The suites run at both optimisation levels

> `README.md:49-50` — "The compiler's own suites run through the same binary: 361 `body_test` cases,
> 81 `check_test` cases and 38 `resolve_test` cases, **each at both levels**."
>
> `README.md:196` — "`make test` # 24 contract tests, then the compiler's own suites at `-O0` and `-O2`"
>
> `AGENTS.md:52` — "and the compiler's own suites (`body_test`, `check_test`, `resolve_test`) at
> `-O0` and `-O2`."

**Contradicted by:** `Makefile:17-22` and the target itself:

```make
# The compiler's own suites restate what the deleted white-box tests covered:
# 361 body cases, 81 checker cases and 38 resolver cases. They run at `-O0` in
# the gate because every case lowers and links its whole module, which makes two
# levels a ninety-minute gate; the corpus already runs all 309 language cases at
# both levels, and `make suites-all` is the two-level form.
test: contract suites

suites:
	$(LOGOSC) test src/logosc/body_test.logos --opt -O0
	$(LOGOSC) test src/logosc/check_test.logos --opt -O0
	$(LOGOSC) test src/logosc/resolve_test.logos --opt -O0
```

`make suites-all` is the two-level form, and no gate runs it.

**Which side is wrong:** the documentation, in three places. The Makefile comment is the honest one.
Note the *corpus* (309 cases) genuinely does run at both levels and compares them — so the claim is
true of one thing and falsely transferred to another, which is exactly the kind of error that survives
review. Fix: document both targets and state that the gate runs the single-level one for time.

---

## 3. "Logos has no comments" vs. design goal #2

> `src/std/io.md` — "Logos has no comments and no doc form, so this file is the header documentation
> the source cannot carry."

**Contradicted by:** `docs/superpowers/specs/2026-11-06-ai-language-design.md:20-22` — design goal
#2: *"Every definition carries its type, its contract and its tests in one place, so an AI reading
one node needs no other file."*

A definition carries its type and its tests (both are grammar); its **contract lives in a sibling
`.md`** that the node cannot reference. For the compiler's own modules the convention works — 15
`.md` files, consistently written. For a consumer's module it means intent is unrecordable.

**Which side is wrong:** neither, quite — the goal is unachieved and the omission is undocumented in
the spec. This is A7: a decision to record, not a bug to fix.

---

## 4. The design of record declares self-hosting a non-goal

> `docs/superpowers/specs/2026-11-06-ai-language-design.md:34` — "Self-hosting (`logosc` is Python in
> v1). It is a later project."
>
> `…:469-470` — "The compiler is a Python package with one entry point, runnable as `python3 -m
> logos` and installed as `logosc`."

**Contradicted by:** the entire tree. `src/logosc/*.logos` is the compiler; `bootstrap/logosc` only
bootstraps it; `bash tools/selfhost.sh` proves gen2 == gen3 byte for byte; there is no Python package
and no packaging at all.

**Which side is wrong:** the spec is stale — not wrong when written. Three later waves (W0-W9) changed
the answer, and no amendment was made. The spec still opens "Status: for approval".

---

## 5. The design promises `patch`; the tool refuses it

> `…:432-435` — "`logosc patch <path>` accepts a replacement subtree, rewrites only that node — or that
> token — and then reformats the whole file, so what `patch` writes is exactly what `fmt` would write
> and every other node keeps its path."
>
> `…:24` (goal #3) — "Every node is addressable by a stable path, so a change is a patch to one node,
> not a rewrite of the file."
>
> `src/logosc/main.md:30` — "`patch` is deliberately absent: see 'The usage block' below."

**Contradicted by:** probe P3 — `invalid choice: 'patch'`, exit 2. The ledger records the verb working
on the Python compiler (Wave B2: *"show/patch on real node paths"*).

**Which side is wrong:** both are internally consistent and they disagree with each other. The port's
reasoning (`main.md`: the verb is used by nobody in the gate and is a developer convenience) is
defensible for a gate; it is not defensible against a published design goal. **A ruling is required**
(A2, V1-07): reinstate the verb, or strike the goal from the spec.

---

## 6. Diagnostics promise the minimal subtree; the tool prints one line

> `…:462-463` — "Diagnostics carry: path, a code (`E0421`), one sentence, and **the minimal
> subtree**. No advice, no prose."

**Contradicted by:** probe P6 — `t/main/2/0: E0100: '+' needs numbers, found :str`. Path and code:
yes. One sentence: yes. No advice or prose: yes. **Subtree: never** — no diagnostic site emits it,
and the emitter that would is not called from the failure paths.

**Which side is wrong:** the implementation dropped a specified field, probably deliberately (printing
a subtree requires a tree at every failure site, and lexer failures have none). Note this is a good
argument *for* E1: the JSON envelope has a natural `node_path` field and, once the tree is in hand, a
`subtree` field that the old text format had no way to carry.

---

## 7. The design says imported functions cannot be lowered

> `…:366-374` — "v1 lowers one module at a time, and a body is emitted only for a definition in the
> module being compiled. An imported *function* therefore has no symbol in the object being built,
> and a call to it is `E0103` `imported functions are not lowered yet`, naming the function."

**Contradicted by:** probe P15 — a two-module program (`(use lib)` + `(twice 21)`) builds and prints
`42`. The compiler itself is a multi-module unit; `main.md` §"Loading the unit" documents loading
every module and lowering the whole set.

**Which side is wrong:** the spec (stale since W7). Consequence worth noting: this is the reason A1
is now on the critical path — multi-module programs are real, so the global-namespace limit is real.

---

## 8. CONTRIBUTING runs a test file that does not exist

> `CONTRIBUTING.md:39` — "```sh python3 -m unittest tests.test_gen2_build -v ```"

**Contradicted by:** `ls tests/test_*.py` →
`tests/test_contributing.py`, `tests/test_runtime.py`, `tests/test_selfhost.py`. Nothing else. The
Makefile's `CONTRACT_TESTS` names the same three.

**Which side is wrong:** CONTRIBUTING.md. The file was deleted with the Python compiler; the example
was not updated.

---

## 9. The bug template's example command invokes a deleted compiler

> `.github/ISSUE_TEMPLATE/bug.yml:31` — `placeholder: python3 -m logos build repro.logos`

**Contradicted by:** there is no `logos` Python package. The command is `logosc build repro.logos`.

**Which side is wrong:** the template. Low severity, high embarrassment: it is the first thing a
reporting agent sees, and it teaches a command that fails.

---

## 10. The README ends mid-thought on the licence

> `README.md:236-241` — "## License / MIT. See `LICENSE`. By opening a pull request you agree to
> license your contribution under these terms. / **Not chosen yet.**"

**Contradicted by:** `LICENSE` exists and is MIT. The ledger records the deferral: *"Deferred to
Stefano: public vs private, and the licence"* (`docs/history/build-ledger.md:277`).

**Which side is wrong:** the README — a leftover line from before the decision. Delete it, or move
the still-open part (visibility) into a Status note.

---

## 11. `Makefile clean` cleans artefacts that no longer exist

> `Makefile:42` — `rm -rf build dist *.egg-info`

`dist/` and `*.egg-info` were Python packaging output. Nothing produces them now.

**Which side is wrong:** the Makefile. Harmless (`rm -rf` of an absent path succeeds), but it is the
same fossil as #8 — evidence that the Python removal was not finished, which is what an agent uses to
estimate how much else might be stale.

---

## 12. `--keep-ir` is accepted and does nothing

> `src/logosc/main.md:45-46` — "`--keep-ir` is accepted and changes nothing, because the IR is always
> kept."

This one is documented honestly and is still a trap: a flag whose only purpose is compatibility with a
deleted tool, on a tool that has no per-verb help (E3) to explain it. Not a contradiction — a fossil
worth removing once E10 is decided.

---

## Summary of which document to trust, and for what

| Question | Trust |
|---|---|
| What does the language accept? | `docs/LOGOS.md` — generated, drift-gated, examples executed. Nothing here is falsified. |
| What does the compiler do *today*? | `src/logosc/*.md` module contracts + the tree itself. |
| Why is it shaped this way? | `docs/history/build-ledger.md` — the rulings, in order, including deferred minors. |
| How do I contribute? | `AGENTS.md` — accurate except the suite-levels claim (#2). |
| What is v1 supposed to be? | `docs/superpowers/specs/2026-11-06-…md` — **stale in four places** (#4, #5, #6, #7). Read with this file open. |
| Is it ready to release? | `README.md` — **no** (#1). Use `docs/00-index.md` instead. |

---

SOURCES (LAYER 3 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> The measurements (P3, P6, P15) that falsify statements 5, 6 and 7.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/repository-inventory.md`
 -> The file listing that falsifies statements 8, 9 and 11.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/02-analysis/b-documentation.md`
 -> What to write, where, and in what order — the constructive counterpart to this list.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Register rows B3, B4, B5 and A2, which this file provides the quotations for.
