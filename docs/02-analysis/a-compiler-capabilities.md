# L2 (a) — Compiler capabilities vs. what v1 needs

What the language and compiler can do today, what a v1 release needs them to do, and the distance
between the two. Every "today" claim is measured or quoted; probes are in
[`../03-dossiers/probe-log.md`](../03-dossiers/probe-log.md).

Gap IDs: **A1-A8**.

---

## What exists (verified, not claimed)

| Capability | Status | Grounding |
|---|---|---|
| Prefix-form surface with one canonical spelling | present; `fmt` is a fixed point over every tracked `.logos` file | gate 5, `tools/selfhost.sh` |
| Types: 13 primitives, structs (C layout), fixed arrays, vectors, `res`, `opt`, enums with payloads, `fn`/`fn*`, `ptr`, `own`, `shared` | present | `docs/LOGOS.md` §Reference |
| Generics by monomorphisation, cap 256 | present (`E0500` at the cap) | `check.logos` |
| Closures confined to their creating frame | present (`E0502`) | design §Closures |
| Manual memory with move checking, leak tracker, `R0002`/`R0004` | present; 10 deliberate leaks baselined | `tests/summary.txt` |
| Threads, mutexes, channels, atomics over pthreads | present (`E0700` marks crossings) | `tests/thread/` |
| `extern` for the C ABI, closed crossing list | present | design §ABI and FFI |
| Multi-module programs, cross-module calls, linker-resolved symbols | **present** — verified: `(use lib)` + `(twice 21)` → builds and prints `42` | probe P15 |
| Tests as grammar (`(test …)`, `(expect …)`) | present; 309 cases, 8 categories | `tests/summary.txt` |
| Self-hosting with byte-identical gen2/gen3 | present | `tools/selfhost.sh` |
| Deterministic output for identical input | **present** — two builds, identical sha256 | probe P13 |
| IR kept beside every binary | present, always written | `src/logosc/main.md` |

There is no meaningful sense in which this compiler is a prototype. The gap list below is about
**reach**, not correctness.

---

## A1 — Names are global across the program (S1, L, backend-engineer)

**Today.** A type or function name must be unique across every module in the unit. Two modules
declaring `point` is refused:

```
E0003: duplicate definition 'point': qa/point and qb/point
```

**Why it blocks v1.** The project's own design document
(`docs/superpowers/specs/2026-11-15-module-qualified-names-design.md`, status *for approval*) opens
with it: *"Any program of size therefore has to enforce a naming discipline by hand, which is a
language constraint, not a program's choice. This is the thing that makes Logos hard to adopt."*
An AI assembling a program from several authored modules cannot guarantee global name uniqueness
without a cross-module grep, and a violated uniqueness rule fails the whole build.

**What v1 needs.** Module-qualified names (`mod.name`) with bare names still resolving when
unambiguous; ambiguity refused at the use, naming both candidates. The design specifies eleven
decisions, the accepted cost (three pinned resolver cases change meaning), and one real risk: the
lowerer's type map is name-keyed (`tnk/tnv/tnl`) and becomes a **silent miscompile** if the feature
lands without re-keying it. The design also names the precedence trap: three passes currently
disagree about own-vs-import order, which is harmless only while duplicates are refused.

**Effort/risk.** L; high blast radius; already designed, so no design time needed. Must land as one
change with the type-map re-key, or not at all.

**AI lens.** Directly enables multi-agent composition: two agents can each author a module without
negotiating a namespace.

---

## A2 — `patch` is specified, was implemented, and is now absent (S2, M, backend-engineer)

**Today.** `logosc show FILE PATH` prints one node. `logosc patch …`:

```
logosc: error: argument command: invalid choice: 'patch'
exit=2
```

**Contradiction.** Design §Addressing documents `logosc patch <path>` writing a replacement subtree
and reformatting, and design goal #3 is *"a change is a patch to one node, not a rewrite of the
file"*. The Python compiler had it (ledger, Wave B2: *"show/patch on real node paths"*).
`src/logosc/main.md:30` records the deliberate removal: *"`patch` is deliberately absent … used by
nobody in the gate, and is a developer convenience rather than something `logosc` keeps."*

