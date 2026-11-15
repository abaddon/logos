# Module-qualified names, and a range check for float literals — design

Design document. 2026-11-15. Status: for approval.

This is the first item on the "not ready for others to adopt" list, plus the one
missing diagnostic on that list. It changes the language, so it comes before any
code.

## Intent

Two gaps, for different reasons.

**Names are global.** With `(use ra)`, a module sees `ra`'s types and functions
by bare name, so names must be unique across the whole program: two modules that
each declare a `point` are refused with `E0003: duplicate definition 'point':
qa/point and qb/point`. A dotted spelling like `ra.amake` is refused as
`E0103: unknown function 'ra.amake'`. Any program of size therefore has to
enforce a naming discipline by hand, which is a language constraint, not a
program's choice. This is the thing that makes Logos hard to adopt.

**A float literal with no finite value is accepted.** `(println 1e999)` builds,
runs, and prints `inf`. The integer half is already correct: `(println
99999999999999999999)` is refused with `E0106: literal 99999999999999999999 does
not fit :i64`. The float path skips the same check, so the same class of mistake
is caught for one type family and silently accepted for the other.

## Goals

1. A type or function may be named by its declaring module, `mod.name`, anywhere
   a bare name is legal today.
2. Two modules may declare the same name. Bare references stay legal while they
   are unambiguous, so every existing program keeps working unchanged.
3. A bare reference that two visible modules define is refused as ambiguous,
   naming both declarations.
4. The compiler's IR for every existing program is unchanged, byte for byte, so
   the 90-file IR parity list and both fixed-point units stay green with no
   fixture edits.
5. A numeric literal, integer or float, that has no finite value in its type is
   refused with a diagnostic that carries a code and a node path.

## Non-goals

- Renaming the compiler's own modules to collide. The port keeps its unique
  names; this feature is for programs that need collisions.
- Namespaces for stdlib modules (`std.str` as a namespace) beyond what falls out
  of the rule.
- `open`-style unqualified imports, or import aliases.
- Changing the mangling of a single-module unit: `%struct.point` stays
  unprefixed when there is one module, because 90 fixtures pin that text.
- A new code for the float case unless the existing one cannot carry it.

## Decisions

These are my calls, from the evidence in this document. Each is stated so it can
be rejected on its own.

**D1. The spelling is `mod.name`, with the dot inside the atom.** No lexer
change: `lex-atom-byte` (`src/logosc/lex.logos:160`) accepts every byte except
space, control, `(`, `)` and `"`, so `ra.amake` is already one token. The work is
in resolution, checking and lowering.

**D2. Qualification is a scope, not a rename.** A declaration's identity becomes
`(module, name)`. Two modules may both declare `point`; each is `ra.point` and
`rb.point`. This is the rule the lowerer's function map already uses
(`4d85171`), and it is what the type map `tnk/tnv/tnl` must adopt, since it is
still keyed by bare name.

**D3. Bare names keep working.** A bare name resolves to the single visible
declaration of that name, searched in the current module first and then its
imports, as today. Only a genuinely ambiguous bare name becomes an error, so the
309-case corpus and the compiler's own source compile unchanged.

**D4. `use` still governs visibility.** `ra.amake` requires `(use ra)` in the
referring module, the same way a bare `amake` does today. A qualified name is not
a way around the import graph, and it keeps one rule for what a module can see.

**D5. The ambiguity error reuses `E0003`, with a new message.** `E0003` is
already "duplicate definition" and the resolver already reports it for this same
situation, so the code is right; the text changes from "duplicate definition" to
naming both candidates and saying the fix, which is to qualify the use. The
declaration is no longer an error by itself, only the ambiguous use, so the
diagnostic moves from the declaration's path to the reference's.

**D6. Mangled symbols already qualify, and must keep doing so.** Functions are
`lg.<module>.<name>` (`4d85171`); structs are `%struct.<module>.<name>` when the
unit has more than one module. Nothing here changes that, and the single-module
case stays unprefixed so the fixtures hold.

