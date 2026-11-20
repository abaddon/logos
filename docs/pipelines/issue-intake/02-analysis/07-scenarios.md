# 7 — Worked scenarios

Eight traces. Each is a complete run: input, decision, log line, state delta.
Two use the live repository's real issues and timestamps; the rest use
synthetic issue numbers so the rule under test is the only variable. An
implementation that reproduces these traces is done.

Notation: `→` is one run. `~` marks a line that is not printed (internal state).

---

## 1 — No new issues (the steady state)

**Input.** State has 38 entries (`seeded` or `picked`). The fetch returns the
same 38 open issues, `304 Not Modified` against `last_etag`.

**Decision.** Nothing is unseen, so nothing is a candidate.

**Output.** Empty stdout — the cron job stays silent. `last_run_at` and
`last_run` are updated; `issues` is untouched. Exit 0.

```
~ run 2026-11-20T13:00:02Z fetched=38(304) unseen=0 ready=0 picked=0 created=0 failed=0
```

This is the expected output of 23 of every 24 runs.

---

## 2 — One new issue

**Input.** `#101` created 2026-11-20T12:41:00Z, title
`docs: limits.md links the wrong anchor`, labels `[docs]`, body has
`**Done when:**` bullets, no `#N` references.

**Decision.** new ✓, not excluded ✓, not blocked ✓, not umbrella ✓ → ready.
Only candidate, so it is picked alone (independence is vacuous with one pick).

**Output.**

```
logos-issue-intake 2026-11-20T13:00:02Z fetched=39 prs=0 unseen=1 ready=1 picked=1 created=1 failed=0 picks=#101
```

**Board side effect.** One task:

- title `[logos#101] docs: limits.md links the wrong anchor`
- assignee `oss-contributor` (label `docs`)
- workspace `worktree:/root/ai-language-program/.worktrees/gh-101`, branch `wt/gh-101`
- idempotency key `logos-issue-101`
- body: the §4.3 template, `Subsystem: docs`, the extracted `**Done when:**`
  bullets in the acceptance section

**State delta.** `issues["101"] = {outcome: "picked", task_id: "t_…", …}`.

---

## 3 — Three new independent issues ⇒ picks 2

**Input.** Three issues created in the same ten minutes:

| # | created_at | title | labels | subsystem | refs |
|---|---|---|---|---|---|
| 102 | 12:10:00Z | `compiler: generic arity is not checked across module boundaries` | `[compiler]` | compiler | — |
| 103 | 12:20:00Z | `runtime: vec-free on a zero-length buffer reads the header` | `[bug, runtime]` | runtime | — |
| 104 | 12:30:00Z | `docs: the stdlib page lists 21 functions, the compiler exports 22` | `[docs]` | docs | — |

**Decision.** All three are ready. FIFO order is `#102, #103, #104`.

- `#102` picked (no pair to test).
- `#103` vs `#102`: no mutual refs, `{runtime} ∩ {compiler} = ∅` → independent → picked.
- `#104`: `len(picked) == MAX_PICKS` → not examined for independence; recorded
  `outcome: "skipped", skip_reason: "cap"`.

**Output.**

```
logos-issue-intake 2026-11-20T13:00:02Z fetched=41 prs=0 unseen=3 ready=3 picked=2 created=2 failed=0 picks=#102,#103 skipped=#104:cap
```

**Next run (14:00).** `#104` is the only unseen ready issue → picked alone.
One hour later of latency, never a dropped issue: that is the whole cost of the
two-per-hour cap.

---

## 4 — A same-subsystem burst (real data)

**Input.** On 2026-11-19 six issues were opened within 45 seconds, measured from
the live API:

| # | created_at | labels | title prefix |
|---|---|---|---|
| 86 | 08:35:06Z | `docs` | `docs:` |
| 87 | 08:35:10Z | `good first issue, docs` | `docs:` |
| 90 | 08:35:21Z | `good first issue, docs` | `docs:` |
| 96 | 08:35:42Z | `good first issue, docs` | `docs:` |
| 97 | 08:35:46Z | `good first issue, docs` | `docs:` |
| 98 | 08:35:50Z | `docs, needs-info` | `docs:` |

