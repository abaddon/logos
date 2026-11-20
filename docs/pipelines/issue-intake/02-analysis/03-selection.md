# 3 — Selection and independence

This is the file the pipeline exists for. Every word that could be argued about
— *new*, *ready*, *independent*, *umbrella*, *subsystem* — is given a test that
a machine evaluates. There is no judgement call left to the implementer.

Inputs: the fetched open issues (`01-polling.md`), the state file
(`02-state.md`), and the config block (`06-config.md`). Output: an ordered list
of at most `MAX_PICKS` (default 2) issues, or fewer, or none.

## 3.1 Vocabulary, each with its test

| Term | Definition (evaluated, not paraphrased) |
|---|---|
| **new** | open, not a pull request, no state entry with `outcome` in {`picked`,`seeded`}, and `created_at > backlog_cutoff` unless `--include-backlog` |
| **refs(x)** | the set of integers captured by `#(\d+)` in `x.title + "\n" + (x.body or "")`, minus `x.number` |
| **structural_refs(x)** | for each line of `body`, if the line matches `(?i)(blocked by\|depends on\|sequenced after\|part of\|sub-?issue of\|parent:\|follow-?up to\|tracking issue for)`, add every `#(\d+)` on **that line**; minus `x.number` |
| **blocked(x)** | `structural_refs(x) ∩ open_numbers` is non-empty. `open_numbers` is the set of numbers fetched this run. A reference to a number that is not open is history, not a blocker |
| **umbrella(x)** | `len(refs(x) ∩ open_numbers) >= UMBRELLA_MAX_REFS` (8) **or** the `title` or the **first non-empty line of `body`** matches `(?i)\b(tracking issue\|index of\|master list\|umbrella)\b` |
| **subsystem(x)** | `SUBSYSTEM_PREFIX[prefix]` where `prefix` is the lowercased text before the first `:` in the title **if** that text is a key of the map; else `{canonical(l) for l in x.labels if l in SUBSYSTEM_LABELS}`; else `{"unclassified"}` |
| **ready(x)** | `new(x) and labels(x) ∩ EXCLUDED_LABELS == ∅ and not blocked(x) and not umbrella(x)` |
| **independent(a,b)** | `b.number not in refs(a) and a.number not in refs(b) and subsystem(a) ∩ subsystem(b) == ∅` |

Two clauses deserve their reasons stated, because they are the ones an
implementer might be tempted to "improve":

**Why `structural_refs` is line-scoped.** The repo writes dependencies as their
own line — measured in the live corpus on 2026-11-20:

```
- **Blocked by #74 — hard** `LIMIT-010`: ...
- **Blocked by:** #99 — generic aggregate parameters do not unify
- **Sequenced after:** the page corrections, so the link points at a page that is true: #52, #78, #82, #86, #90
```

Scanning the whole document for "blocked" would catch prose ("an acceptance
criterion stays unmet", "SIGTERM… re-queues"), and scanning the whole document
for any `#N` would make every issue blocked, because 25 of the 38 open issues
mention the tracking index `#100`. Line scope is the smallest rule that is
exactly right on the real corpus.

**Why refs-to-a-candidate blocks the pair, even without a keyword.** "See #74
for the scheme" is not a dependency declaration, but two cards whose bodies cite
each other are two cards whose workers will touch the same decision. The pair
test is deliberately stricter than the readiness test.

**Why the umbrella threshold is 8 and not 3.** Measured on the 38 open issues
(2026-11-20), the number of distinct `#N` references per issue body is: `#100`
38, `#41` 14, then `#80` 7, `#96` 6, `#74` 6, `#95` 5, `#79` 4, `#93` 3 — a
clean gap between two index documents and the work items that cite a few
neighbours. A threshold of 3 (the obvious first guess) excludes `#74`, a real
design issue that merely lists what it blocks; the reference implementation of
these rules was run against the live corpus and that false positive is what
moved the number to 8. The header test exists because the corpus marks its own
indexes in prose (`#100` title "… index of the 37 gap issues …", `#41` opening
line "Tracking issue for the `compiler` label sweep …"), and the header is where
a human looks first.

## 3.2 The subsystem map (the "same area" test)

Derived from the 38 open issues' titles on 2026-11-20 (prefix counts in
parentheses). Two issues in the same subsystem are **not** independent: their
workers would edit the same files and, for anything under `docs/` or
`src/logosc/`, the same generated artefact or the same bootstrap hash.