**Why it matters for an AI.** Node addressing is the language's stated structural advantage: an
agent can point at `hello/main/2` instead of rewriting a file and hoping formatting matches. Half
the affordance (read) ships without the other half (write). `fmt`'s canonical form guarantees a
whole-file rewrite is *safe*, which lowers the cost of the gap — but it does not deliver goal #3.

**Decision required before work.** Either the verb returns (M: the lowering, the stdin protocol, the
re-format, plus regress cases) or the spec withdraws goal #3. Leaving both is the only
indefensible option: an AI reading the spec will call a verb that does not exist.

**AI lens.** High — but the alternative (canonical whole-file rewrite) is viable, which is why this
is S2 and not S1.

---

## A3 — Float literals with no finite value compile (S2, S, backend-engineer)

**Today.** `(println 1e999)` builds, runs, prints `inf`. The integer path is correct:
`(println 99999999999999999999)` → `E0106: literal … does not fit :i64`.

**Why it matters.** This is the exact failure mode the language exists to prevent: a value that is
silently not what the source says. An AI writing a numeric constant has no way to learn it overflowed.

**What v1 needs.** `E0106` (reworded "literal out of range") for any literal that converts to
infinity, at `:f64` and `:f32`, located at a node path. The design (D7/D14) rules that the check
must be *exact* and must live where both `check` and `build` can use it — a lowerer-only check would
make `check` accept what `build` refuses. That forces a shared module (`lit.logos`) declaring
`rt_parse_f64` once, because declaring it twice would create precisely the cross-module duplicate
A1 is about.

**Effort.** S (the predicate plus the shared module plus two corpus cases), but it is coupled to A1's
extern-duplicate problem.

---

## A4 — The standard library is 21 functions (S2, L, technical-architect + backend-engineer)

**Today.** The entire public surface, measured:

| Module | Functions | Notes |
|---|---|---|
| `src/std/io.logos` | 5 | `io-create`, `io-write`, `io-close`, `io-read`, `io-temp-path` |
| `src/std/str.logos` | 6 | `string-match-at`, `string-find`, `string-starts-with`, `string-split-nonempty`, `string-split`, `string-join` |
| `src/std/map.logos` | 10 | string-keyed, `:i64`-valued only: `map-hash/init/find/get/has/count/needs-grow/grow/insert/put` |

**What is missing that a first real program needs:**

- **`str` → integer parse.** `(str-from-i64 v)` exists; the inverse does not. `examples/json.logos`
  hand-rolls a JSON parser *including* number parsing because the library cannot do it.
- **Integer-keyed maps.** `map` is `(vec :str)` keys → `:i64` values with a caller-managed slot table
  and five parallel `(ref (vec …))` arguments. Ugly to call, unusable for node ids.
- **Sorting.** None.
- **JSON.** `examples/json.logos` (14 KB) parses JSON for a demo; nothing in `src/std` does.
- **Formatting.** No `sprintf`-style or alignment helpers; `println` accepts scalars only.
- **Filesystem beyond create/write/close/read**: no `unlink`, `stat`, `rename`, `mkdir` (the
  compiler itself uses an `rt_` helper for `mkdirs`), no `getenv`.

**Interpretation.** This is a *deliberate* consequence of the project's design ("library code
written in Logos comes later, once raw pointers and extern calls are trusted") and it is the right
call for the compiler's own needs — the compiler needs almost nothing. It is the wrong call for a
v1 a stranger adopts: the adoption experience is "hello world, then write your own stdlib".

**What v1 needs.** A documented floor, not a large library: `str`→`i64` (with an error type), an
integer-keyed map (or a generic one), a sort, and `unlink`/`stat`/`getenv`. Each with a corpus case
(V1-09).

**AI lens.** Very high: every one of these is a thing an AI must otherwise re-derive per project.

---

## A5 — No way to distribute or consume a library (S2, L, technical-architect)