**Decision.**

- `#86` ready → picked (subsystem `docs`).
- `#87`, `#90`, `#97` ready → `subsystem-collision` with `#86`. All four rewrite
  `docs/`, and three of them edit pages that feed the single generated
  `docs/LOGOS.md`; two workers would collide in `git` on every commit.
- `#96` not ready: its body carries
  `- **Sequenced after:** … #52, #78, #82, #86, #90`, and `#52`, `#78`, `#82`,
  `#86`, `#90` are all open → `skip_reason: "blocked"`.
- `#98` `excluded-label` (`needs-info`).

**Output.**

```
logos-issue-intake 2026-11-19T09:00:01Z fetched=38 prs=0 unseen=6 ready=4 picked=1 created=1 failed=0 picks=#86 skipped=#87:subsystem-collision,#90:subsystem-collision,#96:blocked,#97:subsystem-collision,#98:excluded-label
```

**Drain behaviour.** `#87` at 10:00, `#90` at 11:00, `#97` at 12:00 — one docs
card per hour, no two of them in flight together. `#96` stays `blocked` in every
run until its five predecessors close, then becomes ready. The pipeline's
throttle is the same mechanism as its collision avoidance, which is why no
separate "rate limit per label" rule is needed.

---

## 5 — A blocked candidate is skipped, the scan continues

**Input.** Unseen: `#110` (`tooling: fmt --check`, no refs) and `#111`
(`tooling: fmt --check exit codes`, body line `**Blocked by:** #110 — one
contract, two flags`).

**Decision.** `#110` ready → picked. `#111` `structural_refs = {110}` and `#110`
is open → `blocked`, not ready. It never reaches the pair test, so it cannot
consume the second slot.

**Output.**

```
logos-issue-intake 2026-11-20T13:00:02Z fetched=41 prs=0 unseen=2 ready=1 picked=1 created=1 failed=0 picks=#110 skipped=#111:blocked
```

If a third unseen `#112` (`runtime: …`) existed, it would be picked next to
`#110`.

---

## 6 — Two candidates citing each other: the pair test rejects the second

**Input.** Unseen, both ready individually:

- `#105` `compiler: unify generic aggregates`, no refs to `#106`.
- `#106` `compiler: unify generic parameters — same scheme as #105`, refs `{105}`.
- `#107` `docs: write the unification ruling down`, no `#N` references at all.

**Decision.** `#105` picked. `#106` fails `independent` (`#105 ∈ refs(#106)`;
the test is symmetric, so a one-way citation is enough) **and** shares subsystem
`compiler` → `skip_reason: "cross-reference"` (the mutual-ref half is checked
first for the more specific reason). `#107` shares no subsystem with `#105`
(`docs` vs `compiler`) and cites neither pick → `independent` holds → picked as
the second card.

**Output.**

```
logos-issue-intake 2026-11-20T13:00:02Z fetched=44 prs=0 unseen=3 ready=3 picked=2 created=2 failed=0 picks=#105,#107 skipped=#106:cross-reference
```

This is the scenario that shows why the pair test is stricter than the readiness
test: `#106` was ready, and still lost the slot.

---

## 7 — A create fails halfway (partial run)

**Input.** `#102` and `#103` picked. `hermes kanban create` returns rc=0 with a
task id for `#102`; for `#103` it exits 1 with `Error: database is locked`.

**Decision / output.**

```
ERROR create failed issue=#103 rc=1
logos-issue-intake 2026-11-20T13:00:05Z fetched=41 prs=0 unseen=3 ready=3 picked=2 created=1 failed=1 picks=#102,#103
```

Exit **75**. State: `#102` is `picked` with its id; `#103` has no `picked` entry
(it may carry a `skipped`-shaped ledger row, which the next run overwrites).

**Next run (14:00).** `#103` is unseen, its create succeeds — or returns the
task the 13:00 run actually created before the lock error, in which case the log
shows `existing=#103` and no duplicate appears on the board.

---

## 8 — Bootstrap, and the operator's backlog decision

