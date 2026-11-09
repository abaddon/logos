# `src/logosc/resolve.logos` — the resolver

The Logos port of `logos/resolve.py`: one parsed file becomes a module, its
`(use …)` forms are loaded and merged, and every name that means two things is
refused. Task 1 covered one file and its names; Task 2 adds imports, cycles,
merge collisions, the loader and the file origins in the module registry.

Read `lex.md` and `tree.md` first. The resolver reads the arena `tree-parse`
built, and it reads imported files by lexing and parsing their source into a
fresh arena of the same shape.

## API

```logos
(fn resolve-file resolve-error ((nodes (ref (vec node)))
                                (ntexts (ref (vec :str)))
                                (path :str)))

(fn resolve-ok :bool ((e resolve-error)))
(fn resolve-pass resolve-error ())
(fn resolve-fail resolve-error ((code :i64) (path :str) (message :str)))
(fn resolve-code :str ((code :i64)))
```

`resolve-file` is the entry point. `nodes` and `ntexts` are the caller's arena
for the root file; it does not free them. `path` is the root file's own path,
used for two things: the asking directory of the root's imports, and the module
registry's file origin for the root. A caller with no source file passes `""`;
the loader then looks for siblings in the current directory, and the root's
registry entry has no file origin.

The function allocates six small tables, frees all six on every return, and
hands back a value rather than raising: one failure per run, the first one, as
the Python pass does. Imported files are read, lexed and parsed inside the
call; their arenas are freed before the imported resolver call returns, and
their strings are process-lifetime views like every other `:str`.

## The result

```logos
(type resolve-error
  (struct (failed :bool) (code :i64) (path :str) (message :str)))
```

The struct mirrors `lex-error` and `tree-error`. `code` is the numeric tail of
the diagnostic: `1` is `E0001` (an imported file the lexer or parser refused),
`2` is `E0002`, `3` is `E0003`, `4` is `E0004` and `5` is `E0005`.
`resolve-code` spells them by prefixing `E000`.

`path` is the **node path** the diagnostic is about, never a line and column:
`m/f`, `m/test/t`, `m/0`, `a/b`, `b/0`, `dup`. It is empty only for a root
file with no `(mod ...)` form and for an imported file that would not lex or
parse; the driver prints the source path in the first case (see `main.md`).

## The module form

`resolve-mod-form` takes the **first** top-level form whose kind is `mod`,
whether or not it carries a name. This is not `tree-module`: that function only
finds a named module, because it needs a path prefix; the resolver must find a
nameless `(mod)` in order to report it.

| input | code | path | message |
|---|---|---|---|
| no `mod` form | `E0002` | `""` | `missing (mod ...) form` |
| `(mod)` | `E0002` | the form's path | `mod needs a name` |
| a second `(mod n)` | `E0003` | the second form's path | `duplicate module 'n'` |
| a second `(mod)` | `E0002` | the second form's path | `mod needs a name` |

For an imported file the name must be the one `(use name)` asked for. If the
file has no `mod` form the error is `E0002 module '<name>' has no (mod ...)
form` at the `use` node; if it declares another name it is `E0005 module '<name>'
declares itself '<declared>'` at the `use` node.

## Module origins and the registry

A module name is an address and has exactly one file. The registry
(`resolve-mod`: name, file, definition range) records the file that answered
each name. A second file claiming a name that is already owned is `E0003` at the
second file's `mod` form:

```text
duplicate module 'dup': src/logosc/fixtures/origins/left/dup.logos and src/logosc/fixtures/origins/right/dup.logos
```

The comparison is byte equality on the two paths, not the resolved inode: the
loader constructs every sibling path from the root's spelling, so one file
reached twice by the same spelling compares equal. A name whose recorded origin
is `""` (an in-memory root) is unset and accepts its first real file.

The registry is **separate** from the definition namespace: `(mod m)` with
`(type m …)` is legal, as it is in Python, because one is a module name and the
other a definition name.

## The top-level vocabulary

Every top-level form must be one of `mod`, `use`, `fn`, `type`, `extern`,
`test` or `expect-error`. `expect-error` is a harness directive and is skipped.
Any other kind is `E0002 unknown node '<kind>'` at that form's path; a bare list
has no kind, so its message is `unknown node ''`.

