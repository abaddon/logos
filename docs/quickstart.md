# Quickstart — from a checkout to a running binary

Twelve commands, in order, each with the output it must produce. Everything
here was executed on the audit machine; the outputs are copied from that run.

**Two ways in.** Install the published tarball — [`install.md`](install.md) has
the download, the checksum and the unpack — or clone this repository and use
`./tools/logosc.sh`, which builds the compiler on first use. The compiler
resolves its runtime and standard library from its own installation, so it runs
from any working directory; the steps below work either way.

- Prerequisites and platform: [`README.md`](../README.md#requirements).
- What it cannot do: [`reference/limits.md`](reference/limits.md).
- Command reference: [`reference/cli.md`](reference/cli.md).

---

## 1. Get the source and check the toolchain

```sh
git clone <repository-url> logos && cd logos
clang --version          # clang 14 or newer, x86_64 Linux
```

## 2. Build the compiler and print its version

```sh
./tools/logosc.sh version
```

```text
logos 0.2.1
```

The first invocation compiles the compiler from `src/` with the stage-0 binary
in `bootstrap/` and prints nothing while it works — 46 seconds measured on the
audit machine, minutes on a slower one. Every later invocation reuses
`build/logosc` until a source file in `src/` changes. `tools/logosc.sh` checks
the recorded SHA-256 of `bootstrap/logosc` on every run and refuses to proceed
if it does not match.

## 3. Write a program

```sh
cat > hello.logos <<'EOF'
(mod hello)

(fn main :void ()
  (println "hello from logos"))
EOF
```

## 4. Compile it

```sh
./tools/logosc.sh build hello.logos
```

Silence and exit 0. Two files now exist: `build/hello.ll` (the LLVM IR) and
`build/hello` (the native binary). The IR is always written; it is the artefact
to read when a program misbehaves.

## 5. Run it

```sh
./build/hello
```

```text
hello from logos
```

The exit status is the program's own. There is no `run` verb yet; build then
execute.

## 6. Make it wrong, and read the diagnostic

```sh
cat > broken.logos <<'EOF'
(mod broken)

(fn main :void ()
  (println (+ 1 "x")))
EOF
./tools/logosc.sh build broken.logos
```

```text
broken/main/2/0: E0100: '+' needs numbers, found :str
```

Exit status **2** — "the source is wrong". The line is `<node path>: <code>:
<message>`; `broken/main/2/0` is the module, `main`, its third child, that
child's head. `logosc show` prints the node a path names:

```sh
./tools/logosc.sh show broken.logos broken/main/2
```

```text
(println (+ 1 "x"))
```

Codes, shapes and the retry policy: [`reference/diagnostics.md`](reference/diagnostics.md).

## 7. Use the cheap check between edits

```sh
./tools/logosc.sh check broken.logos
```

```text
broken/main/2/0: E0100: '+' needs numbers, found :str
```

`check` is the same source diagnosis without codegen or clang — the call to
make on every edit. Add `--json` for the machine-readable form:

```sh
./tools/logosc.sh check broken.logos --json
```

```json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100","message":"'+' needs numbers, found :str","node_path":"broken/main/2/0","file":"broken.logos","line":0,"col":0}]}
```

## 8. Fix it and re-run the loop

```sh
sed -i 's/(+ 1 "x")/(+ 1 2)/' broken.logos
./tools/logosc.sh build broken.logos -o build/broken && ./build/broken
```

```text
3
```

## 9. Run the corpus

```sh
./tools/logosc.sh test tests --only regress
```

```text
... 33 case lines ...
33 passed, 0 failed, 0 leaked
baseline tests/summary.txt: 0 regression(s)
```

`--only regress` is the fast subset (about four seconds). The full suite is 309
cases at both optimisation levels, compares the levels with each other, and
takes about three minutes — `./tools/logosc.sh test tests`.

## 10. Ask the compiler what the language is

```sh
./tools/logosc.sh guide --json | jq -r '.codes["E0100"]'
```

```text
type mismatch
```

That manifest holds every form, type, operator, reserved name and diagnostic
code. `./tools/logosc.sh guide` prints the whole manual; `--check` proves the
committed copy is current.

## 11. Run the gates a change must pass

```sh
make test && bash tools/accept.sh
```

Six commands in total, listed in [`README.md`](../README.md#done-means-these-six-commands-pass)
and [`AGENTS.md`](../AGENTS.md). `bash tools/pr_gate.sh` runs all of them and
prints one PASS/FAIL line each.

## 12. Delete nothing you did not create

The quickstart writes `hello.logos`, `broken.logos` and `build/`. `build/` is
gitignored; the two sources are yours to keep or remove.

---

## What will bite you next

| Symptom | Cause | Fix |
|---|---|---|
| `logos: clang failed: …` | `clang` is not on `PATH` — it is needed at build time of every program | install clang 14 (`install.md`) |
| `logos: runtime not found: …` | the installation is incomplete: the runtime tree was deleted or the binary was copied out on its own | re-unpack the tarball, keeping the whole directory together |
| `E0005: unknown module 'map'` | the named module is not beside the file and not in the installation's `src/std` | check the spelling; installations ship `io`, `map` and `str` |
| `E0107: unused binding` | you left a `let` nobody reads | delete it or read it — this is an error, not a warning |
| a build seems to hang | the first build compiles the compiler | wait; it is minutes, once |