**First run ever** — no state file. 38 open issues, 0 pull requests.

**Decision.** Every fetched issue is written `outcome: "seeded"`,
`backlog_cutoff = run start (2026-11-20T13:00:00Z)`, nothing is picked.

```
logos-issue-intake 2026-11-20T13:00:01Z bootstrap seeded=38 picked=0 backlog_cutoff=2026-11-20T13:00:00Z
```

Exit 0. **Why this is the default:** an unattended pipeline's first observable
action should be provably inert. A seeded board is auditable in one `git`-free
read of the state file; 38 cards created minutes after install are not, and nine
of those 38 are questions or `needs-info` records nobody can start.

**Operator drain** — same 38 issues, `--include-backlog` on 2026-11-20. The
numbers below are what the spec's rules produce when run over the live issue
bodies (a reference implementation was executed against the fetched JSON; the
bodies are in `../03-dossiers/02-issue-corpus-evidence.md`):

| order | # | why it is ready | result |
|---|---|---|---|
| 1 | 10 | `target, hard`, no refs at all, no structural line | picked (subsystem `target`) |
| 2 | 41 | opening line `Tracking issue for the \`compiler\` label sweep …` | skipped `umbrella` |
| 3 | 52 | `good first issue, docs`, no refs | picked (subsystem `docs`; `{target} ∩ {docs} = ∅`) |
| 4 | 53… | `examples`, `docs`, `stdlib`, `tooling`, … with both slots full | skipped `cap` (20 of them) |

```
logos-issue-intake 2026-11-20T14:00:00Z fetched=38 prs=0 unseen=38 ready=22 picked=2 created=2 failed=0 picks=#10,#52 skipped=#41:umbrella
```

Breakdown of the remaining 36: 20 `cap`, 9 `excluded-label` (`#67, #71, #73,
#75, #76, #79, #89, #93, #98`), 5 `blocked` (`#80, #91, #94, #95, #96`), 2
`umbrella` (`#41`, `#100`). Note `#74` — a real design issue that lists the six
issues it blocks — is **not** umbrella: that is the calibration the threshold of
8 exists for (§3.1 of `03-selection.md`).

The next hour, with `#10` and `#52` in state, picks `#53` (`examples`) and `#54`
(`docs`/manual) — still independent, still two. `--include-backlog` does not
disable the cap or the pair test; for that run it ignores `backlog_cutoff`
**and** waives the `seeded` outcome the bootstrap wrote (without that waiver a
drained state is indistinguishable from a settled one: every issue is `seeded`,
so the drain picks nothing, forever). It does **not** rewrite `backlog_cutoff`,
so the following runs continue from the drained position at 2/hour. The seeded
entries the drain considers are rewritten as `picked` or `skipped` with their
`skip_reason`, which is the ledger above. Draining 38 issues therefore takes
about 19 hours of hourly runs.

---

## Rule → `skip_reason` cross-check

Every rejection in the traces above maps to exactly one clause:

| clause | `skip_reason` | trace |
|---|---|---|
| `MAX_PICKS` reached | `cap` | 3 |
| `independent` false, mutual refs | `cross-reference` | 6 |
| `independent` false, shared subsystem | `subsystem-collision` | 4, 6 |
| `structural_refs ∩ open_numbers ≠ ∅` | `blocked` | 4, 5 |
| `len(refs ∩ open) ≥ 8` or umbrella header (`title`/first body line) | `umbrella` | 8 |
| `labels ∩ EXCLUDED_LABELS ≠ ∅` | `excluded-label` | 4 |

A `skip_reason` outside that table is a defect in the implementation, not a new
category.

SOURCES (LAYER 2 NAVIGATION)
docs/pipelines/issue-intake/02-analysis/03-selection.md
 -> the clauses these traces exercise, and the subsystem map
docs/pipelines/issue-intake/03-dossiers/02-issue-corpus-evidence.md
 -> the raw bodies and API fields the real-data traces were computed from
docs/pipelines/issue-intake/03-dossiers/04-selection-fixtures.json
 -> the same cases as machine-readable fixtures with expected outputs
