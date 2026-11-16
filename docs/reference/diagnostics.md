# Diagnostics reference

Every way `logosc` can fail, and how to read it. One diagnostic per run: the
compiler stops at the first failure and prints exactly one line to stderr.
There are no warnings — every code below is fatal for the command that produced
it.

- Command line, streams and exit codes: [`cli.md`](cli.md).
- What the language accepts: [`../LOGOS.md`](../LOGOS.md).
- The codes are also machine-readable: `logosc guide --json | jq .codes`.

---

## The five shapes

The shape tells you which stage refused, and therefore how much of the file the
compiler actually understood.

| Stage | Shape | Measured example | Exit |
|---|---|---|---|
| lexer | `<file>:<line>:<col>: E0006: <message>` | `unterminated.logos:4:12: E0006: unterminated string` | 2 |
| parser | `<file>:<line>:<col>: E0001: <message>` | `bad.logos:2:1: E0001: unbalanced '('` | 2 |
| resolver | `<node-path>: <CODE>: <message>`, or `<file>:<line>:<col>: <CODE>: …` for an imported file that would not parse | `b/0: E0004: circular import: a -> b -> a` | 2 |
| checker / lowering / emit | `<node-path>: <CODE>: <message>`, or `<module-path>: <CODE>: <message>` | `m/main/2/0: E0100: '+' needs numbers, found :str` | 2 |
| environment | `logos: <what failed>: <detail>` — **no code** | `logos: runtime not found: logos/runtime/rt.c` | 1 |
| `fmt` / `show` source errors | `<file>:<line>:<col>: <CODE>: <message>` — position **first**, then code | `bad.logos:2:1: E0001: unbalanced '('` | 1 |

Two differences worth internalising:

- **`fmt` and `show` put the position first and exit 1**; every other verb puts
  the node path first and exits 2. That is the verb's own contract, not a bug.
- **Environment failures carry no code**, so do not expect one. They are the
  five `logos: …` lines: a missing file, an unwritable file, a missing runtime,
  a clang failure, and an unwritable IR path. Match on the text prefix
  `logos: ` and the exit status `1`.

## Node paths

A node path locates one form in one file: `mod/function/child/child`. The first
segment is the module name from `(mod name)`; then the function; then each
nested form by its **0-based index among its parent's children**, where index 0
is the head (the name or the operator) and 1 is the next element.

```text
(mod t)                       ; t
(fn main :void ()             ; t/main       (0 = main, 1 = :void)
  (println (+ 1 "x")))        ; t/main/2 = (println …), t/main/2/0 = (+ 1 "x")
```

(The `;` marks in that sketch are annotations. Logos has no comments — writing
one is `E0001`.)

The measured diagnostic for that file is `t/main/2/0: E0100: …` — "inside
`main`, the third child, its head". Paths are **positional and stable**: an
edit in another function does not renumber them, which is why they are a safe
addressing scheme for tooling. `logosc show FILE PATH` prints exactly the node
a path names.

A token can be addressed too: the return type is `t/main/1`.

## Codes

Grouped by prefix; the group is the subsystem that owns the rule. The "meaning"
column is the one `guide --json` publishes; the "measured message" column shows
the sentence the compiler actually printed for a probe during this audit — the
message text is **best-effort**, the code is the contract.

### `E00xx` — lexical, syntax, names, definitions

| Code | Meaning | Measured message |
|---|---|---|
| `E0001` | unbalanced parentheses | `unbalanced '('` — `fmt` reports it with a position and exits 1 |
| `E0002` | unknown node | a head that is not a form where the resolver or the lowering expected one |
| `E0003` | duplicate definition | `duplicate definition 'main'` — names are **global across the whole program** (gap A1); also a definition colliding with a reserved form |
| `E0004` | circular import | `circular import: a -> b -> a` |
| `E0005` | name not found | `unknown module 'map'` — outside a checkout, `(use map)` fails here |
| `E0006` | lexical error | `unterminated string` |

### `E01xx` — types and call rules

| Code | Meaning | Measured message |
|---|---|---|
| `E0100` | type mismatch | `'+' needs numbers, found :str`; also `cannot infer the result type of 'ok': annotate the binding or the return type` and `function 'main' returns (res :i64 e), found :i64` |
| `E0101` | unknown type | a type name that is not declared and not primitive |
| `E0102` | wrong arity | `function 'f' takes 1 argument, got 2` |
| `E0103` | unknown function | `unknown function 'nope'`; also `no 'main' function to build` when a build set has no entry point |
| `E0104` | not mutable | assigning to, or taking `(ref …)` of, a `let` binding |
| `E0105` | missing return | `function 'f' must return :i64 but a path falls off the end` |
| `E0106` | integer literal out of range | `literal 99999999999999999999 does not fit :i64`. Note: an **integer** literal out of range is refused; a **float** literal with no finite value is accepted and becomes `inf` (gap A3, measured) |
| `E0107` | unused binding | `unused binding 'x'` — **an error, not a warning**: a binding nobody reads fails the build |
| `E0108` | the entry point is not callable | `the entry point is not callable` — raised on a call to `main` from a body, not by `main`'s own signature |