**D7. The float range check joins the integer one.** `check.logos:2684` already
refuses an integer literal that does not fit its width. The same site must refuse
a float literal whose value is not finite, and a literal whose `:f32` value would
overflow to infinity. Reusing `E0106` means rewording its table entry from
"integer literal out of range" to "literal out of range", which regenerates
`docs/LOGOS.md`; that is a documentation diff, not a code change.

**D8. Both changes ship together, in separate commits.** One is a language
feature, the other a diagnostic. A builder-check found that they are not
independent after all: the only decimal-to-binary conversion in the tree is
`rt_parse_f64`, declared once in `lower.logos:15`, and declaring it again in
`check.logos` would create exactly the cross-module duplicate this design is
about. So the range check has to happen where that conversion is already
reachable, which is the lowerer, unless the answer to question 3 below is a
coarse textual test. The commits stay separate; the dependency is recorded
here rather than assumed away.

**D9. `m.name` is legal in every unit, including a single-module one.** Goal 1
says qualified works wherever a bare name works, and the reviewer is right that
the emission spelling and the reference spelling are different things: a
one-module program is emitted as `%struct.point` to keep 90 fixtures intact, but
`m.point` must still resolve. So resolution returns a `(module, name)` identity
and emission decides the spelling, rather than resolution looking up a qualified
key that does not exist in the single-module case.

**D10. A module may qualify its own declarations without `(use)` itself.** `use`
governs what a module can see of *other* modules; a module always sees its own.
`qa.point` inside `qa` is legal, and D4's rule applies only to foreign modules.

**D11. The reworded ambiguity message is scoped to cross-module collisions.** A
same-module duplicate cannot be fixed by qualifying, so it keeps the bare
`duplicate definition 'f'` text and its existing tests.

## Accepted cost: three pinned cases change meaning

`src/logosc/resolve_test.logos:276-292` pins the exact E0003 text and path for
three merge collisions, and none of the three fixtures ever references the
colliding name. Under D5 they become valid programs with no diagnostic at all.
That is the behaviour being removed, not a regression, so those three cases are
rewritten to reference the name and assert the ambiguity error at the *use*
rather than at the declaration. Acceptance 3 below is the corrected form: the
corpus is unchanged except where a case pins a rule this design replaces.

## What the builder decides

- Whether the qualified lookup lives in the resolver (as a symbol table keyed by
  `(module, name)`) or as a spelling rule in the checker. I lean to the resolver,
  because a qualified name is a name.
- How the type map is re-keyed without allocating a fresh string per lookup. The
  lowerer already builds `lg.<module>.<name>` symbols for functions, so the same
  composite key exists; a type could carry its declaring module's index instead
  of concatenating.
- Whether `E0106`'s message should name the type it did not fit, as the integer
  text does.
- Whether the ambiguity check needs a sweep for cost. A bare name lookup that
  scans every visible module per reference is quadratic over the corpus; the
  existing `vindex`-style tables suggest the fix.

## Evidence

Measured on `main` at `fe1764d`, this session:

| probe | result |
| --- | --- |
| `(ra.amake)` with `(use ra)` | `E0103: unknown function 'ra.amake'` |
| `(let p point …)` in a module that used `ra`, `ra` declaring `point` | accepted, printed `7` |
| `qb` and `qa` both declaring `point`, one unit | `E0003: duplicate definition 'point': qa/point and qb/point` |
| `(println 99999999999999999999)` | `E0106: literal 99999999999999999999 does not fit :i64` |
| `(println 1e999)` | accepted, prints `inf` |
| a dot inside an atom | legal at `lex-atom-byte`, so no lexer change |

## Decisions taken with the owner (2026-11-15)

