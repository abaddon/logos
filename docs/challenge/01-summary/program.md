# The Logos Agent Challenge — Round 1

**This page is the program.** A coordinator can run Round 1 from this document
without making another decision: every date is explicit, every award is one the
repository can actually deliver, every metric is a command, and every branch
("what if nothing happens?") has a rule attached.

One sentence: *an open challenge that pays out in visibility and merged code
rather than money, aimed at third-party agents and the people who run them.*

- Launch: **Tuesday 2026-12-01** (called `L` below; every other date is `L+n`).
- Entries close: **Friday 2027-01-15, 23:59 UTC** (`L+45`).
- Three tracks, one entry form, one ledger, one showcase.
- **No money and no swag.** Section 5 says why, and what would have to be true
  before that changes.
- Feasibility of every mechanism, with the command that proves it:
  [`../02-analysis/feasibility.md`](../02-analysis/feasibility.md).
- Judging rubric, metric definitions and baseline:
  [`../02-analysis/selection-and-metrics.md`](../02-analysis/selection-and-metrics.md).
- Paste-ready assets (entry form, labels, seeded issues, showcase template):
  [`../03-dossiers/assets.md`](../03-dossiers/assets.md).

---

## 1. Why a challenge and not a launch post

A launch post asks for attention. A challenge asks for a commit. The repository's
problem is not that nobody has heard of it — it is that 31 of its 32 merged pull
requests were authored by the owner, and exactly one came from outside (PR #12,
Sonike: a compiler fix with a regress case and a manual chapter). One post
produces reads; one entry produces a programme the compiler had to accept, which
is evidence nothing else in this repository can manufacture.

Two things are counted as the program working, and nothing else:

1. **Things built with Logos** that run, published where someone else can copy
   them.
2. **Code that landed in Logos** from an account that had never landed code
   before.

Everything below is scaffolding for those two numbers.

---

## 2. The three tracks

An entry declares exactly one track. The tracks differ only in what "done" means;
the entry form, the gate and the ledger are identical.

### Track A — Build

Write a program in Logos and publish it in a public repository. It must build
from the published release with one command and do something a reader can name
in one sentence.

Examples of the right size: a JSON-to-CSV converter, a log summariser, a
`wc`-class tool with a real test node, a small network-free simulator, a static
analyser for `.logos` files. The compiler's own `examples/` directory is the
calibration and its spread is wide: `matrix.logos` is 73 lines, `wc.logos` 94,
`json.logos` 487. A 70-line program that does one thing well is a real entry.

Not eligible: a program that only prints a string; a program whose interesting
part is not in Logos; anything that needs the network at run time.

### Track B — Improve

Land a pull request in `abaddon/logos` during the window. Bug fixes, tooling,
examples, documentation and missing standard-library pieces all count. The
repository's own rules apply unchanged: a compiler change needs a `tests/regress/`
case that fails before the fix, every commit needs a `Signed-off-by` trailer, and
`bash tools/pr_gate.sh` must print six gate PASS lines after its sign-off
precondition.

This is the track with the lowest barrier and the shortest feedback loop: a
merged one-line documentation fix scores exactly as much as a merged compiler
fix, and both appear in the ledger. Its one real cost is the gate itself — a full
`tools/pr_gate.sh` run measured **1 h 08 m** on 6 cores on 2026-11-18 — so the
entry form tells Track B entrants to budget an hour, not ten minutes, and to run
the gate once rather than after every edit.

### Track C — Port and teach

Translate something that already exists, or teach the language so that someone
else can. Two accepted shapes:

- **A port**: translate an existing program of at least 100 lines (C, Python,
  Go, Rust, whatever) into Logos, keeping its behaviour, with the original
  linked in the writeup.
- **A lesson**: a tutorial or example set of at least 3 self-contained programs,
  each ≤120 lines, each with the exact stdout it produces, covering at least 3
  features a beginner hits (`map`, `str`, allocation with `free`, a diagnostic
  the compiler refuses).

Not eligible: a restatement of `docs/LOGOS.md`; a tutorial whose programs have
not been compiled.

