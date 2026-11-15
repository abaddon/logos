# W8 cutover inventory — what `logosc` still needs from Logos

Measured at `25bc651` plus the W7 C4 working tree (the `(module, name)` function
index), 2026-11-13. Every count below comes from a command in "Reproduce"; the
builds are under `build/w7c4/` (git-ignored).

The goal: `logosc` is a Logos binary built by Logos, with the Python compiler
deleted. Today gen2 builds the whole source set and emits IR byte-identical to
Python's on both units the gate compares (`tools/selfhost.sh`, phase five), so
the front end is done. What is missing is the driver: the verbs `logosc` exposes
and the OS work they do.

## 0. The verbs that exist, measured

| verb | Python (`logos/cli.py:59-148`) | port (`src/logosc/main.logos:639-655`) |
|---|---|---|
| `build FILE... [-o OUT] [--opt O] [--keep-ir]` | front end, then clang (IR + `rt.c` → binary) | emits IR only; requires `-o` (`main.logos:610-616`); no `--opt`, no default output |
| `fmt FILE...` | rewrites in place; dirs recursively; `-` is stdin | prints canonical source for exactly one file (`main.logos:71-73`); `-` and a directory are `R2`/usage |
| `test [PATH] [--only C] [--opt O]... [--update-baseline]` | builds and runs the whole corpus | usage (exit 2) |
| `guide [--json] [--check]` | generated manual / manifest / drift check | usage (exit 2) |
| `show FILE PATH`, `patch FILE PATH` | print/replace one node | usage (exit 2) |
| `version` | prints the version | usage (exit 2) |
| `resolve FILE...`, `check FILE` | resolver/checker diagnostics | present; parity is the gate's job |

Measured exit codes: `gen2 version`, `gen2 test`, `gen2 guide`, `gen2 show`,
`gen2 patch`, `gen2 fmt -`, `gen2 fmt <dir>` all exit 2 with the usage block
(`main.logos:29-33`). `gen2 fmt <file>` exits 0 and writes the canonical text to
stdout. `gen2 build` exits 0 and writes only the `.ll` it is pointed at.

## 1. `build` — the missing half is the link, not the lowering

The port's build writes LLVM text (`main-spit`, `main.logos:133-140`). Python's
`build` writes the same text and then runs clang:

- `_link` writes `build/<first stem>.ll`, then
  `clang {opt} -target x86_64-unknown-linux-gnu <ll> logos/runtime/rt.c -o <out> -lpthread -lm`
  (`logos/driver.py:225-265`); `--opt` defaults to `-O2` (`cli.py:74-79`);
  the default output is `build/<first stem>` and the IR is
  `build/<first stem>.ll` (`driver.py:116-118,164-165`);
- the runtime path is found beside the package (`driver.py:60-75`), and both
  link flags are unconditional (`driver.py:79`);
- a failure is one `logos: …` line on stderr with exit 1 (`cli.py:319-326`).

No language form is missing: `(run prog args)` is lowered
(`src/logosc/lower.logos:1617`, `lo-run-status`/`-out`/`-err` at 4462 and on),
the runtime starts a child at `logos/runtime/rt.c:989`, and `(args)` is lowered
(`lower.logos:1613`). The work is: build the argument vector (program, the IR
path, the runtime path, `-o`, `--opt`, `-lpthread -lm`), run it, and map a
non-zero status to exit 1. The gate already proves the IR is identical for the
whole set, so this is plumbing over `run`.

One caveat measured while proving the fixed point: clang embeds the IR file's
**basename** as an `STT_FILE` symbol (and in the build id), so two byte-identical
`.ll` files compiled from differently-named paths produce binaries that differ
by that symbol. Compiling the same basename twice is deterministic and
byte-identical. This is outside the IR and does not change parity; a driver
that always writes `build/<stem>.ll` behaves exactly like Python's.

## 2. `fmt` — already lowered; the file-system semantics are missing

`fmt.logos` is one of the 20 modules gen2 is built from, and the gate's
formatting phase is green (`selfhost: 317 files, 0 differences`). The language
work is done. What the CLI verb needs:

- **In place.** Python parses and rewrites each file, printing nothing
  (`cli.py:353-369`); the port prints to stdout (`main.logos:71-73`). Writing is
  available: `read-file` and `rt_create`/`rt_write` (`rt.c:666`) are lowered and
  `main-spit` already uses them (`main.logos:133-140`).
- **Several paths, directories, and `-`.** Python takes `nargs="+"`
  (`cli.py:107-113`), recurses over `rglob("*.logos")` in sorted order
  (`cli.py:344-348`), and formats stdin at most once (`cli.py:336-343,372-379`).
  The port's dispatch accepts exactly one file for `fmt` (`main.logos:650-655`).
  Stdin is available: `(read-all)` reads it (`rt.c:589-620`, lowered at
  `lower.logos:1607`).
- **Directory enumeration is a runtime gap.** `rt.c` has no `opendir`/`readdir`
  (grep: no such call anywhere in the file), so both `fmt <dir>` and `test`'s
  discovery need a new C helper (e.g. `rt_read_dir` + `rt_is_dir`), or the verb
  cannot see a directory at all. This is the one new runtime primitive W8 needs.