### `E02xx` — aggregates

| Code | Meaning | Measured message |
|---|---|---|
| `E0200` | unknown field | `struct 'p' has no field 'y'` |
| `E0201` | field type mismatch | a value of the wrong type for a field |

### `E03xx` — ownership and moves

| Code | Meaning | Measured message |
|---|---|---|
| `E0300` | use after move | `use after move of 'v'` |
| `E0301` | free of a non-owning pointer | `(free p)` where `p` is not an `(own T)` |
| `E0302` | move out of an immutable binding | moving from a `let` binding — it must be `letmut` |
| `E0303` | move of a binding declared outside a loop | moving or freeing, inside a loop, a binding declared before it |
| `E0304` | ref argument is not a mutable binding | `(ref x)` where `x` is a `let` |
| `E0305` | ref escapes the call | storing or returning a `(ref …)` past its call |

### `E04xx` — indexing and strings

| Code | Meaning | Measured message |
|---|---|---|
| `E0400` | index type mismatch | an index that is not `:i64` |
| `E0401` | string not a str | `'str-len' takes a :str, found :i64` |
| `E0402` | vector value not copyable | reading a vector out of a place: a field, an element, a dereference |

### `E05xx` — generics and closures

| Code | Meaning | Measured message |
|---|---|---|
| `E0500` | instantiation limit reached | a generic expanded too many times |
| `E0501` | unbound type variable | a type variable no argument binds |
| `E0502` | closure escapes its function | a capturing closure crossing a call boundary — its environment lives in the creating frame |

### `E06xx` — results, optionals, matching

| Code | Meaning | Measured message |
|---|---|---|
| `E0600` | non-exhaustive match | `this match on e does not handle 'b'` |
| `E0601` | try type mismatch | `cannot 'try' a result whose error is e: function 'h' returns (res :i64 f)` |
| `E0602` | unhandled result | `the result of 'x' is never handled: match it or 'try' it` |

### `E07xx` — concurrency

| Code | Meaning | Measured message |
|---|---|---|
| `E0700` | shared state not marked | a value crossing a thread boundary without `(shared …)` |

### `R0xxx` — run time

Panics in a compiled program. They are not compiler diagnostics: they print a
code and a node path at run time and exit non-zero.

| Code | Meaning | Notes |
|---|---|---|
| `R0001` | division by zero | |
| `R0002` | double free | runtime name only; the ownership rules refuse the programs that could produce it. Release builds do not quarantine, so this is defence in depth |
| `R0003` | failed runtime check | |
| `R0004` | free of an unknown address | runtime name only |
| `R0005` | thread operation failed | |
| `R0006` | a program could not be started | from `(run …)` |
| `R0007` | could not read a file | from `(read-file …)` / `(read-all)` — this one **is** reachable from source |

### `E0000`

Not in the published table: a lowering refusal with no code of its own renders
as `E0000`. The reachable case is `build --test NAME` naming a test the file
does not define:

```text
docs/manual/01-values-and-literals.logos: E0000: no test named 'literals-and-arithmetic'
```

Treat any `E0000` as "this refusal has no code"; report it, because the code
table is meant to be exhaustive.

## Reading a diagnostic in four steps

1. **Shape → stage.** A `logos: ` prefix means the environment, exit 1: check
   the path, the working directory, the runtime and clang before touching the
   source. A `file:line:col` prefix means the file did not parse. A node path
   means the file parsed and the checker refused it.
2. **Code → subsystem.** `E0[1-7]xx` groups by rule family (see the tables
   above); `guide --json` holds the same code → meaning map for tooling.
3. **Node path → the exact form.** `logosc show FILE <path>` prints the node
   the compiler refused. `logosc show FILE <parent>` prints the enclosing form
   when the offending node is a token.
4. **Exit status → retry policy.** `2` = fix the source or the command; `1` =
   fix the environment. See [`cli.md`](cli.md#global-behaviour).

## Worked example, three shapes

```sh
$ printf '(mod t)\n(fn main :void ()\n  (println (+ 1 "x")))\n' > t.logos
$ logosc build t.logos
t/main/2/0: E0100: '+' needs numbers, found :str     # node path, checker, exit 2

$ printf '(mod t)\n(fn main :void ( (println 1))\n' > u.logos
$ logosc build u.logos
u.logos:2:1: E0001: unbalanced '('                    # position, parser, exit 2

$ cd /tmp && logosc build u.logos
u.logos:2:1: E0001: unbalanced '('                    # position, parser, exit 2
```

The compiler resolves its runtime and standard library from its own
installation, so the same source fails the same way wherever it is run.