**D13. Every declaration kind gets `(module, name)` identity: types, functions,
externs and tests.** One rule, no special cases. An extern is the realistic
collision (two modules both declaring libc's `close`), so exempting externs would
have left the common case broken while solving the rare one. `main` stays unique
and keeps its own duplicate check, because the entry point is not a name a module
owns.

Consequence to plan for: the lowerer keys externs by bare name in `enk`
(`lower.logos:920`, `lo-ext-id` at `557`, call sites at `1379`, `1788`, `2217`),
so duplicate externs collide silently today. Re-keying `enk` is part of this
change, not an afterthought.

**D14. The float range check is exact: refuse any literal that converts to
infinity, accept one that converts finite, even one ULP from the limit.** Given
that, the check cannot be a textual exponent test, and it cannot live only in the
lowerer either: `logosc check` does not lower, so a lowerer-only check makes
`check` accept what `build` refuses, which is a new defect in place of the old
one.

The shape I propose: a small shared module (say `src/logosc/lit.logos`) that
declares `rt_parse_f64` as its extern once and carries the predicate "this text
converts to a finite value in this type". `check` and `lower` both use it, so one
extern declaration exists in the unit and both verbs refuse the same literals.
If the builder finds that `check` cannot depend on an extern for a structural
reason, the fallback is an exact integer-arithmetic boundary test in Logos
(significand digits plus decimal exponent against the type's limit), and the
report must say which was chosen and why.

## Precedence: my call, because the owner skipped the question

D3 as first written said a bare name is "searched in the current module first
and then its imports", which is shadowing. Goal 3 said a bare reference that two
visible modules define is refused, which is not shadowing. They give opposite
answers for `fixtures/merge/local.logos`, which declares `f` and imports a
module that also declares `f`.

It matters more than the wording, because three passes already disagree about
order: the lowerer searches own-then-imports (`lo-fn-id`, `lower.logos:542`), the
checker scans `vindex` in imports-then-own order (`check.logos:1801`, first match
wins at `4911`), and the type map is last-write-wins (`lower.logos:760`). They
agree today only because duplicates are refused. Once duplicates are legal, a
bare `f` can check against the local signature and lower to the imported symbol.
That is a silent miscompile, and it is the real risk in this change, not the
type map alone.

**D12, my call: a module's own declaration wins over an import, and ambiguity
arises only between two imports.** Three reasons. It matches what a reader
expects, since the module wrote the name itself. It matches the lowerer's
existing own-then-imports search, so precedence needs no new mechanism in
lowering, only agreement in the checker. And it makes
`fixtures/merge/local.logos` a valid program, which is consistent with the three
merge fixtures becoming valid under D5.

The rule is then: own declaration, else exactly one import declaring it, else
`E0003`. All three passes state that order, and a test covers the case where the
local and imported signatures differ, because that is the shape that would
otherwise check one way and lower the other.

## Risks

- **The type map is the real work.** Allowing duplicate names forces `tnk/tnv/tnl`
  from name-keyed to identity-keyed. That residual was unreachable before because
  the checker refused duplicates; this feature makes it reachable, so it must be
  fixed in the same change or the compiler will mis-resolve a type.
- **Ambiguity has a performance shape.** A naive per-reference scan of visible
  modules is quadratic; the corpus is small enough to hide it and the compiler's
  own build is not.
- **The tightening is visible to users.** A program that today relies on a bare
  name resolving to the only declaration keeps working; one that relies on
  duplicates-as-error will see the error move from the declaration to the use.
- **Docs.** The spec, a manual chapter, `docs/LOGOS.md` (regenerated), and the
  stage-0 binary all move in the same pull requests.

## Acceptance

1. Two modules may each declare `point`, each usable through `(use …)` and a
   qualified name, in one binary, with the right layout for each.
2. A bare reference to such a name is refused with a code, a path and both
   candidates named.
3. Every corpus case passes, except the three merge-collision cases, which are
   rewritten from declaration-time to use-time because the rule they pin is the
   one this design replaces; the 90-file IR parity list is byte-identical with no
   fixture edits.
4. `(println 1e999)` is refused with `E0106` and a node path; `1e400` as `:f64`
   likewise; a large but finite literal is still accepted.
5. `bash tools/pr_gate.sh` is 6/6, the two fixed-point units are unchanged, and
   the stage-0 is rebuilt and byte-identical to its own output.
