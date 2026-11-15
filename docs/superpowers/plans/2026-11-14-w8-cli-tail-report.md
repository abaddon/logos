# W8 step 5a — the CLI tail, measured against Python

`version`, `show`, the dropped `patch`, the usage block and its exit codes, and
`test --update-baseline`, at `830464e` plus this branch. Python is still present
and is the oracle for every row: each command was run twice, once as
`python3 -m logos …` and once as the port, comparing stdout, stderr and exit
status as bytes. The comparator is `build/w8cli/cmp.sh` (one command, both
binaries, three streams, a `SAME`/`DIFF` line).

The port binary is `build/w8cli/gen2`, copied to `build/w8cli/logosc` for the
parity runs. That copy is not cosmetic: the usage block prints the base name of
`argv[0]`, which is how the same binary can be Python's `logosc` in one gate and
`gen2` in another, and it is why the texts below are byte-identical rather than
"identical apart from the program name".

## The parity table

Every row is `SAME` unless the verdict says otherwise; the text is what both
programs printed.

| # | item | command | Python | port | verdict |
|---|---|---|---|---|---|
| 1 | `version` | `logosc version` | `logos 0.1.0`, exit 0 | same bytes, exit 0 | identical |
| 2a | `show` a definition | `logosc show examples/hello.logos hello/main` | `(fn main :void ()\n  (println "hello"))\n`, exit 0 | same | identical |
| 2b | `show` a nested expression | `… hello/main/2` | `(println "hello")\n`, exit 0 | same | identical |
| 2c | `show` a token / bare list | `… hello/main/0`, `… hello/main/1` | `:void\n`, `()\n`, exit 0 | same | identical |
| 2d | `show` the file itself | `logosc show examples/hello.logos ""` | the whole canonical file, exit 0 | same | identical |
| 2e | `show` a missing path | `… hello/main/9` | `logos: show: no node at path 'hello/main/9' in examples/hello.logos\n`, exit 1, stdout empty | same | identical |
| 2f | `show` a malformed path | `… hello`, `… /hello/main`, `… hello//main`, `… hello/main/1/0`, `… x/1/2` | the same no-node line for each, exit 1 | same | identical |
| 2g | `show` an unreadable file | `logosc show /nope.logos /x` | `logos: /nope.logos: No such file or directory\n`, exit 1 | same | identical |
| 2h | `show` every addressable path | 593 `(file, path)` pairs over `examples/hello.logos`, `src/std/map.logos`, `tests/exec/closures.logos`, `tests/regress/multi-module/program.logos` | — | — | 593/593 identical (`build/w8cli/show_sweep.py`) |
| 3a | `patch` dropped | `logosc patch examples/hello.logos hello/main` | Python has the verb: `logos: patch: stdin must hold exactly one form`, exit 1 | `usage: logosc [-h] command ...` / `logosc: error: argument command: invalid choice: 'patch' (choose from 'build', 'test', 'fmt', 'show', 'version', 'guide')`, exit 2 | **intended difference**: an unknown verb, as specified |
| 3b | `patch` gone from the help | `logosc` | help has `    patch     replace one node of a Logos file` | that line absent, everything else byte-identical | **intended difference** |
| 4a | no argument | `logosc` | argparse's help on **stdout**, exit 0 | byte-identical minus the `patch` row, exit 0 | identical apart from 3b |
| 4b | unknown verb | `logosc frobnicate` | `usage: logosc [-h] command ...` / `… invalid choice: 'frobnicate' (choose from 'build', 'test', 'fmt', 'show', 'patch', 'version', 'guide')`, exit 2 | same with `'patch', ` removed from the list, exit 2 | identical apart from 3b |
| 4c | missing required argument | `logosc show`, `logosc show FILE`, `logosc fmt`, `logosc build` | sub-usage line + `logosc show: error: the following arguments are required: FILE, PATH` (and `PATH`, `FILE`, `FILE`), exit 2 | same | identical |
| 4d | extra word / bad flag | `show F P x`, `version extra`, `guide --bogus`, `guide --json --check`, `build F -x`, `test a b`, `test --only`, `test --opt`, `build -o`, `fmt -x`, `fmt -x F` | main-usage line + `logosc: error: unrecognized arguments: …`, or the sub-parser's `argument …: expected one argument`, exit 2 | same | identical |
| 4e | a path that does not exist | `logosc fmt /nope.logos`, `logosc build /nope.logos`, `logosc show /nope.logos /x` | `logos: /nope.logos: No such file or directory\n`, exit 1 | same | identical |
| 4f | `test` on a missing root | `logosc test /nope` | `logos: test: /nope: no such file or directory\n`, exit 1 | same | identical |
| 5a | baseline, full run | `logosc test build/w8cli/corpus --update-baseline` | 310 stdout lines, `baseline build/w8cli/corpus/summary.txt: 308 cases`, exit 0, 176.85 s | byte-identical stdout, exit 0, 197.22 s | identical |
| 5b | baseline, the file | the run above | `summary.txt` = `4bf2f19b9ff9a26877eefa215d1d245335cfbf35f32020010752c6d4d639a31e`, 310 lines | same sha256 | identical, and equal to the committed `tests/summary.txt` |
| 5c | baseline, filtered merge | `--only exec --opt -O0 --update-baseline` over a scratch suite with one failing, one passing case | the failing line rewritten, the other category kept, headers from the previous file, `baseline …: 1 cases`, exit 1 | same bytes, same line, exit 1 | identical |
| 5d | baseline, stale line dropped | delete a fixture, then `--only exec … --update-baseline` | the deleted case's line disappears, the other categories stay | same | identical |
| 5e | baseline, no file to merge into | `--only exec … --update-baseline` on a fresh root | one `PASS` line, **no** `LEAKS`/`OPTS` header | same | identical |
| 5f | baseline, nothing changed | rerun the same full update | the file is rewritten, same bytes | same (mtime advances) | identical |
| 5g | baseline root refused | file, category dir, nested dir, nonexistent path | `logos: test: --update-baseline needs a directory, not a single file` (etc.), exit 2, nothing run, nothing written | same | identical |

