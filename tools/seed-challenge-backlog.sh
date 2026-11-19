#!/usr/bin/env bash
# Seed the Logos Agent Challenge backlog (docs/challenge/03-dossiers/assets.md §3).
# Idempotency: each issue is created only if no open issue already has that title.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=abaddon/logos

make_issue() {  # $1=title  $2=labels  $3=body
  local title="$1" labels="$2" body="$3"
  if gh issue list --repo "$REPO" --state all --search "\"$title\" in:title" --json title --jq '.[].title' | grep -Fxq "$title"; then
    echo "skip (exists): $title"; return 0
  fi
  gh issue create --repo "$REPO" --title "$title" --label "$labels" --body "$body" | sed 's/^/  /'
}

make_issue \
'docs: `limits.md` says a non-finite float literal prints `inf`; the compiler refuses it' \
'good first issue,docs' \
'`docs/reference/limits.md` row A3 (line 36) says a float literal with no finite value is **accepted** and becomes `inf`, and line 70 repeats the claim. That is false.

Reachability, measured today on `main`:

```
$ printf '"'"'(mod t)\n\n(fn main :void ()\n  (println 1e999))\n'"'"' > /tmp/t.logos
$ ./tools/logosc.sh check /tmp/t.logos
t/main/2: E0106: literal 1e999 does not fit :f64
    (println 1e999)
```

It is refused, with code `E0106` and a node path, and `tests/regress/float-range.check` already pins that. Note `check` prints the diagnostic and the corpus case passes; the claim is about the *document*, not the compiler.

**Where:** `docs/reference/limits.md` (two places: the A3 row and the `strtod` row), and any other page that repeats it — `grep -rn "non-finite\|1e999" docs/` finds them.

**Done when:** both rows state what the compiler does (a non-finite float literal is `E0106` at check time), `grep -rn "accepted.*inf" docs/` returns nothing, and `bash tools/check_doc_links.sh .` still reports 0 broken.

**Why this is good first issue:** two rows of prose, one command to prove the replacement text, no compiler source touched.'

make_issue \
'examples: a fourth example program, compared against an external tool by `tools/accept.sh`' \
'good first issue' \
'`tools/accept.sh` already diffs three examples against independent oracles: `examples/wc.logos` against GNU `wc`, `examples/json.logos` against `jq`, `examples/matrix.logos` against a C reference build. A fourth example proves the differential-oracle pattern generalises, which is the only reason the first three are trustworthy.

**Suggested program:** `examples/base64.logos` — read stdin as bytes, encode to base64 with no line wrapping, write to stdout. The oracle is coreutils:

```
head -c 4096 /dev/urandom | ./base64 > /tmp/a
head -c 4096 /dev/urandom | base64 -w 0 > /tmp/b
```

(use the same input twice, then `cmp`). Any program with an external reference is acceptable — a `cat -n`, an `od -An -tx1`, a `cksum`-style checksum. Say which oracle you chose and why in the pull request.

**What "done" means, all four:**

1. `examples/base64.logos` builds with `./tools/logosc.sh build examples/base64.logos -o build/base64`.
2. `tools/accept.sh` gains a section that runs it against the oracle over at least three inputs (empty, one byte, a four-kilobyte random block) and fails loudly on any diff.
3. The same section runs the example at `-O0` and `-O2` and the output is identical — the repository invariant.
4. `examples/base64.logos` is added to `tools/selfhost-manifest.txt` (`git ls-files '"'"'*.logos'"'"' | sort`), or `make test` and `bash tools/selfhost.sh` fail.

**Read first:** `AGENTS.md` (the gates), `docs/reference/language.md` (the v1 subset), `examples/wc.logos` (94 lines, the shape to copy). `clang` is needed for every build.

**Why this is good first issue:** one self-contained file plus one section in an existing script; no compiler change, so no bootstrap rebuild.'

make_issue \
'manual: cause and fix hint for `E0001`–`E0103` (parse and type diagnostics)' \
'good first issue,docs' \
'Part 1 of 4. `docs/reference/diagnostics.md` gives every code a short message but not what causes it or what to do about it. A reader who hits the code — usually an agent, mid-loop, with no human to ask — needs both in one line.

