# `src/logosc/lex.logos` — the lexer

The first module of the self-hosted compiler: `logos/lexer.py` (146 lines) ported to
Logos. Logos has no comments and no doc form, so this file is the header
documentation the source cannot carry. Read it before calling the module.

The lexer is the only part of the front end that knows about characters. It emits
five token kinds and no newline or comment tokens: Logos has one construct per
node name and no comments, so whitespace carries no meaning.

## API

```logos
(fn lex lex-error ((src :str)
                   (kinds (ref (vec :i64)))
                   (texts (ref (vec :str)))
                   (lines (ref (vec :i64)))
                   (cols (ref (vec :i64)))))
```

`lex` appends one entry per token to each of the four caller-owned vectors and
returns a `lex-error`, which is the first error or `lex-pass`. Nothing else is
allocated that survives the call: the scanner's own state vector is freed before
the return.

| function | returns | meaning |
|---|---|---|
| `lex src kinds texts lines cols` | `lex-error` | tokenize `src`, appending to the four vectors |
| `lex-pass` | `lex-error` | the "no error" value |
| `lex-fail line col msg` | `lex-error` | the error value |
| `lex-ok e` | `:bool` | whether `e` is `lex-pass` |
| `lex-token …` | `lex-error` | implementation: one token at the current index |
| `lex-next …` | `lex-error` | implementation: skip whitespace, then `lex-token` |
| `lex-skip src st n` | `:void` | implementation: consume whitespace |
| `lex-string`, `lex-atom`, `lex-paren` | `lex-error` | implementation: one token of each shape |
| `lex-emit …` | `:void` | implementation: one push to each of the four vectors |

The scanner state is a three-element `(vec :i64)` — index, line, column — created
inside `lex` and passed to the helpers by `(ref …)`. A struct cannot hold a
vector, and a `:i64` is passed by value, so a vector of three integers is the
smallest thing a helper can mutate in its caller.

### The four vectors are the caller's

`lex` never frees them, never shrinks them and never reads them. They come back
with one element appended per token, so `(vec-len kinds)` is the token count and
index `i` of each vector describes the same token. `vec-free` each of the four
when done — they are four separate buffers, so four frees, not one.

**A text is a view unless the string had an escape.** Atom, number and paren
texts are `str-slice` views into `src`, and so is a string token with no escapes.
They point into the buffer the caller passed, which therefore must outlive them.
Only a string that contained an escape is built with `str-concat`, and those
buffers live for the process (design §D9). Freeing `texts` frees the vector, not
the bytes in it; there is no per-element free.

### On error the vectors hold a prefix

`lex` stops at the first error. The token that failed is **not** appended, so the
four vectors then describe the tokens before it — a prefix, not a token list.
The caller's duty is to check `(lex-ok e)` before reading them; a caller that
reads them anyway sees a well-formed but short stream, never a torn token.

## Token kinds

Kinds are `:i64` codes in the `kinds` vector. The language has no constants, so
the numbers are repeated at the few call sites and named here:

| code | name | text in `texts` |
|---|---|---|
| 0 | `LPAREN` | `(` |
| 1 | `RPAREN` | `)` |
| 2 | `ATOM` | the source text |
| 3 | `STRING` | the decoded text |
| 4 | `NUMBER` | the source text |

`NUMBER` keeps its source text, not a parsed value: the text is what the tree and
`fmt` carry, so `1.50` and `1e3` survive a round trip unchanged.

## Positions

One-based: the first character of the file is line 1, column 1. A token's
position is that of its **first** character, which for a string is the opening
quote.

- A `\n` ends the line: line plus one, column back to 1.
- A `\r` does **not**: it is ordinary whitespace, one column. A CRLF file
  therefore counts the `\r`, exactly as `logos/lexer.py` does.
- A tab is **one** column.
- A column counts **characters**, not bytes. That is a UTF-8 rule, because a
  `:str` is bytes: a byte that is not a continuation byte (`0x80`–`0xBF`) adds
  one column, a continuation byte adds none. `héllo (x)` puts the `(` at column
  7, and `(é)` puts its `)` at column 3, though those texts are 6 and 2 bytes.
  `src/logosc/lex_test.logos` pins both.

