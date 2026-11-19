# What was published, what it returns, and what it cost

Everything below was executed from this host on 2026-11-18/19 by an agent
operating the GitHub account `abaddon`. Each row names its evidence; the raw
commands and outputs are in
[`../03-dossiers/verification-log.md`](../03-dossiers/verification-log.md).

## 1. The repository is claimable — the precondition for every other row

| Check | Before | After | Evidence |
|---|---|---|---|
| `good first issue` open | 0 | **6** | `gh issue list --label 'good first issue' --state open --json number --jq length` |
| issues open in total | 3 | **12** | issues #52–#61 filed, #6 closed as `superseded` by #54–#57 |
| `challenge-entry` label | absent | **present** | `gh label list \| grep challenge` |
| entry form | absent | **`.github/ISSUE_TEMPLATE/challenge-entry.yml`** | PR [#62](https://github.com/abaddon/logos/pull/62) |
| showcase + ledger | absent | **`docs/showcase/00-index.md`, `ledger.csv`** | PR [#62](https://github.com/abaddon/logos/pull/62) |
| forkable starting point named | no | **`examples/agent-gate/`** named in Track A | PR [#62](https://github.com/abaddon/logos/pull/62) |
| repository topics | 10 | **12** — `good-first-issues` and `llms-txt` added | `gh api repos/abaddon/logos --jq .topics` |

The spec in `docs/challenge/03-dossiers/assets.md` called for eight seeding items
that become eleven issues. Ten were filed: the first item ("the docs index says
35 diagnostic codes") had already been fixed, so filing it would have been a
false defect report — `grep -n '35' docs/00-index.md` returns nothing and every
page says 36. That correction is recorded in `assets.md` itself rather than left
as a trap for the next person to file.

## 2. Two third-party publications

### 2.1 `github/awesome-copilot` — `instructions/logos.instructions.md`

- **PR:** [#6516](https://github.com/github/awesome-copilot/pull/6516), titled
  `Add Logos instructions 🤖🤖🤖` (the repo's documented agent fast-track marker).
- **What it is:** the largest public catalog of agent instruction files (41,331
  stars, 195 instruction files, pushed continuously). A file here is loaded by
  Copilot and mirrored by clients that consume the same catalog.
- **Why this file and not a post:** a frontier model has never seen Logos, so an
  agent asked to write it produces plausible Lisp that does not compile — `;` is
  a parse error, `let` without a use is `E0107`, a dropped result is `E0602`.
  The file is written for that failure, and it is the only publication in this
  batch that changes what a third-party agent *can do*, not just what it knows.
- **Verification:** all four `logos` blocks in the file were compiled and run
  with the published compiler (v0.2.2) before the PR was opened. Outputs `3`,
  `42`, `42`, `7`; the block carrying a `(test …)` node reports
  `1 passed, 0 failed, 0 leaked` at both `-O0` and `-O2`.
- **Catalog CI at open:** `validate-readme` (the generated index row),
  `codespell`, `check-line-endings`, `evaluate`, `scan`, `pr-check` — pass.

### 2.2 `up-for-grabs.net` — `_data/projects/logos.yml`

- **PR:** [#6451](https://github.com/up-for-grabs/up-for-grabs.net/pull/6451).
- **What it is:** the curated index of projects with newcomer tasks, consumed by
  several aggregators and by the `goodfirstissue`-style feeds. Its listing
  criteria are exactly what check 6 was cleared for: curated small tasks, an
  available maintainer, an active project.
- **Why it is worth one YAML file:** it is machine-readable, it is where people
  look when they have decided to contribute *somewhere* and need a candidate,
  and the `upforgrabs` block points directly at the label URL that now exists.

## 3. What it returns, measured rather than hoped

| Metric | Value on 2026-11-19 (baseline) | Read it with |
|---|---|---|
| repository stars / forks | 0 / 2 | `gh api repos/abaddon/logos --jq '.stargazers_count, .forks_count'` |
| open issues | 12 | `gh issue list --state open --json number --jq length` |
| `good first issue` open | 6 | same, `--label 'good first issue'` |
| challenge entries | 0 — Round 1 opens 2026-12-01 | `gh issue list --label challenge-entry --json number --jq length` |
| merged PRs from outside the owner's account | 1, ever | `gh pr list --state merged --json author` |
| v0.2.2 tarball downloads | see the API at read time | `gh api repos/abaddon/logos/releases` |

The lens for the next review is in
[`../02-analysis/channels.md`](../02-analysis/channels.md#how-to-read-the-result):
the first number that matters is not stars, it is **entry issues opened by an
account other than the owner's**, because that is what "third-party agents are
using this" means in a form that cannot be faked by the maintainer.

## 4. What was deliberately not done

| Not done | Why | What would unblock it |
|---|---|---|
| A post to Show HN or r/LocalLLaMA | no account here, and both venue rules require disclosed authorship and account history; a cold promotional post from a new account is removed, not read | the owner's own account, after wave 1 has run |
| An official MCP Registry entry | the registry indexes installable packages; this host has no npm/PyPI credential and no Docker daemon, so there is nothing to install from | one published package (`npm`, `pypi` or `oci`), which also needs a remote endpoint to be worth listing |
| Six MCP-adjacent listings (mcp.so, Smithery, both awesome-mcp lists, Docker catalog, HF Space) | same missing artifact, plus HF and Docker Hub credentials | the same package, and a public endpoint |
| A `CLAUDE.md`, `.cursorrules` or Cursor rules file in another catalog | `awesome-cursorrules` last pushed 2026-05-30 and is stale; a second instruction catalog adds a maintenance surface without adding a reader | a catalog that is actively maintained |

No publication above claims a result it has not measured, and no channel is
recorded as executed unless a URL exists that returns it.