- **Errors and exit.** Python prints `logos: <path>: <strerror>` and returns 1
  (`cli.py:355-368`); the port prints `<path>:<line>:<col>: Rxxxx: …` and returns
  2 (`main.logos:35-46`). The gate compares stdout, so today's difference is
  invisible; a CLI parity test will see it.

## 3. `test` — a missing lowering mode, one missing form, and the harness

`test` is three pieces.

**(a) The test mode of the build.** The plan already documents it
(`docs/superpowers/plans/2026-11-13-w7-cutover-gaps.md` §4); the code it names
is unchanged:

- `run_test` selects `(test NAME …)` from the root module and links the result
  (`logos/driver.py:197-222`);
- `lower_test_program` lowers the test body as `main` after `forget_main`
  removes every module's `main` (`lower.py:851-895`; `forget_main` at
  `1072-1076`), and filters the `(expect …)`/`(expect-leak …)` directives
  (`lower.py:883-893`, `DIRECTIVES` at `check.py:1429`);
- a test build is a **debug** build: `main` declares and calls
  `rt_leak_report` before every exit (`lower.py:1933-1938`, called at
  `1786-1788` and `1922-1927`), and the link defines `LOGOS_DEBUG=1`
  (`driver.py:243-247`) so the runtime quarantines frees
  (`rt.c:350-365` prints one `LEAK …` line per live block);
- IR lands at `build/<stem>.<sanitized>.ll` (`driver.py:134-137`).

The port has none of this: `lower-build` has no `debug` notion and no test
entry (`src/logosc/lower.logos:4767` onward), and the port's checker has no
`test` branch — the module walk reads `fn`, `type` and `extern` only
(`check.logos:1645,1798,2047`) where Python also checks `module.tests`
(`check.py:1573`). The port's `main` return plumbing exists: `(ret …)` in
`main` goes through `lo-ret-main` (`lower.logos:2162-2163`) and the fallthrough
returns `i32 0` (`lower.logos:3369-3371`).

**(b) One form the corpus needs that the port refuses: closures.** The
runnable corpus has 162 `(test …)` nodes (137 in `tests/exec`, 7 in `regress`,
8 in `thread`, 7 in `mem`, 3 in `parse`). `tests/exec/closures.logos` holds 14
`(fn :T …)` forms and 17 of the exec cases; the port refuses that form at the
call site through `lo-not-yet` (`lower.logos:674-683`, fallback at `1684`), and
`lower.md` lists closures as not lowered. Everything else the test corpus uses
is in the port's dispatch: `run`/`run-status`/`run-out`/`run-err`,
`read-file`, `args`, the `str-*`/`vec-*`/`arr-*`/`atomic-*` families, channels,
mutexes and `spawn` all have `str-eq h "…"` branches in `lower.logos`.
`(expect …)`, `(expect-leak …)` and module-level `(expect-error …)` are
directives, not expressions: the lowerer filters the first two and the harness
reads all three (`tester.py:640`, `check.py:1429`).

