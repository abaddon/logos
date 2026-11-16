# L3 — Probe log: every measured behaviour

Grounding for every factual claim in this pyramid. Each probe is a command that was actually run on
commit `9194412`, in the worktree `/root/ai-language-program/.worktrees/t_7a5a4fe5`, with its real
output and exit status. Nothing here is inferred from documentation.

Environment: Ubuntu, clang 14.0.0-1ubuntu1.1, Python 3.14.9, kernel 5.15.0-198-generic, x86_64.

---

## P0 — Rebuilding the compiler from source takes ~6 minutes

```sh
$ ./tools/logosc.sh version      # build/ missing → triggers a full rebuild
```
Started 19:52, `build/logosc` present at completion; total ≈ 6 min. Intermediates:

```
build/body_test.ll   24,595,352 bytes    # the compiler's own IR (named after the first source's stem)
build/logosc          1,366,624 bytes
```

The IR filename comes from the **first file in the build set** (`src/logosc/body_test.logos` sorts
first), not from `-o`. Worth knowing before writing an installer that assumes `build/logosc.ll`.

**Supports:** A8 (build latency), C8 (gate duration), D10 (installer should pass explicit paths).

---

## P1 — Version is a source constant

```sh
$ ./tools/logosc.sh version
logos 0.1.0
exit=0
```

No `--version` flag, no JSON form. The literal lives in `src/logosc/main.logos:96`.

**Supports:** E5, V1-02.

---

## P2 — No argument prints help to stdout and exits 0

```sh
$ ./tools/logosc.sh
usage: logosc [-h] command ...

Compiler for Logos, a prefix-form language for AI readers.

positional arguments:
  command
    build     compile Logos source files to a native binary
    test      compile and run the (test ...) nodes in a file
    fmt       rewrite Logos source in canonical form
    show      print one node of a Logos file
    version   print the compiler version
    guide     print the generated Logos manual or its manifest

options:
  -h, --help  show this help message and exit
exit=0
```

**Supports:** E4 (the list omits `resolve` and `check`), C2 (nothing pins this).

---

## P3 — The `patch` verb does not exist

```sh
$ ./tools/logosc.sh patch x.logos hello/main/2
usage: logosc [-h] command ...
logosc: error: argument command: invalid choice: 'patch' (choose from 'build', 'test', 'fmt',
 'show', 'version', 'guide')
exit=2
```

**Supports:** A2, V1-07. The design document specifies this verb and the ledger records it working on
the Python compiler (Wave B2).

---

## P4 — The advertised verb list is six; the working set is eight

`resolve` and `check` are absent from both the help block and the choice list (P2, P3) but work:

```sh
$ ./tools/logosc.sh resolve examples/hello.logos
exit=0                       # silent success, by design
$ ./tools/logosc.sh check examples/hello.logos
exit=0
```

**Supports:** E4, B2.

---

## P5 — `guide --json` is valid JSON with seven keys, unversioned

```sh
$ ./tools/logosc.sh guide --json > /tmp/g.json; echo $?
0
$ head -c 120 /tmp/g.json
{
  "forms": [
    {
      "name": "mod",
      "arity": "1",
      "meaning": "`(mod name)` names the module; one per file"
    },
$ jq -e 'keys' /tmp/g.json
[ "builtins", "categories", "codes", "forms", "operators", "reserved", "types" ]
```

No `schema_version`; no schema file; no statement of stability anywhere.

**Supports:** E9, V1-13. Also the positive model for E1: the project can emit clean JSON when it
decides to.

---

## P6 — Diagnostics are one prose line, and there are two shapes

Checker failure:

```sh
$ printf '(mod t)\n(fn main :void () (println (+ 1 "x")))\n' > /tmp/t.logos
$ ./tools/logosc.sh build /tmp/t.logos
t/main/2/0: E0100: '+' needs numbers, found :str
exit=2
```

Resolver failure (node path):

```sh
$ ./tools/logosc.sh check p2.logos          # (use nosuch)
p/0: E0005: unknown module 'nosuch'
exit=2
```

Environment failure (no code at all):

