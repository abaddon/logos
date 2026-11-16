# L1 — Findings: what stands between this compiler and v1

**Audit of commit `9194412`, 2026-11-15.** Full backlog in [`gap-register.md`](gap-register.md);
criteria in [`v1-acceptance-criteria.md`](v1-acceptance-criteria.md).

---

## 1. The compiler is finished. The product is not.

Every engineering claim in `README.md` survives inspection. The corpus is 309 cases and runs at
`-O0` and `-O2` **compared against each other**, not merely against an expectation. The compiler is
written in its own language and reaches a byte-identical fixed point. Two builds of the same input
produce the same binary — I verified this: `sha256sum` of two independent builds of
`examples/hello.logos` is `e0d4a8a1…` both times. Diagnostics carry codes and node paths. Ownership
rules are enforced by the compiler, not hoped for. This is not a prototype.

What does not exist is everything between that binary and a stranger:

- **It cannot leave the repo.** `./build/logosc build hello.logos` from `/tmp` exits 1 with
  `logos: runtime not found: logos/runtime/rt.c` — the runtime path is resolved against the working
  directory. So is the standard library: in an isolated directory `(use map)` is
  `E0005: unknown module 'map'`.
- **Nothing to install.** `pyproject.toml`, `setup.py` and `tools/verify_install.sh` were removed
  with the Python compiler (as was correct — no second compiler should exist). Nothing replaced
  them. There is no archive, no registry entry, no `make install`.
- **Never released.** `git tag` is empty. There is no release workflow, no CHANGELOG, and the
  version lives as the literal `logos 0.1.0` inside `src/logosc/main.logos`.
- **Private.** The project ledger records the blocker in one sentence: *"the repository is private,
  so nobody finds it"*. Until that changes, "adopted by any AI" is not a goal, it is a wish.

## 2. The single biggest ergonomic gap is the one the project was built to avoid.

Logos exists because *"a model can read and write the language without guessing"* and because every
diagnostic carries a code and a node path. That machinery is real — `p/main/3/0: E0304: a ref
argument must be a mutable binding, and 'k' is not` is a genuinely good error.

It is delivered as **a line of prose on stderr**. The only JSON the product emits is
`logosc guide --json` (a seven-key manifest of forms, types, operators, builtins, reserved names,
diagnostic codes and test categories — valid, useful, and the model for what the rest should look
like). An AI consuming this compiler has to parse text to find `E0304`, to find the node path, to
find which file. Every other consumer in the pipeline gets structure; the diagnostic channel does
not. Closing that gap (E1) is a day of work and changes the character of the product more than any
compiler feature on this list.

The same asymmetry repeats at the boundary:

| Surface | Machine-readable today | Should be |
|---|---|---|
| `guide` | ✅ JSON manifest | keep, add `schema_version` (E9) |
| diagnostics (`build`/`check`/`resolve`) | ❌ one stderr line | `--json` with `{code, severity, node_path, file, line, col, message}` (E1) |
| `test` results | ❌ `PASS id -` text | JSON report + the same schema (C3) |
| exit status | ✅ 0/1/2 exist | ❌ undocumented, and 2 means two different things (E2) |
| version | ❌ a constant, no flag | `--version` / `version --json` (E5) |
| IR | ✅ `.ll` always written | keep — this is the best debugging affordance in the product |

## 3. The language has one blocker, and the project already designed the fix.

Names are global across the whole program: two modules each declaring `point` is
`E0003: duplicate definition 'point': qa/point and qb/point`. The design document for the fix opens
by naming the consequence: *"Any program of size therefore has to enforce a naming discipline by
hand, which is a language constraint, not a program's choice. This is the thing that makes Logos
hard to adopt."*

That document (`docs/superpowers/specs/2026-11-15-module-qualified-names-design.md`, status *for
approval*) is unusually good: eleven decisions, the accepted cost, the one real risk (the type map
is name-keyed and becomes a silent miscompile if this lands half-done), and five acceptance
criteria. It has no implementation. **This is the highest-value language work available and it is
already specified** — the remaining job is execution, not design.

## 4. Node addressing stops at reading.

Design goal #3: *"Every node is addressable by a stable path, so a change is a patch to one node,
not a rewrite of the file."* `logosc show <file> <path>` works and is tested. `logosc patch` is
specified in the same section of the design, was implemented on the Python compiler (ledger, Wave
B2: *"show/patch on real node paths"*), and is **deliberately absent** from the Logos port —
`src/logosc/main.md` line 30: *"`patch` is deliberately absent"*.

Verified: `logosc patch x.logos hello/main/2` → `invalid choice: 'patch'`, exit 2.