A source is UTF-8, as it must be for `logos/lexer.py` to have read it: a file
whose bytes are not valid UTF-8 has no column model there at all.

## Whitespace

Space, `\t` (`0x09`), `\n` (`0x0a`), `\v` (`0x0b`), `\f` (`0x0c`) and `\r`
(`0x0d`) are skipped and produce no token. That is exactly `str.isspace()` on
ASCII, so a source that lexes under `logos/lexer.py` skips the same bytes here.

## Atoms

An atom is a run of bytes that are none of:

- whitespace (above),
- `(` `0x28`, `)` `0x29`, `"` `0x22`,
- an illegal control byte (see *Unknown characters*),
- and it is at least one byte long.

Everything else belongs to the atom, including `+`, `-`, `.`, `%`, `:` and the
bytes of a non-ASCII character. That is the whole rule: `logos/lexer.py` has no
atom grammar either, because the checker owns the vocabulary and the parser
refuses nothing but unbalanced parentheses.

If the whole atom matches the number shape it is a `NUMBER`, otherwise an `ATOM`.

## Numbers

```
[+-]?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?
```

Anchored at both ends: the atom must match completely. Consequences, all pinned
by tests:

| text | kind | why |
|---|---|---|
| `1`, `-3`, `+7` | `NUMBER` | a sign is part of the number |
| `1.5`, `-2.5E-3`, `1e10` | `NUMBER` | fraction and exponent |
| `5.` | `ATOM` | a `.` must be followed by at least one digit |
| `1e` | `ATOM` | the exponent needs digits |
| `.5` | `ATOM` | a word may not start with `.`; there is no leading-digit-less form |
| `1.5.2` | `ATOM` | one fraction, and it must end the text |
| `-` | `ATOM` | a sign alone has no digits |
| `+` in `(+ -3 4)` | `ATOM` | an operator is an atom like any other |

The scanner is hand-written, not a regex, because the language has none: scan the
optional sign, scan digits, then an optional `.` plus digits, then an optional
`e`/`E` plus optional sign plus digits, and require the end of the text.

## Strings

A string starts at `"` and ends at the next unescaped `"`. The token's text is
the **decoded** contents, without the quotes.

| escape | byte |
|---|---|
| `\\` | `\` (92) |
| `\"` | `"` (34) |
| `\n` | line feed (10) |
| `\t` | tab (9) |
| `\r` | carriage return (13) |
| `\0` | NUL (0) |

Any other byte after a `\` is `unknown escape \<byte>`, reported at the line and
column of the **backslash**. The message is the one `logos/lexer.py` prints:
`unknown escape \q`, and — for a backslash before a raw newline — `unknown
escape \` followed by that newline byte. The escape is validated the moment it is
seen, so `"a\q` reports the unknown escape, not the missing quote.

A **raw newline inside a string is content**, not an error: it is appended to the
decoded text and advances the line counter. `"a` then a newline then `b"` is one
`STRING` of three bytes, `97 10 98`, on line 1.

A backslash as the last byte of the file, or a string that reaches the end of the
file without a closing quote, is `unterminated string`, reported at the line and
column of the **opening quote** — the position of the token that could not be
finished, which is what `logos/lexer.py` reports too.

**An escape-free string is a view, not a copy.** `(str-slice src (+ open 1) end)`
is the same buffer at an offset; the text then aliases `src`. A string with at
least one escape is rebuilt by `str-concat`, one escape at a time, so a string of
*n* escapes costs *n* copies and the result points into a buffer the process keeps
forever. That is the slow shape and it is deliberate: §D9 forbids freeing, and no
string builder exists yet.

## Unknown characters

A byte below `0x20` that is not one of the six whitespace bytes, or `0x7f` (DEL),
is `unknown character`, reported at its own position, and lexing stops there.
This is the one rule the port adds: `logos/lexer.py` cannot report it, because an
atom there is *any* run of non-delimiter bytes and a control byte would simply
join one. The W4 plan asks for `E0006` on an unknown character, so the port draws
the line where the Python lexer's permissiveness is clearly a bug rather than a
feature: a source with a NUL or a stray `0x01` in it is corrupt, and saying so at
its position beats lexing it into an atom that the parser then chokes on.