**Today.** `use` searches (1) the asking file's directory, then (2) `src/std/<name>.logos`, and
nothing else — explicitly: *"no environment variable, configuration file or caller directory adds a
third"*. Measured: in an isolated directory `(use map)` → `E0005`.

**Why it blocks an ecosystem.** Any shared Logos code must be copied into the consumer's tree or
vendored at a path the resolver happens to look at. There is no version pinning, no lockfile, no
registry, no way for agent A to publish a library agent B uses. Combined with D3 (the stdlib path
is cwd-relative), even the built-in library is not reliably reachable.

**What v1 needs (minimum).** A search path that includes the installation root, plus one caller-
controllable entry (`LOGOS_PATH`, colon-separated), documented. A registry is v1.1.

**AI lens.** High for the ecosystem story; the minimum fix is small and unlocks "an AI can ship code
another AI depends on".

---

## A6 — One platform (S3, L, backend-engineer)

x86_64 Linux only. The target triple is already a flag; arm64 and Darwin are untested, and the
stage-0 binary is itself x86_64 Linux, so a new platform needs a bootstrap built where the compiler
already runs. Documented honestly in README. Acceptable for v1 if stated in the release notes; most
AI agent hosts are x86_64 Linux, which is why this is S3.

---

## A7 — The language has no comments and no doc form (S3, M, technical-architect — decision)

Verified by the project's own admission: `src/std/io.md` — *"Logos has no comments and no doc form,
so this file is the header documentation the source cannot carry."* Design goal #2 is *"Every
definition carries its type, its contract and its tests in one place, so an AI reading one node needs
no other file"* — the type and tests are in the node; **the contract is in a sibling `.md` the node
does not reference**.

For a human-first language this would be fine. For an AI-first one it is a real cost: an agent
editing a function cannot record why, and an agent reading one cannot see intent. Two defensible
resolutions: (a) add a `(doc "…")` node that is grammar and is dropped from emission, or (b) record
in the spec that intent lives in sibling files by design. **v1 needs one of them stated.**

---

## A8 — The compiler's own build takes ~6 minutes (S3, L, backend-engineer)

Measured: `./tools/logosc.sh version` from a clean tree built 24.6 MB of IR and linked it in about
six minutes (started 19:52, completed by 19:59). Every gate that touches `src/` pays this once; the
self-hosting gate pays it twice. There is no incremental compilation, no parallel module lowering
and no cache.

For a human this is tolerable. For an agent iterating on the compiler it is the dominant cost of
every loop, and it is why the corpus runs at one optimisation level in `make test` (C1). Not a v1
blocker; the first thing to fix after v1 if compiler work continues.

---

## Deliberate refusals — not gaps

README §"What it refuses, on purpose" lists nine restrictions (no copying owners; no owner in an
aggregate; no move across a loop; no capturing closure across a call; `alloc` only of
invariant-free types; unhandled result is an error; `try` needs an exact error type; `(shared T)`
checked through aggregates; no silent backend gap). Each is justified by a memory-safety or
`-O0`/`-O2`-parity invariant. **Do not "fix" these.** They are the reason the invariants hold, and
they should be stated in the release notes as features.

---

SOURCES (LAYER 2 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Register rows A1-A8 with severity, effort and owner.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/superpowers/specs/2026-11-06-ai-language-design.md`
 -> The original design: goals, non-goals, and the acceptance criteria this audit measures against. Note that it predates self-hosting and is contradicted by the current tree (see `03-dossiers/doc-contradictions.md`).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/superpowers/specs/2026-11-15-module-qualified-names-design.md`
 -> Designed, unapproved fix for A1: 14 decisions, the type-map risk, the precedence trap, five acceptance criteria, measured evidence.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/src/logosc/main.md`
 -> The CLI contract as the compiler documents it, including the deliberate absences (`patch`, per-verb help, stdin for build).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/src/std/io.md`
 -> The standard library's own statement that "Logos has no comments and no doc form", plus its documented limits (no unlink, no stat, no getenv, no errno).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> P13 (determinism), P15 (cross-module calls), P10-P11 (stdlib resolution), P0 (build time).
