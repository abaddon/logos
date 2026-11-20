# Dossier — what the 38 issue bodies actually look like

The selection rules are only as good as their fit to this corpus. Everything
below is measured or verbatim from the 38 open issues fetched on 2026-11-20.

## Dependency declarations are a written convention, not free prose

Counts of the bolded phrase across the corpus:

```
3   **Blocked by #74 — soft**      (the same #74 cited by three different issues)
1   **Blocked by #74 — hard**
1   **Blocked by #61 — soft**   **Blocked by #73 — soft**   **Blocked by #76 — soft**
1   **Blocked by #79 — hard**   **Blocked by #80 — hard**   **Blocked by #80 — soft**
1   **Blocked by #93 — soft**
1   **Blocked by:**             (number on the same line: "#99 — generic aggregate parameters…")
12  **Blocks #N — soft|hard**  (the reverse direction: #10, #75, #76, #79, #89, #91, #93, #94, #95)
1   **Sequenced after:** … #52, #78, #82, #86, #90
```

Verbatim examples, one per shape:

```
- **Blocked by #74 — hard** `LIMIT-010`: a qualified-name scheme is what makes transitive visibility safe
- **Blocked by:** #99 — generic aggregate parameters do not unify; a correctness bug in its own right, and a prerequisite here
- **Sequenced after:** the page corrections, so the link points at a page that is true: #52, #78, #82, #86, #90
```

Consequences encoded in the spec:

- the phrases are a closed list (`blocked by`, `depends on`, `sequenced after`,
  `part of`, `sub-issue of`, `parent:`, `follow-up to`, `tracking issue for`);
- a phrase only produces a reference when a `#N` sits on the **same line**, which
  is what the corpus does;
- `**Blocks #N**` is deliberately **not** in the list — it declares the opposite
  direction (this issue blocks another; it does not depend on it).

## The one false positive that shaped the rule

`#86`'s body, line 8, verbatim:

```
**Impact.** Worst direction of staleness: a parameter exists and three documents say it does not. A consumer who needs a per-call budget concludes it is unavailable and hand-rolls supervision, and the `-1`-versus-`R0006` contract that depends on passing a budget is documented nowhere.
```

The words "depends on" appear; no `#N` appears on that line. Under the
line-scoped rule `structural_refs(#86) = ∅` and `#86` is ready — which is correct:
it is a docs issue with no dependency. A document-wide regex would have marked it
blocked by whatever number happened to be elsewhere in the body.

## References per issue — the umbrella calibration

Distinct `#N` in title + body, counted against the whole corpus:

| # | refs | what it is |
|---|---|---|
| 100 | 38 | the gap index ("index of the 37 gap issues") |
| 41 | 14 | the label-sweep tracking issue (most targets already closed) |
| 80 | 7 | real work: five stdlib functions |
| 96 | 6 | real work: link the limits page from AGENTS.md |
| 74 | 6 | real work: module-qualified names (lists what it blocks) |
| 95 | 5 | real work: promote the json example |
| 79 | 4 | real work (and `needs-info`) |
| 93 | 3 | real work (and `needs-info`) |

`UMBRELLA_MAX_REFS = 8` sits in the gap between 7 and 38. The first draft used 3,
which excluded `#74`; running the rules over this table is what corrected it.

The header arm covers the two indexes the count arm would also catch, and would
still catch an index whose refs were mostly closed: `#100` title contains
"index of", `#41`'s first body line is `Tracking issue for the \`compiler\` label
sweep run on 2026-11-17.`

## `**Done when:**` is the repository's definition of done

34 of the 38 open issues contain the marker `**Done when:**`; one more uses
`**Done when.**`. Verbatim (`#52`):

```
**Done when:** both rows state what the compiler does (a non-finite float literal
is `E0106` at check time), `grep -rn "accepted.*inf" docs/` returns nothing, and
`bash tools/check_doc_links.sh .` still reports 0 broken.
```

Bullety variant (`#96`):

```
**Done when:**

- `grep -in limit AGENTS.md` returns the line
- `bash tools/check_doc_links.sh` reports 0 broken (the link resolves from the repository root)
- `python3 -m unittest tests.test_docs` passes
- V1-16 is marked met in `docs/01-summary/v1-acceptance-criteria.md`.
```

No issue in the corpus uses a `- [ ]` checklist, which is why that arm of the
extraction algorithm is second, not first.

## Title prefixes are the subsystem vocabulary

Counts of the text before the first `:` across the 38 titles:

| prefix | count | mapped subsystem |
|---|---|---|
| `docs` | 12 | docs |
| `tooling` | 6 | tooling |
| `language` | 5 | compiler |
| `manual` | 4 | docs |
| `stdlib` | 3 | stdlib |
| `examples` | 2 | examples |
| `compiler` | 2 | compiler |
| `target` | 1 | target |
| `question` | 1 | — (excluded by label anyway) |
| *(no prefix)* | 2 | labels, else `unclassified` |