| Title prefix | Subsystem | Merged because |
|---|---|---|
| `docs` (12), `documentation`, `manual` (4) | `docs` | all rewrite `docs/`, and the manual chapters regenerate the single file `docs/LOGOS.md` |
| `compiler` (2), `language` (5) | `compiler` | both edit `src/logosc/*.logos` and both change `bootstrap/logosc` |
| `stdlib` (3) | `stdlib` | `src/std/*.logos` + `rt.h`, no bootstrap change |
| `tooling` (6) | `tooling` | `tools/*.sh`, `Makefile` |
| `examples` (2) | `examples` | `examples/*` |
| `target` (1) | `target` | cross-target build + CI |

Label fallback uses `SUBSYSTEM_LABELS = {compiler, runtime, docs, documentation,
target, accessibility, tooling}` with `documentation → docs`; any other label
(`bug`, `hard`, `question`, `good first issue`, `help wanted`, `enhancement`,
`needs-info`) is not a subsystem. An issue with no title prefix and no subsystem
label is `unclassified`, and **`unclassified` collides with `unclassified`**:
unknown area is assumed to be the same area. Today that costs at most one
unclassified pick per run and never a silent file collision.

`runtime` has no title prefix in the current corpus but exists as a label
(`#80`, `#94`), so it stays in the map.

## 3.3 Eligibility exclusions, with the real issues they exclude

`EXCLUDED_LABELS = {question, needs-info, invalid, wontfix, duplicate, superseded, in-progress}`

An issue wearing one of these is not work an agent can start: it is a question
waiting on a human ruling, or a duplicate/superseded record, or already claimed.
Excluding them is what keeps the board from filling with cards whose first
action by any worker would be "ask the maintainer". Real exclusions in the
2026-11-20 corpus: `#67` (`question,needs-info`), `#89`, `#93`, `#98`
(`needs-info`), `#71`, `#76`, `#79` (`needs-info`).

The exclusion is a **skip**, not a filter: the issue is written to state with
`outcome: "skipped", skip_reason: "excluded-label"` so an operator can see the
pipeline considered it. It is re-evaluated next run (the label may come off).

## 3.4 The algorithm

```
candidates = [i for i in fetched if ready(i)]           # see 3.1
candidates.sort(key=lambda i: (i.created_at, i.number))  # FIFO: oldest first

picked = []
for i in candidates:
    if len(picked) == MAX_PICKS:
        record_skip(i, "cap");        continue
    if all(independent(i, p) for p in picked):
        picked.append(i)
    else:
        record_skip(i, "cross-reference" if mutual_ref(i, picked) else "subsystem-collision")
```

`mutual_ref(i, picked)` is true when `i` and any picked issue cite each other;
it exists only to pick the right `skip_reason` string. It never changes the
outcome.

Properties an implementer can assert in a test:

- `len(picked) <= MAX_PICKS`, always.
- `picked` is a subset of `candidates`, in `candidates` order.
- Every pair in `picked` satisfies `independent`.
- Fewer than 2 independent candidates ⇒ fewer than 2 picks. **Never** relax the
  independence test to reach 2, and never widen the candidate set to reach 2.
- An issue not picked this run stays `skipped` (or absent) in state, so it is
  considered again next run — no issue is starved, because the order is FIFO by
  creation and picks consume the front of the queue.

## 3.5 Why two, and why independence, in one paragraph

Two cards is the largest number the board can absorb per hour without the
maintainer losing track of what the fleet is doing, and it is the number the
operator asked for. Independence is what makes two *parallel* cards safe rather
than twice as expensive: two workers on the same subsystem produce two branches
that must be reconciled by hand, and two workers on a blocked/dependency pair
produce one card that cannot finish. The pipeline's job is to spend both slots
on work that can actually land side by side. When it cannot, one card — or
none — is the correct output, not a failed run.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/03-dossiers/02-issue-corpus-evidence.md
 -> the measured dependency lines, the 34/38 `**Done when:**` count, the umbrella issues
docs/pipelines/issue-intake/03-dossiers/04-selection-fixtures.json
 -> machine-readable cases for `ready`/`independent`, expected pick lists included
docs/pipelines/issue-intake/02-analysis/04-task-creation.md
 -> what happens to each picked issue