## What each item cost

### 1. `version`

One string. `main-version` prints `logos 0.1.0\n` to descriptor 1 and returns
0 — Python's `f"logos {__version__}"` (`cli.py:131`, `logos/__init__.py:3`).
Any argument after the verb is `unrecognized arguments`, as `argparse` reports
it.

### 2. `show`

The address is the node path the diagnostics already print, and the port
already assigns those paths (`tree.logos`'s `tree-fill-paths` is
`nodes.assign_paths`). What was missing was the lookup. `main-find-tree` asks
each top-level form for its stored path and descends through `main-find-below`,
numbering each form's children from zero; tokens are numbered too, because
`m/f/0` is a return type and can be shown, while a token stores no path of its
own — so the walk mirrors the assignment instead of reading the field.
`main-prefix` is `str.startswith(child + "/")`, including its empty-prefix
behaviour, which is why `hello//main` and `/hello/main` miss exactly as Python's
do.

Printing is the existing printer: `fmt-form` at column zero for a form,
`fmt-token` for a token, each plus the one newline `render` appends; the empty
path is the whole file (`fmt 1`), which is also why an empty file prints
nothing. The 593-path sweep is the evidence that "addressable by Python" and
"addressable by the port" are the same set, not just the six shapes the test
names.

### 3. `patch` dropped

Removed from the help and from the dispatch. It was never a `logosc` verb —
it replaces one node from stdin, no gate and no script uses it, and a verb that
is a developer convenience is not part of the contract. Given a `patch` command
line the port now does what it does for `frobnicate`: `argparse`'s invalid-choice
error naming the six remaining verbs, exit 2. Python still has the verb, so this
row is a **deliberate** difference, not a failure; the help and the choice list
are otherwise Python's bytes.

### 4. Usage block and exit codes

`argparse` reports two kinds of error from two parsers, and the text says which:
a sub-parser's own complaint (a missing positional, a mutually exclusive pair)
prints **that verb's** usage line and `<prog> <verb>: error: …`, while
`invalid choice` and `unrecognized arguments` come from the top-level parser and
print the main usage line and `<prog>: error: …`. `main-cli-error` is both
shapes; `main-verb-usage` is the table of per-verb usage tails.

`COLUMNS` is not honoured: Python's help wraps at the terminal width, the port
prints the 80-column rendering. Every measured row ran without `COLUMNS` set,
which is how the gate runs.

### 5. `test --update-baseline`

`tester.write_baseline` (`760-830`) is the only writer of `summary.txt`, so its
bytes are the contract:

- two headers — `LEAKS <n>`, `OPTS -O0 -O2` — then one line per case,
  `PASS|FAIL <encoded id> <detail>`, in **run order** (category order, each
  category's files sorted, each file's tests in source order), never sorted by
  id;
- the id is `quote(id, safe="/._-")` — `h-encode` keeps `[A-Za-z0-9]` and
  `/._-~` and spells everything else `%XX`;
- a `PASS` detail is `-`; a `FAIL` detail is escaped (`\r`, `\n`, `\t`) and cut
  to 240 bytes;
- a **full** run replaces the file, which is what drops a deleted case and
  records the leak total and its levels; a **filtered** run merges — it rewrites
  the lines it ran, keeps the rest, drops a line under the category it covered
  in full whose case did not come back, appends new cases in run order, and
  keeps the *previous* `LEAKS`/`OPTS` because a filtered run does not see the
  whole suite;