---

## 3. Who may enter, and the disclosure norm

**Anyone may enter** — a person, or an agent driven by a person. The repository
already accepts pull requests from AI agents acting through an operator's
account, under the same gates as anyone else; the challenge writes that down
where an entrant will see it.

**Agents are welcome. Disclose the agent.** Every entry states:

- **the agent**: the model and the harness (for example `claude-sonnet-4.5 in
  Claude Code`, `gpt-5 in a custom loop`, `deepseek-v4 via Hermes`);
- **the operator**: the GitHub account the work is submitted from, which is the
  account answerable for it.

This is a disclosure norm, not a handicap. A disclosed entry is never scored
lower than an undisclosed one, and the ledger prints the agent in a column next
to every project. Three consequences, all intended:

1. A featured entry says what wrote it, because "an agent wrote this and the
   compiler accepted it" is the claim the whole project rests on.
2. An entry that hides its agent is asked once, publicly, to fill the field in.
   If it is still missing at close, the entry is not featured — the code is not
   disqualified, the *credit* is.
3. The operator is responsible for the submission, the licence, and the
   following of the entry rules. An agent cannot be the point of contact.

Rules for fairness: at most **3 entries per operator account**; an entry may be
edited until close; the same project may not be re-entered under a second
account; no entry may include code the entrant has no right to license.

---

## 4. How an entry is made

One entry is one issue on `abaddon/logos`, opened with the
`challenge-entry.yml` form ([`../03-dossiers/assets.md`](../03-dossiers/assets.md)
carries the exact YAML). The form asks for six fields and two acknowledgements,
and nothing else:

| Field | What it takes | Why it is required |
|---|---|---|
| Track | A, B, or C | routes the entry to the right gate |
| Repository or pull request URL | public repo with a `LICENSE` file, holding the Logos source — or, for Track B, the pull request URL | the entry must be copyable |
| Run command | one line, executed from a fresh clone (Track A and C); Track B leaves it as "merged" | the reproducibility gate |
| What it does | ≤5 sentences, and the expected output | a reader must be able to check it |
| Agent | model + harness, or "written by hand" | the disclosure norm; optional in the form so that Gate 1 has something to catch |
| Operator | the GitHub account answerable for the entry | the disclosure norm |

The two acknowledgements are: the rules were read, and the code is the entrant's
to license.

**Track B substitutes one field for two.** A Track B entry has no repository and
no run command of its own: its "repository" is the pull request URL and its run
command is `merged`. Gate 0 for Track B is "the pull request was merged inside
the window" — checked with `gh pr view <n> --json mergedAt,state` — and it is the
only track whose gate does not clone anything.

The issue is the **venue of record** — the ledger, the judging sheet and the
results all point at issue numbers, so a submission cannot get lost in a chat
thread.

Track B entrants do not need to open an entry issue as well as the pull request
if they would rather not: a merged pull request whose description names the agent
and the operator is listed by the coordinator at the ledger update following the
merge. The entry issue is the recommended route because it is the one that
appears in the entrant's own timeline and because the form prompts for the
disclosure field, which a pull-request description only carries by convention.

Where entries live:

- **The issue** — the venue of record for Track A and C, and for Track B when the
  entrant opens one; a merged Track B pull request is the record when they do not.
- **`docs/showcase/`** — one page per featured entry (`docs/showcase/<slug>.md`),
  linked from `docs/showcase/00-index.md`, which also carries the leaderboard
  table. Merged by the coordinator, never by the entrant, so the showcase stays
  consistent.
- **The repository topic** `logos-agent-challenge` — optional, for entrants who
  want their project findable next to the others. It is not a submission channel
  and is not counted; `logos-lang` is already used by 5 unrelated repositories,
  so the challenge uses its own name.

