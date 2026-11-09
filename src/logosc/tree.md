# `src/logosc/tree.logos` — the sexpr tree and its paths

The second module of the self-hosted compiler: `logos/parser.py` (87 lines) and
the path half of `logos/nodes.py` (211 lines) ported to Logos. Logos has no
comments and no doc form, so this file is the header documentation the source
cannot carry. Read it before calling the module.

The parser knows no grammar. `(` opens a node whose kind is its head atom, `)`
closes it, and everything else is a token. Arity, node vocabulary and types
belong to the resolver and the checker, so `(wibble 1 2)` parses and prints.

## API

```logos
(fn tree-parse tree-error ((kinds (ref (vec :i64)))
                           (texts (ref (vec :str)))
                           (lines (ref (vec :i64)))
                           (cols  (ref (vec :i64)))
                           (nodes (ref (vec node)))
                           (ntexts (ref (vec :str)))))

(fn tree-path :str ((nodes (ref (vec node)))
                    (ntexts (ref (vec :str)))
                    (root :i64)
                    (target :i64)))
```

`tree-parse` reads the four token vectors the lexer filled and appends one
`node` per form and per token to `nodes`, with the text of every token and every
form head appended to `ntexts`. It returns a `tree-error`; on success the arena
holds the whole tree, and on failure it holds the prefix built before the first
error (see Errors).

`nodes` must be **empty** on entry. `tree-parse` pushes the file node as the
next entry and hardcodes frame 0 as id `0`, so it assumes that entry is node 0.
A caller that passes a non-empty `nodes` gets a corrupted arena with no error:
the top-level forms attach to the caller's node 0 and the file node `tree-parse`
pushes is left childless, so `tree-path` treats the caller's node 0 as the root.
Call `tree-path` with `root` = `0`. `ntexts` may be pre-filled — texts are
appended and addressed by their id in the vector, so earlier entries only shift
the ids (`dirty-arena` pins both facts). `tree-parse` does not free either
vector; the caller frees both.

| function | returns | meaning |
|---|---|---|
| `tree-parse …` | `tree-error` | build the arena from the lexer's four vectors |
| `tree-path nodes ntexts root target` | `:str` | the path of node `target`, or `""` for the root and for a token |
| `tree-ok e` | `:bool` | whether `e` is `tree-pass` |
| `tree-pass` | `tree-error` | the "no error" value |
| `tree-fail path line col msg` | `tree-error` | the error value |
| `tree-open`, `tree-close`, `tree-leaf`, `tree-token` | `tree-error` | implementation: one `(`, one `)`, one atom/string/number, one token |
| `tree-finish`, `tree-finish-head` | `:void` | implementation: name a closed form and drop its head/name from the child chain |
| `tree-module`, `tree-segment`, `tree-below`, `tree-join` | `:i64` / `:str` | implementation: path computation |
| `tree-unclosed` | `tree-error` | implementation: the partially built tree's innermost open form |

## Arena shape (§D7)

One `(vec node)` holds every form and every token; a `(vec :str)` holds their
texts. That is the shape the plan's "Shape (§D7)" section and §D7 itself name:
one `(vec node)` for the tree, children by first-child and next-sibling ids,
text by id into `(vec :str)`. The plan's sketch of `node` has five `:i64`
fields; this module needs seven (`text`, `tok`, `first`, `next`, `name`, `line`,
`col`), and a struct of `:i64` fields is what the plan allows. One struct arena
plus one text vector keeps each function to two arena `(ref …)` parameters
instead of a parallel vector per field. Editing one link is `vec-get`,
`set-field`, `vec-set` — three statements — and every function passes the two
arenas by `(ref …)` and ids, never pointers.

