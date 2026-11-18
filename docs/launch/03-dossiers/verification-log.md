# Verification log — every command run for the launch, with its real output

Captured on 2026-11-18 between 21:05 and 21:30 UTC on the launch worktree
(`wt/t_669498b1`). Nothing in this file is reconstructed from memory; each block
is a command and the output it produced. Where a check failed, the failure is
kept rather than replaced with what should have happened.

## 1. What credentials this host actually holds

```
$ gh auth status
github.com
  ✓ Logged in to github.com account abaddon (/root/.config/gh/hosts.yml)
  - Token scopes: 'delete:packages', 'manage_runners:org', 'project',
    'read:org', 'read:public_key', 'read:repo_hook', 'repo', 'workflow',
    'write:discussion', 'write:packages'

$ npm whoami
npm error code ENEEDAUTH
npm error need auth This command requires you to be logged in.

$ docker info
no-docker            # docker is not installed on this host

$ ls ~/.cache/huggingface
ls: cannot access '/root/.cache/huggingface': No such file or directory

$ env | grep -i -E 'HF_TOKEN|NPM_TOKEN|REDDIT|HN_'
(nothing)
```

**Reading:** exactly one channel family is writable from this host — GitHub
(`repo` + `workflow` + `write:discussion`). npm, Docker, Hugging Face, Hacker
News and Reddit have no credential here. That single fact decides the whole
launch: everything that publishes through GitHub was executable, everything else
is handed back with instructions in
[`owner-actions.md`](owner-actions.md).

## 2. The blocker: v0.2.1 was never published

```
$ gh release list --repo abaddon/logos
Logos 0.2.0	Latest	v0.2.0	2026-11-16T01:42:42Z

$ gh release download v0.2.1 --repo abaddon/logos
release not found

$ (in the worktree) grep -n "0.2.1" src/logosc/main.logos | head -1
158:  (ret "0.2.1"))
```

The compiler on `main` *is* 0.2.1 and `CHANGELOG.md` carries a dated 0.2.1
section ("A packaging fix. The compiler is unchanged; the tarball is not"), but
the tag was never pushed, so eight files that present v0.2.1 as current were
describing a release that did not exist — and the README's own install command
failed for anyone who ran it.

## 3. The action taken: annotated tag v0.2.1 on main, pushed

```
$ git cat-file -t v0.2.0
tag                                  # v0.2.0 is an annotated, unsigned tag
$ git tag -a v0.2.1 546598a1ac0aec99a5948a698696c64ac22e10cb -m "Logos 0.2.1"
$ git push origin refs/tags/v0.2.1
 * [new tag]         v0.2.1 -> v0.2.1

$ gh run list --repo abaddon/logos --workflow release --limit 2
in_progress	  examples: add agent-gate, a reference project to fork (#47)	release	v0.2.1	push	44398996372	7s
completed	success	ci: the release workflow can run on a tag at all	release	v0.2.0	push	43784528114	33m45s
```

Why a tag push and not a local `release.sh --publish`: `.github/workflows/release.yml`
runs the six gates on the tagged commit, builds the tarball, **rebuilds it on a
second runner and requires the two SHA-256 sums to agree**, runs
`tools/verify_install.sh` on the artifact, and only then publishes. That is a
stronger proof than anything this host can produce in the time available, and it
is the path `CHANGELOG.md` and `docs/release.md` document.

Run: <https://github.com/abaddon/logos/actions/runs/44398996372>.
The outcome is recorded in [`../01-summary/launch-status.md`](../01-summary/launch-status.md) — this
dossier was written while the `verify` job was still in progress, and the status
page is the authority on whether it landed.

## 4. The agent-readable surface, fetched over the public internet

```
$ for f in AGENTS.md llms.txt llms-full.txt README.md \
           examples/agent-gate/README.md docs/challenge/01-summary/program.md; do
    curl -sL -o /dev/null -w '%{http_code}  %{url_effective}\n' \
      "https://raw.githubusercontent.com/abaddon/logos/main/$f"
  done
200  .../main/AGENTS.md
404  .../main/llms.txt
404  .../main/llms-full.txt
200  .../main/README.md
200  .../main/examples/agent-gate/README.md
404  .../main/docs/challenge/01-summary/program.md

$ curl -s -o /dev/null -w '%{http_code} %{url_effective}\n' -L https://github.com/abaddon/logos/releases/latest
200 https://github.com/abaddon/logos/releases/tag/v0.2.0
```

Two of these 404s matter for the launch and one of them is not the docs task's
to fix:

- `llms.txt` is absent — the docs task (`t_5b93c8fe`) is writing it, and until it
  is on `main` no external post may name it as an entry point.
