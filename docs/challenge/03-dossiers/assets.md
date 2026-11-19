# Assets — the files to create before launch, ready to paste

Everything in this page is a file the coordinator creates once, before
`2026-12-01`. None of it needs a decision: the text, the labels, the seeded
issues and the templates are final. Where a command must be run, the command is
here.

---

## 1. The entry form — `.github/ISSUE_TEMPLATE/challenge-entry.yml`

Drop in verbatim. It uses the same issue-form mechanism as the existing
`bug.yml`, so nothing new is needed on the repository side.

```yaml
name: Challenge entry
description: Enter the Logos Agent Challenge — build with Logos, or make Logos better.
title: "[entry] "
labels: ["challenge-entry"]
body:
  - type: markdown
    attributes:
      value: |
        One entry per issue. At most three entries per operator account. An
        entry may be edited until 2027-01-15 23:59 UTC.

        Agents are welcome. Disclose the agent and the operator: a disclosed
        entry is never scored lower, and an undisclosed one is not featured
        until the field is filled in.

        Rules: https://github.com/abaddon/logos/blob/main/docs/challenge/01-summary/program.md

  - type: dropdown
    id: track
    attributes:
      label: Track
      description: Declare one.
      options:
        - "A — build a program with Logos"
        - "B — land a pull request in abaddon/logos"
        - "C — port a program, or teach the language"
    validations:
      required: true

  - type: input
    id: repo
    attributes:
      label: Repository URL — or the pull request URL, for Track B
      description: A public repository with a LICENSE file, holding the Logos source. For Track B, link the pull request instead.
      placeholder: https://github.com/you/your-project
    validations:
      required: true

  - type: input
    id: run
    attributes:
      label: One run command
      description: "Executed from a fresh clone on x86_64 Linux with clang 14+. This is what gets run before anything is scored, so paste it exactly."
      placeholder: ./bin/logosc build main.logos -o app && ./app
    validations:
      required: true

  - type: textarea
    id: what
    attributes:
      label: What it does, and the output it prints
      description: Five sentences at most. End with the exact stdout the run command produces.
      placeholder: |
        Reads a JSON file and prints one CSV row per record.
        Refuses a record with a non-integer field and says which field, with exit 2.
        Output:
        a,1
        b,2
    validations:
      required: true

  - type: input
    id: agent
    attributes:
      label: Agent — model and harness
      description: For example "claude-sonnet-4.5 in Claude Code", "gpt-5 in a custom loop", "deepseek-v4 via Hermes". Say "written by hand" if that is the truth. Disclosing is a norm, not a handicap.
    validations:
      required: false

  - type: input
    id: operator
    attributes:
      label: Operator
      description: The GitHub account answerable for this entry.
    validations:
      required: true

  - type: checkboxes
    id: ack
    attributes:
      label: Acknowledgements
      options:
        - label: I read the rules, and I understand the repository accepts entries from agents acting through an operator's account.
          required: true
        - label: The code is mine to license, and the repository has a LICENSE file.
          required: true
```

Test it before launch: open the form URL, submit a test entry, confirm the
`challenge-entry` label was applied automatically, **remove that label**, then
close the issue as *not planned*. If the label did not apply, the counting
commands in the program return zero and every metric is wrong; if it is left on,
the test entry counts as entry one forever and the floor of 5 is really 4.

---

## 2. Labels to create

```sh
gh label create challenge-entry    --repo abaddon/logos --color 1d76db \
  --description "An entry to the Logos Agent Challenge" || true
gh label create challenge-findings --repo abaddon/logos --color fbca04 \
  --description "A defect or rough edge found by a challenge entry" || true
gh label list --repo abaddon/logos | grep challenge
```

`challenge-findings` is the metric M7 label. The coordinator applies it when an
entry exposes a limitation, with the entry's issue number in the body.

---

## 3. Seeded issues — the `good first issue` pathway

Today there are **3 open issues and 0 open `good first issue`**. The pathway is
therefore a seeded backlog, not an invitation. File these eight items before
launch; each names a source so no research is needed, and each has a done
condition a newcomer can check without asking.

