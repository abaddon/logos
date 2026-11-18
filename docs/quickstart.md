# Quickstart — five commands to a running binary

**This is the canonical quickstart.** Two routes in, five commands each: the
release tarball (the consumer path) and a checkout (the compiler's own source).
Everything below was executed on 2026-11-18 against `logos 0.2.2`, and the
outputs are copied from that run. The transcript, command by command, is
[`distribution/03-dossiers/verification-log-2026-11-18.md`](distribution/03-dossiers/verification-log-2026-11-18.md).

- What you need, and why `clang` is one of them: [`README.md`](../README.md#requirements).
- What the compiler cannot do yet: [`reference/limits.md`](reference/limits.md).
- Every verb and flag: [`reference/cli.md`](reference/cli.md).

---

## Route 1 — install the release (the consumer path)

x86_64 Linux, glibc 2.35 or newer, `clang` 14 or newer, and `gh` for the
download (the `curl` form is below the block).

```sh
gh release download v0.2.2 --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
sha256sum -c SHA256SUMS
tar -xzf logos-0.2.2-x86_64-linux.tar.gz && cd logos-0.2.2-x86_64-linux
cat > hello.logos <<'EOF'
(mod hello)

(fn main :void ()
  (println "hello from logos"))
EOF
./bin/logosc build hello.logos -o hello && ./hello
```

```
logos-0.2.2-x86_64-linux.tar.gz: OK
hello from logos
```

The first command prints nothing when it succeeds and leaves two files in the
working directory. The middle one verifies the tarball against the checksum the
release publishes — `OK`, or `FAILED` and exit 1 with nothing to install.

Without `gh`, the same two files come from the release page:

```sh
base=https://github.com/abaddon/logos/releases/download/v0.2.2
curl -fsSLO "$base/logos-0.2.2-x86_64-linux.tar.gz" -O "$base/SHA256SUMS"
```

Unpacking *is* installing: one directory holding `bin/logosc`, the C runtime and
the standard library beside it. Nothing is written outside it, nothing is added
to `PATH`, and uninstalling is one `rm -rf` of that directory. The compiler
finds its own runtime and library from the executable's location, so it runs
from any working directory — [`install.md`](install.md) has the lookup order,
`LOGOS_ROOT`/`LOGOS_PATH`, and the packaging layout.

```sh
$ ./bin/logosc version
logos 0.2.2
```

## Route 2 — from a checkout (the compiler's own source)

x86_64 Linux with `clang` 14 or newer; Python is only for the contract tests.

```sh
git clone https://github.com/abaddon/logos && cd logos
./tools/logosc.sh version
./tools/logosc.sh build examples/hello.logos
./build/hello
./tools/logosc.sh test tests --only regress
```

```text
logos 0.2.2
hello
59 passed, 0 failed, 0 leaked
```

The first invocation compiles the compiler from `src/` with the stage-0 binary
in `bootstrap/` and prints nothing while it works — 47 seconds measured on this
machine, minutes on a slower one. Every later invocation reuses `build/logosc`
until a file in `src/` changes. `tools/logosc.sh` checks the recorded SHA-256 of
`bootstrap/logosc` on every run and refuses to proceed if it does not match.

`build examples/hello.logos` is silent and exits 0. Two files now exist:
`build/hello.ll` (the LLVM IR) and `build/hello` (the native binary). The IR is
always written; it is the artefact to read when a program misbehaves.

---

## Read a failure as data

Make it wrong:

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
    (+ 1 "x")
```

Exit status **2** — "the source is wrong". The first line is
`<node path>: <code>: <message>`; `broken/main/2/0` is the module, `main`, its
third child, that child's head. The line under it is that node, rendered, so the
broken expression is in front of you.

`check` is the same diagnosis without codegen or `clang` — the call to make on
every edit — and `--json` turns it into one object an agent can branch on:

```sh
./tools/logosc.sh check broken.logos --json
```

```json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100","message":"'+' needs numbers, found :str","node_path":"broken/main/2/0","file":"broken.logos","line":0,"col":0}]}
```

Hand the `node_path` back and the compiler prints that subtree, including the
enclosing form:

```sh
./tools/logosc.sh show broken.logos broken/main/2
```

```text
(println (+ 1 "x"))
```

The three exit codes are the contract: `0` success, `2` your source or command
line is wrong, `1` your environment is wrong (missing file, missing runtime,
`clang` failure). Details and the retry policy:
[`reference/diagnostics.md`](reference/diagnostics.md).

## Put the expectation in the file

A program states what it must do in `(test …)` nodes beside the code that does
it. No flag means both optimisation levels, and a case that disagrees between
them fails:

```sh
./tools/logosc.sh test examples/agent-gate/gate.logos
```

```text
PASS exec/gate/allows-a-listing -
PASS exec/gate/denies-a-recursive-delete -
PASS exec/gate/denies-a-plaintext-url -
PASS exec/gate/allows-an-https-get -
PASS exec/gate/denies-a-post -
PASS exec/gate/denies-an-absolute-write -
PASS exec/gate/allows-a-relative-write -
PASS exec/gate/denies-a-read-outside-the-workspace -
PASS exec/gate/denies-an-unknown-tool -
9 passed, 0 failed, 0 leaked
baseline: none
```

`examples/agent-gate/` is the reference project to copy: 174 lines, nine tests,
and a list of the rough edges its author hit
([`../examples/agent-gate/README.md`](../examples/agent-gate/README.md)).

## Ask the compiler what the language is

```sh
./tools/logosc.sh guide --json | jq -c '{forms:(.forms|length),codes:(.codes|length)}'
```

```text
{"forms":96,"codes":36}
```

That manifest holds every form, type, operator, reserved name and diagnostic
code under `schema_version: 1`. `./tools/logosc.sh guide` prints the whole
manual; `--check` proves the committed copy is current, and it is a gate.

## Run the gates a change must pass

```sh
make test && bash tools/accept.sh
```

Six commands in total, listed in
[`../README.md`](../README.md#done-means-these-six-commands-pass) and
[`../AGENTS.md`](../AGENTS.md); `bash tools/pr_gate.sh` runs all of them and
prints one PASS/FAIL line each. A compiler change additionally needs a case
under `tests/regress/` that fails before the fix and passes after it.

---

## What will bite you next

| Symptom | Cause | Fix |
|---|---|---|
| `logos: clang failed: …` | `clang` is not on `PATH` — it is needed at build time of every program | install clang 14 ([`install.md`](install.md)) |
| `logos: runtime not found: …` | the installation is incomplete: the runtime tree was deleted or the binary was copied out on its own | re-unpack the tarball, keeping the whole directory together |
| `E0005: unknown module 'map'` | the named module is not beside the file and not in the installation's `src/std` | check the spelling; installations ship `io`, `map` and `str` |
| `E0107: unused binding` | you left a `let` nobody reads | delete it or read it — this is an error, not a warning |
| a build seems to hang | the first build compiles the compiler | wait; it is minutes, once |
| `selfhost: manifest lists N files but git tracks N+1` | a `.logos` file was added, removed or renamed | `git ls-files '*.logos' \| sort > tools/selfhost-manifest.txt` |

## Where to go next

- [`reference/agent-contract.md`](reference/agent-contract.md) — the one page an
  agent needs: exit codes, JSON shapes, determinism check, traps.
- [`LOGOS.md`](LOGOS.md) — the manual, cheat sheet first, one executable chapter
  per feature.
- [`reference/language.md`](reference/language.md) — the language on one page,
  ten rules each with the code it raises.
- [`../examples/agent-gate/README.md`](../examples/agent-gate/README.md) — the
  program to fork.
- [`challenge/01-summary/program.md`](challenge/01-summary/program.md) — the
  Logos Agent Challenge: build a program, land a pull request, or port and teach.

## Cleaning up

Route 1 wrote nothing outside one directory: `rm -rf
logos-0.2.2-x86_64-linux`. Route 2 wrote `build/` (gitignored) plus the sources
you created. Nothing else was touched.