**Gate 0 — reproducibility.** Before an entry is scored, the coordinator runs the
entry's own run command from a fresh clone, on x86_64 Linux with clang 14+, and
records the exit status. `logosc` itself is provided to that run from the
published release: the coordinator unpacks the tarball and puts its `bin/` on
`PATH`, so an entry may write `logosc build main.logos -o app && ./app` and does
not have to vendor a compiler. Vendoring `bin/logosc` is allowed but not
required, and the entry's writeup must say which release version it was built
with. This is not a judgement call: the command either builds and runs or it does
not. An entry that fails is told which command failed and why, may fix it and ask
for one re-run, and is otherwise listed in the ledger as submitted but not
featured. The re-run is offered once, not repeatedly.

---

## 5. What an entry can win

Every award below is one this repository can deliver this month with no budget,
no logistics and no third party.

| Award | What it is, exactly | Cost |
|---|---|---|
| **Public leaderboard** | The `docs/showcase/00-index.md` table is the leaderboard: project, track, agent, entry and score, one row per entry that passes Gate 0, refreshed every Monday. It is the ledger and the leaderboard at once, so there is one number to keep correct, not two. | 2 minutes a week + 2 minutes a row |
| **Showcase page** | `docs/showcase/<slug>.md`: the writeup, the run command with its recorded output, the agent, and the score. Permanent, linkable, in-repo. | 15 minutes |
| **Co-author credit** | The commit that adds a showcase page carries `Co-authored-by: <entrant's git identity>`, so the entrant's name is in the repository's history, not just in a list. | free |
| **Maintainer credit** | Track B entries are already in the history: their commit is the credit. The next `CHANGELOG.md` version section names them under "Thanks". | free |
| **`good first issue` pathway** | The coordinator seeds 8 items that become 11 issues (7 `good first issue`, 4 `help wanted`) before launch, each with a done condition a newcomer can check. Landing one is a Track B entry by definition. | 1 hour, once |
| **Named in the recap** | `docs/showcase/results.md` lists every entrant, agent, score and merged PR. | 1 hour, once |

**What is not offered, and why it matters that it is not.**

- **No cash prize.** The repository has no `FUNDING.yml`, no GitHub Sponsors
  account, and no budget line. A promised bounty that is not paid is worse for
  the project than no challenge at all, so the program does not offer one.
- **No swag.** Physical rewards need a budget, an address-handling policy and a
  shipping destination per entrant. None of the three exists.
- **No "job", "internship" or "grant".** Nothing in the repository can back those
  words.

**The one amendment.** If the maintainer decides before `L-7` to fund Round 1,
the coordinator adds exactly this and nothing more, announced while entries are
open and never after:

> One cash award of £<amount> per track, paid once by the maintainer after results
> are announced — through GitHub Sponsors if the winner has a sponsorable
> account, otherwise by bank transfer to an account the winner names. Judging is
> unaffected: the award goes to the rubric's winner.

That is the entire amendment. No tiers, no runner-up prizes, no retroactive
change, no award added mid-round. If it is taken, exactly two lines change: the
ledger gains an `award` column, and the paste block's "No cash, no swag" sentence
becomes "One award per track — rules: <challenge URL>".

---

## 6. How entries are judged

Two gates and a rubric. The rubric is published before launch, every score is
published after, and the coordinator applies it alone — there is no panel to
convene and no judge to recruit.

**Gate 0 (reproducibility)** — as in section 4, binary.

**Gate 1 (disclosure)** — the agent field is filled in. Missing: asked once;
still missing at close: not featured.

**Rubric, 0–2 per criterion, maximum 10.** Chosen so that most points are
mechanical rather than aesthetic:

| # | Criterion | 0 | 1 | 2 |
|---|---|---|---|---|
| 1 | Runs | Gate 0 failed | runs after a fix | runs as submitted |
| 2 | States its own expectations | no expected output | expected output in the writeup | at least one `(test …)` node, run by `logosc test` |
| 3 | Substance | under 40 Logos lines | 40–149 lines | 150+ lines, or a port of a 100+ line program |
| 4 | Canonical form | `logosc fmt` rewrites the source | — | `logosc fmt` on a copy leaves it byte-identical (no `--check` flag exists today; the test is `cp x.logos y.logos && logosc fmt y.logos && diff x.logos y.logos`). If seeded issue 2 lands `fmt --check` during the round, the criterion uses that flag and the copy-and-diff is the fallback for entries that pass either way |
| 5 | Handles a refusal | ignores input errors | documents what it rejects | prints a diagnostic code the compiler can emit, or refuses explicitly in the writeup |

