# W8 cutover — deleting the Python compiler

Written 2026-11-14 at `830464e`, after `guide` was ported and controller-verified.
This is the controller's plan; the CLI tail (`show`, `version`, `--update-baseline`,
dropping `patch`) is a separate task and lands first.

## What is true today

Every verb `logosc` needs now exists in Logos and matches Python:

| verb | evidence |
|---|---|
| `build` | links with clang, self-hosts: gen2→gen3 `e3f5cb9b5d886f2d`, 946,664 B |
| `fmt` | rewrites 364 manifest paths in place, `git diff --exit-code` clean |
| `test` | `308 passed, 0 failed, 10 leaked` — the line Python prints, verified by hand |
| `guide` | manual byte-identical (24,643 B), `--json` identical (18,808 B), `--check` agrees |

The front end is byte-identical over the whole source set (`unit: 2 files`,
18,243,243 B), so the compiler is self-hosting in the only sense that can be
measured: it emits the same IR as the reference, from itself.

## The question the deletion forces

**Nothing can compile the compiler.** Today `tools/selfhost.sh` phase one runs
`python3 -m logos build src/logosc/*.logos -o gen2`. Delete Python and that line
has no subject.

Three answers, only one of which survives scrutiny:

1. **Keep a Python bootstrap forever.** Defeats the goal — Python stays a
   dependency of every build, and the thing being deleted is the thing invoked.
2. **Trust the last binary.** No bootstrap at all; assert that `build/logosc`
   exists. Unverifiable from a clean checkout, so a corrupted or stale binary is
   undetectable, and a new machine cannot build the project.
3. **Ship a bootstrap binary and make the fixed point the proof.** Commit
   `bootstrap/logosc`, record its SHA-256, and have phase one use it:
   bootstrap → gen2 → gen3, with gen2 and gen3 required to be byte-identical.
   A corrupt bootstrap cannot pass, because the fixed point rebuilds it from
   source and compares.

**Decision: option 3.** `bootstrap/logosc` is ~1.3 MB and its SHA-256 is
recorded in `bootstrap/logosc.sha256`. Phase one verifies the checksum before
using it, so the file cannot be swapped silently. This is the same shape as
every other self-hosting toolchain: a stage-0 binary that exists only to be
replaced by its own output.

**Measured at `830464e`, by the controller, with no Python in the loop:**
`build/w8guide/gen3` built `logosc-a`, `logosc-a` built `logosc-b`, and the two
are byte-identical at `9410eae82df72ae2`, 1,328,800 bytes. That is the
bootstrap fixed point on the current tree, and it is what `bootstrap/logosc`
will be. (The hash moved from `e3f5cb9b5d886f2d` because the `guide` tables are
now part of the source.)

## What is deleted, and what it cost

| deleted | size |
|---|---|
| `logos/` (the reference implementation) | 16,327 lines, 16 modules |
| 19 test files that import it, plus `tests/run.py` | ~1,068 tests |
| `pyproject.toml`'s `logosc = "logos.cli:run"` | one entry point |

**It is not all 31 files, and my first count of the survivors was wrong.** Two
passes over the tree:

- 18 test files import `logos`, and `test_packaging.py` exercises pip-installing
  it. Those die obviously.
- The five `test_gen2_*.py` files (61 tests) *look* standalone — they drive the
  port as a subprocess — but they build that binary with `sys.executable -m
  logos` and diff against the same interpreter as the oracle. They are
  differential tests **against the thing being deleted**, so they die too.

| keeps running | tests |
|---|---|
| `test_contributing.py` — pins AGENTS.md's six commands against `pr_gate.sh` and the workflow | 20 |
| `test_runtime.py` — compiles a C program against `rt.c`; tests the runtime, not the compiler | 3 |
| `test_selfhost.py` — reads `selfhost.sh`'s summary lines | 1 |
| **surviving total** | **24** |

**24 of 1,131 tests live; 1,107 die with the implementation or the oracle they
compared against.** Everything the contract needs is in the 24 — the gate list,
the sign-off precondition, the workflow, the runtime and the self-hosting
summary — and everything that judged the *compiler* is now a Logos suite, the
corpus, or the fixed point.

`test_runtime.py` and the port's own suites need their `logos/runtime/rt.c` path
updated when the runtime moves out of the deleted package — `runtime/rt.c` at
the repository root, which is also where `build` and `selfhost.sh` must look.

