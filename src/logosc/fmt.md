# `src/logosc/fmt.logos` — the canonical printer

The third module of the self-hosted compiler: `logos/fmt.py` (115 lines) ported to
Logos. Logos has no comments and no doc form, so this file is the header
documentation the source cannot carry. Read `tree.md` first: `fmt` reads the
arena `tree-parse` builds and assumes node `0` is the file.

Every source file has one printed shape, so `fmt` output can be compared byte for
byte and used as canonical source an AI can rewrite without guessing. This
module produces that shape by walking the arena and printing fragments; it does
not build a string (§D10).

## API

```logos
(fn fmt :void ((nodes (ref (vec node)))
               (ntexts (ref (vec :str)))))
```

`fmt` prints the whole file to stdout: every top-level form at column zero, one
blank line between forms, a final newline. An empty file prints nothing. It
reads the two arenas and allocates nothing that survives the call; the caller
frees both, as it would after `tree-path`.

`nodes` and `ntexts` must be the arenas `tree-parse` filled successfully, with
the file node at id `0`. `fmt` never frees them and never reads a token vector
from the lexer: the tree owns every text it needs.

| function | returns | meaning |
|---|---|---|
| `fmt nodes ntexts` | `:void` | print the whole file canonically |
| `fmt-form nodes ntexts id column` | `:i64` | print one form starting at `column`; return its end column |
| `fmt-token ntexts tok text col` | `:i64` | print one token; a string is quoted and re-escaped |
| `fmt-string ntexts text col` | `:i64` | print a string token's canonical spelling |
| `fmt-put col s` | `:i64` | print `s`, return the column after its last byte |
| `fmt-break column` | `:i64` | print a newline and `column` spaces, return `column` |
| `fmt-indent n` | `:i64` | print `n` spaces, return `n` |
| `fmt-breaks nodes ntexts id` | `:bool` | whether this form puts its form children on their own lines |
| `fmt-form-count nodes id` | `:i64` | number of form children in the chain |
| `fmt-skip nodes ntexts id` | `:i64` | items before the first child: 0 bare list, 1 head only, 2 named, 3 named `extern` |
| `fmt-name ntexts kind name col` | `:i64` | print the retired definition name (and `extern`'s `fn` marker) |
| `fmt-gap`, `fmt-tail` | `:void` | implementation: the blank line between top-level forms and the final newline |
| `fmt-block-kind`, `fmt-field-kind`, `fmt-continuation` | `:bool` | implementation: kind tests and UTF-8 continuation bytes |

Every printer helper takes the current column and returns the column just past
what it printed. The column is the only state a recursive descent needs, and
passing it as an integer keeps the walk functional: no string builder, no
mutable position vector.

## The layout rule

One rule covers every form. The opening parenthesis and the head atom start a
line. Every inline item stays on that line: tokens, bare lists such as `()` and
a parameter list, and field lists. Each **form** child goes on its own line at
two spaces past the opening parenthesis, except that a form child is kept on the
opening line when it is the form's first item (position 0).

A form's children break when:

- the form has a head atom, and
- the head is not `struct` or `enum`, and
- it has two or more form children, or it is `fn`/`test` with at least one.

The second condition is why a `struct` or `enum` body never breaks even though
its fields and variants are forms. The third is why `(ret (+ a b))` stays on one
line while `(fn f :i64 () body)` always puts the body on its own line — a body
is a statement sequence and should be visible at a glance. `test` follows `fn`:
its `expect` and body each start a line.

A subtlety of the Python implementation this ports exactly: "position 0" means
the first item in the source, and a definition's **name** is an item. A named
form's first child is therefore never at position 0. That is why a composite
return type is broken:

```logos
(fn f
  (vec :i64) ()
  (ret (vec-len (make (vec :i64)))))
```

`(vec :i64)` is a form child at position 1, so it starts its own line; the `()`
that follows is a bare list, so it stays on that line. A closure takes no name
and keeps a token return type on the opening line.

Top-level forms start at column zero and are separated by one blank line; the
output ends in a newline. An empty file prints nothing.

## Columns

Continuation lines use **absolute** columns: a broken child is indented
`column + 2`, where `column` is the column where its parent started. That is
why each printer returns where it ended and takes where it starts.

`fmt-put` counts UTF-8 code points, not bytes: a continuation byte (`128..191`)
adds nothing, every other byte adds one. Python's `len` counts characters, so a
byte count would drift on a line holding a multibyte token before an inline form
that breaks. The `unicode-head` test pins it:

```logos
(é (g (a 1)
     (b 2))
  (c 3)
  (d 4))
```

`(g` starts at character column 3, so its `(b 2)` child is indented five
columns. Counting the two bytes of `é` would indent six.

## The retired head, name and `fn` marker

The tree's child chain starts **after** the head atom and the definition name;
`tree-finish-head` retires them (`tree.md`). `fmt` therefore prints them itself:

- the head text comes from `node.text`;
- a name comes from `node.name`;
- a named `extern` writes its marker third, `(extern fn name …)`, so
  `fmt-name` prints `" fn"` before the name — the tree stores the marker only
  implicitly, by accepting `extern`'s name solely when that marker is `fn`.

`fmt-skip` reconstructs the Python item positions from those retired entries: a
bare list skips none, a head-only form skips one, a named form two, a named
`extern` three. The break test uses it only to decide "position 0 or not", but
without it a named form's first child would wrongly stay inline.

## Strings

Atoms and numbers are re-emitted from their text, so `-2.5E-3`, `+7` and `1e10`
keep their spelling: the printer never reformats a number. A string token is
quoted and every byte is re-escaped:

| byte | printed |
|---|---|
| `\` | `\\` |
| `"` | `\"` |
| newline | `\n` |
| tab | `\t` |
| carriage return | `\r` |
| NUL | `\0` |

Everything else passes through, including UTF-8 bytes and other control bytes.
A raw newline or tab inside the source string therefore comes back as an escape;
`raw-newline` pins it. The lexer already decoded the escapes, so the printer is
the only place that spells them.

## Arena and ownership

`fmt` reads `nodes` and `ntexts` exactly as `tree-parse` left them. It assumes
node `0` is the file and walks `first`/`next` from there; it does not walk
tokens through a parallel array and does not use `node.path`. It allocates
nothing (each `fmt-*` helper returns an integer), so there is nothing to free in
the module and `(leaks 0)` holds whenever the caller frees the arenas it created
for the lexer and the tree.

## `src/logosc/fmt_test.logos`

Twenty cases, each `(leaks 0)` and each run at `-O0` and `-O2`:

1. `mod-alone` — `(mod a)` prints itself.
2. `inline-ret` — `(fn add …)` breaks its body; `(ret (+ a b))` stays on one line.
3. `fn-body-breaks` — `letmut`, `while`, `set` and `ret` each on its own line.
4. `test-body-breaks` — `test` breaks its `expect` and body; `expect` breaks its
   `(code …)` and `(leaks …)` clauses.
5. `struct-inline` — a two-field `struct` stays on one line.
6. `enum-inline` — a variant with a payload `(some :i64)` stays inline.
7. `escapes` — one string containing all six escaped bytes plus `é`.
8. `raw-newline` — a source string holding a raw newline and tab is re-escaped.
9. `deep-nested` — a chain of four nested forms, each with one form child,
   stays compact.
10. `sibling-run` — nested `if` forms: each branch starts its own line.
11. `composite-return` — `(vec :i64)` after a named `fn` breaks; `()` rejoins it.
12. `extern-named` — `(extern fn getpid :i64 ())` keeps the marker and name.
13. `closure` — an unnamed `fn` keeps `:i64` on the opening line and breaks its
    body at the form's column plus two.
14. `bare-heads` — a string head and a number head are bare lists and print
    their items inline.
15. `empty-list` — `()` is an inline item, not a break.
16. `unicode-head` — the multibyte head before a break pins character columns.
17. `canonical-file` — a whole module, `(use …)`, both type bodies, `extern`,
    two `fn`s with a `match`, and a `test`; its canonical form equals its input.
18. `empty-file` — prints nothing.
19. `numbers-and-cast` — number spellings and `(cast :f64 1e10)` pass through.
20. `match-and-calls` — two functions, `match` arms and a float division.

The harness feeds each source through `lex`, `tree-parse` and `fmt` and asserts
the exact stdout with `(out …)`. `fmt-src` frees all six vectors it creates.

`python3 -m logos test src/logosc/fmt_test.logos --opt -O0 --opt -O2` reports
`20 passed, 0 failed, 0 leaked`.

## Parity

`fmt` was compared against `logos/fmt.py` over 125 files — every tracked `.logos`
file plus this module and its test — with a throwaway driver that reads a path,
lexes it, parses it and runs `fmt`. Every one of the 125 outputs is identical to
`logos/fmt.py` at both `-O0` and `-O2`; the two levels agree with each other.

Of those 125, **123 already were canonical**: their Logos `fmt` output equals
their bytes. That includes all 19 manual chapters, all six `src/std/*.logos`
files, all four `src/logosc/*.logos` files that existed, and both new files.
Two do not format to themselves:

- `examples/json.logos` — hand-formatted. Its `(while (and …))` keeps a second
  operand on the opening line, and several long `(vec-set …)` calls keep several
  form children on one line. The canonical printer breaks both (`and` with two
  form children; `vec-set` with three). `fmt` is not wrong here; the example is
  not canonical, and `logosc fmt` rewrites it.
- `examples/wc.logos` — the long `(or (or …))` chain in `wide-space` is one
  hand-wrapped line. Canonical layout puts every form after the first on its own
  line, so the chain becomes fourteen indented lines. Again the file is not
  canonical.

The 31 files the plan names — 19 manual chapters, 6 std, 4 `src/logosc`, plus
the two this task adds — are all in the 123.

## What it does not do

- **No lexing or parsing.** It reads an arena; callers run `lex` and
  `tree-parse` first. A failed parse must not be printed.
- **No diagnostics.** Every byte it prints comes from a tree the parser built;
  a malformed form such as `(wibble 1 2)` prints like any other.
- **No comments.** Logos has none.
- **No string building.** The output is a stream of fragments. A caller that
  wants a string must capture stdout, which is exactly how the test suite
  asserts it.
- **No line wrapping.** Lines grow with the source; only form children break.