Track B does not use this rubric. Its score is the number of merged pull
requests inside the window, with a first-time-contributor marker in the ledger;
ties break on the earliest merge. A Track B entry that changes the compiler is
already held to a stricter published standard (regress case, six gates, DCO) and
adding a second rubric on top would be double-counting.

**Selection.** Featured = Gate 0 passed and score ≥6. Winner per track = highest
score, ties broken by the earlier entry timestamp (UTC, as recorded by GitHub).
Scored sheet published at `docs/showcase/results.md` on results day, including
entries that scored below 6 and why. One coordinator, one rubric, published
scores: nothing to negotiate.

---

## 7. Timeline

`L` = **Tuesday 2026-12-01**. All dates UTC.

| When | Date | What happens |
|---|---|---|
| Pre-launch | 2026-11-18 → 2026-11-27 | The pre-launch checklist in section 9, in order. Hard blockers only. |
| **Launch** | **Tue 2026-12-01** | Challenge page and entry form live; the 3-step block (section 10) goes out to the channels ranked in the channel map, top three first and in that order, because the map's own sequencing rule forbids posting to the open forums before the demo and the endpoint exist. |
| Ledger updates | Mondays: 12-07, 12-14, 12-21, 12-28, 01-04, 01-11 | One row per new entry, scores for anything finishing early, one comment in the tracking issue. |
| **Rescue checkpoint** | **Mon 2026-12-21** (`L+20`) | If fewer than 5 entries exist, extend the window by 14 days: close moves to **Fri 2027-01-29**, judging to **Mon 2027-02-01 → Fri 2027-02-05**, results to **Wed 2027-02-10**, recap to **Wed 2027-02-17**. The coordinator also sends the 10 invitations named in section 11. Announced once. No second extension. |
| **Entries close** | **Fri 2027-01-15, 23:59 UTC** (`L+45`) | Nothing accepted after this, edits included. |
| Judging | Mon 2027-01-18 → Fri 2027-01-22 | Gate 0 and score every entry; draft the showcase pages. |
| **Results** | **Wed 2027-01-27** | `docs/showcase/results.md` published; winners named; showcase pages merged. |
| **Recap** | **Wed 2027-02-03** | `docs/showcase/recap.md`: what was built, what landed, the three defects the entries exposed, and the Round 2 date. |

**Slip rule.** Launch depends on the hard blockers in section 9, not on the
calendar. If any hard blocker is red on **Fri 2026-11-27**, `L` moves to
**Tue 2026-12-08**; if it is still red on 2026-12-04, to **Tue 2026-12-15**; if
still red, to **Tue 2027-01-05** (the two weeks either side of the new year are
skipped deliberately). The table above gives each date with its `L+n` offset, so
the new dates are arithmetic, not judgement. A slip re-issues exactly four
artifacts: this timeline table, the close date inside the paste block (§10), the
close date inside the entry form (assets §1), and the two dates inside the M4/M5
queries (§8). The coordinator announces the slip once, in the same place as the
launch.

**Why 45 days, and why across the holidays.** Agents do not take holidays; their
operators do. A window that ends mid-January gives an operator who reads the
launch post on 2026-12-20 a full working month, and gives an agent a long enough
loop to attempt several entries. A 14-day sprint would have measured the
calendar, not the language.

**Coordinator load, stated up front.** Launch week is about 4 hours (page, form,
labels, seeded issues, first post). Each week after that is under 30 minutes.
Gate 0 costs about 5 minutes an entry; scoring and drafting a showcase page adds
10–20. Judging is therefore about 3 hours at the floor (5 entries) and 5–6 hours
at the target (12), inside one week. If the coordinator cannot hold that, the
program does not launch — a challenge that stalls mid-round damages the project
more than one that never started.

---

## 8. Metrics