- the write is unconditional (Python rewrites even when nothing changed), the
  stdout line is `baseline <root>/summary.txt: <n> cases`, and the exit status
  is 1 when any case failed;
- nothing is written when the run found no case or skipped a file — Python
  returns 1 before the write in both branches.

The proof is the whole corpus twice: a copy of `tests/` under
`build/w8cli/corpus`, both tools run with `--update-baseline`, and the two
`summary.txt` files `cmp`-identical at 310 lines — and identical to the
committed `tests/summary.txt`, which is what a full rewrite of an unchanged
suite must produce. Both stdout streams are byte-identical too, including the
trailing baseline line. The real `tests/summary.txt` was never passed to either
tool.

## Deviations, stated

| deviation | why |
|---|---|
| `patch` is gone (help, choice list, dispatch) | the task: it is not a verb `logosc` keeps |
| the usage/help text names `argv[0]`'s base name, not a constant | Python hardcodes `logosc`; the port must also run as `gen2` in the self-hosting gate. Copied to `logosc`, its text is Python's bytes |
| `resolve` and `check` are not in the help | they are this port's verbs and have no Python spelling; the help is Python's, so it cannot name them. They keep one usage line each (`main-port-verb`) |
| `COLUMNS` does not rewrap the help | the text is a constant; argparse wraps at the terminal width |
| an **absolute** root's baseline line is not shortened against the working directory | the language has no `getcwd` and adding one changes the runtime and every binary's IR. A relative root — `logosc test --update-baseline`, the cutover's invocation — prints Python's bytes |
| a malformed baseline is merged, not refused | Python raises `SuiteError` naming file and line; the port reads the headers it understands and treats the rest as case lines. W9 owns the comparison and its diagnosis |
| `_one_line`'s 240-byte cut counts bytes, not code points | Python counts characters. Every detail in the corpus is ASCII |
| a run without `--update-baseline` still prints no baseline line | comparing against the baseline (`BASELINE <id> …`, `n regression(s)`) is W9 by the inventory; this step adds only the writer |

## Tests

`tests/test_gen2_cli.py` (new, 22 cases, 167 s including one `gen2` build) runs
both binaries on the same tree and compares three streams byte for byte: version,
`show` (definition, nested form, token, bare list, whole file, every path of
three files, missing, malformed, unreadable file), the help and the choice list
(with `patch` subtracted exactly), missing arguments, extra words, missing
paths, and the baseline (full, rewritten unchanged, filtered merge with a stale
line dropped, a failing run's exit 1, no headers without a file, the refusals).

## Gates

`bash tools/pr_gate.sh` on this branch at `9f2b3ea` — the only change since is
the gate section of this file, which no gate reads: sign-off, then
**6/6 gates passed** — unit tests (`Ran 1153 tests`, 1317 s, the 1131 plus these
22), corpus, acceptance, manual drift, formatting, self-hosting
(`selfhost: 364 files, 0 differences`; `ir: 90 files, 0 differences`;
`resolve: 14 fixtures, 0 differences`; `check: 123 fixtures, 0 differences`;
`unit: 2 files, 0 differences`) — and `git diff --exit-code -- '*.logos'` clean
after `fmt`, which is the fixed point `make fmt` also holds.

The formatting gate is the one that matters for this change: everything above
was written by hand, then `python3 -m logos fmt` was run over the three edited
modules, and the gate re-runs it over the whole tree and finds nothing to
change. `python3 -m logos guide --check` reports `guide: docs/LOGOS.md is
current`, so the manual did not move: the CLI is documented in `main.md` and
`harness.md`, not in the generated manual.

## Files

| file | change |
|---|---|
| `src/logosc/main.logos` | `main-help`, `main-verb-usage`, `main-cli-error`, `main-required`, `main-unrecognized`, `main-invalid`, `main-prog`; `version`; `show` and its path lookup; `patch` removed; the dispatch rewritten; `build`'s unreadable-path line; `main-test`'s baseline-root check |
| `src/logosc/harness.logos` | the case records (`h-pass`/`h-fail`), `h-encode`/`h-one-line`, the baseline text/merge/write (`h-baseline-*`, `h-lines`, `h-line-id`, `h-merged`), `h-run`'s `update` argument; the three `rt_*` externs moved here |
| `src/logosc/guide.logos` | the three externs removed (they live in `harness.logos`, which `guide` already uses) |
| `src/logosc/main.md`, `harness.md`, `guide.md` | the command line, `version`/`show`, the baseline, the externs' home |
| `tests/test_gen2_cli.py` | new |
| `docs/superpowers/plans/2026-11-14-w8-cli-tail-report.md` | this file |
