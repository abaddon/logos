# W6 — the checker, in Logos, in three pull requests

Wave W6 of `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md`. The
largest wave: `logos/check.py` is 5,784 lines and `logos/types.py` is 641. The
design splits it into three pull requests. Each PR is shippable on its own: it
adds a pass, extends `gen2 check`, and extends the parity list by exactly the
fixtures it can decide.

Read with `logos/types.py` and `logos/check.py` as the specification, `src/std/`
for the house style (map, string tools, io, the `.md` beside each source), and
`src/logosc/resolve.logos` for the shape a port of a big pass takes.

## The honest mechanism: a coverage list

A partial checker accepts what Python rejects. That is fine as long as the
repository says so. Each PR adds fixtures to `tools/selfhost-check.txt`, one path
per line, and `tools/selfhost.sh` gains a phase that runs `gen2 check` over that
list and compares the code with the `.expect` beside each fixture. The list is
floor-guarded, so a pruned list fails instead of passing over nothing.

The wave is done when the list is every negative fixture in the corpus and
`gen2 check` agrees with Python on all of them.

## Shape

A type is an arena node, not a Python object:

```
tags   (vec :i64)   one per type node: prim, ptr, own, arr, vec, ref, res, opt,
                    fn, shared, chan, atomic, struct, enum, var
names  (vec :str)   a primitive's spelling, a declaration's name and owner, a var's name
elem   (vec :i64)   the first child type id, -1 when none
extra  (vec :i64)   the second child (Arr length, Fn arity, Res error, …)
```

`parse-type` reads the tree node id and the module's declaration table and
returns a type id. `compatible` compares two ids. `substitute` and `typevars`
walk the arena. Every function takes the arenas by `(ref …)`.

The checker's environment is parallel vectors as well: name, type id, mutable,
moved, used, scope depth. The map answers lookups.

## Diagnostics

Every failure is the same struct the resolver and the lexer use: `failed`,
`code`, `path`, `message`. `gen2 check <file>` prints `<path>: <CODE>: <message>`
and exits 2, or prints nothing and exits 0. One code per run, the first failure,
as Python reports.

## Global constraints

- `git commit -s`; one logical commit per step; six gates green at the end of
  each PR.
- `src/logosc` cases at both levels with `(leaks 0)`.
- A new tracked `.logos` file means a regenerated manifest.
- The Python compiler may change only to fix a defect the port proves, and then
  with a regress case.

## PR A — types and declarations

- [ ] A1 `src/logosc/types.logos`: the fifteen type tags, `parse-type`,
      `compatible`, `substitute`, `typevars`, `has-typevar`, and the spelling
      rules (`mangle-type`) that the IR and `show` use. Parity: a table of type
      spellings parsed by Python and by gen2, compared as text.
- [ ] A2 `src/logosc/check.logos` declarations: `fn`/`extern`/`type` signatures,
      struct fields (no vector field, no enum field with invariants), enum
      variants and `enum-contains-itself`, `reserved-name`, the visibility rules,
      generic instantiation with a limit, and the E0100–E0108 codes they own.
      `gen2 check` lands here.
- [ ] A3 `tools/selfhost.sh` gains the `gen2 check` phase and
      `tools/selfhost-check.txt` with the fixtures A1/A2 decide.

## PR B — statements, expressions, calls

- [ ] B1 scalars: literals, arithmetic, shifts, casts, comparisons, `let`/`letmut`/`set`.
- [ ] B2 control flow: `if`, `while`, `match` with exhaustiveness, `ret`, blocks.
- [ ] B3 calls: arity, argument types, the entry point rule (E0108), `print`/`println`,
      extern calls across the C boundary, and the string/vector/fixed-array forms.
- [ ] B4 the fixtures B1–B3 decide, added to the parity list.

## PR C — ownership, containers, results, threads

- [ ] C1 moves and frees: E0300–E0303, the leak-balance rule, `free` of a
      non-owning pointer, a move out of a loop; plus E0005 unknown name (which
      B3's two E0107 suppressions wait on) and narrowing the move-only E0107
      suppression to the shape Python's E0302 actually decides.
- [x] C1b the resolver's memory: `resolve` grew quadratically in top-level
      definitions because `tree-path` was called once per definition and
      re-walked every earlier sibling's whole subtree. `resolve-build` now
      computes each top-level form's path once, in its own sibling walk, and
      passes it down, so peak RSS is linear: 500 → 2.4 MB, 1,000 → 3.4 MB,
      2,000 → 4.7 MB, 4,000 → 7.7 MB, 8,000 → 14.2 MB (×1.35–1.86 per
      doubling; before: 57 / 222 / 880 / 3,510 MB, with 6,300 killed at the
      4 GB cap). Pinned by the generated case `build/c1b/gen.py` +
      `build/c1b/rss.sh`, two `resolve_test` cases, and the table in
      `check.md`.
- [ ] C2 `(ref T)`: E0304/E0305 at every escape site.
- [ ] C3 results and optionals: `res`/`opt`, `try`, E0600–E0602. **Type the containers.**
      `some`/`ok`/`err`/`none` currently yield an unknown type, so no fit gate fires and four
      accepted ref escapes survive (found by the C2 re-review, all pre-existing):
      `(some (if b v v))` returned (Python E0305 at `f/2/2/0`; the carries-a-ref walk recurses
      only into `some`/`ok`/`err`, not `if`/`match`), `(err (bad v))` with a ref-carrying enum
      payload (Python E0305 `carrying it in enum 'e'`), `(some (some v))` into
      `(opt (opt (ptr …)))` (Python E0100), and the `E0107` line that shadows the escape when the
      binding is unused. C3 is not done until the walk covers `if`/`match` and the containers have
      real types; an accepted ref escape outranks the task boundary, as C2 established.
- [ ] C4 closures, threads, mutexes, atomics, channels: E0502, E0700.
- [ ] C5 the rest of the negative corpus, and the wave's PR with all fixtures in
      the parity list.

## Review focus

1. The parity list only names fixtures the pass can decide; a pass that silently
   accepts is worse than no pass.
2. Every diagnostic the port emits carries the same code and the same node path
   as Python's, checked fixture by fixture, not by eye.
3. Arena types: `compatible` must be symmetric where Python's is, and must treat
   two declarations with one name from different modules as different.
4. The environment's move and used flags are restored through a branch, as
   Python's `snapshot`/`restore` do; a branch that leaks a flag is a bug the
   corpus will only sometimes catch.
5. The instantiation limit (E0500) still fires, and a program that hits it says
   the same thing.