Definitions are commands, run at close and again at recap. Baseline measured on
2026-11-18 is in [`../02-analysis/selection-and-metrics.md`](../02-analysis/selection-and-metrics.md).

| # | Metric | How it is counted | Floor | Target | Stretch |
|---|---|---|---|---|---|
| M1 | Entries submitted | labelled issues, count | 5 | 12 | 25 |
| M2 | Distinct operator accounts | unique issue authors | 4 | 8 | 15 |
| M3 | Distinct agents disclosed | unique agent strings in the ledger CSV | 3 | 6 | 10 |
| M4 | Merged PRs from outside the owner | merged-in-window authors, minus `abaddon` | 2 | 6 | 12 |
| M5 | First-time landers | M4 authors with no merged PR before `L` | 1 | 4 | 8 |
| M6 | Entries reused elsewhere | per showcase repo: forks after entry, or inbound issues/PRs | 1 | 3 | 8 |
| M7 | Defects found by entries | issues labelled `challenge-findings` | 8 | 15 | 30 |

The commands, exactly as the coordinator runs them:

```sh
# M1 — entries (the pre-launch test entry has had its label removed, see §9)
gh issue list --repo abaddon/logos --label challenge-entry --state all \
  --json number --jq 'length'

# M2 — distinct operator accounts
gh issue list --repo abaddon/logos --label challenge-entry --state all \
  --json author --jq '[.[].author.login] | unique | length'

# M3 — distinct agents (from the ledger CSV's agent column)
tail -n +2 docs/showcase/ledger.csv | cut -d, -f3 | sort -u | wc -l

# M4 — merged PRs inside the window, excluding the owner
gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged+merged:2026-12-01..2027-01-15+-author:abaddon" \
  --paginate --jq '.items | length'

# M5 — of those, first-time landers: authors with no merged PR before launch
gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged+merged:<2026-12-01" \
  --paginate --jq '.items[].user.login' | sort -u > /tmp/before.txt
gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged+merged:2026-12-01..2027-01-15" \
  --paginate --jq '.items[].user.login' | sort -u > /tmp/after.txt
comm -13 /tmp/before.txt /tmp/after.txt | wc -l

# M6 — reuse, one line per showcase repository (repo column is full URLs)
tail -n +2 docs/showcase/ledger.csv | cut -d, -f5 | sed 's#https://github.com/##' | while read -r r; do
  printf '%s\t%s\n' "$r" "$(gh api "repos/$r" --jq '[.forks_count, .watchers_count] | @tsv')"
done

# M7 — defects found by entries
gh issue list --repo abaddon/logos --label challenge-findings --state all \
  --json number --jq 'length'
```

Two notes on the queries: GitHub's search API is rate-limited per minute, so run
them once at close rather than in a loop; and M6's fork count is a *lower bound*
on reuse, because copy-paste is invisible to it.

**Primary success = M1 ≥ 5 and M4 ≥ 2.** Everything else is diagnostic. If the
floor is missed, the recap says so in its first line and names the reason it is
judged to have happened; the remedy for Round 2 follows from that reason, not
from a wish.

M7 exists because a challenge is also a test harness: every entry built by an
agent outside the project is a probe of the language's ergonomics. Each entry's
rough edges are filed by the coordinator as `challenge-findings` issues, with the
entry's issue number in the body. An entry that produces no finding and no merged
code is a weak entry even if it runs.

---

## 9. Pre-launch checklist

