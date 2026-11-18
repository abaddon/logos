# Launch checklist — every channel, what gets posted, and the gate in front of it

One row per channel from the channel map's 17-entry table, plus the two surfaces
that table treats as fixed ("GitHub topics", "AGENTS.md") and the challenge launch
the whole thing points at. **Status is what was true at 2026-11-18 21:30**, not
what was planned.

`EXECUTED` = something is public because of this task. `READY` = copy exists and
the command is one line, blocked on a named gate. `DEFERRED` = not attempted, with
the reason. Nothing here is "in progress" — a launch that reports intentions is a
launch that reports nothing.

## The table

| # | Channel | What gets posted | Framing / length | Rules to respect | Gate in front of it | Status |
|---|---|---|---|---|---|---|
| R | **GitHub Release v0.2.1** (the installable artifact) | annotated tag `v0.2.1` on `main` → `release.yml` builds, double-builds and publishes the tarball + `SHA256SUMS` | release notes come from `CHANGELOG.md`, not rewritten | tag must equal `logosc version`; artifact must be byte-reproducible across two runners | gates + `verify_install.sh` in CI | **ATTEMPTED, NOT PUBLISHED** — acceptance gate failed on the aarch64 sysroot; fix in PR #48, root cause in [`../01-summary/launch-status.md`](../01-summary/launch-status.md) |
| 1 | Official MCP Registry | `server.json` + `mcp-publisher publish` under `io.github.abaddon/logos` | capability-first description, 131 chars, five tool descriptions written as instructions | no human review; namespace proved by a repo marker; `version` must match the binary | **the endpoint must answer `tools/list`** | DEFERRED — no MCP server exists in the repo |
| 2 | mcp.so | free submission form, one page per server | 198-char description, category Developer Tools | a dead URL is permanent in crawlers | the endpoint | DEFERRED — same |
| 3 | Smithery | `@smithery/cli` deploy | same description | point at **your** endpoint, never a Smithery-hosted URL (its docs are migrating URLs back to vendors) | the endpoint | DEFERRED — reach is volatile; not worth an unowned dependency |
| 4 | `awesome-remote-mcp-servers` PR | one Markdown line + PR body with disclosure | legible with no README beside it; `🤖🤖🤖` at the end of the **title** | one line, alphabetical, remote-only servers go to the remote list | an endpoint **or** an installable package | READY — copy complete in [`../02-analysis/copy/awesome-list-pr.md`](copy/awesome-list-pr.md) |
| 5 | GitHub topics + repo metadata | topics already correct; description already correct | — | — | — | **VERIFIED** — 10 topics incl. `ai-agents`, `mcp`-adjacent set; `homepage` is **null** (nothing to point at yet) |
| 6 | `AGENTS.md` | already live, 200 over HTTPS | — | — | — | **VERIFIED** (`200`); updates owned by `t_5b93c8fe` |
| 7 | `llms.txt` | an index of overview / quickstart / reference / examples / contribute | short, every entry resolvable | 97% of llms.txt files are never fetched — hygiene, not distribution | file must be **on `main`**, not only on a branch | DEFERRED to `t_5b93c8fe` (running in parallel; 404 today) |
| 8 | npm (`logos-mcp`) | shim package, `npx logos-mcp` talks to the endpoint | description names the verbs; README must say "does not bundle the Linux binary" | do not ship the binary — it breaks on macOS | `npm login` **and** the endpoint | DEFERRED — `npm whoami` → `ENEEDAUTH` |
| 9 | PyPI | same shim as a Python package for registry `packages[]` | — | — | same as npm | DEFERRED — secondary to npm; one package type is enough to prove ownership |
| 10 | Docker MCP Catalog | image on GHCR + `servers/abaddon-logos/` PR | `secrets: []` stated as the security argument; say unprompted that the image executes model-authored source | PR, not form; image must actually run | a host with Docker | READY — Dockerfile + `server.yaml` + tools manifest in [`../02-analysis/copy/space-and-container.md`](copy/space-and-container.md) |
| 11 | Hugging Face Space | Docker Space running the four examples, source → IR → run | one click to a real compiler output; "what is not here" section | — | Docker + `huggingface-cli login` | READY — frontmatter and copy written |
| 12 | Claude Connectors Directory | verification packet | — | needs organisation, privacy page, support address, stable endpoint for ≥1 month | **all of the above** | DEFERRED — month 3; attempting early fails verification and burns the slot |
| 13 | ChatGPT apps directory | submission | — | needs a publicly hosted MCP + review | the above | DEFERRED — month 3 |
| 14 | LangChain / LlamaIndex adapters | **nothing to post** — any MCP server is importable | — | — | the registry record | DEFERRED — passive; it becomes true when #1 lands |
| 15 | Show HN | title + first comment | falsifiable claim, runnable artifact, limits stated, author in-thread 3h | no marketing voice; must run on the reader's machine — say "Linux only" yourself | **endpoint answering + demo running**, then 48h of clean wave-1 calls | READY — [`../02-analysis/copy/forum-posts.md`](copy/forum-posts.md) |
| 16 | r/LocalLLaMA | question-shaped post, authorship disclosed in line one | argues the sub's own verification question; asks for data it can give | self-promotion restricted; needs an account with history; 2 weeks after HN | HN posted, +14 days | READY — same file, deliberately different post |
| 17 | Dev Discords / Slacks | join, listen, do not schedule | — | invite-gated, invisible to crawlers, no citable size | — | DEFERRED by the map's own finding — relationship channel, not a launch channel |
| C | **Logos Agent Challenge** launch | the §10 paste block, the entry form, labels, seeded backlog | no prizes; reproducibility gate; agent disclosure | don't post the date before the 8 hard checks are green | checks 3–8 red today (page unmerged, form unsubmitted, 0 `good first issue`) | DEFERRED — see [`../03-dossiers/owner-actions.md`](../03-dossiers/owner-actions.md) §A9 |

