# W5 — resolve, in Logos: names, scopes, duplicates, imports

Wave W5 of `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md`. The
resolver decides which file answers a module name, which names a module owns, and
which declarations collide. Its contract is exact: **the codes and paths the
negative corpus expects must come out of `gen2` unchanged**.

Read with `logos/resolve.py` (469 lines) as the specification and
`src/logosc/` for the house style: no comments, the contract in a `.md` beside
the source, containers by `(ref …)`, one flag-returning function per check.

## What is being ported

| Python | Job |
|---|---|
| `_Resolver.module` | one parsed file becomes a `Module`, or E0002/E0005 |
| `_claim` | a module name has exactly one file, or E0003 |
| `_build` | walk the file's forms, define or refuse each |
| `_import` | `(use name)`: load, refuse cycles (E0004) and unknown names (E0005) |
| `_merge` | an imported name colliding with a local one is E0003, naming both |
| `_define*` | `fn`, `type`, `extern fn`, `test`: a name, once |
| `_duplicate` | E0003, with both node paths when they differ |
| `_cycle` | the `a -> b -> a` spelling |

`E0007` (unused binding) is the checker's rule, not the resolver's: W6 owns it. W5
ends at "every name is owned by exactly one declaration".

## Shape (§D7)

The module model cannot hold vectors, so it is a set of parallel tables the caller
owns, keyed by the map from W3:

```
names   (vec :str)  one per definition
kinds   (vec :i64)  fn / type / extern / test
paths   (vec :str)  the declaring node's path
modules (vec :str)  one per module: its name
files   (vec :i64)  the module index that owns each name
```

Loading is file IO: `(use util)` reads `util.logos` beside the asking file. Path
joining is `src/std/str.logos` work. The loader reads each file once per
(name, asking directory), as Python does.

## Diagnose, do not raise

The resolver returns a value: `(struct (failed :bool) (code :i64) (path :str)
(message :str))`, the shape the lexer and tree already use. `main` prints
`<path>: <code>: <message>` and exits 2. One code per run, the first failure, as
the Python compiler reports.

## Global constraints

- One logical commit per step; `git commit -s`.
- `src/logosc` cases run at both levels with `(leaks 0)`.
- `tools/selfhost.sh` stays green: a new `.logos` file means a regenerated
  manifest, and the manifest count must equal `git ls-files '*.logos'`.
- The wave may not change the Python compiler except to fix a defect the port
  proves, and then only with a regress case.

## Task 1: one file, its module, its names

- [ ] `src/logosc/resolve.logos`: `resolve-file` over one parsed arena —
      `(mod …)` present (E0002), named, name required, and the module's own name
      claimed; every top-level form defines its name or is E0002 (`unknown node`);
      `fn`, `type`, `extern fn` and `test` each carry a name and a duplicate is
      E0003 with both paths when they differ.
- [ ] `gen2 resolve <file>` in `src/logosc/main.logos`: parse, resolve, print
      `<path>: E0003: …` and exit 2, or print nothing and exit 0.
- [ ] `src/logosc/resolve.md` and `resolve_test.logos`: a module alone; a
      duplicate `fn`; a `fn`/`type` collision; a duplicate `test`; an `extern`
      colliding with a `fn`; a second `(mod …)` in one file; a top-level
      `(println 1)`; a file with no `mod`.
- [ ] Parity: the corpus has exactly **one** resolver-owned negative case,
      `tests/parse/unknown-node` (`E0002 unknown node 'wat'`). The six regress
      cases that expect E0002 or E0003 are checker diagnostics (allocation
      invariants, a recursive enum, reserved names) and the resolver accepts
      them, so they are not this task's target. Task 3 adds the missing
      resolver fixtures.

## Task 2: imports and cycles

- [ ] `(use name)`: one atom argument; unknown module E0005 at the `use` node;
      a module that declares a different name E0005; a cycle E0004 spelled
      `a -> b -> a`; a merge collision E0003 naming both declarations.
- [ ] The loader: read `<name>.logos` beside the asking file, parse it, resolve
      it, and cache one answer per (name, asking directory).
- [ ] Tests: two-module import; diamond import (one file loaded twice, not a
      duplicate); self-import; two-cycle; missing file; module naming itself
      differently.
- [ ] Parity: the E0004/E0005 regress cases.

## Task 3: the wave's gate work

- [ ] Resolver-owned negative fixtures under `tests/parse/` with `.expect`
      codes, one per rule the resolver owns: no `(mod …)`, a nameless `mod`, a
      second `mod`, an unknown top-level node, a duplicate `fn`, a duplicate
      `test`, an `extern` collision, `(use)` with no name, `(use a b)`, an
      unknown module, a module that declares another name, a cycle, and a merge
      collision naming both sides. Each must fail under Python with the code the
      fixture claims, and `gen2 resolve` must print the same code at the same
      path.
- [ ] `tests/test_resolve_parity.py` (or house equivalent) that runs `gen2 resolve`
      over every fixture in that set and asserts code and path. Checker-owned
      cases are out of scope by construction: `gen2` stops at resolve.
- [ ] Manifest regenerated; `bash tools/selfhost.sh` still `0 differences`;
      `bash tools/pr_gate.sh` 6/6; PR; squash-merge with the admin bypass.

## Review focus

1. A duplicate through an import names both sides; a duplicate inside one module
   names neither, and the short form is the one that is actionable.
2. Diamond imports load once, and two directories asking for one name still get
   their own answer.
3. A cycle reports the closing chain, not the whole import stack.
4. The first failure wins and its path is the node's path, not the file's.
5. The module's own name is claimed in the module registry, which is **separate**
   from the definition namespace: `(mod m)` with `(type m …)` is legal, as it is
   in Python. Do not "fix" that into an error.