**What is lost is white-box coverage of a deleted implementation.** The defects
that mattered were caught by the outside contract, and it is what remains: 308
corpus cases, 361 `body_test`, 80 `check_test`, 38 `resolve_test`, 7 acceptance
sections against gcc, jq and `wc`, the 90-file IR parity list, the manual drift
check, the formatting fixed point, and the unit IR fixed point.

Two of those are **not gate-run today** and must become gates in the same
change, or the loss is larger than stated:

- `body_test.logos` (361) and `check_test.logos` (80) are run by hand today;
- `resolve_test.logos` (34) likewise.

## The six commands after cutover

`AGENTS.md` documents six commands whose names `tests/test_contributing.py`
pins against `tools/pr_gate.sh`. That test **survives** (it never imports
`logos`), so the contract stays enforced — but the commands it names must
change, and the test must be updated in the same commit.

| before | after |
|---|---|
| `make test` (`unittest discover`, 1,131 tests) | `make test` — 24 contract tests, then the Logos suites at `-O0` |
| `python3 -m logos test` | `./logosc test` — the 308-case corpus |
| `bash tools/accept.sh` | unchanged, but `PYTHON -m logos` becomes `$LOGOSC` |
| `python3 -m logos guide --check` | `./logosc guide --check` |
| `python3 -m logos fmt …` | `./logosc fmt …` |
| `bash tools/selfhost.sh` | unchanged externally; phase one uses `bootstrap/logosc` |

## Order of work

1. CLI tail lands (`show`, `version`, `--update-baseline`, `patch` dropped).
2. `logosc` at repo root: a committed build of the compiler, plus
   `bootstrap/logosc` with its checksum. Both are outputs of the same source.
3. `tools/selfhost.sh` phase one switches to `bootstrap/logosc`; phase five
   keeps comparing the unit and the whole source set, now bootstrap vs gen2 vs
   gen3 instead of Python vs gen2. `tests/test_selfhost.py` keeps working
   unchanged, since it reads the same five summary lines.
4. `tools/accept.sh` gains `LOGOSC` (default `./logosc`) and stops naming Python.
5. `Makefile`: `test` runs the 63 surviving tests **and** the three Logos
   suites through `./logosc test` — measured green through the port's own binary
   on 2026-11-14: 361 + 80 + 38 = **479 cases** — so the 479 Logos cases replace the 1,068 deleted ones rather than nothing
   replacing them; `fmt` runs `./logosc fmt .`.
6. `tools/pr_gate.sh`: gates become `make test`, `./logosc test`, acceptance,
   manual drift, formatting, self-hosting. `tests/test_contributing.py` is
   updated in the same commit and still pins AGENTS.md, the gate script and the
   workflow against each other.
7. `pyproject.toml`: drop the `logosc` entry point and the `logos` package.
8. `AGENTS.md`: the six commands, the manual's provenance, and the fixed-point
   statement, rewritten to describe the Logos compiler.
9. Delete `logos/` and the 19 implementation test files in one commit, with the
   gates already green on the new path. Move `logos/runtime/` to `runtime/` in
   the same commit and repoint `build`, `selfhost.sh` and `test_runtime.py`.

## What must be true before step 9

- `bootstrap/logosc` and `logosc` are byte-identical, and both are reproducible
  from `src/logosc/*.logos` by the bootstrap.
- Every gate passes with Python absent: `PATH` filtered, `python3` unreachable.
  This is the check that matters and it is cheap: `env PATH=/usr/bin:/bin` with
  `python3` masked, then run all six.
- `logosc test --update-baseline` rewrites `tests/summary.txt` to the same bytes
  Python would.
- No tracked file invokes `python3` for anything but non-compiler tooling.

## Risks

- **A committed binary is not reviewable.** Mitigation: checksum in phase one,
  and the fixed point rebuilds it; a hand-edited binary fails the comparison.
- **The bootstrap is x86_64-linux only.** Stated in `bootstrap/README.md`; other
  platforms must build from a suitable stage-0, which this repository does not
  ship. This is a real limitation of the toolchain, not a hidden one.
- **Losing white-box tests** — see above; the Logos suites become gates.
- **`make test` time grows** because six compiler builds already cost ~52 s
  each; measure and record the new total.
