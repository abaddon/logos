# Logos documentation index

Entry point for everything in `docs/`. Choose the row that matches what you are
doing; each links to one page that answers it.

Logos is a prefix-form language for AI readers, compiled by `logosc` to native
x86_64 Linux binaries. The compiler is self-hosting and deterministic; it is
released as a verified tarball ([`install.md`](install.md)) named `v0.2.2`
([`../CHANGELOG.md`](../CHANGELOG.md), [`release.md`](release.md)). Pre-1.0: the
[`reference/limits.md`](reference/limits.md) page is the honest list of what it
cannot do yet.

---

## Start here

| I want to… | Read | Time |
|---|---|---|
| install it and compile something | [`install.md`](install.md) — download, checksum, unpack, hello world | 5 min |
| follow it command by command | [`quickstart.md`](quickstart.md) — **the canonical quickstart**: both routes in five commands each, then a diagnostic, a test run, the corpus and the gates; every output verified | 10 min |
| point an agent at this repository, with no human in the loop | [`../llms.txt`](../llms.txt) — the one-file index: install, start-here docs, language, examples, contribution | 2 min |
| write Logos correctly the first time | [`reference/language.md`](reference/language.md) — v1 subset, rules, verified idioms | 20 min |
| drive the compiler from a script | [`reference/cli.md`](reference/cli.md) — verbs, flags, exit codes, JSON documents, artefacts | 15 min |
| understand a failure | [`reference/diagnostics.md`](reference/diagnostics.md) — the shapes, all 36 codes | 10 min |
| know what it cannot do | [`reference/limits.md`](reference/limits.md) — one page, every limit | 5 min |
| use the standard library | [`reference/stdlib.md`](reference/stdlib.md) — all 21 functions | 5 min |
| be an agent in this repository | [`reference/agent-contract.md`](reference/agent-contract.md) — consumer contract and the index to the contributor one | 15 min |
| change the compiler | [`../AGENTS.md`](../AGENTS.md) — gates, invariants, bootstrap, regress rule | 20 min |
| join the Logos Agent Challenge | [`challenge/01-summary/program.md`](challenge/01-summary/program.md) — three tracks, entry form, dated timeline, rubric | 10 min |
| know how v1 quality was measured | [`qa/00-index.md`](qa/00-index.md) — the gate, the coverage, the sign-off | 20 min |
| know the gap history | [`01-summary/gap-register.md`](01-summary/gap-register.md) — 46 gaps, 18 release criteria, what closed | 30 min |
| cut a release | [`release.md`](release.md) — version source, rehearsal, tag, publish | 10 min |
| check the docs against the compiler | [`distribution/00-index.md`](distribution/00-index.md) — what was verified, by what command, and the result | 10 min |
| run the outreach launch, or see where it got to | [`launch/00-index.md`](launch/00-index.md) — channel status, paste-ready copy, the owner actions it waits on | 10 min |

## Reference — the v1 doc set

Written for an agent with no prior context: every command and every code
example was executed against the compiler on this tree.

| Page | Covers | Gaps closed |
|---|---|---|
| [`quickstart.md`](quickstart.md) | **the canonical quickstart** — release tarball and checkout, five commands each, then a diagnostic read as data, a test run, the language manifest and the gates, end to end | B6, D6, V1-18 |
| [`reference/agent-contract.md`](reference/agent-contract.md) | the consumer contract in one page: what works, exit codes, machine-readable surfaces, determinism, traps, and the docs a change obliges you to update | B6 |
| [`reference/cli.md`](reference/cli.md) | eight verbs, per-verb help, flags, exit-code contract, `--json` diagnostics and the two versioned JSON documents, artefact paths, the installation lookup | B2, E2, E3, E4, E5, E9 |
| [`reference/language.md`](reference/language.md) | the v1 subset: model, ten rules → codes, verified idiom per feature, what v1 lacks | B2 |
| [`reference/diagnostics.md`](reference/diagnostics.md) | the five diagnostic shapes, node paths, all `E0xxx`/`R0xxx` codes, retry policy | E2 |
| [`reference/stdlib.md`](reference/stdlib.md) | `io`, `str`, `map`: signatures, ownership, error behaviour, one verified program | B7 |
| [`reference/limits.md`](reference/limits.md) | reach, platform, language, memory, threading, tooling limits in one page | B9, V1-16 |

## The language manual

