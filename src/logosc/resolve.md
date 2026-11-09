# `src/logosc/resolve.logos` — one file, its module and its names

The first half of the resolver: `logos/resolve.py`'s `_Resolver.module`,
`_claim`, `_build`, `_define`, `_define_extern`, `_define_test`,
`_duplicate`, `_module_form`, `_missing_module` and `_duplicate_module`, ported
to Logos. It answers three questions about one parsed file: does it declare a
module, what names do its top-level forms own, and does any name mean two
things. Imports, cycles and the merge of an imported definition belong to
Task 2; this module deliberately accepts `(use ...)` and does not follow it.

Read `tree.md` first. The resolver reads the arena `tree-parse` built and
touches nothing else.

## API

```logos
(fn resolve-file resolve-error ((nodes (ref (vec node)))
                                (ntexts (ref (vec :str)))))

(fn resolve-ok :bool ((e resolve-error)))
(fn resolve-pass resolve-error ())
(fn resolve-fail resolve-error ((code :i64) (path :str) (message :str)))
(fn resolve-code :str ((code :i64)))
```

`resolve-file` is the entry point. `nodes` and `ntexts` are the caller's
arena; it does not free them. It allocates five small tables, frees all five on
every return, and hands back a value rather than raising: one failure per run,
the first one, as the Python pass does.

## The result

```logos
(type resolve-error
  (struct (failed :bool) (code :i64) (path :str) (message :str)))
```

The struct mirrors `lex-error` and `tree-error`: `resolve-pass` is the whole
"no error" value, `resolve-ok` reads `failed`, and `resolve-fail` builds a
failure. `code` is the numeric tail of the diagnostic code: `2` is `E0002`,
`3` is `E0003`; `resolve-code` spells it `E0002`/`E0003` by prefixing
`E000`. Task 2 adds `4` and `5` on the same scale.

`path` is the **node path** the diagnostic is about, never a line and column:
`m/f`, `m/test/t`, `m/0`, `a/b`. It is empty only for the one diagnostic that
has no node behind it — a file with no `(mod ...)` at all. The driver prints
the source path in that case (see `main.md`).

## The module form

`_module_form` takes the **first** top-level form whose kind is `mod`, whether
or not it carries a name. This is not `tree-module`: that function only finds a
named module, because it needs a path prefix; the resolver must find a nameless
`(mod)` in order to report it.

| input | code | path | message |
|---|---|---|---|
| no `mod` form | `E0002` | `""` | `missing (mod ...) form` |
| `(mod)` | `E0002` | the form's path | `mod needs a name` |
| a second `(mod n)` | `E0003` | the second form's path | `duplicate module 'n'` |
| a second `(mod)` | `E0002` | the second form's path | `mod needs a name` |

Before its forms are walked, the module's own name is **claimed** in a registry
of module names. A name already in the registry is `E0003`
`duplicate module '<name>'` at the claiming form. One file claims once, so the
refusal cannot fire in Task 1; the registry is the seam Task 2 shares across an
import graph, where two files must not answer to one module name.

## The top-level vocabulary

Every top-level form must be one of `mod`, `use`, `fn`, `type`, `extern`,
`test` or `expect-error`. `use` and `expect-error` are accepted and ignored
here — `use` is Task 2's, and `expect-error` is a harness directive. Any other
kind is `E0002 unknown node '<kind>'` at that form's path; a bare list has no
kind, so its message is `unknown node ''`.

The resolver does not descend into a `fn` or `test` body. A `(println 1)`
inside a function is the checker's business, not a module-level form.

## Names

`fn`, `type` and `extern fn` share one namespace, because all three insert
their bare name into a path: `math/add` is one address whether it holds a
function, a type or a C declaration. `test` has its own, because its path
segment is `test/<name>`: `(fn add ...)` and `(test add ...)` coexist, as
`math/add` and `math/test/add`.

The name is the tree's `name` field, so it follows the same rule as
`nodes.Node.name`: an atom that does not start with `:`, and for `extern` the
third item after the `fn` marker. A form with no name in that sense is refused
at its own path:

| form | code | message |
|---|---|---|
| `(fn ...)` with no name | `E0002` | `fn needs a name` |
| `(type ...)` with no name | `E0002` | `type needs a name` |
| `(test ...)` with no name | `E0002` | `test needs a name` |
| `(extern ...)` not spelled `(extern fn name ...)` | `E0002` | `extern needs (extern fn name :ret ((p :type) ...))` |

A name already owned by the same namespace is `E0003` at the second
declaration. The message names both declarations when their node paths differ,
and is short when they do not:

```text
duplicate definition 'x': a/b and a/c
duplicate definition 'x'
```

