# AGENTS.md

Logos is a prefix-form language built for AI readers, where every allocation,
fallible call and release is visible in the source. This repository holds
`logosc`, a compiler written in Logos that type-checks Logos and lowers it to
LLVM IR, plus the C runtime that clang links into a native x86_64 Linux binary.
The compiler is self-hosting: `src/logosc/*.logos` is the whole compiler, and
`bootstrap/logosc` is a stage-0 binary whose only job is to build it. Building
`gen2` with the stage-0 and `gen3` with `gen2` produces two byte-identical
binaries, and that equality is the claim the last gate measures.

Read `docs/LOGOS.md` first. It is the generated manual: a cheat sheet followed
by one executable chapter per feature, and it is the ground truth for what the
language accepts.

## Done means these six commands pass

Run them from the repository root, in this order:

```sh
make test
./tools/logosc.sh test tests
bash tools/accept.sh
./tools/logosc.sh guide --check
./tools/logosc.sh fmt $(git diff --name-only main...HEAD -- '*.logos')
bash tools/selfhost.sh
```

Before any of them, every commit on your branch must carry a `Signed-off-by`
trailer matching its author. `tools/pr_gate.sh` runs `bash tools/check_dco.sh`
first and stops if it fails. See `CONTRIBUTING.md`.

`bash tools/pr_gate.sh` runs exactly this list, prints PASS or FAIL for each
gate, and exits non-zero if any failed. Run it before you open a pull request.
Do not weaken a gate, skip a gate, or change its expected result to make a
change pass.

`tools/logosc.sh` is the compiler every gate tests: it checks
`bootstrap/logosc` against its recorded SHA-256, rebuilds `build/logosc` from
`src/` whenever the source is newer, and runs that. Never run
`bootstrap/logosc` as an oracle for a source change — it is the previous
compiler, so it would pass while the source is broken.

The last gate builds `gen2` from `src/logosc/*.logos` with the stage-0 binary,
builds `gen3` from the same sources with `gen2`, and requires the two binaries
to be byte-identical before it compares their IR. It then requires `gen2`'s
`fmt` to reproduce every tracked `.logos` file byte for byte, so the
self-hosting claim is measured on every pull request.

`make test` runs two things: the contract tests under `tests/` — the gate list
itself, the C runtime, and the self-hosting summary lines — and the compiler's
own suites (`body_test`, `check_test`, `resolve_test`) at `-O0` and `-O2`. The
Python implementation, its white-box tests and the suites that used it as a
differential oracle were deleted once the port matched it; do not reintroduce a
second compiler to test the first.

## A compiler change needs a regress case

A change to the compiler is not done until a case under `tests/regress/` fails
before the fix and passes after it. A positive case is `name.logos`; a negative
case is `name.logos` plus `name.expect` containing the expected diagnostic code
(for example `E0002`). Run `./tools/logosc.sh test tests --only regress` with
and without your fix and record both outcomes in the pull request.

Deleting, weakening, renaming away or otherwise neutering an existing regress
case is grounds for rejection. The corpus is the contract; do not edit it to
match a regression.

## Invariants that are not negotiable

- No accepted program may read freed or uninitialised memory.
- No accepted program may behave differently at `-O0` and `-O2`.
- No form the checker accepts may be unimplemented in the backend.
- Every diagnostic carries a code and a node path.

If a change makes one of these false, the change is wrong even if every test
passes. Add the test that would have caught it, then fix the compiler.

## A compiler change changes the bootstrap

Editing `src/logosc/*.logos` changes the compiler, so `bootstrap/logosc` no
longer reproduces it. Rebuild the stage-0 in the same pull request:

```sh
./tools/logosc.sh version                      # builds build/logosc from src/
cp build/logosc bootstrap/logosc
( cd bootstrap && sha256sum logosc > logosc.sha256 )
```

The commit that changes the compiler carries the new binary and its hash, and
`bash tools/selfhost.sh` proves the pair is a fixed point. A pull request that
changes `src/` and leaves the old bootstrap behind fails the sign-off of the
fixed point, which is the intended outcome.

## Adding a language feature

Work in this order; do not start with the code.

1. Change the specification first: `docs/superpowers/specs/`.
2. Add or update a numbered chapter in `docs/manual/`.
3. Add the corpus cases, including a negative case for each new diagnostic and
   a `tests/regress/` case for the defect the feature prevents.
4. Implement the front end and backend change.
5. Regenerate the manual and prove it current:
   `./tools/logosc.sh guide > docs/LOGOS.md`, then
   `./tools/logosc.sh guide --check`.

## The manual is generated

`docs/LOGOS.md` is generated from the compiler's own tables and the chapter
sources in `docs/manual/`. Never edit `docs/LOGOS.md` by hand. Change the
chapter or the compiler table, regenerate, and let
`./tools/logosc.sh guide --check` prove the committed manual is current.

## Opening the pull request

- Branch from `main` with a `feat/`, `fix/` or `docs/` prefix, for example
  `fix/vec-get-place` or `docs/threads-chapter`.
- Keep one logical change per pull request. Do not mix a compiler fix with a
  refactor or a reformat.
- Fill in `.github/PULL_REQUEST_TEMPLATE.md` completely: the result line for
  every gate, the regress case and its pre-fix failure, the reason for any
  `tests/summary.txt` baseline change, and a statement that the four invariants
  still hold.
- Run `bash tools/pr_gate.sh` immediately before opening the pull request.
- Do not reformat files you did not otherwise change. `logosc fmt` output is
  canonical, so a formatting-only diff means your change touched more than it
  should have.

The repository accepts pull requests from people and from AI agents acting
through their operator's account. The same gates apply to both.