```sh
$ cd /tmp && /…/build/logosc build /…/examples/hello.logos -o /tmp/hh
logos: runtime not found: logos/runtime/rt.c
exit=1
```

Three different shapes, no machine-readable form, one with no code. Compare the project's own
generated table of 35 diagnostic codes (`docs/LOGOS.md` §Diagnostic codes) — every code exists;
what is missing is the envelope.

**Supports:** E1, E2, V1-10, V1-11.

---

## P7 — The compiler cannot compile outside a repository checkout

```sh
$ cd /tmp && /root/…/t_7a5a4fe5/build/logosc build /root/…/examples/hello.logos -o /tmp/hh
logos: runtime not found: logos/runtime/rt.c
exit=1
```

`src/logosc/main.md` §"Finding the runtime" documents this as deliberate: the runtime is named
`logos/runtime/rt.c` relative to the working directory.

**Supports:** D2, V1-03 — the single most important measured fact in this audit.

---

## P8 — `-h` is a usage error on a sub-verb; unknown flags exit 2

```sh
$ ./tools/logosc.sh build -h >/tmp/o 2>/tmp/e; echo "exit=$?"
exit=2
$ cat /tmp/o            # empty
$ cat /tmp/e
usage: logosc [-h] command ...
logosc: error: unrecognized arguments: -h

$ ./tools/logosc.sh build examples/hello.logos --frob
usage: logosc [-h] command ...
logosc: error: unrecognized arguments: --frob
exit=2
```

**Supports:** E3 (no per-verb help), C2 (nothing pins the status), E2 (usage errors are 2).

---

## P9 — `fmt -` works; the manual documents neither the CLI nor the stdlib

```sh
$ printf '(mod z)\n(fn  main :void ()  (println "x"))' | ./tools/logosc.sh fmt -
(mod z)

(fn main :void ()
  (println "x"))
exit=0
```

```sh
$ grep -c "io-create\|map-get\|string-find" docs/LOGOS.md
1                       # one incidental hit across 932 lines
$ grep -c '^### ' docs/LOGOS.md
20 chapters + reference sections — none of them about the command line
```

**Supports:** B2, B7, E7 (stdin is supported by `fmt` only).

---

## P10 — The standard library does not resolve outside a checkout: `map`

```sh
$ D=/tmp/iso_…; mkdir -p $D/bin $D/work; cp …/build/logosc $D/bin/
$ cd $D/work && printf '(mod p)\n(use map)\n(fn main :void () (let k :(vec :str) (make (vec :str))) (println (map-count k)))\n' > m.logos
$ $D/bin/logosc check m.logos
p/0: E0005: unknown module 'map'
exit=2
```

Control (same command, cwd = repository root): exit 0.

**Supports:** D3, V1-04, A5.

