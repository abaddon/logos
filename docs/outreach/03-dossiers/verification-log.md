# Verification log — 2026-11-19

Every block below is a command that was run from this host and its output,
copied. Where a block is a claim about a third party (a PR, a CI check), the
URL is the evidence and the state is quoted as the API returned it.

## 1. What this host can authenticate as

```
$ gh auth status
github.com
  ✓ Logged in to github.com account abaddon (/root/.config/gh/hosts.yml)
  - Token scopes: 'delete:packages', 'manage_runners:org', 'project', 'read:org',
    'read:public_key', 'read:repo_hook', 'repo', 'workflow', 'write:discussion',
    'write:packages'

$ npm whoami
npm error code ENEEDAUTH
npm error need auth This command requires you to be logged in.

$ which docker podman xurl
(nothing)
```

One credential: a GitHub token. That single fact decided the channel order in
[`../02-analysis/channels.md`](../02-analysis/channels.md) — everything that
needs npm, Docker, Hugging Face, Hacker News or Reddit is blocked, and no amount
of planning changes it.

## 2. The challenge's pre-launch checks 4–8

### Labels

```
$ gh label create challenge-entry    --repo abaddon/logos --color 1d76db --description "An entry to the Logos Agent Challenge"
$ gh label create challenge-findings --repo abaddon/logos --color fbca04 --description "A defect or rough edge found by a challenge entry"
$ gh label list --repo abaddon/logos | grep challenge
challenge-entry	An entry to the Logos Agent Challenge	#1d76db
challenge-findings	A defect or rough edge found by a challenge entry	#fbca04
```

### The seeded backlog

`tools/seed-challenge-backlog.sh` filed ten issues, idempotently (it skips a
title that already exists), from the spec in
`docs/challenge/03-dossiers/assets.md` §3:

```
https://github.com/abaddon/logos/issues/52   docs: limits.md says a non-finite float literal prints inf
https://github.com/abaddon/logos/issues/53   examples: a fourth example program vs an external oracle
https://github.com/abaddon/logos/issues/54   manual: cause and fix hint for E0001–E0103
https://github.com/abaddon/logos/issues/55   manual: cause and fix hint for E0104–E0201
https://github.com/abaddon/logos/issues/56   manual: cause and fix hint for E0300–E0402
https://github.com/abaddon/logos/issues/57   manual: cause and fix hint for E0500–E0800, R0006–R0007
https://github.com/abaddon/logos/issues/58   tooling: add logosc fmt --check
https://github.com/abaddon/logos/issues/59   tooling: add logosc doctor
https://github.com/abaddon/logos/issues/60   stdlib: string-to-integer parsing in str
https://github.com/abaddon/logos/issues/61   language: ordering comparison for :str
```

Counts, read back after #6 was closed as `superseded`:

```
$ gh issue list --repo abaddon/logos --state open --json number --jq 'length'
12
$ gh issue list --repo abaddon/logos --label 'good first issue' --state open --json number --jq 'length'
6
$ gh issue list --repo abaddon/logos --label 'help wanted' --state open --json number --jq 'length'
4
$ gh issue view 6 --repo abaddon/logos --json state,labels --jq '{state, labels:[.labels[].name]}'
{"labels":["docs","superseded"],"state":"CLOSED"}
```

Check 6 needs ≥5 `good first issue` and ≥10 open: 6 and 12. Check 7 needs both
labels: present. Check 8 needs a named forkable starting point:
`examples/agent-gate/` is named in §2 of the program.

### The spec's item 1 was already fixed

The spec says to file "the docs index says 35 diagnostic codes, the compiler
emits 36". It is not filed, because it is not true any more:

```
$ grep -n '35' docs/00-index.md
(nothing)
$ jq -r '.codes | keys | length' /tmp/guide.json
36
```

Filing it anyway would have been a defect report for a defect that does not
exist; `assets.md` records the correction instead.

## 3. The repository checks for that change

```
$ bash tools/check_doc_links.sh .
117 files, 232 relative links, 0 broken

$ python3 -m unittest tests.test_docs tests.test_contributing
Ran 24 tests in 1.003s
OK
```

One real defect was caught this way: the first draft of the Track A sentence
linked `../../examples/agent-gate/`, which resolves to `docs/examples/` and does
not exist. The checker reported it and the link became
`../../../examples/agent-gate/README.md` — a file the release tarball also
ships (`tools/dist.sh` installs both agent-gate pages), so the link survives
packaging.

## 4. The instruction file's code was compiled, not sketched

Four `logos` blocks were extracted from
`instructions/logos.instructions.md` and each was compiled and run with the
published compiler (v0.2.2):

