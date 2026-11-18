# Verification log — 2026-11-18

Every number and every mechanism in this pyramid was exercised on this date, on
the audit machine (x86_64 Linux, Ubuntu clang 14.0.0, lld 14, gcc, jq). This page
is the transcript, so a later reader can tell a measured claim from a remembered
one.

---

## 1. The consumer path, from the published release, tagless

`gh release download` with no tag downloads the latest release — this is the form
the paste block uses, and the reason it cannot rot when a new version ships.

```text
$ cd $(mktemp -d)
$ gh release download --repo abaddon/logos \
    --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
$ ls
SHA256SUMS  logos-0.2.0-x86_64-linux.tar.gz
$ sha256sum -c SHA256SUMS
logos-0.2.0-x86_64-linux.tar.gz: OK
$ tar -xzf logos-*-x86_64-linux.tar.gz && cd logos-*-x86_64-linux
$ ./bin/logosc version
logos 0.2.0
```

Verbatim execution of the three-step block in `program.md` §10, as a script:

```text
logos-0.2.0-x86_64-linux.tar.gz: OK
logos 0.2.0
hello from logos
STEP2_EXIT=0
```

Build and run, with an explicit output path and from a foreign working directory:

```text
$ ./bin/logosc build ../hello.logos -o ../out_hello && ../out_hello
hello from logos
$ ./bin/logosc build hello.logos          # no -o: writes ./build/hello, cwd-relative
```

## 2. Machine-readable failure

```text
$ ./bin/logosc build ../bad.logos --json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100",
 "message":"let 'x' has type :i64, found :void",
 "node_path":"bad/main/2/2","file":"../bad.logos","line":0,"col":0}]}
exit 2
$ ./bin/logosc show ../hello.logos hello/main/2
(println "hello from logos")
```

## 3. The compiler's manifest — the seeded-issue evidence

```text
$ ./tools/logosc.sh guide --json | jq '{codes:(.codes|length),forms:(.forms|length),types:(.types|length),ops:(.operators|length)}'
{ "codes": 36, "forms": 96, "types": 16, "ops": 17 }
$ grep -rn '35 codes' docs/*.md docs/reference/*.md
docs/00-index.md:| understand a failure | … all 35 codes | 10 min |
docs/00-index.md:| `logosc guide --json` | … 35 codes, 8 categories |
```

(Line numbers are omitted deliberately: this run predates the row that was added
to that table, so any number here would be wrong by the time a reader checks it.)

→ seeded issue #1. Two lines, one command to check, and it is wrong today.

## 4. `logosc fmt` has no `--check` flag

```text
$ ./bin/logosc fmt -h
usage: logosc fmt [-h] FILE [FILE ...]
rewrite Logos source in canonical form, in place
options:
  -h, --help  show this help message and exit
  --json      emit diagnostics as JSON on stderr
```

The rubric therefore specifies the copy-and-`diff` test. Executed:

```text
$ cp hello.logos h2.logos && ./bin/logosc fmt h2.logos && diff hello.logos h2.logos
FMT_NO_CHANGE
```

## 5. `logosc test` — the criterion-2 check

```text
$ ./bin/logosc test t2.logos
PASS exec/t2/add-works -
1 passed, 0 failed, 0 leaked
baseline: none
```

## 6. A limit the documentation gets wrong — found while seeding issues

`docs/reference/limits.md` (A3) and `docs/01-summary/gap-register.md` say a
non-finite float literal is **accepted** and becomes `inf`. The compiler refuses
it, on both the released binary and this tree:

```text
$ ./bin/logosc build inf.logos          # v0.2.0
t/main/2: E0106: literal 1e999 does not fit :f64
exit 2
$ ./tools/logosc.sh build inf.logos      # this tree (src/)
t/main/2: E0106: literal 1e999 does not fit :f64
    (println 1e999)
$ cat tests/regress/float-range.check
float-range/main/2: E0106: literal 1e999 does not fit :f64
```