The resolver does not descend into a `fn` or `test` body. A `(println 1)` inside
a function is the checker's business, not a module-level form.

## Names

`fn`, `type` and `extern fn` share one namespace, because all three insert
their bare name into a path: `math/add` is one address whether it holds a
function, a type or a C declaration. `test` has its own, because its path
segment is `test/<name>`: `(fn add …)` and `(test add …)` coexist, as
`math/add` and `math/test/add`.

The name is the tree's `name` field, so it follows the same rule as
`nodes.Node.name`: an atom that does not start with `:`, and for `extern` the
third item after the `fn` marker. A form with no name in that sense is refused
at its own path:

| form | code | message |
|---|---|---|
| `(fn …)` with no name | `E0002` | `fn needs a name` |
| `(type …)` with no name | `E0002` | `type needs a name` |
| `(test …)` with no name | `E0002` | `test needs a name` |
| `(extern …)` not spelled `(extern fn name …)` | `E0002` | `extern needs (extern fn name :ret ((p :type) ...))` |

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

## `use`

`(use name)` takes exactly one atom argument. A `use` form pushes its arguments
as children, so the check is: exactly one child, and that child is an `ATOM`
token. `(use)`, `(use a b)` and `(use 1)` are all `E0002 use takes one module
name` at the `use` node. Names are atoms; a name may contain `/`, which is how
an import reaches a file in a subdirectory (see the loader).

## Imports and the loader

`(use name)` asks the loader for `<dir>/<name>.logos`, where `<dir>` is the
directory of the file that asked. The path is built by string work:
`resolve-dir` finds the final `/`, and `resolve-sibling` appends `/<name>.logos`
(or `<name>.logos` when there is no directory). Because the name is an atom and
atoms may contain `/`, `(use left/left)` reads `left/left.logos` and puts the
imported module's own imports in the `left` directory.

The loader's answer is cached once per **(name, asking directory)**, keyed by
`dir + "\0" + name`. A diamond — `left` and `right` both `(use base)` in one
directory — loads `base.logos` once and both imports share its one module
record. Two directories asking for one name each load their own file: the
`origins` fixture's `left` and `right` reach `left/dup.logos` and
`right/dup.logos`, and the second claim is the `E0003` above. Caching by name
alone would silently reuse the first answer and hide that collision.

A name no file answers is `E0005 unknown module '<name>'` at the `use` node. The
existence probe is a shortcut, and it is deliberate:

> Logos has no `stat` form. `(read-file path)` panics `R0007` on a missing file,
> which cannot become a resolver diagnostic, and this wave may not change the
> Python compiler or its runtime. The loader therefore asks the POSIX `test`
> program: `(run "test" (["-f", path]))`, and treats status 0 as "a regular file
> answers this name". The cost is one child process per uncached import and a
> dependency on `test` being on `PATH`; neither is on the gen2 gate's path,
> which formats sources and never resolves imports.

The loaded file is read with `read-file`, lexed with `(lex …)` and parsed with
`tree-parse` into fresh arenas, then resolved recursively under the expected
name. A lexer or parser failure in an imported file is `E0001` with the
diagnostic's message (the struct has no line/column field for another file);
the common case is `E0002`/`E0005` above.

The loaded module's **own** definitions are what merge into the asker. A
module's imported names are visible inside it but are not part of its range, so
imports are not transitive: `a` sees `b`'s definitions, not the ones `c`
contributed to `b`. The `nontrans` fixture pins this — a `g` defined in `base`
and imported by `mid` does not collide with `g` in the root.

## Cycles

A `use` of a name already on the active stack is `E0004` at the `use` node. The
message is the chain from the name's **first** appearance on the stack to the
repeat, not the whole stack:

```text
circular import: a -> b -> a
circular import: b -> c -> b
circular import: self -> self
```

The stack holds module names, and a depth counter marks the live prefix; the
resolver never truncates the backing vector.

## Merge collisions

The asker's visible definition table is a vector of `resolve-def` records
(name, path, own flag) plus its tests table and the names it has already
imported. A `use` first checks the imported-name list (a repeated `(use b)` is
one import), then the cycle stack, then the `(name, directory)` cache, then
loads and merges. The merge copies the imported module's own definitions in
source order. A name already present is `E0003` at the `use` node, naming the
path already owned and the path the import brings:

```text
E0003 merge-local/1: duplicate definition 'f': merge-local/f and other/f
```

When the import comes first and the file defines the name later, the duplicate
is the definition, so the diagnostic points at it and the message reverses:

```text
E0003 merge-imported/f: duplicate definition 'f': other/f and merge-imported/f
```

The order is Python's: the name already owned comes first, the second
declaration second; the path is whichever form introduced the second copy.

## Tables and §D8

The resolver's tables are parallel vectors, not the W3 map, and that is a
deliberate exception with a concrete blocker:

- The definition table is per module and is rebuilt on every recursive
  `resolve-module` call; it is local to that call and freed on return. The
  module table is a `(vec resolve-mod)` of structs; the definition table is a
  `(vec resolve-def)` of structs; the test table is two parallel `(vec :str)`.
  Lookup is a linear scan (`resolve-index`, `resolve-def-find`,
  `resolve-mod-find`).
- §D8 says every named table uses the `src/std/map.logos` map. The map is a
  stdlib module, but `src/logosc/resolve.logos` cannot import it in this tree:
  the Python test harness resolves a test file's `use` forms **beside the
  asking file** (§D6's single-file rule). `(use map)` from
  `src/logosc/resolve.logos` would look for `src/logosc/map.logos`; the map is
  in `src/std`, and `python3 -m logos test src/logosc/resolve_test.logos` would
  fail to build before any test runs. Widening gen2's build set does not help
  here, because `run_test` hands `checked_program` one root, not a build set.
  The three escapes are all worse: a std search path violates §D6's "no hidden
  lookup", a second map implementation in the resolver duplicates the thing
  §D8 says is singular, and changing the frozen Python harness is outside this
  wave. So the resolver keeps linear scans; the build set is still widened (see
  below) so gen2 can use the map as soon as the harness can hand it a build
  set or the compiler's modules move beside the stdlib. The merge cost is
  small — a module has tens of definitions — and the scan is measured by the
  `(leaks 0)` suite, not assumed.

`resolve-file` creates and frees six tables:

| vector | holds |
|---|---|
| `all` | `resolve-def` records: every module's own definitions, concatenated |
| `mods` | `resolve-mod` records: module name, file, own-definition range |
| `active` | the module-name stack |
| `depth` | the live length of `active` |
| `asked-keys` | `dir + "\0" + name` for every loaded import |
| `asked-vals` | the module index each key was answered with |

Each `resolve-module` call adds four more locals — the visible `resolve-def`
table, `tests`, `test-paths` and `imported` — and frees them on every return.

## Flow

```text
resolve-file
  resolve-check
    resolve-module              find the mod form; missing/mismatched name
      resolve-named             the mod's name
        resolve-match           expected name vs declared
          resolve-claim         the module registry and its file origin
            resolve-open        push the module record; push the active name
              resolve-build     walk the top-level chain
                resolve-one     skip the mod form; dispatch
                  resolve-form      fn / type / extern / test / unknown
                  resolve-import    use: validate, cycle, cache, load, merge
                    resolve-load      read, lex, tree-parse, recursive module
                      resolve-merge   copy own definitions; collisions
```

Each step returns `resolve-error`; loops stop as soon as `resolve-ok` is false,
so the first failure is the one reported and no later form is examined. Every
diagnostic's path comes from the form it refuses, not from the file.

## Build set

`gen2` is built from `src/logosc/*.logos` **and** `src/std/map.logos` and
`src/std/str.logos` — not the whole `src/std` directory. The stdlib's `_test`
files carry `(test …)` forms and are not modules gen2 needs. `tools/selfhost.sh`
uses the same set.

The fixtures live under `src/logosc/fixtures/`, which is outside the
`src/logosc/*.logos` glob, so they are not roots of gen2; they are tracked files
and therefore appear in `tools/selfhost-manifest.txt` and are formatted by the
gate like every other source.

## What it does not do

- **No type checking.** `(fn f :nope () …)` resolves; the checker refuses the
  type.
- **No call checking.** A call to a name no import provides is the checker's
  `E0103`, not the resolver's.
- **No transitive imports.** A module sees the definitions of the modules it
  names, not the ones they name.
- **No file-name rule.** The resolver never compares a file name to a module
  name; mapping a name to a file belongs to the loader.
- **No output.** It returns a value; `main` prints it.

## Tests

`src/logosc/resolve_test.logos` has 31 cases, each run at `-O0` and `-O2` with
`(leaks 0)`:

1. `module-alone` — `(mod a)` resolves with no output.
2. `definitions-ok` — a type, a function, a test and an extern coexist.
3. `duplicate-fn` — the second `fn` is `E0003` at `m/f`.
4. `duplicate-type` — the second `type` is `E0003` at `m/p`.
5. `fn-type-collision` — `type p` then `fn p` is `E0003` at `m/p`.
6. `duplicate-test` — the second test is `E0003` at `m/test/t`.
7. `extern-fn-collision` — `fn get` then `extern fn get` is `E0003`.
8. `second-module` — `(mod a)(mod b)` is `E0003 duplicate module 'b'`.
9. `unknown-node` — `(println 1)` is `E0002 unknown node 'println'`.
10. `missing-module` — a file with no `mod` is `E0002` at the empty path.
11. `nameless-module` — `(mod)` is `E0002 mod needs a name`.
12. `extern-spelling` — `(extern get …)` is `E0002` with the full spelling.
13. `body-ignored` — a `fn` body is not examined.
14. `use-no-argument` — `(use)` is `E0002 use takes one module name`.
15. `use-two-arguments` — `(use a b)` is the same.
16. `use-number` — `(use 1)` is the same.
17. `nameless-fn` — `(fn)` is `E0002 fn needs a name`.
18. `nameless-type` — `(type (struct))` is `E0002 type needs a name`.
19. `nameless-test` — `(test (expect …))` is `E0002 test needs a name`.
20. `duplicate-extern` — two `extern fn get` are `E0003`.
21. `import-two` — `two/a.logos` loads `two/b.logos`.
22. `import-diamond` — `left` and `right` share one `base`.
23. `import-not-transitive` — a name imported by an import is not visible.
24. `import-self` — `(mod self)(use self)` is `E0004 self -> self`.
25. `import-cycle` — `a -> b -> a` at `b/0`.
26. `unknown-module` — a `use` with no file is `E0005`.
27. `wrong-module-name` — a file declaring another name is `E0005`.
28. `merge-local-first` — a local `f` then `(use other)` names both paths.
29. `merge-import-first` — `(use other)` then a local `f` names both paths.
30. `merge-kind-order` — with two collisions, the type is reported before the
    function, which is Python's `_merge` order (types, fns, externs).
31. `duplicate-module-file` — two directories' `dup.logos` files are `E0003`
    with both file origins.

The suite is `python3 -m logos test src/logosc/resolve_test.logos --opt -O0
--opt -O2`, run from the repository root (the fixture paths are relative to
it). The whole front-end suite is `python3 -m logos test src/logosc --opt -O0
--opt -O2`.

## Parity

`gen2 resolve` and the Python compiler agree on code, path and message for
every resolver-owned fixture:

| fixture | diagnostic |
|---|---|
| `two/a.logos` | exit 0 |
| `diamond/root.logos` | exit 0 |
| `nontrans/root.logos` | exit 0 |
| `self/self.logos` | `self/0: E0004: circular import: self -> self` |
| `cycle/a.logos` | `b/0: E0004: circular import: a -> b -> a` |
| `missing/root.logos` | `root/0: E0005: unknown module 'nope'` |
| `wrong/root.logos` | `root/0: E0005: module 'wrong' declares itself 'other'` |
| `merge/local.logos` | `merge-local/1: E0003: duplicate definition 'f': merge-local/f and other/f` |
| `merge/imported.logos` | `merge-imported/f: E0003: duplicate definition 'f': other/f and merge-imported/f` |
| `merge/cross.logos` | `merge-cross/2: E0003: duplicate definition 'b': merge-cross/b and cross-other/b` |
| `origins/root.logos` | `dup: E0003: duplicate module 'dup': …/left/dup.logos and …/right/dup.logos` |

The one resolver-owned negative corpus case remains `tests/parse/unknown-node`
(`E0002 unknown node 'wat'`). The six regress `.expect` cases with codes E0002
or E0003 are checker diagnostics — allocation invariants, a recursive enum,
reserved names — and the resolver accepts them; the wave's negative corpus for
this pass is the fixture table above (Task 3 promotes them to `tests/parse/`).