**Codes in this part:** `E0001`, `E0002`, `E0003`, `E0004`, `E0005`, `E0006`, `E0100`, `E0101`, `E0102`, `E0103`.

**What to write, per code:** one *cause* line (the form in the source that produces it) and one *fix* line (the edit that removes it), each verified against a program that actually triggers the code. The corpus already carries most of them: `tests/regress/*.expect` and the negative corpus under `tests/` name the code for a program that provokes it, so the trigger is copyable rather than invented.

**Done when:**

- `docs/reference/diagnostics.md` carries both lines for each of the ten codes above;
- every cause line names a real source form, and every fix line names a real edit — no "check your syntax";
- `./tools/logosc.sh guide --check` still passes (this page is not generated, but the table must not contradict `logosc guide --json`, which reports 36 codes in 8 categories);
- `bash tools/check_doc_links.sh .` reports 0 broken.

Parts 2–4 cover the rest; do not touch their codes in this issue. See the sibling issues labelled `good first issue` and titled `manual: cause and fix hint for …`.'

make_issue \
'manual: cause and fix hint for `E0104`–`E0201` (type, arity, mutability, fields)' \
'good first issue,docs' \
'Part 2 of 4. Same job as Part 1, different codes.

**Codes in this part:** `E0104`, `E0105`, `E0106`, `E0107`, `E0108`, `E0200`, `E0201`.

**What to write, per code:** one *cause* line (the form in the source that produces it) and one *fix* line (the edit that removes it), each verified against a program that actually triggers the code. `tests/regress/*.expect` and the negative corpus name the code for a program that provokes it, so the trigger is copyable rather than invented.

Two of these need care rather than a template: `E0107` (`unused binding`) is refused by the checker but is not an error in most languages, and `E0106` covers both integer and float literals out of range — say so, and see `tests/regress/float-range.check`.

**Done when:** both lines exist for all seven codes in `docs/reference/diagnostics.md`; each is proved by a program that produces that exact code; `./tools/logosc.sh guide --check` passes; `bash tools/check_doc_links.sh .` reports 0 broken.'

make_issue \
'manual: cause and fix hint for `E0300`–`E0402` (moves, frees, places)' \
'good first issue,docs' \
'Part 3 of 4. Same job as Part 1, and the most valuable part of the four: these are the codes a newcomer to Logos hits first, because the language makes ownership explicit and refuses the forms that hide it.

**Codes in this part:** `E0300`, `E0301`, `E0302`, `E0303`, `E0304`, `E0305`, `E0400`, `E0401`, `E0402`.

**What to write, per code:** one *cause* line (the form in the source that produces it) and one *fix* line (the edit that removes it), each verified against a program that actually triggers the code. `docs/LOGOS.md` rules 4–7 and `tests/regress/*.expect` give the trigger for each; the negative corpus under `tests/` carries more.

`examples/agent-gate/` hit two of these for real in its own `EVIDENCE.md` "rough edges" list — a `:str` allocation that cannot be freed and a `:verdict` type spelled with a colon. Read that page before writing: it is what the codes look like to someone who did not design them.

**Done when:** both lines exist for all nine codes in `docs/reference/diagnostics.md`; each is proved by a program that produces that exact code; `./tools/logosc.sh guide --check` passes; `bash tools/check_doc_links.sh .` reports 0 broken.'

make_issue \
'manual: cause and fix hint for `E0500`–`E0800` and `R0006`–`R0007` (generics, results, threads, regress, diff)' \
'good first issue,docs' \
'Part 4 of 4. Same job as Part 1, and the part that covers the two codes a reader is most likely to misread.

**Codes in this part:** `E0500`, `E0501`, `E0502`, `E0600`, `E0601`, `E0602`, `E0700`, `E0800`, `R0006`, `R0007`.

Three of these carry a distinction worth stating explicitly rather than in a template:

