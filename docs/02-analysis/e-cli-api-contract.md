# L2 (e) — CLI and API contract

The compiler's internal contracts are excellent — every diagnostic carries a code and a node path,
every failure has one shape, exit statuses are deliberate. The **external** contract is where the AI
lens bites: those internal structures are delivered as prose on stderr, the exit-code semantics are
unpublished, two verbs are hidden, and the two flags an agent would reach for (`--json`, `--emit`)
do not exist.

Gap IDs: **E1-E10**.

---

## The surface, as measured

```
usage: logosc [-h] command ...

Compiler for Logos, a prefix-form language for AI readers.

positional arguments:
  command
    build     compile Logos source files to a native binary
    test      compile and run the (test ...) nodes in a file
    fmt       rewrite Logos source in canonical form
    show      print one node of a Logos file
    version   print the compiler version
    guide     print the generated Logos manual or its manifest

options:
  -h, --help  show this help message and exit
```

| Verb | Real signature (from `src/logosc/main.md`) | In `--help`? |
|---|---|---|
| `version` | `version` | yes |
| `show` | `show FILE PATH` | yes |
| `fmt` | `fmt FILE\|DIR\|- ...` | yes |
| `build` | `build FILE... [-o OUT] [--opt O] [--test NAME] [--keep-ir]` | yes |
| `test` | `test [PATH] [--only CAT] [--opt LEVEL]... [--update-baseline]` | yes |
| `guide` | `guide [--json\|--check]` | yes |
| `resolve` | `resolve FILE...` | **no** |
| `check` | `check FILE` | **no** |
| `patch` | specified, implemented on the Python compiler, **absent** | no |

Measured variant behaviours: no argument → help on stdout, exit 0. Unknown verb → `invalid choice`,
exit 2. `build -h` → `unrecognized arguments: -h`, exit 2. Missing file → `logos: <path>: No such
file or directory`, exit 1. Source error → one line on stderr, exit 2.

---

## E1 — No machine-readable diagnostics (S1, M) — **the highest-leverage gap in this audit**

Every failure is one text line whose shape varies by stage:

```
t/main/2/0: E0100: '+' needs numbers, found :str          # checker
p/0: E0005: unknown module 'map'                          # resolver
<file>:<line>:<column>: E0006: …                          # lexer, file first
logos: runtime not found: logos/runtime/rt.c              # environment, no code at all
logos: clang failed: …                                    # link, no code
```

An AI must decide which regex applies, strip the code, recover a node path *or* a file position, and
guess severity — for every failure. The information is all present internally (the node path is what
the checker reports, the code is an enum in `guide.logos`) and is thrown away at the print site.

**Proposed contract** (`--json` on `build`, `check`, `resolve`, `test`):

```json
{
  "schema_version": 1,
  "verb": "build",
  "ok": false,
  "exit_code": 2,
  "diagnostics": [
    {
      "code": "E0100",
      "severity": "error",
      "message": "'+' needs numbers, found :str",
      "node_path": "t/main/2/0",
      "file": "t/t.logos",
      "line": 1,
      "column": 21
    }
  ]
}
```

Design decisions to ratify:

1. **One object on stdout**, human text suppressed, exit code unchanged. Rationale: an agent pipes
   `| jq` without touching stderr, and the exit code stays the primary signal. (Alternative —
   NDJSON per diagnostic on stderr — is better for streaming a long build; pick one and document it.)
2. **`node_path` and `file/line/column` are both optional** but at least one is always present,
   because the compiler genuinely has one or the other (that is already its internal rule).
3. **Environment failures carry a code too.** `logos: runtime not found` and `logos: clang failed`
   are the two uncoded failures today; they should be `E1000`/`E1001`-style codes so a caller can
   classify them without string matching.
4. **`schema_version` from day one**, so the shape can grow (E9 asks the same of `guide --json`).
5. **The manual chapter (B2) documents the schema** and a corpus case pins it (C2).

Effort is genuinely M, not L: `main-write` is already the one function that reaches stderr, and the
diagnostic sites already hold code + path + message.

---

## E2 — The exit-code contract is undocumented and unpinned (S2, S)

What exists, measured:

| Situation | Status | Documented in the manual? | Tested? |
|---|---|---|---|
| success | 0 | no | no |
| lexer/parser/resolver/checker/lowering error | 2 | no | no |
| usage error (bad verb, bad flag, missing arg) | 2 | no | no |
| missing file / IO failure / link failure / no runtime | 1 | no | no |
| no `main` in the set (`E0103`), two `main`s (`E0003`) | 2 | partial | no |

Two different meanings of `2` (source error and usage error) is defensible — `argparse` conventions
favour 2 for usage, and the port kept Python's. But an agent retrying on failure needs to know that
`1` means "fix the environment" and `2` means "fix the source", and that a link failure is `1` even
though it is caused by the source's demands. **Publish the table; add one corpus case per row; keep
the values.**

Note the port deliberately changed the front-end status from the Python driver's `1` to `2`
(`main.md` §"What it does not do"). That is a good change for classification — it just has to be
written down.

---

## E3 — No per-verb help (S2, S)

`logosc build -h` → `unrecognized arguments: -h`, exit 2. `logosc build --frob` → the same error.

Flag discovery therefore requires the manual, which does not document flags (B2), or the source. For
an agent that has just installed a binary, `logosc build --help` is the *first* command it will run.
Note also `--keep-ir` is accepted and **changes nothing** (the IR is always kept) — a flag that
exists only for compatibility is a trap when there is no help text to say so.

Effort S: an arity table and a usage block per verb, mirroring `main-verb-usage`.

---

## E4 — Two verbs are hidden (S2, S)

