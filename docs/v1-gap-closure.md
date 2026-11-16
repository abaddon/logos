# v1 gap closure — what this branch changes and what it defers

The audit of commit `9194412` (46 gaps, deliverable on branch `wt/t_7a5a4fe5`
at `docs/00-index.md`) is the backlog this branch works from. This file maps
every gap to its state after the branch, so a reviewer can see both halves
honestly: what is now true, and what still needs a different owner or a
decision.

Severity is the audit's. Evidence for each closed item is a command in
`tests/test_cli.py` or a case under `tests/regress/`, and both run in
`make test`.

## Closed by this branch

| Gap | Sev | What changed | Evidence |
|---|---|---|---|
| **E1** no machine-readable diagnostics | S1 | `--json` anywhere on the command line makes every compiler failure a JSON object on stderr: `schema_version`, `severity`, `code`, `message`, `node_path`, `file`, `line`, `col`. Human text stays the default and the exit code is unchanged. Schema published at `docs/schemas/diagnostic-v1.schema.json`. | `tests/test_cli.py::JsonDiagnostics` — one probe per failing phase (lexer, parser, resolver, checker, lowerer) asserts the field set, the code, the node path; `test_human_text_remains_the_default` pins the text form. |
| **D2** build depends on the working directory | S1 | The runtime is found from the compiler's own location: `<root>/share/logos/runtime/rt.c` (installed), `<root>/logos/runtime/rt.c` (checkout), then `logos/runtime/rt.c` relative to the cwd as the legacy fallback. `<root>` is derived from `/proc/self/exe` (one `readlink`, no subprocess) and `LOGOS_ROOT` overrides it, not `$PWD`. A miss is `E0800` naming the whole search order, and `--json` shapes it like every other diagnostic. | `tests/test_cli.py::Portability::test_build_and_run_outside_the_checkout` builds and runs from a temp directory; `tests/test_install.py::DiagnosticTest` pins `E0800`, its exit status 1, the removed IR and the JSON form. |
| **D3** stdlib resolves from the cwd | S1 | `(use name)` searches the asking file's directory, then the `LOGOS_PATH` entries, then `<root>/share/logos/std`, `<root>/src/std`, then `src/std`; `E0005` prints the order it tried. | `tests/test_cli.py::Portability::test_stdlib_modules_resolve_from_the_installation` builds a program that `(use map)`s and runs it; `tests/test_install.py::InstallLayoutTest` pins the prefix, `LOGOS_ROOT`, `LOGOS_PATH`, the symlink and the working-directory-last cases. |
| **A3** non-finite float literals accepted | S2 | A literal that has no finite value in its own type is refused with `E0106` and a node path: decimal exponent compared against the type's maximum (`17976931348623157` for `:f64`, `34028234` for `:f32`), which is the same digit-string comparison the integer path already used. `1e308` still compiles. The comparison is deliberate at the maximum, not at the rounding midpoint, so a literal within one ulp of the maximum is refused as well — the safe direction, since it can never let an `inf` through. The `E0106` table entry is now `literal out of range for its type`, because the code no longer covers integers only. | `tests/regress/float-range` (`E0106`, `:f64`), `tests/regress/float-range-f32` (`E0106`, `:f32`), `tests/regress/float-finite` (1e308 and DBL_MAX print, at `-O0` and `-O2`), `tests/regress/float-leading-zeros` (`0.0001e312` is 1e308 and must compile). |
| **E2** exit-code contract undocumented and unpinned | S2 | One table in `docs/reference/cli.md`, one test per row: `0` success, `2` source *and* usage error, `1` I/O or toolchain. `fmt` now reports a source error as 2 instead of 1 (it used to report success — see below). | `tests/test_cli.py::ExitCodes` (five rows). |
| **E3** no per-verb help | S2 | Every verb answers `-h`/`--help` with its own usage, positional arguments and flags, on stdout, exit 0. `logosc -h` and `logosc` both print the top-level help. | `tests/test_cli.py::Help::test_every_verb_has_its_own_help` (8 verbs). |
| **E4** two verbs hidden | S2 | `resolve` and `check` appear in `--help` and in the invalid-choice list, with their own usage lines. | `tests/test_cli.py::Help::test_top_level_help_lists_every_verb`, `test_invalid_choice_names_every_verb`. |
| **E5** version is a source constant with no machine-readable form | S3 | `version --json` → `{"schema_version":1,"name":"logos","version":"0.2.0"}`; `--version` is the flag form. The string lives in one function, `main-semver`. Schema at `docs/schemas/version-v1.schema.json`. | `tests/test_cli.py::Version`. |
| **E9** the one JSON surface is unversioned | S2 | `guide --json` carries `"schema_version": 1` as its first key and is documented in `docs/reference/cli.md` as a stable contract; the manual's own sentence now names the schema directory. | `tests/test_cli.py::Guide::test_manifest_is_versioned`. |
| **B2** the manual documents the language, not the tool (compiler half) | S2 | `docs/reference/cli.md`: verbs, flags, streams, exit codes, both JSON documents, and the install layout the runtime/stdlib lookup follows. Linked from `README.md`. | `docs/reference/cli.md`; the contract above is what it documents. |

### A defect found and fixed on the way