## The waves, and what each one is allowed to change

The plan is four waves with a hard gate between each — not a schedule. A wave
starts when its gate is green, which is why no date is printed here.

**Wave 0 — the installable surface. Done today.**
The release, the metadata check, the demo run from a cold clone. Everything else
links here, so it goes first even though it is invisible.

**Wave 1 — the machine surfaces.** Registry record → npm → mcp.so and mirrors →
awesome-remote PR. All four are one description string in four places, so they
ship in one sitting. **Observe 48h after this wave, and measure tool calls and
`npx` installs, not stars.** The 48h exists for one reason: a broken tool
discovered by 40 agents is a fixed bug; the same bug discovered by a front-page
thread is a reputation.

**Wave 2 — Show HN.** Gate: wave 1 ran 48h with zero tool errors, and the demo
runs from a fresh clone (verified today, re-verify on the day). What wave 1's
48h is allowed to change about the post: **if the tool-call errors cluster on one
form, the HN body leads with that form's diagnostic instead of the one drafted**,
because the first comment will be about whatever broke. If install friction
dominates the inbound questions, the title keeps the invariant framing and the
body moves the demo above the mechanism.

**Wave 3 — r/LocalLLaMA, +14 days.** Not a repost. What changes it: the questions
HN produced. The two or three most-repeated questions become the post's body, and
any claim an HN commenter falsified gets corrected in the Reddit draft — the
revision is the point of the two-week gap.

**Wave 4 — month 3.** Claude/ChatGPT directories (needs an org, a privacy page and
a support address — paperwork, not traffic), Docker catalog, HF Space. These are
gated on assets a single-maintainer repo does not have yet; doing them early means
failing verification and waiting out a rejection window.

**Never scheduled:** Discords and Slacks. Join them, listen, answer questions that
arrive; do not announce into them.

## The tracking instrument

Every row of [`../01-summary/channel-ledger.md`](../01-summary/channel-ledger.md) is
filled by one of these commands, so the numbers are re-derivable rather than
remembered. These are the ones that work without a web analytics account:

```sh
# installs — the only hard number a wave produces
gh api repos/abaddon/logos/releases --jq '.[] | .tag_name as $t | .assets[] | "\($t) \(.name) downloads=\(.download_count)"'

# repo traffic, last 14 days (maintainer only; 14 is GitHub's window, not a choice)
gh api repos/abaddon/logos/traffic/clones --jq '{count,uniques}'
gh api repos/abaddon/logos/traffic/views  --jq '{count,uniques}'

# the funnel's far end: anyone who got as far as forking or opening something
gh api repos/abaddon/logos --jq '{stars,forks,watchers,open_issues}'
gh pr list --repo abaddon/logos --state all --json number,author,createdAt \
  --jq '[.[] | select(.author.login != "abaddon")] | length'
gh issue list --repo abaddon/logos --state all --json number,author,createdAt

# challenge entries, once the label exists
gh issue list --repo abaddon/logos --label challenge-entry --state all --json number --jq 'length'

# npm installs per day, once published
curl -s https://api.npmjs.org/downloads/point/last-week/logos-mcp

# HN: the post's own numbers, plus whether anything new cites the repo
curl -s 'https://hn.algolia.com/api/v1/search?query=abaddon/logos&tags=(story,comment)'
```

`download_count` and `traffic/*` are the two that matter in week one. Stars are
excluded from the retro's decision on purpose: they measure the title, not whether
anything ran.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> The live checks behind every VERIFIED/EXECUTED row: credentials, release cut, 404s, cold-clone demo
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> The exact commands and URLs for every DEFERRED/READY row
/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/02-analysis/channel-map.md
 -> The per-channel rules summarised in the fourth column, as fetched 2026-11-18