- `R0006` / `R0007` are `R`-prefixed because they are *runtime* failures from `(run …)` and `(read-file …)`, not checker refusals — `R0007` is reachable from source. Diagnosis is still a code and a node path, so the entry belongs in the same table with that difference in one clause.
- `E0700` (`shared` marker) fires at *two* sites: the declaration and the thread boundary. Say which line the reader will see fixed.
- `E0800` is the differential-oracle code — a program that built but disagreed with its reference. It is the only code whose fix is "the program, not the syntax".

**Done when:** both lines exist for all ten codes in `docs/reference/diagnostics.md`; each is proved by a program or a corpus case that produces that exact code; `./tools/logosc.sh guide --check` passes; `bash tools/check_doc_links.sh .` reports 0 broken.'

make_issue \
'tooling: add `logosc fmt --check` (exit non-zero when a rewrite is needed)' \
'help wanted' \
'`fmt` rewrites files in place and has no way to ask "would this change anything?", so every contributor and every CI script implements the check by hand: copy the tree, run `fmt`, `diff`. That is the one tooling gap the release notes have hit twice.

Measured today on `main`:

```
$ ./tools/logosc.sh fmt --help
usage: logosc fmt [-h] FILE [FILE ...]
```

`--check` is absent; `--json` is present and emits diagnostics on stderr.

**What to add:** `logosc fmt --check FILE...` — exit `0` when every file is already canonical, exit non-zero when at least one would be rewritten, write nothing to disk in either case, and print the offending paths. `--check` and `--json` must compose (JSON diagnostics on stderr, one per file that needs rewriting). A `-` stdin argument keeps its current meaning and `--check` on stdin reports whether the input is canonical without echoing the rewrite.

**Done when:**

- `fmt -h` documents the flag;
- a test under `tests/` proves **both** outcomes — a canonical file exits 0, a file with a dropped-indent or an alias spelling exits non-zero and names it;
- `fmt FILE` and `fmt -` behave exactly as they do today (`fmt` is idempotent on all tracked `.logos` files — the self-hosting gate re-checks that);
- `bootstrap/logosc` is rebuilt in the same pull request with `cp build/logosc bootstrap/logosc && (cd bootstrap && sha256sum logosc > logosc.sha256)`, because this changes `src/logosc/*.logos`;
- `bash tools/pr_gate.sh` prints six PASS lines.

**Read first:** `AGENTS.md` (the bootstrap rule, the regress rule, the six gates), `src/logosc/` for the `fmt` verb, `tools/logosc.sh` for how the compiler is invoked. Budget an hour for the gate — it is measured at 1 h 08 m on six cores.

**Why help wanted and not good first issue:** it touches the compiler binary, so it obliges a bootstrap rebuild and a regress case. That is a real but scoped compiler change, not a sitting.'

make_issue \
'tooling: add `logosc doctor` — an install self-check' \
'help wanted' \
'The first support question any new install produces is "it says it cannot find clang / the runtime / the stdlib", and the compiler answers it with whichever failure it hit first, one at a time. A `doctor` verb turns that into one command with one verdict.

Today there is no such verb:

```
$ ./tools/logosc.sh doctor
logosc: error: argument command: invalid choice: '"'"'doctor'"'"'
  (choose from '"'"'build'"'"', '"'"'check'"'"', '"'"'fmt'"'"', '"'"'guide'"'"', '"'"'resolve'"'"', '"'"'show'"'"', '"'"'test'"'"', '"'"'version'"'"')
```

**What to add:** `logosc doctor` reports, one line each, with a stable `key: value` shape (so a script can grep it and `--json` can be added later without breaking anyone):

- the compiler version and the target triple it emits for;
- the resolved `clang` path and its `--version` first line;
- the C runtime file it will link, with its path and whether it is readable;
- the stdlib directory it will search, with its path and whether it is a directory;
- the installation layout it decided on (tarball-relative or repository-relative — the same lookup `build` uses), because that lookup is the actual source of most "cannot find" reports.

Exit `0` when every line resolved, exit `1` when any did not, and name the missing thing on its own line so the failing line is the diagnosis. No network, no compilation, nothing written.

**Done when:**