`main-or` collapsed any non-zero status to `1` and only recognised `1`, so
`logosc fmt` returned **0** for a file that does not lex — the diagnostic
printed and the status said success. That is a silent failure in the one verb
an agent runs to rewrite sources, and it made the exit-code table untrue. It is
now `(if (= a 0) b a)`: the first non-zero status wins, so a source error stays
2 and an I/O failure stays 1. Pinned by
`tests/test_cli.py::ExitCodes::test_fmt_source_error_is_two`.

A second one was found while probing the A3 range check: it computed the
magnitude exponent from every mantissa digit, so leading zeros counted as
magnitude and `0.0001e312` — which is `1e308` and finite — was refused with
`E0106`. The exponent now subtracts the leading zeros it already strips
(`e - s + before - 1`), and `tests/regress/float-leading-zeros` pins the case.

A third one came out of asking what the exit-code table actually promises: the
compiler did not *handle* an unreadable input, it crashed on it. `check`,
`resolve` and `build` passed the path straight to `read-file`, whose runtime
aborts with `R0007` and the compiler's own node path — `main/main-source/2/2:
R0007: could not read gone.logos`, exit 2. A directory argument did the same,
because `path-error` returns empty for one. Every verb now tests the input
once (`main-file-why`: the `path-error` message, else `not a regular file` when
`test -f` fails) and reports it the way `build` already did — `logos:
<path>: <reason>` on stderr, exit 1. `R0007` is a runtime panic code for
`read-file` inside a compiled program; the compiler no longer borrows it.
Pinned by `tests/test_cli.py::ExitCodes` — one case per reading verb, one for
multi-file `resolve`, one for a directory.

## Deferred, with the reason

| Gap | Sev | Why it is not in this branch | Owner |
|---|---|---|---|
| **A1** names are global across the program | S1 | The design exists (`docs/superpowers/specs/2026-11-15-module-qualified-names-design.md`) and it is a language change: the resolver, the checker's name tables, the lowerer's symbol mangling and the manual all move together, plus the bootstrap. It is a branch of its own, and it is the largest remaining v1 item. | backend-engineer |
| **A2** the `patch` verb is missing | S2 | The spec promises it and the port refuses it deliberately. V1-07 allows either shipping it or withdrawing the design goal; that is an owner ruling on the spec, not a compiler fix. Implementing it without the ruling risks building an addressed-editing contract nobody ratified. | technical-architect + owner |
| **A4** stdlib is 21 functions | S2 | Growing the stdlib (string→int, integer-keyed map, sort, JSON, sprintf, `stat`/`getenv`) is new language surface: each function needs a manual entry, a corpus case and a `.md` contract. It does not belong in a change about the CLI contract. | technical-architect |
| **A5** no third-party library story | S2 | Needs a distribution model (registry, lockfile, version constraints) that depends on D7. | technical-architect |
| **A6** arm64 and Darwin untested | S3 | Needs a host that already runs the compiler to produce a stage-0 there. | platform-engineer |
| **A7** no comments, no doc form | S3 | A language ruling to record in the spec, not an implementation task. | technical-architect |
| **A8** compiler rebuild is slow | S3 | Measured at 45 s on this host, not the 6 min the audit saw cold; incremental builds are an optimisation with no v1 decision behind them. | backend-engineer |
| **E6** no `run` verb, no `--emit` | S2 | The IR path is already addressable (`--keep-ir`, `-o`, `build/<stem>.ll`). A `run` verb needs a decision about where the temporary binary lives and how the exit code is forwarded. | backend-engineer + owner |
| **E7** no stdin for `build`/`check` | S3 | `fmt -` exists; the same shape for `build` needs a filename for diagnostics, which is a contract question. | backend-engineer |
| **E8** `build/` is cwd-relative | S3 | `-o` already names the output; the default is documented in `docs/reference/cli.md`. | backend-engineer |
| **E10** diagnostic text is a byte-for-byte contract | S3 | Ruled out of scope here: the JSON form is now the stable machine surface, so `--json` is what an agent should bind to. Deciding whether the text may change is still the architect's. | technical-architect |
| **C1-C9** test depth, baseline, coverage, fuzzing, `test --json` | S3 | The corpus and the suites are unchanged and green; machine-readable `test` output is the next QA-visible item. | qa-engineer |
| **D1, D4-D10** install artifact, release pipeline, distribution format, CI matrix, repo visibility, no `make install` | S1/S2 | Packaging and publishing, with one owner ruling inside it (D5, repository visibility). This branch makes the compiler *able* to run from an installation (D2, D3); producing that installation is the packaging workstream. | platform-engineer, oss-contributor, owner |
| **B3-B9** README overstatement, spec contradictions, stale Python references, no stdlib reference | S2/S3 | Documentation work; only the sentences this branch made false were corrected (`inf` on non-finite literals, the contract-test count, the manifest keys). | technical-writer |

## What the next session should do first

1. **A1** — it is the only S1 that is compiler work, and it is designed.
2. **A2 + E10 + A7** — one sitting with the architect to rule on three
   documented-but-unimplemented promises.
3. **D1 + D7 + D4** — packaging, so V1-01 through V1-05 can be tested. The
   lookup this branch landed is already written for the layout
   `$PREFIX/bin/logosc` + `$PREFIX/share/logos/{runtime,std}`; a tarball that
   installs there needs no compiler change.