```
$ for f in blk1 blk2 blk3 blk4; do ./tools/logosc.sh check --json $f.logos; echo "exit=$?"; done
exit=0
exit=0
exit=0
exit=0

$ ./tools/logosc.sh build blk1.logos -o b1 --opt -O2 && ./b1
3
$ ./tools/logosc.sh build blk2.logos -o b2 --opt -O2 && ./b2
42
$ ./tools/logosc.sh build blk3.logos -o b3 --opt -O2 && ./b3
42
$ ./tools/logosc.sh build blk4.logos -o b4 --opt -O2 && ./b4
7

$ ./tools/logosc.sh test blk4.logos --opt -O0
1 passed, 0 failed, 0 leaked
$ ./tools/logosc.sh test blk4.logos --opt -O2
1 passed, 0 failed, 0 leaked
```

Each idiom in the file is therefore backed by a program the compiler accepts,
not by the manual's prose. Two claims in the file were also verified directly
because they are the ones an agent is most likely to doubt:

```
$ printf '(mod c)\n\n(fn main :void ()\n  (let x :i64 1)\n  (println 2))\n' > c.logos
$ ./tools/logosc.sh check --json c.logos
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0107","message":"unused binding 'x'","node_path":"c/main/2",...}]}

$ printf '(mod d)\n; a comment\n(fn main :void ()\n  (println 1))\n' > d.logos
$ ./tools/logosc.sh check --json d.logos
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0001","message":"form outside parentheses","node_path":"","file":"d.logos","line":2,"col":1}]}
```

## 5. The two third-party pull requests

```
$ gh pr view 6516 --repo github/awesome-copilot --json title,state,url
Add Logos instructions 🤖🤖🤖   OPEN   https://github.com/github/awesome-copilot/pull/6516

$ gh pr checks 6516 --repo github/awesome-copilot
build                 pass    2m10s
validate-readme       pass    20s      # the generated catalog row
codespell             pass    18s
check-line-endings    pass    7s
evaluate              pass    50s
scan                  pass    11s
pr-check              pass    12s
submission-gate       action_required   "Waiting on review (merge-risk:medium): needs 1 more approval(s)"
```

`submission-gate` is not a failure of content: its own summary is
`Ready for review · merge-risk:medium`, and the tier is "new resource, 189 lines
against a 40-line low-risk limit". It needs one approving human, which is the
correct state for a first-time contribution to a 41k-star catalog.

```
$ gh pr view 6451 --repo up-for-grabs/up-for-grabs.net --json title,state,url
Add Logos   OPEN   https://github.com/up-for-grabs/up-for-grabs.net/pull/6451

$ gh pr checks 6451 --repo up-for-grabs/up-for-grabs.net     # non-skipped rows
Project Changes        pass   17s
netlify deploy-preview pass   0s   ready
```

## 6. The baseline these publications are measured against

Read on 2026-11-19, before any of them can have an effect:

```
$ gh api repos/abaddon/logos --jq '.stargazers_count, .forks_count'
1
2

$ gh issue list --repo abaddon/logos --label challenge-entry --state all --json number --jq 'length'
0

$ gh pr list --repo abaddon/logos --state merged --limit 100 --json author --jq '[.[].author.login] | group_by(.) | map({a:.[0], n:length})'
[{"a":"Sonike","n":1},{"a":"abaddon","n":36}]

$ gh api repos/abaddon/logos --jq '{topics, homepage}'
{"topics":["agents","ai-agents","code-generation","compiler","language-design","llm","llvm",
"programming-language","self-hosting","system-programming","good-first-issues","llms-txt"],
 "homepage":null}
```

The two topics added are the ones a discovery surface actually filters on
(`good-first-issues` for contributor-facing aggregators, `llms-txt` for the
crawlers that index machine-readable repo surfaces). The homepage is left null
deliberately: a homepage needs a stable URL that is a destination, and pointing
it at a markdown file in the repository adds a second landing page competing with
the README rather than a place to arrive at.

One merged pull request from an account other than the owner's, in the
repository's entire history. That, not the star count, is the number the
challenge is supposed to move.

## 7. The local gate, and what it could not measure

`bash tools/pr_gate.sh` stops at its DCO precondition on this worktree:

```
sign-off: commit 959908a6644b782e02c08fee46f86bd6c74898ce has no Signed-off-by trailer matching its author
sign-off: 2 of 3 commit(s) failed the DCO check
The six gates were not run: every commit must carry a Signed-off-by trailer
```

Both commits it objects to are squash-merge commits that arrived from
`origin/main` (`#50`, `#51`): the worktree's local `main` ref is at `c55a99f`,
two merges behind, and `main` is checked out in another worktree so it cannot be
advanced from here without disturbing that checkout. The range that matters is
correct:

```
$ bash tools/check_dco.sh origin/main HEAD
sign-off: 1 commit(s) carry a matching Signed-off-by trailer
```

The six gates were therefore run as the commands the gate would have run, and CI
runs the same set on the pull request.