```logos
(type node (struct (text :i64)   ; head atom of a form, or a token's text
                   (tok :i64)    ; -2 file, -1 form, 2 ATOM, 3 STRING, 4 NUMBER
                   (first :i64)  ; first child id, -1 for none
                   (next :i64)   ; next sibling id, -1 for none
                   (name :i64)   ; the definition name's text id, -1 for none
                   (line :i64)   ; one-based `(` or token position
                   (col :i64)))
```

`text` is `-1` for a bare list (`()` or a form whose first item is not an atom,
such as `("s" x)`), because such a form has no kind. Token kind codes are the
lexer's: `2` `ATOM`, `3` `STRING`, `4` `NUMBER`. `LPAREN` and `RPAREN` are never
stored as nodes — they build and close forms — and `tok = -2` marks the file
node, `tok = -1` marks every form.

Every form's head atom and every named form's name are allocated as nodes like
any other token, then retired: `tree-finish-head` sets `first` past them when
the form closes, so they remain in `nodes` and `ntexts` but appear in no child
chain. `(mod a)` therefore allocates four entries and has a tree chain of two.
`(vec-len nodes)` is an allocation count, not a tree-node count — it includes
the retired head and name entries. `tree-path` and the `first`/`next` chains are
the tree.

`text` ids are **not** the lexer's token indexes: every text a node needs is
appended to `ntexts`, which the tree owns. The strings themselves are views into
the source (or process-lifetime buffers, for an escaped string), so appending
one copies a pointer, not bytes.

## Children

A form's children are the linked `first`/`next` chain. The head atom and the
definition name are **not** in it: they are part of the form. This mirrors
`nodes._children` exactly, including its four cases:

| form | children start at | example |
|---|---|---|
| no head (bare list, or a non-atom first item) | the first item | `(a b)` keeps `a`; `("s" x)` keeps the string |
| head, no name | the item after the head | `(fn :i64 …)` numbers `:i64` as child 0 |
| head and name | the item after the name | `(fn f :i64 …)` numbers `:i64` as child 0 |
| `extern` with a name | after the `fn` marker and the name | `(extern fn getpid :i64 ())` numbers `:i64` as child 0 |

`name` is filled by the same rule as `Node.name`:

- `mod`, `fn`, `test`, `type` and `extern` are the named kinds;
- the candidate must be an `ATOM` that does not start with `:` (a type marker
  such as `:i64` is not a name, so a closure has no name);
- `extern` writes its name third, `(extern fn name …)`, and only when the
  second item is the atom `fn`; an `extern` spelled any other way has no name
  and keeps its second item as child 0.

A malformed form is never refused. `(extern fn :i64 ())` has no name, so its
`fn` marker is a numbered child; `(fn (a :i64) …)` has no name either. The
resolver reports the malformed spelling.

## Paths

Paths follow `nodes.assign_paths` exactly.

- The file's path is `""`.
- The **module** is the first top-level form whose kind is `mod` and which has a
  name. Its path is its name. It is not part of the numbering of the other
  top-level forms.
- Every **other top-level form** gets a segment: its name for a named kind,
  `test/<name>` for a test, and the decimal slot otherwise. `slot` counts the
  top-level forms that are not the module, from zero. A second `(mod m2)`, or a
  nameless `(mod)`, is an ordinary form and gets its name or a slot.
- Every **other child**, at any depth, gets its decimal index in the parent's
  child chain. The index counts **tokens as well as forms**: a token occupies a
  slot but has no path of its own. This is the one place the brief's "its slot
  index among the node children" undersells `assign_paths`; the Python is
  authoritative, and the tests pin it.

Examples, each pinned by `tree_test.logos`:

| source | paths |
|---|---|
| `(mod a)` | `mod` is `a` |
| `(mod d)(fn f :i64 ()…` | `mod` is `d`, `fn` is `d/f`, its parameter list `d/f/1`, its body `d/f/2` |
| `(mod s)(fn a…)(fn b…)(fn c…)` | `s/a`, `s/b`, `s/c` |
| `(mod p)(fn f :i64 ((x :i64)) (ret (+ x 1)))` | `p/f/1` is the parameter list (the `:i64` token is index 0), `p/f/2` the `ret`, `p/f/2/0` the `+` |
| `(mod u)(wibble 1 2)` | `u/0` — an unknown head still parses and has a path |
| `(mod m)(test t …)` | the test is `m/test/t` and its `expect` is `m/test/t/0` |
| `(mod a)(mod b)(fn f :i64 ())` | `mod a` is `a`; the second `mod` is an ordinary named form, `a/b`; the `fn` is `a/f` and its `()` is `a/f/1` |
| `(x) (y)` with no module | `0`, `1` |

A top-level form with a name uses the name even when no module exists: `(fn a
:i64 ()) (fn b :i64 ())` gives `a` and `b`. The module is the only form whose
own path replaces its segment.

`tree-path` computes the path on demand, walking from `root` and carrying the
prefix; no path vector is stored. It returns `""` both for the root and for a
node that is not in the tree (including every token), so a caller that asks for
a token gets the same answer as for a missing node. Paths are built with
`str-concat` and are process-lifetime strings, untracked by §D9.

## Errors — all `E0001`

`tree-error` mirrors `lex-error`: `(failed :bool) (path :str) (line :i64)
(col :i64) (msg :str)`. It carries no code because every failure is `E0001`;
Task 4 prefixes the code when it writes stderr (the lexer's `E0006` arrives the
same way).

| input | `path` | `line`, `col` | `msg` |
|---|---|---|---|
| `)` with no open form | `""` | the `)` | `unbalanced ')'` |
| unclosed `(` | the innermost open form's path | its `(` | `unbalanced '('` |
| atom outside any form | `""` | the atom | `form outside parentheses` |

The third case is in `parser.py` even though the brief names only the first two;
a top-level atom has no form to belong to and is the same code.

An empty `path` is the signal for "the diagnostic precedes any node", so Task 4
renders `file:line:col` for it and `file:path:line:col` otherwise — exactly
`parser.py`'s two shapes.

**On failure the arena holds a prefix.** Parsing stops at the first error, but
the nodes already built remain: for the unclosed case the open forms are
attached to their parents (a form is appended when its `(` is read, not when it
closes), so the partial tree can be given paths. The innermost open form is
still on the frame stack; `tree-unclosed` names every open form and asks
`tree-path` for that one. For a lone `)` or a top-level atom there is nothing to
name and no path is computed.

## The frame stack

The parser is iterative, as `parser.py` is. Its stack is a `(vec open)` where

```logos
(type open (struct (id :i64) (line :i64) (col :i64) (last :i64)))
```

Frame 0 is the file node; an open form's frame is appended at index `depth`,
and `(vec :i64) state` holds the depth, i.e. one more than the number of open
forms. `last` is the form's last child so a sibling can be linked in O(1).
Both vectors are created inside `tree-parse` and freed on **every** return,
success or failure; the arena is the caller's, like the lexer's four vectors.
A close finalizes the form (kind, name, child start) and decrements the depth;
the node was already linked when it opened, so it is never linked twice.

`tree-path` and `tree-below` recurse once per nesting level. Logos allows
recursion; the depth of a real source is small (the tests go to six levels), and
there is no explicit limit.

## What it does not do

- **No arity or vocabulary check.** `(wibble 1 2)` and `(fn)` parse; the
  resolver owns E0002 and the checker owns the rest.
- **No formatting.** `fmt` is Task 3 and reads this arena.
- **No error recovery.** The first error ends the parse, as in `parser.py`.
- **No line/column work.** It copies the lexer's one-based positions.
- **No parent pointers.** `tree-path` walks down from the root; there is no
  parent id to maintain.

## `src/logosc/tree_test.logos`

Fourteen cases, each `(leaks 0)` and each run at `-O0` and `-O2`:

1. `mod-alone` — `(mod a)`, whose module is the whole output.
2. `nested-depth-5` — six nested forms under `(mod d)`, pinning every numeric
   path.
3. `sibling-run` — three `fn` forms in a row under `(mod s)`: `s/a`, `s/b`,
   `s/c`, and no sibling dropped.
4. `nested-paths` — `:i64` and the parameter list make the body `p/f/2`, so the
   token-counts-in-the-index rule is visible.
5. `unknown-head` — `(wibble 1 2)` parses and prints at `u/0`.
6. `test-name` — `(mod m)(test t (expect 1))`: the test is `m/test/t` and its
   `expect` is `m/test/t/0`.
7. `extern` — `(mod x)(extern fn getpid :i64 ())`: the `extern` is `x/getpid`;
   the `:i64` return type occupies child 0 and the `()` is `x/getpid/1`.
8. `bare-heads` — `(mod h)("s" x)(1 2)`: a string and a number as the first item
   make bare lists at `h/0` and `h/1`, each keeping both children.
9. `two-modules` — `(mod a)(mod b)(fn f :i64 ())`: the second `mod` is an
   ordinary named top-level form, `a/b`, and the `fn` is `a/f`.
10. `dirty-arena` — a pre-filled `nodes` (and `ntexts`) pins the entry
    precondition: `tree-parse` reports success, the module hangs off the
    caller's node 0, and the file node it pushed is childless.
11. `lone-close` — `)` at line 2 column 1, `path` empty.
12. `unclosed-form` — `(fn f :i64 ()` under `(mod e)` reports `e/f`.
13. `unclosed-nested` — `(+ 1` reports `e/f/2/0` at column 20.
14. `top-level-atom` — `x` reports `form outside parentheses`.

Each case prints the arena as `depth path label` lines, the root first, so the
child chain, the sibling order and the paths are all visible. `label` is the
form's head atom (`()` for a bare list), or `t<kind>:<text>` for a token, and a
token's path prints `-`. `vec-len nodes` is printed ahead of the dump; because
retired head and name entries stay in the arena this is an allocation count, and
it pins that no entry was appended twice. Raw ids are not part of the expected
output: those ids follow from the head/name allocation and are not an invariant.

Beyond the expectations, the module was compared against `logos/parser.py` over
26 sources: every form's depth, path and kind, and every error's path, line,
column and message, are identical (121 form lines, plus the error cases). The
comparison was a throwaway harness, not a committed test, because there is no
`logosc parse` verb to diff against.

## Before this module existed

`python3 -m logos test src/logosc/tree_test.logos --opt -O0 --opt -O2` then (the
nine cases in the file at the time) failed with `0 passed, 9 failed`; every case
reported `E0005 tree-test/1: unknown module 'tree'` at both levels, because `use
tree` had no `tree.logos` beside it. After the module:
`9 passed, 0 failed, 0 leaked`.