`manual` is folded into `docs` because a manual chapter is a file under
`docs/manual/` **and** the generated artefact `docs/LOGOS.md` is rebuilt from it —
two concurrent manual tasks would collide on that single generated file.
`language` is folded into `compiler` because both edit `src/logosc/*.logos` and
both change `bootstrap/logosc`.

## Every open issue, and the verdict the rules reach

Produced by executing the spec's selection rules over the fetched JSON with
`backlog_cutoff = 2026-11-20T00:00:00Z` and `--include-backlog` (i.e. the
operator's drain run). `refs→open` counts distinct references that are themselves
open this run.

| # | created | subsystem | labels | refs→open | verdict |
|---|---|---|---|---|---|
| 10 | 2026-11-08 | target | target,hard | 0 | **picked** |
| 41 | 2026-11-17 | unclassified | — | 1 | umbrella |
| 52 | 2026-11-19 | docs | good first issue,docs | 0 | **picked** |
| 53 | 2026-11-19 | examples | good first issue | 0 | cap |
| 54 | 2026-11-19 | docs | good first issue,docs | 0 | cap |
| 55 | 2026-11-19 | docs | good first issue,docs | 0 | cap |
| 56 | 2026-11-19 | docs | good first issue,docs | 0 | cap |
| 57 | 2026-11-19 | docs | good first issue,docs | 0 | cap |
| 58 | 2026-11-19 | tooling | help wanted | 0 | cap |
| 59 | 2026-11-19 | tooling | help wanted | 0 | cap |
| 60 | 2026-11-19 | stdlib | help wanted | 0 | cap |
| 61 | 2026-11-19 | compiler | help wanted,compiler | 0 | cap |
| 66 | 2026-11-19 | docs | good first issue,docs | 2 | cap |
| 67 | 2026-11-19 | unclassified | question,needs-info | 1 | excluded-label |
| 69 | 2026-11-19 | docs | good first issue,docs | 1 | cap |
| 70 | 2026-11-19 | target | target | 2 | cap |
| 71 | 2026-11-19 | compiler | compiler,needs-info | 1 | excluded-label |
| 73 | 2026-11-19 | compiler | compiler,hard,needs-info | 2 | excluded-label |
| 74 | 2026-11-19 | compiler | compiler,hard | 6 | cap |
| 75 | 2026-11-19 | compiler | compiler,needs-info | 2 | excluded-label |
| 76 | 2026-11-19 | tooling | compiler,needs-info | 3 | excluded-label |
| 78 | 2026-11-19 | docs | good first issue,docs | 1 | cap |
| 79 | 2026-11-19 | compiler | question,compiler,hard,needs-info | 4 | excluded-label |
| 80 | 2026-11-19 | stdlib | help wanted,runtime | 6 | blocked |
| 82 | 2026-11-19 | docs | good first issue,docs | 1 | cap |
| 86 | 2026-11-19 | docs | docs | 1 | cap |
| 87 | 2026-11-19 | docs | good first issue,docs | 1 | cap |
| 89 | 2026-11-19 | tooling | question,compiler,needs-info | 2 | excluded-label |
| 90 | 2026-11-19 | docs | good first issue,docs | 1 | cap |
| 91 | 2026-11-19 | tooling | help wanted,compiler | 2 | blocked |
| 93 | 2026-11-19 | tooling | compiler,needs-info | 3 | excluded-label |
| 94 | 2026-11-19 | examples | runtime | 2 | blocked |
| 95 | 2026-11-19 | stdlib | compiler,hard | 5 | blocked |
| 96 | 2026-11-19 | docs | good first issue,docs | 6 | blocked |
| 97 | 2026-11-19 | docs | good first issue,docs | 1 | cap |
| 98 | 2026-11-19 | docs | docs,needs-info | 1 | excluded-label |
| 99 | 2026-11-19 | compiler | bug,compiler,hard | 2 | cap |
| 100 | 2026-11-19 | docs | docs | 29 | umbrella |

Totals: 38 fetched, 0 PRs, 38 unseen, 22 ready, 2 picked, and 36 skipped
(20 `cap`, 9 `excluded-label`, 5 `blocked`, 2 `umbrella`).

Two rows are worth reading twice:

- `#41` is `unclassified` and shows `refs→open = 1` — the sweep's other targets
  are closed, so the count arm would not catch it. It is caught by its opening
  line, which is why the header arm exists.
- `#76` maps to `tooling` by title prefix while carrying a `compiler` label; the
  title says what the work touches, the label says which area filed it. Title
  first is the rule.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/03-selection.md
 -> the rules this table was produced by, clause by clause
docs/pipelines/issue-intake/03-dossiers/04-selection-fixtures.json
 -> the same behaviours as executable cases (14)
docs/pipelines/issue-intake/03-dossiers/01-github-evidence.md
 -> the request/response facts behind the 38-item set