- the verb exists and is listed in `logosc -h` and in `docs/reference/cli.md`;
- a test proves the exit `0` case and the exit `1` case (point the stdlib lookup at a missing directory via the same environment variable or flag the install lookup already honours);
- `bootstrap/logosc` is rebuilt in the same pull request with `cp build/logosc bootstrap/logosc && (cd bootstrap && sha256sum logosc > logosc.sha256)`;
- `bash tools/pr_gate.sh` prints six PASS lines.

**Why help wanted and not good first issue:** it is compiler source plus a documented CLI contract, so it carries the bootstrap rebuild and the full gate.'

make_issue \
'stdlib: string-to-integer parsing in `str`' \
'help wanted' \
'`docs/reference/stdlib.md` says it plainly: "there is no string→integer parse". Every program that reads a number from `argv`, from a config file or from `calls.txt` — including `examples/agent-gate/`, which hand-rolled a byte scan for it — pays for that gap, and the workaround is the one place in the stdlib where a wrong implementation is silently wrong rather than refused.

**What to add:** a parse function with the conventions the rest of `str` uses (name it as the neighbours are named; return a `(res T E)` the way the fallible functions do, so the caller must handle it and `E0602` refuses a dropped result):

- accepts an optional leading `-` (and `+` if the neighbours do), digits only — no whitespace, no underscores, no radix prefix;
- refuses an empty string, a lone sign, a trailing character, and a value outside `:i64` with a distinct error per case rather than one "invalid";
- allocates nothing (a parse that allocates would be the only `str` function whose result nobody can free — see `docs/reference/limits.md`);
- documented in `docs/reference/stdlib.md` with its signature, its ownership behaviour ("allocates nothing") and its error cases, matching its neighbours'"'"' entries.

**Done when:** the function exists in the stdlib, has a `(test …)` node covering at least `"0"`, `"42"`, `"-7"`, `""`, `"12x"`, `"--1"` and one out-of-range value, `docs/reference/stdlib.md` documents it in the same shape as its neighbours, `bootstrap/logosc` is rebuilt, and `bash tools/pr_gate.sh` prints six PASS lines.

**Read first:** `docs/reference/stdlib.md` (21 functions, conventions, one verified program), `examples/agent-gate/gate.logos` (the hand-rolled scan this replaces), `AGENTS.md` (gates and bootstrap).'

make_issue \
'language: ordering comparison for `:str` (`(< "a" "b")` is `E0100` today)' \
'help wanted,compiler' \
'`docs/reference/limits.md` records the gap: `=` and `!=` work on `:str`, but `(< "a" "b")` is `E0100: '"'"'<'"'"' needs numbers, found :str`. Sorting strings therefore has no primitive, so `examples/json.logos`-class programs carry a hand-written byte comparator, and a challenge entrant sorting table keys will hit it immediately.

**What to add:** `<`, `>`, `<=`, `>=` accept `:str` operands, ordered by byte value (the same order `=` already uses), with the mixed-type case still `E0100` — `(< "a" 1)` must remain refused, and refusing it is the part that has to be tested.

**Done when:**

- the checker accepts the four operators on `:str` and still refuses mixed operands, each pinned by a case under `tests/regress/` (a positive `.logos` and a negative `.logos` + `.expect` carrying `E0100`);
- the backend lowers them (LLVM `icmp` on the byte comparison the `=` path already uses) and the accepted case is identical at `-O0` and `-O2`;
- `docs/reference/limits.md` drops the limit, and `docs/reference/language.md` lists the operators with an idiom;
- `./tools/logosc.sh guide > docs/LOGOS.md` is regenerated (this changes the compiler'"'"'s own tables) and `./tools/logosc.sh guide --check` passes;
- `bootstrap/logosc` is rebuilt in the same pull request;
- `bash tools/pr_gate.sh` prints six PASS lines.

**Why help wanted:** front end, backend, regenerated tables and a bootstrap rebuild — a week'"'"'s work for a contributor who has not read the checker, and the repository'"'"'s four invariants apply unchanged (`AGENTS.md`).'

echo "--- open issues now:"
gh issue list --repo "$REPO" --state open --json number,labels --jq 'length'
gh issue list --repo "$REPO" --label 'good first issue' --state open --json number --jq 'length'