So the AI can address the node it must change and then has no tool to change it. Either `patch`
returns for v1 (S2, ~3 days) or the design goal is formally withdrawn — leaving it in the spec while
the tool refuses the verb is the worst of both.

## 5. Documentation is strong where it is hardest, and missing where it is easiest.

`docs/LOGOS.md` is genuinely impressive: 20 executable chapters, a cheat sheet, a forms table with
arities, a 34-entry diagnostic code table, and `guide --check` proving it cannot drift from the
compiler. That is better than most language docs.

What it does not contain is **the tool**: no chapter on `build`/`test`/`fmt`/`show`/`guide`, their
flags, their exit codes, their streams, or where the IR lands. `README.md` covers usage in 10 lines
and overstates v1 status in the first sentence of Status. `AGENTS.md` is a superb contributor
contract and says nothing to an AI that *has* an installed compiler.

Four specific falsehoods, each one sentence to fix:

1. `README.md:40` — *"Logos v1 is complete for one target"* — while D1-D5 are open.
2. `README.md:49-50` — the suites run *"each at both levels"*; `make test` runs `-O0` only
   (`Makefile:17-22` says exactly why, and `make suites-all` is the two-level form).
   `AGENTS.md` repeats the false version.
3. `README.md:241` — the file ends with a bare `Not chosen yet.` left over from the licence
   question, directly under an MIT licence statement.
4. `CONTRIBUTING.md:39` — `python3 -m unittest tests.test_gen2_build` — that test file does not
   exist; the bug template's placeholder command is `python3 -m logos build`, also deleted.

Plus the design spec, which still says self-hosting is a **non-goal** and *"`logosc` is Python in
v1"* — the opposite of what the repository now is.

## 6. The gates are the strongest part of the project and they have one shape of blind spot.

Six gates run locally (`tools/pr_gate.sh`) and in CI, with a DCO precondition, a documented floor on
every section, a baseline that refuses to compare rather than fail open, and a stage-0 binary whose
hash is checked before any build. That is a better quality system than most released compilers have.

What the gates cannot see:

- **the CLI**, because the tests that pinned it were Python and went with the Python compiler (C2);
- **the install**, because there is none (C7);
- **coverage**, because nothing measures it (C5);
- **their own documented claim**, since `make test` is described as two-level and is one (C1).

The gap list is therefore not "add more tests" — it is "pin the contract that exists and prove the
one thing v1 actually promises".

## 7. What an AI consumer needs that no human-first checklist would ask for

Judged only by *does this make an AI's life easier*:

1. **A JSON diagnostic on the first failure, not a text line** (E1). Highest ratio of value to effort on this list.
2. **A documented exit-code contract** (E2) — an agent branches on status; ambiguous 2 breaks retry logic.
3. **Deterministic, reproducible output** — already true, unpublished. Say it in the release notes and in `AGENTS.md`; it is a selling point that costs nothing.
4. **`--emit=ir` and `run`** (E6) — an agent debugging a miscompile wants the IR without knowing a path convention.
5. **A stdlib that can parse a number** (A4) — the first realistic program needs `str`→`i64`.
6. **A machine-readable test report** (C3) — so one agent can gate another agent's PR without prose parsing.
7. **A schema `version` on the manifest** (E9) — the cheapest possible forward-compatibility promise.

## 8. Recommended order, and why it is this order

1. **Decisions first** (D5 public/private, D7 distribution format, A2 patch, A7 comments,
   E10 text-as-contract). All are free today and all constrain weeks of work if deferred.
2. **Installable** (D1→D2→D3→D10→D6→C7) — nothing else can be tested by an outsider until this works, and C7 makes every later step verifiable.
3. **Machine-readable** (E1→E9→E2→C2→C3) — the differentiator; small effort, large effect.
4. **Language blockers** (A1→A2→A3→A4) — A1 is designed; A2 is a design decision first.
5. **Publish** (D4→B8→D8→D7→release).
6. **Docs correction in parallel** (B2-B9), with B4 (spec contradiction) early because the spec is
   currently cited as authority for `patch` and against self-hosting.

## 9. The one-sentence version

The compiler is ready; the product around it is not. Seven blockers, none of them architectural, all
of them about reaching a consumer: no install, no runtime resolution outside the repo, no release,
a private repo, no JSON diagnostics, and a global namespace the project has already designed its way
out of.

---

SOURCES (LAYER 1 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> The full 46-gap register with severity, effort, owner and evidence link per item; the stopping condition is in the sibling criteria file.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/v1-acceptance-criteria.md`
 -> 18 testable criteria with the command that proves each — the definition of "shipped".

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> The measurements behind sections 1, 4, 5 and 6: exact commands, exact output, exit codes.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/doc-contradictions.md`
 -> The quoted spec/README/AGENTS/CONTRIBUTING text that section 5 cites, with file and line.
