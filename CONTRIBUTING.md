# Contributing to Logos

Logos is a prefix-form language for AI readers, compiled by `logosc` to native
x86_64 Linux binaries. `AGENTS.md` is the full contract; this page is the
shorter human route through it. Read `docs/LOGOS.md` for the language itself.

## Set up

Ubuntu 22.04, Python 3.10+, clang, lld, gcc, jq and GNU make:

```sh
sudo apt-get install -y clang lld gcc jq
make test
```

No install step is needed: `./tools/logosc.sh` builds the compiler from the
checkout on first use and runs it. The bootstrap binary it starts from,
`bootstrap/logosc`, only compiles the compiler; it is not the compiler you are
testing.

## The six gates

```sh
make test
./tools/logosc.sh test tests
bash tools/accept.sh
./tools/logosc.sh guide --check
./tools/logosc.sh fmt $(git diff --name-only main...HEAD -- '*.logos')
bash tools/selfhost.sh
```

`bash tools/pr_gate.sh` runs the sign-off check first, then all six, and prints
one PASS or FAIL line per gate. A pull request must show all six passing and
every commit signed off.

To run one contract test file, name it (`CONTRACT_TESTS` in `Makefile` lists
them all):

```sh
python3 -m unittest tests.test_contributing -v
```

To run one compiler suite, or one corpus category at one optimisation level:

```sh
./tools/logosc.sh test src/logosc/body_test.logos --opt -O0
./tools/logosc.sh test tests --only regress --opt -O0
```

The compiler's own suites (`body_test`, `check_test`, `resolve_test`) are the
direct check on a lowering or checker change; they are written in Logos and run
by the compiler itself.

## Compiler changes need a regress case

Add `tests/regress/name.logos`, plus `tests/regress/name.expect` with the
diagnostic code when the case is negative. It must fail before the fix and pass
after it. Do not delete or weaken an existing regress case; that is grounds for
rejection.

## The baseline

`tests/summary.txt` records every corpus case, the optimisation levels it ran
and the suite's leak total. Regenerate it only when you add a case or
intentionally change an existing one:

```sh
./tools/logosc.sh test tests --update-baseline
```

Never regenerate it to hide a failure. A case that passed in the baseline and
fails now is a regression and exits 1; a higher leak total at the same
optimisation levels also exits 1. `--update-baseline --only CATEGORY` merges:
it rewrites that category and leaves the rest alone. Review
`git diff tests/summary.txt` before committing and say in the pull request why
the change is legitimate.

## The manual is generated

Never hand-edit `docs/LOGOS.md`. Edit the chapter in `docs/manual/` or the
compiler table it comes from, then:

```sh
./tools/logosc.sh guide > docs/LOGOS.md
./tools/logosc.sh guide --check
```

If you change `src/logosc/`, the stage-0 binary must be rebuilt in the same
pull request, because it is the only compiler that can build the source. The
`bash tools/selfhost.sh` gate fails if the pair is not a fixed point:

```sh
./tools/logosc.sh version
cp build/logosc bootstrap/logosc
( cd bootstrap && sha256sum logosc > logosc.sha256 )
```

## Invariants

Every change must preserve all four:

- no accepted program reads freed or uninitialised memory;
- no accepted program behaves differently at `-O0` and `-O2`;
- no checker-accepted form is unimplemented in the backend;
- every diagnostic carries a code and a node path.

## Pull requests

Branch with a `feat/`, `fix/` or `docs/` prefix, keep one logical change per
pull request, and fill in `.github/PULL_REQUEST_TEMPLATE.md`. Run
`bash tools/pr_gate.sh` before you push and paste its result lines. Do not
include unrelated reformatting.

Every commit must carry a DCO sign-off whose email matches the commit author.
`git commit --signoff` adds it. This is a precondition, not one of the gates:
`bash tools/pr_gate.sh` checks it before the six gates and stops there if any
commit is unsigned, and the CI job runs the same check before its gates. Run
`bash tools/check_dco.sh` directly to inspect a branch; it prints the offending
commit SHA and the exact trailer to add when one is missing.

Bugs go through the issue form at `.github/ISSUE_TEMPLATE/bug.yml`; include the
smallest program that reproduces the problem, the exact command, the expected
output, the actual output or diagnostic code, and both `-O0` and `-O2`.

## Licence

MIT. By opening a pull request you agree to license your contribution under it.
