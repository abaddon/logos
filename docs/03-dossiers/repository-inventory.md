# L3 — Repository inventory

Static counterpart to the probe log: what is on disk at commit `9194412`, counted. This is the
evidence for every "absent" claim in the register — an item missing here was verified missing, not
assumed.

---

## Scale

| Measure | Value |
|---|---|
| Tracked files | 757 |
| `.logos` files | 366 |
| `.logos` lines | 42,122 |
| C runtime (`logos/runtime/rt.c` + `rt.h`) | 2,274 lines |
| Compiler modules (`src/logosc/*.logos`, excluding `_test`) | 12 |
| Compiler test modules (`src/logosc/*_test.logos`, `src/std/*_test.logos`) | 12 |
| Compiler fixtures (`src/logosc/fixtures/`) | 147 files |
| Git commits / tags | 104 / **0** |
| Corpus cases (`tests/summary.txt`) | 309 |
| Contract tests (Python `def test_`) | 24 (20 contributing, 3 runtime, 1 selfhost) |

## Compiler modules and their line counts

```
src/logosc/check.logos      7,424      src/logosc/emit.logos        850
src/logosc/lower.logos      6,515      src/logosc/resolve.logos     637
src/logosc/main.logos       1,614      src/logosc/ir.logos          491
src/logosc/guide.logos      1,849      src/logosc/tree.logos        288
src/logosc/harness.logos    1,854      src/logosc/lex.logos         252
src/logosc/types.logos      1,061      src/logosc/fmt.logos         162
```

Each module is paired with a `.md` beside it (15 such files across `src/logosc` and `src/std`)
carrying the contract, the reasoning and the documented limits — the closest thing this project has
to architecture decision records, and better than most.

## Standard library (the whole public surface — 21 functions)

| File | Lines | Functions |
|---|---|---|
| `src/std/io.logos` | 23 | `io-create`, `io-write`, `io-close`, `io-read`, `io-temp-path` |
| `src/std/str.logos` | 69 | `string-match-at`, `string-find`, `string-starts-with`, `string-split-nonempty`, `string-split`, `string-join` |
| `src/std/map.logos` | 86 | `map-hash`, `map-init`, `map-find`, `map-get`, `map-has`, `map-count`, `map-needs-grow`, `map-grow`, `map-insert`, `map-put` |

No `str`→integer parse, no sort, no JSON, no formatting, no `unlink`/`stat`/`getenv` (A4).

## Test corpus

| Category | `.logos` files | Purpose |
|---|---|---|
| `type/` | 106 | type errors, mutability, moves, error handling (negative, `.expect` codes) |
| `regress/` | 40 | one case per fixed defect — 33 cases total (multi-file fixtures) |
| `exec/` | 21 | compile and run, stdout + exit code |
| `parse/` | 18 | accepted and rejected grammar, multi-module resolution |
| `diff/` | 3 | differential oracle against gcc (`arith`, `arrays`, `strings`) |
| `thread/` | 2 | spawn/join/channel stress |
| `generics/` | 2 | instantiation limit, unbound variable |
| `mem/` | 1 | leak accounting |
| `golden/` | 1 | `vec.ll` IR golden file |

Config: `tests/summary.txt` — 311 lines, `LEAKS 10`, `OPTS -O0 -O2`, then one `PASS <id> <detail>` per
case. Text only (C3).

## Documentation

| Path | Size | Notes |
|---|---|---|
| `docs/LOGOS.md` | 932 lines | generated; cheat sheet, 20 chapters, reference (forms, primitives, operators, builtins, reserved names, 35 diagnostic codes, test categories) |
| `docs/manual/*.logos` | 20 files | the chapter sources |
| `docs/history/build-ledger.md` | 35,741 bytes / 277 lines | the rulings ledger — the only record of *why* |
| `docs/superpowers/plans/*.md` | 34 files | working reports |
| `docs/superpowers/specs/*.md` | 3 files | design of record (**stale**, B4) + self-hosting design + qualified-names design |
| `src/logosc/*.md`, `src/std/*.md` | 15 files | per-module contracts |
| `AGENTS.md` | 6,876 B | contributor contract |
| `CONTRIBUTING.md` | 4,345 B | human route (one stale command, B5) |
| `README.md` | 12,353 B | status, usage, limits (overstates status, B3) |
| `IDEA.md` | 49 B | one line: *"Build a modern program language optimised for AI"* |

**Absent** (verified by `ls`): `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
`ARCHITECTURE.md`, `docs/00-index.md` (until this audit), `docs/README.md`, any `releases/` notes.

## Build, packaging and CI

**Present:**

```
Makefile                 targets: test, contract, suites, suites-all, fmt, clean   (no install/dist/release)
tools/logosc.sh          bootstrap hash check → rebuild from src → exec
tools/selfhost.sh        gen2==gen3, IR parity, fmt reproduction, stage-0 currency
tools/accept.sh          7 sections, per-section floors
tools/pr_gate.sh         DCO precondition + 6 gates, PASS/FAIL per gate
tools/check_dco.sh       Signed-off-by enforcement
bootstrap/logosc         1,366,624 B stage-0 (+ .sha256, .gitattributes binary -text -diff)
.github/workflows/gate.yml     one job, ubuntu-22.04, timeout-minutes: 90
.github/PULL_REQUEST_TEMPLATE.md   gate table + checklist
.github/ISSUE_TEMPLATE/bug.yml     one bug form (stale command, B5)
.github/CODEOWNERS       every path owned by @abaddon; high-risk paths listed
```

**Absent** (all verified by `ls`):

```
pyproject.toml  setup.py  setup.cfg  MANIFEST.in
tools/verify_install.sh
Dockerfile  .devcontainer
.github/workflows/release.yml (or any workflow other than gate.yml)
install/  dist/  packaging/
CHANGELOG.md
```

`Makefile:42` still cleans `dist *.egg-info` — the packaging that used to exist (B5).

## CI job, as written

`gate.yml` — `on: push[main], pull_request`; `permissions: contents: read`; concurrency group per
ref; `runs-on: ubuntu-22.04`; `timeout-minutes: 90`; steps: checkout (fetch-depth 0) → install
`clang lld gcc jq python3` → create local `main` → DCO (pull_request only, base/head SHAs from the
event) → `make test` → corpus → `accept.sh` → `guide --check` → fmt diff gate → `selfhost.sh`.

No matrix, no cache, no artifact upload, no release trigger, no container.

## Toolchain observed

```
clang 14.0.0-1ubuntu1.1 (Target: x86_64-pc-linux-gnu)
python3 3.14.9 (contract tests only)
gcc 11 / jq 1.6 (differential + JSON oracles in accept.sh)
GNU make
```

The compiler binary is a dynamic PIE against `libc.so.6` and `libm.so.6` (P12), so a distribution
inherits the build host's glibc floor.

## What a consumer would actually receive today

Nothing. There is no artifact, no tag, no install instruction and no verifiable checksum. The only
supported way to run this compiler is `git clone` + `./tools/logosc.sh`, which builds it from source
in ~6 minutes using the committed stage-0 binary.

---

SOURCES (LAYER 3 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/probe-log.md`
 -> The dynamic counterpart: what the counted things actually do when executed.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/doc-contradictions.md`
 -> Where the written record disagrees with this inventory.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Every register row, with the inventory fact that supports it.