The behaviour is correct and already pinned by a regress case; two documentation
pages describe the old behaviour. This became seeded issue #4 — the version
written before the test said something else, and the test is why it changed.

## 7. `:str` ordering — the other seeded language issue

```text
$ ./bin/logosc build c.logos
c/main/2/0: E0100: '<' needs numbers, found :str
exit 2
```

## 8. Repository facts the program depends on

```text
$ gh api repos/abaddon/logos --jq '{has_discussions,has_issues,topics,stargazers_count,forks_count}'
{"has_discussions":false,"has_issues":true,"topics":[],
 "stargazers_count":0,"forks_count":2}

$ gh label list --repo abaddon/logos            # 18 labels, incl. 'good first issue'
$ gh issue list --repo abaddon/logos --state open
41  OPEN  Compiler label sweep 2026-11-17 …
10  OPEN  Build a macOS target (x86_64 and arm64)   target, hard
6   OPEN  Manual: cause and fix hint for every diagnostic code   docs

$ gh issue list --repo abaddon/logos --label 'good first issue' --state open
(empty)                                          # 0 open; #3, #4, #5, #14 are closed

$ gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged" --jq .total_count
32
$ gh api "/search/issues?q=repo:abaddon/logos+is:pr+is:merged" --paginate \
    --jq '.items[].user.login' | sort | uniq -c
     31 abaddon
      1 Sonike
$ gh pr view 12 --repo abaddon/logos --json author,files,additions,deletions
{"author":"Sonike","additions":130,"deletions":40,
 "files":["docs/LOGOS.md","docs/manual/01-values-and-literals.logos",
          "docs/superpowers/specs/…","logos/check.py","logos/lower.py",
          "tests/regress/print-small-numbers.logos","tests/summary.txt",
          "tests/test_emit.py","tests/test_text.py"]}

$ git ls-files | grep -i -E 'funding|sponsor'
(no output — no funding file, no sponsors metadata)

$ gh auth status
Logged in to github.com account abaddon … scopes: 'repo', 'workflow',
'write:discussion', 'project', 'read:org', …
```

Topic collision check, so the program does not mint a marker that already means
something else:

```text
$ gh api "/search/repositories?q=topic:logos-lang" --jq .total_count
5
$ gh api "/search/repositories?q=topic:logos-agent-challenge" --jq .total_count
0
```

## 9. The gate a contributor must pass

`bash tools/pr_gate.sh` was run in this worktree on 2026-11-18, end to end, with
the docs-only change in the tree. Real output:

```text
PASS sign-off (precondition)
PASS unit tests
PASS corpus
PASS acceptance
PASS manual drift
PASS formatting
PASS self-hosting

6/6 gates passed
3032.75user 486.09system 1:01:08elapsed 95%CPU
```

**One hour, eight minutes, on a 6-core box that was running a second full gate
run at the same time.** That number belongs in the program: a newcomer who
budgets ten minutes for the gate will abandon the pull request, and the entry
form's "one run command" instruction only works for Track A and C, which never
touch the compiler.

## 10. What was *not* verified

Stated so the program's claims stay honest:

- **The 45-day window is an estimate.** No measurement supports it; the rescue
  checkpoint at `L+20` exists because of that.
- **A GitHub Actions runner was not exercised.** Gate 0 ran on the audit machine
  (x86_64 Linux, clang 14), which is the same platform the release targets, but
  no workflow file in this repository downloads the tarball into CI.
- **M6 reuse** was not measured on any real entry, because there are none.
- **The entry-form YAML** was written against the schema the repository's
  `bug.yml` uses; it has not been submitted. Submitting a test entry is a hard
  pre-launch check precisely because of that.

---

SOURCES

- `../01-summary/program.md` — the claims these transcripts support.
- `../02-analysis/feasibility.md` — the per-mechanism verdicts derived from them.
- `../02-analysis/selection-and-metrics.md` — the baseline table.
- `../03-dossiers/assets.md` — the eight seeding items (eleven issues), three of which are evidenced here.