Inside one file a repeated name has the same node path both times — the path
segment *is* the name — so a local duplicate is always the short form. The
both-path form exists for the import merge, where a local `m/f` and an imported
`other/f` are two different paths.

## Tables

The module model cannot hold containers, so the tables are parallel vectors
owned by `resolve-file`:

| vector | holds |
|---|---|
| `modules` | the module names claimed so far |
| `names` | one bare name per `fn`/`type`/`extern` definition |
| `paths` | the declaring node's path, parallel to `names` |
| `tests` | one bare name per `test` |
| `test-paths` | the declaring node's path, parallel to `tests` |

Lookup is a linear scan (`resolve-index`). A module has tens of top-level
definitions and Task 1 resolves one file, so the scan is cheaper than a hash
table's bookkeeping; the W3 map becomes worthwhile in Task 2, when imports
merge whole definition sets and a module's table can grow by another module's
count. The two namespaces stay two tables in either shape.

`resolve-file` creates all five with `(make (vec ...))` and frees every one
before it returns, including on the failure path — the vectors are the only
allocations this module owns, and `(leaks 0)` in the tests enforces it.

## Flow

```text
resolve-file
  resolve-check        find the mod form; missing mod
    resolve-declared   the mod's name; nameless mod
      resolve-claimed  claim the name, then walk the forms
        resolve-forms  loop over the top-level chain, stop at the first error
          resolve-one  skip the mod form; dispatch mod/use/expect-error
            resolve-form   fn / type / extern / test / unknown
              resolve-record   name or missing-name
                resolve-stored    duplicate or store
                  resolve-store
```

Each step returns `resolve-error`; `resolve-forms` stops as soon as
`resolve-ok` is false, so the first failure is the one reported and no later
form is examined. Every diagnostic's path comes from the form it refuses, not
from the file.

## What it does not do

- **No imports.** `(use name)` is accepted and skipped; unknown modules,
  cycles (`E0004`) and a module that declares another name (`E0005`) are Task 2.
- **No merge.** An imported definition colliding with a local one is also Task
  2's `E0003`.
- **No bodies.** Forms inside `fn` and `test` are the checker's.
- **No type checking.** `(fn f :nope () ...)` resolves; the checker refuses the
  type.
- **No file-name rule.** The resolver never compares a file name to a module
  name; mapping a name to a file belongs to the driver's loader.
- **No output.** It returns a value; `main` prints it.

## Tests

`src/logosc/resolve_test.logos` has thirteen cases, each run at `-O0` and
`-O2` with `(leaks 0)`:

1. `module-alone` — `(mod a)` resolves with no output.
2. `definitions-ok` — a type, a function, a test and an extern coexist; the
   function and the test share a name.
3. `duplicate-fn` — the second `fn` is `E0003` at `m/f`.
4. `duplicate-type` — the second `type` is `E0003` at `m/p`.
5. `fn-type-collision` — `type p` then `fn p` is `E0003` at `m/p`.
6. `duplicate-test` — the second test is `E0003` at `m/test/t`.
7. `extern-fn-collision` — `fn get` then `extern fn get` is `E0003` at
   `m/get`.
8. `second-module` — `(mod a)(mod b)` is `E0003` `duplicate module 'b'` at
   `a/b`.
9. `unknown-node` — `(println 1)` is `E0002 unknown node 'println'` at `m/0`.
10. `missing-module` — a file with no `mod` is `E0002` at the empty path.
11. `nameless-module` — `(mod)` is `E0002 mod needs a name` at path `0`
    (there is no module to prefix the path).
12. `extern-spelling` — `(extern get :i64 ())` is `E0002` with the full
    spelling message at `m/0`.
13. `body-ignored` — `(println 1)` inside a function resolves: the resolver
    does not descend.

The suite is `python3 -m logos test src/logosc/resolve_test.logos --opt -O0
--opt -O2`.

## Parity

The resolver-owned negative corpus case is `tests/parse/unknown-node.logos`:
`gen2 resolve` prints `m/0: E0002: unknown node 'wat'`, matching the Python
compiler's `E0002 m/0: unknown node 'wat'` in code, path and message.

Every `.expect` under `tests/regress` whose code is `E0002` or `E0003`
(`alloc-enum-in-struct`, `alloc-enum`, `alloc-fn`, `recursive-enum`,
`reserved-name`, `rt-definition`) is a **checker** diagnostic, not a resolver
one: allocation invariants, an enum that contains itself, and reserved names
are all raised by `logos/check.py`. `gen2 resolve` accepts all six files, so
those expectations cannot be met by this pass and are reported as a finding
for the checker task rather than papered over.