`0x7f` and the other `0x00`–`0x1f` bytes are covered; a NUL is the only one a
Logos *literal* can produce (`"\0"`), so it is the one the tests use. Every byte
from `0x80` up is an atom byte, so no source that lexes today stops lexing.

**The one other divergence is Unicode whitespace.** `logos/lexer.py` calls Python's
`str.isspace()`, which is true of NBSP, U+2028 and a dozen others; this module is
byte-level and sees only ASCII whitespace, so such a character joins the atom
around it instead of separating tokens. No file in the corpus has one outside a
string, and inside a string there is no difference at all.

## The error value is a struct, not the enum the brief sketched

The brief suggested `(type lex-error (enum (fine) (bad (line :i64) …)))`. Two
language rules forbid it as written, and one compiler bug forbids a plain
work-around:

1. **A variant takes at most one payload type.** `(bad (line :i64) (col :i64)
   (msg :str))` is `E0002 an enum variant must be (name) or (name type)`.
2. **A payload may not be a struct defined in another module**, when the enum is
   matched *outside* the module that declares it. `(enum (fine) (bad lex-fault))`
   compiles, and the checker accepts every use, but the emitted IR mixes
   `%struct.lex-fault` with `%struct.lex.lex-fault` at the payload bitcast and
   clang rejects the module:

   ```
   error: '%t20' defined with type '%struct.lex-fault*' but expected '%struct.lex.lex-fault*'
   ```

   A wildcard arm `((bad _) …)` does not escape it, and W4 may not change the
   checker or the lowerer, so the shape moves:

```logos
(type lex-error (struct (failed :bool) (line :i64) (col :i64) (msg :str)))
```

A struct crosses a module boundary, is passed by value and is read with `(get e
line)` without trouble; only the enum-with-a-struct-payload path is broken. The
cost is one `:bool` and two helpers, `lex-pass` and `lex-fail`, in place of a
match. When the payload bug is fixed, this can go back to the enum the brief
wanted; nothing else in the module would change.

`line` and `col` are `0` in `lex-pass` and are meaningless there: read them only
when `(lex-ok e)` is false.

## What it does not do

- **No `E0006` prefix and no `file:line:col` line.** The error is a value, not a
  rendered diagnostic; Task 4 prefixes it when it writes stderr.
- **No newline, comment or EOF token.** The empty source is zero tokens, and
  trailing whitespace is not a token either.
- **No re-emission of escapes.** Decoding is this module's job; `fmt` owns the
  canonical spelling of the text it prints (§W4 task 3).
- **No validation of the number's range.** `99999999999999999999` is a `NUMBER`
  here; `E0106 integer literal out of range` belongs to the checker.
- **No UTF-8 validation and no Unicode classes.** Bytes only; the column rule is
  the one place the byte stream is read as characters.
- **No error recovery.** The first error ends the scan; there is no "skip and
  continue" mode, because a diagnostic per token is not what the compiler prints.

## `src/logosc/lex_test.logos`

22 cases, each `(leaks 0)` and each run at `-O0` and `-O2`: the empty source; `(`;
`)(`; `(a) (b)`; `(+ -3 4)`; the number matrix above; a tab's column; the
character columns of `héllo (x)` and `→\t(`; a three-line source; CRLF and `\t`
as whitespace; adjacent strings; the six escapes decoded byte by byte
(`92 34 10 9 13 0`); a string holding a NUL; the empty string; a raw newline
inside a string; `"abc` under `unterminated`; `"abc\` under
`unterminated-escape`; `"a\qb"` under `unknown-escape`; a backslash before a raw
newline under `unknown-escape-newline`; `"a\q` with no closing quote under
`unknown-escape-unterminated`; and a NUL outside a string under
`unknown-character`. Each error case asserts the line, the column and the whole
message.

Beyond the tests, the port was compared token by token against
`logos/lexer.py` over 29 corpus files (`docs/manual/*.logos`, `src/std/*.logos`,
this module, `src/logosc/lex_test.logos`, `tests/exec/results.logos`,
`tests/exec/strings.logos`): 12,992 token lines, identical kind, line, column,
byte length and decoded bytes. The comparison was a throwaway harness, not a
committed test — the plan's parity rule for W4 task 1 is hand-written
expectations, because there is no `logosc lex` verb to diff against.