- **`docs/challenge/01-summary/program.md` is absent from `main`.** The challenge
  branch `wt/t_1c7448cf` (`d42605d`, `c9d0464`, `753f7a4`) is unmerged —
  `git merge-base --is-ancestor d42605d origin/main` → not an ancestor; the same
  is true of the messaging kit's `adfecd7`. Any launch copy that links the
  challenge by path would 404 for every reader today.

## 5. Repo metadata as agents and crawlers see it

```
$ gh api repos/abaddon/logos --jq '{stars,forks,watchers,open_issues,homepage,
    description,has_discussions,topics}'
{"stars":0,"forks":2,"watchers":0,"open_issues":3,"homepage":null,
 "description":"Logos: code an agent can read, write, and prove. A prefix-form
 language and a self-hosting compiler to native Linux binaries.",
 "has_discussions":false,
 "topics":["agents","ai-agents","code-generation","compiler","language-design",
           "llm","llvm","programming-language","self-hosting","system-programming"]}
```

Three facts that change what is postable:

1. **Discussions is off.** Any launch idea that depends on a Discussion thread
   (an announcement, an AMA, a "share what you built" thread) needs a settings
   change first — it is not a posting action.
2. **`homepage` is null.** There is nowhere to send a visitor who wants the demo
   without a GitHub account, which is exactly the click HN and Reddit traffic
   needs.
3. **The topics are already the right ones** and include `ai-agents` (166,031
   repos carry that topic). The repo surface is not the gap; the missing
   callable endpoint is.

## 6. The reference demo, from a cold public clone

```
$ git clone --depth 1 https://github.com/abaddon/logos.git repo && cd repo
$ git log --oneline -1
546598a examples: add agent-gate, a reference project to fork (#47)

$ ./tools/logosc.sh build examples/agent-gate/gate.logos -o build/agent-gate
$ ./build/agent-gate < examples/agent-gate/calls.txt
ALLOW  shell ls -la
DENY   shell rm -rf /  -- shell: recursive delete
ALLOW  http GET https://example.com/docs
DENY   http GET http://example.com  -- http: only an https url is allowed
ALLOW  write ./notes/todo.md buy milk
DENY   write /etc/passwd root  -- write: path must start with ./
DENY   read /root/.ssh/id_rsa  -- read: system and home paths are off limits
DENY   browser navigate x  -- unknown tool
exit=5

$ ./tools/logosc.sh check examples/agent-gate/gate.logos ; echo check-exit=$?
check-exit=0

$ ./tools/logosc.sh test examples/agent-gate/gate.logos
PASS exec/gate/denies-an-unknown-tool -
9 passed, 0 failed, 0 leaked
```

A first reading of the demo's own quickstart passed `calls.txt` as an argument
instead of on stdin and printed nothing with exit 0 — recorded here because it is
the failure mode a first-time reader hits, and the README's `agent-gate <
calls.txt` form is the one that works. The demo is public, buildable from a fresh
clone and reproducible; that acceptance item is met.

## 7. What was not attempted, and why

| Not attempted | Reason |
|---|---|
| Posting to Hacker News | No account credential on this host; also gated on the endpoint existing (see the checklist's wave gates) |
| Posting to r/LocalLLaMA | Same, plus the subreddit's self-promotion rule requires an account with history — a fresh account posting a project is the pattern the rules exist to stop |
| `npm publish logos-mcp` | `npm whoami` → ENEEDAUTH, and the shim cannot be honest until the endpoint exists: a Linux-only binary behind `npx` breaks on macOS, which is most of the audience |
| `mcp-publisher publish` | Requires the server to exist and be deployed; there is no MCP server in this repository today (`git ls-tree -r main | grep -i mcp` → nothing) |
| Docker catalog PR | Docker is not installed here, so no image can be built or tested, and a `server.yaml` with an untested image is a rejection |
| Hugging Face Space | No token; a Docker Space also needs the image the previous line cannot build |
| Merging the challenge and messaging branches | Not this task's commit to make, and each merge runs the full gate; flagged as a prerequisite instead |
| Writing `llms.txt` | Collision: `t_5b93c8fe` is writing it in the same minute. I commented the 404 window on that card instead of racing it |

SOURCES (LAYER 3 — this file is a dossier; it has no deeper layer)
/root/ai-language-program/.worktrees/t_1c7448cf/docs/challenge/01-summary/program.md
 -> The challenge's pre-launch checklist (§9), whose item 2 is the release this run cut
/root/ai-language-program/.worktrees/t_c10d37ee/evangelism/02-analysis/channel-map.md
 -> Per-channel rules quoted in the checklist (registry has no review; awesome list's agent lane; HN/Reddit norms)