**(c) The harness itself.** `logos/tester.py` is 976 lines: categories and
order (`tester.py:80`), default levels `-O0 -O2` (`93`), a 10 s timeout (`96`),
discovery (`_discover`, `187-250`), one status line per case with the
`category/file/test` id (`496`), build-and-run per level including the
cross-level disagreement check (`516-530`), the `expectation_of` reader
(`640`), and `summary.txt` baselines (`760-800`, W9 per the design's line 297).
It needs process spawn (present, `rt.c:989`), directory walk (the same missing
runtime helper as `fmt`), sorted paths, percent-encoded ids, and the timeout
kill. This is the largest single W8 item; none of it is a language form.

## 4. `guide` — no lowering work; data that lives only in Python

`guide` generates `docs/LOGOS.md` (928 lines / 24,098 bytes) from tables and the
20 chapters under `docs/manual/`, and `--json` prints an 18,008-byte manifest
with 7 keys (`guide.py:389-417`). `--check` regenerates in memory and compares
bytes (`guide.py:603-610`).

**Already in Logos.** The code tables (`types.logos:16` `type-code`,
`check.logos:28` `check-code`), the primitive whitelist (`types.logos:244`), the
reserved-name tests (`check.logos:108,258`), the form vocabulary
(`lower.logos:144-176`) and the operator families (`lower.logos:158-176`).

**Only in Python, so it must move into Logos before `guide` can ship:**

| data | size | source |
|---|---|---|
| `diag.CODES` (every E/R code **with its message**) | 35 pairs | `logos/diag.py:68` |
| `types.FORMS` | 12 | `logos/types.py:69` |
| `types.PRIMITIVES` / `INTEGERS` / `FLOATS` | 16 / 8 / 2 | `logos/types.py:39-65` |
| `RESERVED_FORMS` / `_PREFIXES` / `_VARIANTS` | 45 / 4 / 19 | `logos/check.py:1453-1470` |
| `FORM_DOCS` (arity + meaning per form) | 84 entries | `logos/guide.py:189` |
| `TYPE_ARITY`, `TYPE_MEANING` | 12 + 12 | `logos/guide.py:156-188` |
| `RULES` (the ten rules and where they are enforced) | 10 | `logos/guide.py:66-152` |
| `CHAPTER_TITLES` | 20 | `logos/guide.py:39-60` |
| `CATEGORIES` | 8 | `logos/tester.py:80` |
| chapter walk + `(expect …)` extraction | 20 files | `guide.py:645-683` (`fmt.render` at `fmt.py:41`, `tester.expectation_of` at `tester.py:640`) |

The chapters are ordinary Logos modules and already compile; rendering them is
the same printer `fmt` uses. The one dependency worth calling out: the
markdown's "Expected stdout" block comes from `tester.expectation_of`
(`guide.py:671`), so `guide` should follow `test`, not precede it.

## 5. The smallest order to `logosc` in Logos

Each step uses only what the one before it proved, and every step is testable by
comparing with the Python CLI before it is deleted.

1. **`build` links.** Add the clang invocation, `--opt`, default `-o`, and
   `logos: …` error lines (`driver.py:225-265`, `cli.py:311-327`). Evidence:
   `gen3 = clang(gen2's IR)` already produces a binary byte-identical to
   Python's when the IR basenames match (§1), and `gen3 build src/logosc/*.logos
   src/std/map.logos src/std/str.logos` must reproduce that IR. This step makes
   the compiler self-hosting without Python; nothing else can be tested on a
   binary that is produced by a Python driver.
2. **`fmt` rewritten in place** with multiple paths, directory recursion and
   stdin (`cli.py:330-379`). Add the `rt_read_dir`/`rt_is_dir` runtime helper
   (§2). Evidence: `gen3 fmt` rewrites every file in `tools/selfhost-manifest.txt`
   and leaves `git diff --exit-code` clean, exactly as the formatting gate does
   today.
3. **`test`** — the debug lowering mode (§3a), closure lowering (§3b), then the
   harness (§3c). Evidence the design already fixes: the same pass count and the
   same leak total as `python3 -m logos test` (design D3 item 4), which is
   162 `(test …)` cases at `-O0` and `-O2`.
4. **`guide`** — move the tables in §4 and reuse the harness's directive
   reader. Evidence: `gen3 guide` is byte-equal to `docs/LOGOS.md`, `guide
   --json` parses as the same 7-key manifest, and `guide --check` passes.
5. **CLI tail and cutover.** `show`/`patch` need path lookup and AST replacement
   (`cli.py:401-497`; the port has `tree-path` but no `find`-by-path), `version`
   needs one string (`cli.py:131`), the usage block and exit codes must match
   (`main.logos:29-33` vs `cli.py:151-184`), and the `logosc` entry point
   (`pyproject.toml:13-14`) must point at the Logos binary. Baselines stay W9
   (`tester.py:760-800`, design line 297), so step 3 may ship `test` without
   `--update-baseline`; `gen2 test` matching the Python run is the W8 gate
   (design line 316).

Steps 1 and 2 are independent of steps 3-5 and are the two that remove Python
from the *produce a binary* and *format a source* loops. `test` is the longest
because it needs both a new lowering mode and the only missing form family;
`guide` is last because it is the only verb that reuses another verb's reader.

## Reproduce

```sh
cd /root/ai-language-program
B=build/w7c4/gen2-new                     # Python-built gen2 from this tree
for v in version guide test "show src/std/map.logos hello/main" "fmt -"; do
  $B $v >/dev/null 2>&1; echo "$B $v -> $?"
done
$B fmt src/std/map.logos | head -2        # canonical text on stdout
grep -n "opendir\|readdir" logos/runtime/rt.c || echo "no directory walk in the runtime"

python3 - <<'EOF'
from logos import diag, guide, tester, types, check
print("codes", len(diag.CODES), "forms", len(types.FORMS),
      "primitives", len(types.PRIMITIVES),
      "reserved", len(check.RESERVED_FORMS), len(check.RESERVED_PREFIXES),
      len(check.RESERVED_VARIANTS), "categories", len(tester.CATEGORIES))
EOF
python3 - <<'EOF'
import glob
from logos.parser import parse
from logos.diag import LogosError
n = 0
for f in glob.glob("tests/*/*.logos"):
    try:
        n += sum(1 for it in parse(open(f).read(), f).items if getattr(it, "kind", "") == "test")
    except LogosError:
        pass
print("tests", n)          # 162
EOF
grep -c "(fn :" tests/exec/closures.logos
wc -l logos/tester.py logos/guide.py docs/LOGOS.md
ls docs/manual/*.logos | wc -l
```

Fixed-point evidence for §1 (already green in `tools/selfhost.sh` phase five):
`selfhost: 317 files, 0 differences`, `ir: 50 files, 0 differences`,
`resolve: 14 fixtures, 0 differences`, `check: 122 fixtures, 0 differences`,
`unit: 2 files, 0 differences`.