*(Method note: an earlier attempt appeared to resolve `map` outside the repo. The cause was
`/tmp/probe`, a scratch directory from a previous session, which contains symlinks such as
`io.logos -> src/std/io.logos`. The isolated-directory probe above is the authoritative one: `use`
searches the asking file's directory and `src/std/<name>.logos`, and nothing else.)*

---

## P11 — The same for `io`, and the build succeeds only if the runtime is copied beside the source

```sh
$ cd $D/work && $D/bin/logosc check p.logos     # (use io) + (io-create …)
p/0: E0005: unknown module 'io'
exit=2

$ mkdir -p logos/runtime && cp …/logos/runtime/rt.{c,h} logos/runtime/
$ $D/bin/logosc build p.logos -o p4
build exit=0                                    # with both obstacles hand-patched away
```

Two independent obstacles to a portable build, both closed by a prefix-relative search (D-1 in
`02-analysis/d-build-packaging-ci.md`).

**Supports:** D2, D3, A5.

---

## P12 — The compiler binary is a dynamic PIE, not stripped

```sh
$ file build/logosc
ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked,
interpreter /lib64/ld-linux-x86-64.so.2, BuildID[sha1]=bff18ab8…, for GNU/Linux 3.2.0, not stripped

$ ldd build/logosc
linux-vdso.so.1
libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6
libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6
/lib64/ld-linux-x86-64.so.2
```

**Supports:** D7 (distribution format: a glibc floor is implied by the build host), V1-17.

---

## P13 — Two builds of the same input are byte-identical

```sh
$ ./tools/logosc.sh build examples/hello.logos -o /tmp/h1
$ ./tools/logosc.sh build examples/hello.logos -o /tmp/h2
$ sha256sum /tmp/h1 /tmp/h2
e0d4a8a164cb89d1dd4994db57e060be191eb5c1c892ac8226c0a4dd2ee87d8a  /tmp/h1
e0d4a8a164cb89d1dd4994db57e060be191eb5c1c892ac8226c0a4dd2ee87d8a  /tmp/h2
```

Same-host determinism is real. Cross-host equality is unmeasured and unpublishable today.

**Supports:** V1-14 (PASS on determinism, FAIL on publication), D8.

---

## P14 — The regress suite is fast and green; its report is text

```sh
$ time ./tools/logosc.sh test tests --only regress --opt -O0 | tail -3
PASS regress/vec-place-copy -
33 passed, 0 failed, 0 leaked
baseline tests/summary.txt: 0 regression(s)

real    0m3.571s
```

Baseline format (`tests/summary.txt`, 311 lines, 309 cases):

```
LEAKS 10
OPTS -O0 -O2
PASS parse/duplicate-fn -
PASS parse/duplicate-test -
…
```

**Supports:** C3 (text-only report), C8 (a 3.5 s fast loop exists and is undocumented), C2.

---

## P15 — Cross-module calls work (contradicting the design spec)

```sh
$ cat build/probe2/lib.logos
(mod lib)
(fn twice :i64 ((x :i64)) (ret (* x 2)))
$ cat build/probe2/app.logos
(mod app)
(use lib)
(fn main :void () (println (twice 21)))
$ ./tools/logosc.sh build build/probe2/app.logos -o build/probe2/app && ./build/probe2/app
42
exit=0
```

The 2026-11-06 design says *"a call to it is E0103 `imported functions are not lowered yet`"* and
*"v1 lowers one module at a time"*. The implementation links across modules and the compiler is
itself multi-module. The spec is stale (B4).

**Supports:** B4, A1 (multi-module is real, so the namespace gap is now on the critical path),
`02-analysis/a-compiler-capabilities.md`.

---

## P16 — The happy path is exactly as advertised

```sh
$ time ./tools/logosc.sh build examples/hello.logos
real    0m0.843s
exit=0
$ ./build/hello
hello
run exit=0
$ ls build/
body_test.ll  hello  hello.ll  logosc  logosc-build.log
```

**Supports:** the audit's premise — nothing here is broken; the gap is reach, not function.

---

## Method notes and limits of this audit

- **Not run:** the full six-gate list (`bash tools/pr_gate.sh`, ~1 hour by its own comment). Gates
  1-6 are reported as PASS on the project's own record (CI + ledger). P14 is the one gate section
  this audit executed.
- **Not measured:** cross-host reproducibility, arm64/Darwin, clang 15+, memory usage, corpus
  coverage. Each is flagged as unmeasured where it matters rather than asserted.
- **Not modified:** no source, test, doc or configuration file was changed except the creation of
  this pyramid under `docs/`. Probe artefacts live under `build/` (gitignored) and `/tmp`.
- **Run as:** the bootstrap-verified `tools/logosc.sh`, never `bootstrap/logosc` directly (AGENTS.md
  forbids using the stage-0 as an oracle).

---

SOURCES (LAYER 3 — NAVIGATION)

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/00-index.md`
 -> Which register row each probe supports (the "Evidence" column).

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/repository-inventory.md`
 -> The static counterpart: what exists on disk, counted.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/docs/03-dossiers/doc-contradictions.md`
 -> The documentation counterpart: which written statement each probe contradicts.

`/root/ai-language-program/.worktrees/t_7a5a4fe5/src/logosc/main.md`
 -> The contract these probes test, verb by verb, including the documented reasons for the gaps.