Run in order on 2026-11-27. Anything in the **hard** column that is red invokes
the slip rule. Commands are in
[`../03-dossiers/assets.md`](../03-dossiers/assets.md#5-pre-launch-commands-in-order).

| # | Check | Hard? | Done when |
|---|---|---|---|
| 1 | The install path works from the published release, tagless | hard | `gh release download --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS` + `sha256sum -c SHA256SUMS` + `./bin/logosc version` all succeed. **Verified 2026-11-18 against v0.2.0.** |
| 2 | One version is published and every page names it | hard | `gh release list --repo abaddon/logos` shows `v0.2.2` as Latest and `grep -rn '0\.2\.1' README.md CHANGELOG.md docs/ src/logosc/main.logos` returns only the CHANGELOG's record that `v0.2.1` was tagged and refused by the release gate. **Resolved 2026-11-18:** `v0.2.1` was tagged and its packaging gate stopped the release (the README linked a page the tarball did not carry); `v0.2.2` publishes with the fix, and the README, install page, quickstart and `logosc version` all name it |
| 3 | This document merged, at a stable URL | hard | `curl -sI https://raw.githubusercontent.com/abaddon/logos/main/docs/challenge/01-summary/program.md` returns 200 |
| 4 | `challenge-entry.yml` merged and filing an issue | hard | open the form URL, submit a test entry, **remove its `challenge-entry` label**, close it, then `M1` returns 0 |
| 5 | `docs/showcase/` exists with an empty ledger table and the `ledger.csv` header | hard | `docs/showcase/00-index.md` renders with 0 rows and `docs/showcase/ledger.csv` exists with its header line |
| 6 | At least 5 `good first issue` open, and at least 10 scoped issues open in total | hard | `gh issue list --repo abaddon/logos --label 'good first issue' --state open --json number --jq 'length'` ≥ 5 and `gh issue list --repo abaddon/logos --state open --json number --jq 'length'` ≥ 10. **Today: 3 open, 0 of them `good first issue`.** The eight seeding items (eleven issues) are in [`../03-dossiers/assets.md`](../03-dossiers/assets.md#3-seeded-issues--the-good-first-issue-pathway) |
| 7 | Labels created: `challenge-entry`, `challenge-findings` | hard | `gh label list --repo abaddon/logos \| grep challenge` lists both |
| 8 | A forkable starting point exists and the challenge page names it | hard | if the reference demo has not merged, `examples/wc.logos`, `examples/json.logos` and `examples/matrix.logos` are named instead — they build and run, and `tools/accept.sh` compares them against external references |
| 9 | `llms.txt`, repo topics, README hero | soft | the docs task's own checklist |
| 10 | MCP endpoint live | soft | the endpoint's own checklist |

Checks 1–8 are the program. Checks 9–10 make it findable, and a launch without
them still runs — it just reaches fewer agents.

---

## 10. The one-page block, ready to paste

Four destinations, one block, in this order — it is the channel map's order, and
the map's own rule is that nothing is posted to an open forum before an agent can
call the compiler:

1. **The repo surface** — the README's "build something with it" section and
   `llms.txt`. This is a file, not a post, and it lands first because every other
   destination links to it.
2. **The MCP registry record and the npm package description** — the block's
   first four lines, as the description of the tool an agent finds by searching.
3. **A Show HN post**, once the endpoint and a runnable demo exist.
4. **r/LocalLLaMA**, two weeks after the HN post, with the authorship disclosed in
   the first line — that subreddit's self-promotion rules require it.

The block's commands were executed verbatim on 2026-11-18, and the
`gh release download` form carries no version number, so it cannot rot when the
next release ships.

```text
Logos Agent Challenge — build something with Logos, or make Logos better.
Agents welcome: say which agent you are and whose account you act through.

1. Get the compiler (x86_64 Linux, clang 14+):
   gh release download --repo abaddon/logos \
     --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
   sha256sum -c SHA256SUMS && tar -xzf logos-*-x86_64-linux.tar.gz
   cd logos-*-x86_64-linux && ./bin/logosc version     # logos 0.2.0

2. Make one thing run with one command:
   printf '(mod hello)\n\n(fn main :void ()\n  (println "hello from logos"))\n' > hello.logos
   ./bin/logosc build hello.logos -o hello && ./hello  # hello from logos

3. Submit: https://github.com/abaddon/logos/issues/new?template=challenge-entry.yml
   Repo URL + that one command + 5 sentences + your agent and operator.

Three tracks: build a program (A) · land a pull request in Logos (B) ·
port or teach it (C). Entries close 2027-01-15 23:59 UTC.
Every entry that reproduces gets a row in the ledger; featured entries get a
page in docs/showcase/ and a co-authored commit. No cash, no swag — this is a
reputation and merged-code challenge, stated plainly so nobody is surprised.
Rules: https://github.com/abaddon/logos/blob/main/docs/challenge/01-summary/program.md
```

Two things a sender must not change: the `gh release download` form (adding
`v0.2.1` breaks it — that release does not exist), and the "no cash, no swag"
line (removing it produces exactly the reply the program cannot answer).

---

## 11. What could go wrong

Named here so the coordinator meets it as a plan rather than a surprise.

| Risk | What it looks like | The rule |
|---|---|---|
| **Zero entries** | silence after launch | Rescue checkpoint at `L+20`: one 14-day extension, plus the 10 invitations below, then close and publish the recap with the reason. The recap is published either way. |
| **The 10 invitations** | who gets invited, decided in advance | `gh search repos 'AGENTS.md in:readme' --topic ai-agents --sort stars --limit 10 --json fullName` — one issue per repository, addressed to its operator, with the paste block. Run on 2026-11-18 it returns `affaan-m/ECC`, `deepseek-ai/deepseek-harness`, `NousResearch/hermes-agent`, `firecrawl/firecrawl`, `DietrichGebert/ponytail`, `Graphify-Labs/graphify`, `stablyai/orca`, `browser-use/browser-use`, `thedotmack/claude-mem`, `paperclipai/paperclip`. Re-run the query on the day, do not reuse this list, and do not @-mention more than once per repository. |
| **Entry spam** | dozens of "hello world" repos | Gate 0 does not filter them — criterion 3 does, and the ledger row costs 2 minutes. There is no cap on entries that fail the rubric, because a public row saying "40 lines, no test, 2/10" is a fair answer. |
| **An agent floods Track B** | 30 trivial PRs | The repo's own gates reject most of them (regress case, DCO, six gates). If a flood still arrives, the coordinator merges the good ones and labels the rest `challenge-findings`, which is the honest outcome: a language whose gate accepts trivia has a gate problem, and that is worth learning. |
| **Coordinator disappears** | ledger stops updating | The window still closes on its date and the results page is still published, even if empty. An unjudged round is a failure; a *late* round is a normal risk. |
| **A winner's entry cannot be licensed** | showcase page cannot quote the code | Eligibility requires a `LICENSE` file at entry. Discovered at close: the entry is listed, not featured. |
| **Someone asks for prize money** | the obvious question | Section 5's answer, verbatim: no budget, and the amendment is the only path. |
| **The release is still v0.2.0** | entrants' writeups cite a version that differs from the README | The paste block is tagless and the challenge page names `v0.2.0` explicitly. If `v0.2.1` ships mid-round, the tagless command keeps working and the challenge page gets one line saying so. |

---

## 12. After the round

The recap is not a blog post; it is the input to Round 2.

1. `docs/showcase/results.md` — every entry, agent, score, merged PR, and the
   scored sheet.
2. `docs/showcase/recap.md` — the three most consequential of the M7 findings
   (each linked to its `challenge-findings` issue), the metric table with
   floor/target/stretch marked, and one paragraph naming the reason for each miss.
3. Round 2's date, set at the recap: the first Tuesday at least 8 weeks after the
   recap, or "not before v1.0", whichever the metrics argue for. Written down in
   the recap, so the program has a next step that does not depend on anyone
   remembering it.

---

SOURCES

- `../02-analysis/feasibility.md` — each mechanism and award cross-checked
  against the repository and GitHub's actual capabilities, with the command that
  proves it.
- `../02-analysis/selection-and-metrics.md` — the rubric in full, the baseline
  measured on 2026-11-18, and the exact metric queries.
- `../03-dossiers/assets.md` — the entry form YAML, the label list, the seeded
  issue table, the showcase and ledger templates, and the pre-launch commands.
- `../03-dossiers/verification-log.md` — every command run while writing this,
  with its output.
- `/root/ai-language-program/.worktrees/t_c0360ffd/docs/messaging/01-summary/positioning-kit.md`
  — the voice rules and the verified copy blocks this document borrows from.
- `/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/01-summary/findings.md`
  — the channel ranking that section 10's block is sent through.
