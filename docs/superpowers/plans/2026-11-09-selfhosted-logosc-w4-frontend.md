# W4 — the front end in Logos: lexer, tree, `fmt`

Wave W4 of `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md`. The
first wave where compiler code itself is ported. Target: **`gen2 fmt` rewrites
every corpus `.logos` file byte for byte**, and `tools/selfhost.sh` becomes the
sixth gate.

Read with §D7 (arenas and integer handles), §D9 (no free inside the compiler),
§D10 (fragments) and the layout section (`src/logosc/`).

## What is being ported

The Python front end is small enough to port whole:

| Python | Lines | Ported to |
|---|---|---|
| `logos/lexer.py` | 146 | `src/logosc/lex.logos` |
| `logos/parser.py` | 87 | `src/logosc/tree.logos` |
| `logos/nodes.py` (paths) | 211 | `src/logosc/tree.logos` |
| `logos/fmt.py` | 115 | `src/logosc/fmt.logos` |
| `logos/cli.py` (fmt verb only) | — | `src/logosc/main.logos` |

Five token kinds (`LPAREN`, `RPAREN`, `ATOM`, `STRING`, `NUMBER`), no comments,
no newline tokens, one-based positions where a tab is one column. The parser
knows no grammar: `(` opens a node whose kind is its head atom, `)` closes it.
Paths are `name/child/child…` in source order.

## Shape (§D7)

No struct holds a vector, so the tree is an arena:

```
(nodes (vec node))    kind by id, first child by id, next sibling by id
(texts (vec :str))    atoms, strings and numbers by id
(kinds (vec :i64))    token kind by id
(lines (vec :i64))    line by id
(cols (vec :i64))     column by id
```

`node` is a struct of five `:i64` fields. Every function takes the arenas by
`(ref …)` and passes ids, never pointers.

## Global constraints

- Every `.logos` file is `fmt`-canonical and idempotent; `logosc fmt` changes nothing.
- Each task's tests fail before its code and pass after; record the failing line.
- Tests run under `python3 -m logos test src/logosc/… --opt -O0 --opt -O2`.
- `git commit -s`; one logical change per commit.
- No checker change in this wave. If a task needs one, stop and report.

## Task 1: the lexer

- [ ] `src/logosc/lex.logos`: five token kinds, the escape table
      (`\\ \" \n \t \r \0`), the number shape
      `[+-]?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?`, one-based line/col, tab is one
      column, `E0006` on an unknown character or an unterminated string or an
      unknown escape.
- [ ] `src/logosc/lex_test.logos`: empty source; one paren; every escape; a
      string with a NUL; integers, floats, exponents; `(+ -3 4)`; a tab's column;
      an unterminated string (`E0006`); an unknown escape (`E0006`); a lone `)`.
- [ ] Parity: for each source, assert the token count, the kinds and the
      decoded texts, chosen to pin the rules above. There is no `logosc lex`
      verb to diff against, so the expectations are written by hand.

## Task 2: the tree and the paths

- [ ] `src/logosc/tree.logos`: the arena, `tree-parse` building it from tokens,
      first-child/next-sibling links, `tree-path` producing `name/0/1`, and
      `E0001` for unbalanced input (a lone `)` or an unclosed `(`).
- [ ] `src/logosc/tree_test.logos`: `(mod a)` alone; nesting to depth 5; a
      sibling run; the path of a nested node; unbalanced cases.
- [ ] The parser refuses nothing else: an unknown head atom still parses and
      prints, because the checker owns the vocabulary.

## Task 3: `fmt`

- [ ] `src/logosc/fmt.logos`: canonical printing — one node per line, two-space
      indent per level, atoms and strings re-escaped exactly, numbers re-emitted
      from their text, a blank line after `(mod …)`, trailing newline.
- [ ] `src/logosc/fmt_test.logos`: the canonical forms of every construct the
      corpus uses; a string needing every escape; a deeply nested form; a file
      that is already canonical (the output equals the input).
- [ ] The rule: `fmt (parse s) == s` for every canonical source in the repo.

## Task 4: the verb and the sixth gate

- [ ] `src/logosc/main.logos`: `argv` → `fmt <file>` → read, parse, print to
      stdout; exit 0, or 2 with `file:line:col: E0006: …` on stderr.
- [ ] `tools/selfhost.sh`: build `gen2` from `src/logosc/*.logos` with the Python
      compiler, run `gen2 fmt` over `tools/selfhost-manifest.txt`, and diff every
      output against the file itself. The floor asserts the manifest's count.
- [ ] Wire it as the sixth gate: `tools/pr_gate.sh`, `AGENTS.md`,
      `.github/workflows/gate.yml`, and the count `tests/test_contributing.py`
      pins — in this commit, so the gate never ships unenforced.
- [ ] Parity: every manifest file formats byte-identically. Any file that does
      not is either a `fmt` bug or a non-canonical file; the wave stops until
      each is explained.

## Review focus

1. The arena's links: a child chain that drops a sibling, or a first child that
   points at the wrong node, must fail a test.
2. Escapes: a string containing every escape round-trips through print and
   re-parse.
3. Paths: the path a node reports is the one the Python compiler reports for the
   same source.
4. `fmt` on a non-canonical file: the output is canonical, and formatting it
   again changes nothing.
5. The sixth gate's floor: an empty manifest must fail, not pass.
