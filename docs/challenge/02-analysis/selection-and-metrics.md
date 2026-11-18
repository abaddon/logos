# Selection and metrics — the rubric in full, and the baseline it moves

The program's judging rules are three paragraphs in
[`../01-summary/program.md`](../01-summary/program.md#6-how-entries-are-judged).
This page is the coordinator's working copy: worked examples so the rubric is
calibrated before the first entry arrives, the procedure step by step, the
publication format, the measured baseline, and where each metric is weak.

---

## 1. The rubric, as a decision procedure

Score every entry on five criteria, 0–2 each. Two of the five are binary facts,
one is a line count, one is a `diff`, and one is a judgement with a fixed test.

### Criterion 1 — Runs (0/1/2)

| Score | Condition |
|---|---|
| 2 | The entry's own run command, executed from a fresh clone on x86_64 Linux with clang 14+, exits 0 as written |
| 1 | It exits non-zero, the entrant fixes it before close, and the corrected command exits 0 |
| 0 | It cannot be made to run by close |

### Criterion 2 — States its own expectations (0/1/2)

The language's own testing form is `(test name (expect (out …) (code 0) (leaks 0)) …)`, run by
`logosc test FILE`.

| Score | Condition | How the coordinator checks |
|---|---|---|
| 2 | The repository contains ≥1 `(test …)` node and `logosc test` reports it passing | run `logosc test` on the entry's file(s) |
| 1 | No test node, but the writeup states the exact expected stdout, and running the program reproduces it | run the command, compare |
| 0 | No expected output anywhere | — |

### Criterion 3 — Substance (0/1/2)

Count lines of `.logos` source in the submitted repository (all of them, not the
largest file).

| Score | Condition |
|---|---|
| 2 | ≥150 lines, or a port of an existing program ≥100 lines |
| 1 | 40–149 lines |
| 0 | <40 lines |

### Criterion 4 — Canonical form (0/1/2)

`logosc fmt` has **no `--check` flag** — it rewrites in place. The test is:

```sh
cp prog.logos /tmp/copy.logos && logosc fmt /tmp/copy.logos && diff prog.logos /tmp/copy.logos
```

| Score | Condition |
|---|---|
| 2 | `diff` is empty for every submitted `.logos` file |
| 0 | `fmt` changes anything |

There is no middle score: the language claims one canonical spelling, and this
criterion measures whether the entry respects it.

### Criterion 5 — Handles a refusal (0/1/2)

| Score | Condition |
|---|---|
| 2 | The program refuses bad input explicitly, and the writeup names the diagnostic code it relies on (a `E0xxx` the compiler emits, or a deliberate rejection the program itself prints) |
| 1 | The writeup says what input it rejects, but the program does not demonstrate it |
| 0 | Bad input is ignored, or the writeup never mentions it |

### Worked examples

| Entry | 1 | 2 | 3 | 4 | 5 | Total | Featured? |
|---|---|---|---|---|---|---|---|
| A log-summariser, 220 lines, three `(test …)` nodes, `fmt`-clean, refuses a malformed line with an explicit message | 2 | 2 | 2 | 2 | 2 | **10** | yes — winner candidate |
| A JSON→CSV tool, 90 lines, no test node but the writeup pins the exact output, `fmt`-clean, ignores bad JSON silently | 2 | 1 | 1 | 2 | 0 | **6** | yes — the floor, and the writeup says what to fix next round |
| A "hello world" with a `map`, 25 lines, `fmt` changed a bracket, no expected output | 2 | 0 | 0 | 0 | 0 | **2** | no — ledger row only |
| A 300-line program whose run command needs a private package | 0 | — | — | — | — | **0** | no — Gate 0 failed, listed with the failure |

The fourth row is why Gate 0 comes first: scoring a program whose command does
not run measures the writeup, not the code.

---

## 2. The judging procedure

Six steps, ~10 minutes for a small entry and ~25 for a large one.

1. **Freeze.** At close, record the entry list:
   `gh issue list --repo abaddon/logos --label challenge-entry --state all --json number,author,createdAt,body > entries.json`.
2. **Gate 1 (disclosure).** For each entry, read the agent field. If it is empty, comment once asking for it — on the day the entry is opened, not at close, because no edit is accepted after close. An entry still empty at close is listed and scored, but not featured.
3. **Gate 0.** `git clone <repo>` into a scratch directory, run the entry's command, save stdout/stderr and the exit status. Record `pass` / `fail` / `fixed`.
4. **Score.** Apply criteria 2–5 to every entry that passed Gate 0. Write the scores into `docs/showcase/ledger.csv` — **`ledger.csv` is the only score sheet**; the table in `docs/showcase/00-index.md` is generated from it, so a number exists in exactly one place.
5. **Rank.** Highest total per track; ties break on `createdAt` (earlier wins, as recorded by GitHub). Track B ranks on merged-PR count, ties on earliest merge.
6. **Publish.** `docs/showcase/results.md` plus the showcase pages, in one pull request, on results day.

### Publication format

`docs/showcase/results.md` carries:

- the metric table (floor / target / stretch, with the measured number in bold next to each);
- the full ranked sheet, including non-featured entries and their scores — a public score is a fair score;
- one line per entry naming its gate-0 outcome and the one thing the entry's author should fix;
- the primary-success verdict in the first line: `Primary success: M1 = 9 (floor 5) · M4 = 3 (floor 2) — met.`

---

## 3. Baseline, measured 2026-11-18

Every metric in the program starts from a number measured on this tree, not from
zero by assumption.

| Metric | Baseline | Command |
|---|---|---|
| Merged PRs, all authors | **32** | `gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged" --jq .total_count` |
| Merged PRs by the owner | **31** | same, `--paginate --jq '.items[].user.login' \| sort \| uniq -c` |
| Merged PRs by anyone else | **1** — PR #12, `Sonike`, "fix: print narrow integers and f32 without explicit casts", 130+/40−, with a regress case and a manual chapter | same |
| Open issues | **3** — #41 (label sweep), #10 (macOS target), #6 (manual hints) | `gh issue list --repo abaddon/logos --state open` |
| Open `good first issue` | **0** (4 ever, all closed: #3, #4, #5, #14) | `gh issue list --repo abaddon/logos --label 'good first issue' --state all` |
| Stars / forks | **0 / 2** | `gh api repos/abaddon/logos --jq '{stars:.stargazers_count,forks:.forks_count}'` |
| Entries | **0** (label does not exist) | — |
| Distinct external agents disclosed anywhere | **0** in the ledger; the compiler history carries 87 commits by `Logos Builder <agent@logos.local>` | `git log --format='%an' \| sort \| uniq -c` |

**Why the targets are what they are.** The floor (5 entries, 4 operators, 2
external merged PRs) is roughly a fivefold increase on the all-time external
contribution count of 1, which is what a program with a channel plan behind it
should achieve. The target (12/8/6) assumes the MCP endpoint and the docs work
land — an agent that can call the compiler does not need to read a blog post. The
stretch (25/15/12) assumes a second round of organic links and is not what the
program is planned against.

Two honest notes:

- **0 stars** means there is no audience to convert; every entry is a new arrival.
  If M1 misses the floor, the likely cause is reach (the channel plan), not the
  program — and the recap should say which.
- **PR #12 is the existence proof.** An outside contributor can land a compiler
  fix in this repository with a regress case and a manual chapter in one pull
  request. Track B is not a hypothesis.

---

## 4. Where the metrics are weak

| Metric | Weakness | What is done about it |
|---|---|---|
| M3 distinct agents | self-reported; the coordinator cannot verify a model name | reported as "disclosed agents", never as "agents that exist" |
| M4 merged PRs | counts trivial merges equally | the repo's gate is the filter; the recap names the substantive ones |
| M6 reuse | forks and inbound links undercount copy-paste | stated as a lower bound |
| M7 defects | depends on the coordinator filing them at close | filed during judging step 6, in the same pull request as the results, so it cannot be skipped |
| All of them | a 45-day window with a small N | every number is published with its floor/target/stretch, so a miss is legible rather than smoothed over |

---

## 5. Tie-breaks and edge cases, decided in advance

| Situation | Rule |
|---|---|
| Two entries tie on total | earlier `createdAt` wins |
| A Track B PR is opened before `L` and merged inside the window | counts — the merge is the event, not the open |
| A Track B PR is merged by the owner after close | does not count; the window closes on the merge timestamp |
| An entry is edited after close | the entry as of close is judged; edits after close are ignored |
| An entrant also volunteered to judge | they are not a judge; the coordinator judges alone |
| An entry arrives from an account with no public history | eligible; the ledger records the account |
| Two entries from one operator are the same project | the later one is marked duplicate in the ledger, both are scored |
| An agent submits under three different operator accounts | allowed up to 3 entries each, since the limit is per operator and each operator is answerable for their own |

---

SOURCES

- `../01-summary/program.md` — the program this page serves (§5 awards, §6 judging, §8 metrics).
- `../02-analysis/feasibility.md` — why each judging check is mechanically possible.
- `../03-dossiers/verification-log.md` — the commands behind the baseline table.
- `../03-dossiers/assets.md` — `ledger.csv` header and the `results.md` skeleton.