| Page | Covers |
|---|---|
| [`LOGOS.md`](LOGOS.md) | **generated** — cheat sheet, 20 executable chapters in learning order, and the reference tables (forms, types, operators, builtins, reserved names, codes, test categories). The ground truth for what the language accepts. **Never edit by hand.** |
| [`manual/`](manual/) | the 20 numbered chapter sources the manual embeds; each is a complete module whose `(test …)` node declares its output |
| `logosc guide --json` | the same tables as a machine-readable manifest (96 forms, 16 types, 17 operators, 2 builtins, 36 codes, 8 categories) |
| `logosc guide --check` | proves the committed manual is current; a gate |

## v1 audit — why the release is blocked

Commissioned at commit `9194412`. Every behavioural claim was measured; the
commands and outputs are in the dossiers.

| Page | Covers |
|---|---|
| [`01-summary/gap-register.md`](01-summary/gap-register.md) | the 46-gap register with severity, effort and owner; the recommended sequence |
| [`01-summary/findings.md`](01-summary/findings.md) | the audit in one page |
| [`01-summary/v1-acceptance-criteria.md`](01-summary/v1-acceptance-criteria.md) | 18 criteria, each with the command that proves it |
| [`02-analysis/a-compiler-capabilities.md`](02-analysis/a-compiler-capabilities.md) | namespaces, patch, literals, stdlib, targets, build latency |
| [`02-analysis/b-documentation.md`](02-analysis/b-documentation.md) | what documentation was missing or false, file by file |
| [`02-analysis/c-tests-and-gates.md`](02-analysis/c-tests-and-gates.md) | what the six gates do and do not cover |
| [`02-analysis/d-build-packaging-ci.md`](02-analysis/d-build-packaging-ci.md) | the install gap and its three root causes |
| [`02-analysis/e-cli-api-contract.md`](02-analysis/e-cli-api-contract.md) | the CLI surface, exit codes, JSON schema, hidden verbs |
| [`03-dossiers/probe-log.md`](03-dossiers/probe-log.md) | 16 probes: exact command, output, exit code |
| [`03-dossiers/repository-inventory.md`](03-dossiers/repository-inventory.md) | what exists, measured |
| [`03-dossiers/doc-contradictions.md`](03-dossiers/doc-contradictions.md) | every written statement the tree contradicted, with file and line |

## History and design

| Page | Covers |
|---|---|
| [`history/build-ledger.md`](history/build-ledger.md) | the rulings behind the current design, in order — the "why" the source cannot carry (the language has no comments) |
| [`superpowers/specs/`](superpowers/specs/) | design specifications. **Stale in four places** — self-hosting, packaging, `patch` and imported functions — see [`03-dossiers/doc-contradictions.md`](03-dossiers/doc-contradictions.md) §4-7 before citing them |
| [`superpowers/plans/`](superpowers/plans/) | the implementation reports, one per work wave. Historical |

## Outside `docs/`

| Path | Covers |
|---|---|
| [`../README.md`](../README.md) | what Logos is, requirements, status, gates, layout |
| [`../llms.txt`](../llms.txt) | the one-file machine-readable index for an agent that has just arrived: an install block, the start-here docs, the language references, the examples and the contribution route |
| [`../AGENTS.md`](../AGENTS.md) | the contributor contract: the six gates, invariants, regress rule, bootstrap rule, PR rules. **One stale claim:** it says the compiler's own suites run at `-O0` and `-O2`; the gate runs them at `-O0` and `make suites-all` is the two-level form (`Makefile`). Everything else in it is accurate |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | the shorter human route through `AGENTS.md` |
| `../src/logosc/*.md` | per-module contracts, the authoritative statement of what each compiler stage does |
| `../src/std/*.md` | per-module contracts and rationale for the standard library |

## How this index is maintained

- **Every new page gets a row here before it is merged.** A page nobody can
  find is a page nobody maintains.
- Pages are organised by audience, not by author or date: consumer, language,
  audit, history.
- `LOGOS.md` and `manual/` are generated. Their rows say so; do not add prose
  edits to them.
- The audit pages are a **record**, not a live backlog — they describe commit
  `9194412`. Their findings stay true about that commit; a row's gap is closed
  when the code change that closes it lands, not when the prose improves.
- Links are relative and must resolve inside the repository. Before merging,
  extract every relative link target under `docs/` and check each path exists;
  a broken link is a documentation build failure even though no gate measures
  it.