`resolve` and `check` are real, useful, and absent from `--help` and from the invalid-choice list.
`main.md` gives the reason: the help text is Python's byte-for-byte, and the Python tool had neither
verb. That reason expired when the Python tool was deleted.

For an AI consumer, `check` is the cheap validation call to make between edits (no codegen, no
clang). It should be the most discoverable verb in the product, not the least.

**Fix:** put both in the help and the choice list, in `main.logos` and in the manual chapter. This
also removes the only place where the tool's own `--help` is inaccurate.

---

## E5 — Version is a constant with no machine-readable form (S3, S)

`logosc version` → `logos 0.1.0`, exit 0, from the string literal in `main-version`. There is no
`--version` flag, no `version --json`, and no file any release tooling could read. Version-bump
automation has nothing to operate on, and an agent cannot tell whether the binary it found is the one
the project released.

Fix: keep the verb, add `--json` (`{"version":"1.0.0","schema_version":1,"commit":"…","target":"x86_64-unknown-linux-gnu"}`),
and generate the constant at build time from the tag rather than storing it by hand.

---

## E6 — No `run`, no `--emit`, no IR on stdout (S2, M)

Today: `build` writes `build/<stem>.ll` and `build/<stem>` (or `-o`), then you execute the binary
yourself; `--keep-ir` is a no-op because the IR is always written.

What an agent wants and cannot ask for:

| Want | Today |
|---|---|
| compile **and** run, with the exit status of the program | `build` then `./build/x` — two steps and a path convention |
| just the IR, to stdout or a named file | IR is always at `build/<stem>.ll`, stdout impossible |
| just an object file, to link with something else | not possible |
| a specific target triple | `-target` is a flag *inside* clang invocation, not exposed |

Minimum for v1: `run` (build + exec, propagating the program's exit status and passing argv through)
and `--emit=ir|exe|<path>` where `--emit=ir -o -` writes IR to stdout. These are small changes to
`main-built`'s tail and they remove a convention from the contract.

---

## E7 — `fmt -` exists, `build -` does not (S3, S)

`fmt -` reads stdin and writes canonical text to stdout — verified working. `build`, `check` and
`resolve` accept only paths. An agent generating source in memory must write a temp file (and then
own its cleanup, which the language's `io` module cannot even `unlink`). Either support `-`
consistently or document why not.

---

## E8 — Build artefacts go into cwd-relative `build/` (S3, S)

`build` creates `build/` **relative to the working directory**, not beside the source and not in a
caller-named place (unless `-o` is given, and even then the IR still goes to `build/<stem>.ll`). A
consumer compiling a file in their project silently gets a `build/` directory they did not ask for,
and two concurrent builds of same-named files in one cwd collide (both write `build/<stem>.ll`).

Fix: default output beside the source (`<dir>/<stem>` and `<stem>.ll`), or require `-o`. The
reproducibility guarantee is anchored to the IR being at a stable *basename*, not a stable
*directory*, so moving the default does not endanger V1-14 — but it must be verified, not assumed.

---

## E9 — `guide --json` is the only JSON, and it is unversioned (S2, S)

Measured: valid JSON, seven top-level keys — `forms`, `types`, `operators`, `builtins`, `reserved`,
`codes`, `categories`. A genuinely good artifact: an agent can learn the whole surface without
scraping markdown.

It has no `schema_version`, no published schema, and no statement of stability. Since AIs will build
tooling on it, it needs the same treatment as E1: a version field, a schema file in the repo, and one
line in the manual saying that a breaking change bumps it.

---

## E10 — Diagnostic *text* is a contract with a deleted implementation (S3, M — decision)

`main.md` is explicit: the command line is `argparse`'s *"because the tool it replaces is Python's
and a script that reads a message reads it byte for byte"*, the help block is *"the replaced tool's
contract"*, and even `%XX` decoding in baseline lines reproduces Python's printing.

That was the right call during the port (parity was the acceptance criterion). It is now a liability:

- it freezes a **dead dependency's** message text as the product's contract;
- it is why `resolve`/`check` are hidden (E4) and why `-h` does not work (E3);
- it makes every future message improvement a breaking change;
- it optimises for a consumer (a Python script regexing argparse text) that no longer exists.

**Recommendation:** declare text best-effort and *codes + JSON schema* the contract (E1), then fix
`-h`, unhide the verbs, and stop reproducing Python's wording where it fights clarity. This is one
decision that unblocks E3, E4 and part of B2.

---

## What the CLI already gets right (do not regress)

- **One canonical failure shape per stage**, documented in `main.md`'s pipeline table.
- **Nothing is silent**: every verb prints nothing on success and one classified line on failure.
- **`fmt` is idempotent and in-place**, composable with git — the correct design for an agent.
- **`guide --check` as a gate**: documentation drift is a build failure, which is the single best
  documentation practice in the repository.
- **`--update-baseline` refuses a category directory or a stray file** rather than writing a
  misleading baseline.
- **The node path is stable and positional** (`mod/fn/index/index`), so it survives sibling edits —
  the property that makes E1's `node_path` field worth having.

---

SOURCES (LAYER 2 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Register rows E1-E10 with severity, effort and owner.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/01-summary/v1-acceptance-criteria.md`
 -> Criteria V1-10…V1-13 (machine-readable) and the exit-code criterion V1-11.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> P1-P9, P14: every CLI behaviour quoted here, with the command and the exit code.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/src/logosc/main.md`
 -> The authoritative CLI contract: verb table, flag parsing, exit-status rules, diagnostic shapes per stage, the deliberate absences.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/superpowers/specs/2026-11-06-ai-language-design.md`
 -> §Addressing and tooling: the `patch`/`show` design and goal #3, which E-level gaps and A2 measure against.