**The eight items become eleven issues: 7 labelled `good first issue` and 4
labelled `help wanted`.** Rows 2 and 3 touch the compiler itself, so they need a
bootstrap rebuild and the six gates — a week's work for a newcomer, not a sitting.
Row 8 converts existing issue #6 into four.

**Filed 2026-11-19 as #52–#61 by [`../../../tools/seed-challenge-backlog.sh`](../../../tools/seed-challenge-backlog.sh):
ten issues, 6 `good first issue` and 4 `help wanted`, 12 open in total.** Row 1
was already fixed before seeding (`grep -n '35' docs/00-index.md` returns
nothing; every page says 36) so it was not filed, and row 8's issue #6 was closed
as `superseded` in favour of its four (#54–#57).

| # | Title | Label | Size | Done when |
|---|---|---|---|---|
| 1 | docs: the docs index says 35 diagnostic codes, the compiler emits 36 | `good first issue`, `docs` | tiny | `docs/00-index.md` says 36 in both places, matching `./tools/logosc.sh guide --json` (`codes: 36`). Two lines. |
| 2 | tooling: add `logosc fmt --check` (exit non-zero when a rewrite is needed) | `help wanted` | medium | `fmt -h` documents the flag; a test proves both outcomes; `fmt FILE` behaviour unchanged; bootstrap rebuilt and `tools/pr_gate.sh` green |
| 3 | tooling: add `logosc doctor` — an install self-check | `help wanted` | medium | `logosc doctor` reports clang path and version, the runtime file, the stdlib directory and the compiler version; exits 1 when anything is missing; bootstrap rebuilt and `tools/pr_gate.sh` green |
| 4 | docs: `limits.md` says a non-finite float literal is accepted and prints `inf`; the compiler refuses it | `good first issue`, `docs` | tiny | `docs/reference/limits.md` (A3) and `docs/01-summary/gap-register.md` are corrected to match the compiler: `(println 1e999)` is refused with `E0106` and a node path, already pinned by `tests/regress/float-range.check`. Verified 2026-11-18 on both v0.2.0 and this tree. |
| 5 | examples: a fourth example program, compared against a reference tool by `tools/accept.sh` | `good first issue` | medium | `examples/<name>.logos` exists, `tools/accept.sh` compares its output to the external tool, and the diff is empty |
| 6 | stdlib: string-to-integer parsing in `str` | `help wanted` | medium | a function with the signature conventions in `docs/reference/stdlib.md`, a documented error behaviour, and a passing `(test …)` node |
| 7 | language: ordering comparison for `:str` (`(< "a" "b")` is `E0100` today) | `help wanted` | medium | the checker accepts `<`/`>` on `:str`, `tests/regress/` covers the accepted and the refused case, and the diagnostic table is regenerated |
| 8 | manual: cause-and-fix hint for every diagnostic code — split four ways, one issue per two categories | `good first issue`, `docs` | small ×4 | four issues, each covering two of the eight categories, each with a hint per code, and `logosc guide --check` still current. Issue **#6** already exists for this; convert it into these four rather than duplicating it |

File one with, for example:

```sh
gh issue create --repo abaddon/logos \
  --title 'docs: the docs index says 35 diagnostic codes, the compiler emits 36' \
  --label 'good first issue,docs' \
  --body 'docs/00-index.md says "all 35 codes" and "35 codes" in the manifest row. `./tools/logosc.sh guide --json` reports 36. Fix both lines. Done when the two agree.'
```

Seven of the eleven issues are deliberately *documentation* fixes: a first
contribution should be landable in one sitting, because the point of the pathway
is the merge, not the difficulty. The four `help wanted` ones are scoped but
real compiler work, and they exist so the backlog is honest about difficulty
instead of labelling everything easy.

---

## 4. The showcase skeleton — `docs/showcase/`

Four files. `00-index.md` and `ledger.csv` are created before launch; the rest
are written by the coordinator as entries arrive.

### `docs/showcase/00-index.md`

```markdown
# Showcase — the Logos Agent Challenge, Round 1

Every entry that reproduced from its own run command, one row each. The agent
column is what the entrant disclosed; it is not verified. This table is generated
from `ledger.csv` — do not edit it by hand.

| # | Project | Track | Agent | Operator | Entry | Score |
|---|---|---|---|---|---|---|
| — | *no entries yet — Round 1 opens 2026-12-01* | | | | | |

- Machine-readable ledger: `ledger.csv`
- Rules: `../challenge/01-summary/program.md`
- Results: `results.md` (published 2027-01-27)
```

### `docs/showcase/ledger.csv`

```csv
entry_issue,track,agent,operator,repo,score,gate0,merged_prs,notes
```

One row per entry at close, header exactly as above. `score` is the rubric total;
`gate0` is `pass`, `fail` or `fixed`; `merged_prs` is Track B's count.

### `docs/showcase/<slug>.md`

`<slug>` is the entry's repository name, lowercased with hyphens — `json-to-csv`.
If two entries collide, append the entry issue number.

````markdown
# <project name>

<one sentence: what it does>

- **Track:** A
- **Agent:** <model and harness> · **Operator:** @<account>
- **Entry:** #<issue>
- **Score:** 8/10 — <one line on the two points lost>

## What it does

<the entrant's five sentences, lightly edited>

## Run it

```sh
git clone <repo> && cd <repo>
<the one command>
```

```text
<the recorded stdout of that command, pasted from the gate-0 run>
```

## What it shows about Logos

<two or three sentences: which language features carry the weight, and which
limit it ran into>
````

### `docs/showcase/results.md`

Published on results day; skeleton in
[`../02-analysis/selection-and-metrics.md`](../02-analysis/selection-and-metrics.md#publication-format).

---

## 5. Pre-launch commands, in order

```sh
# 1. The install path works from the published release, tagless.
cd "$(mktemp -d)"
gh release download --repo abaddon/logos \
  --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
sha256sum -c SHA256SUMS
tar -xzf logos-*-x86_64-linux.tar.gz
cd logos-*-x86_64-linux && ./bin/logosc version      # logos 0.2.0

# 2. The version story is consistent: publish v0.2.1, or re-point every claim.
gh release list --repo abaddon/logos
grep -rn '0\.2\.1' README.md CHANGELOG.md docs/ src/logosc/main.logos

# 3. This document is at a stable URL.
curl -sI https://raw.githubusercontent.com/abaddon/logos/main/docs/challenge/01-summary/program.md | head -1

# 4./5. The form and the showcase exist.
#      Open https://github.com/abaddon/logos/issues/new?template=challenge-entry.yml,
#      submit "test", confirm the label was applied, REMOVE the label, close it,
#      then check that M1 returns 0.

# 6. The backlog exists: >= 5 good first issue, >= 10 issues open in total.
gh issue list --repo abaddon/logos --label 'good first issue' --state open --json number --jq 'length'
gh issue list --repo abaddon/logos --state open --json number --jq 'length'

# 7. The labels exist (section 2).

# 8. A forkable starting point exists and the challenge page names it.

# 9./10. Soft checks: llms.txt, repo topics, README hero, MCP endpoint.
gh api repos/abaddon/logos --jq '.topics'
```

---

## 6. What to add to `docs/00-index.md`

One row, in the "Start here" table, after the contributor rows:

```markdown
| join the Logos Agent Challenge | `challenge/01-summary/program.md` — tracks, entry form, dates, rubric | 10 min |
```

---

SOURCES

- `../01-summary/program.md` — §4 (mechanics), §5 (awards), §9 (pre-launch checklist).
- `../02-analysis/selection-and-metrics.md` — the ledger's column meanings and the results skeleton.
- `../03-dossiers/verification-log.md` — the measurements these assets rest on.
- `../../reference/limits.md` — the documented limits the seeded issues are drawn from.
