# agent-gate: a policy gate for an agent's tool calls, in Logos

A complete, runnable Logos program in **one file and 174 lines**. It reads
proposed tool calls from standard input, allows or denies each one, and exits
with the number of denials — so a shell can gate an agent with
`agent-gate < proposed.txt || stop`.

```console
$ printf 'shell ls -la\nshell rm -rf /\nhttp GET https://example.com\n' | ./build/agent-gate
ALLOW  shell ls -la
DENY   shell rm -rf /  -- shell: recursive delete
ALLOW  http GET https://example.com
$ echo $?
1
```

## Quickstart

From a fresh clone, five commands:

```sh
git clone https://github.com/abaddon/logos && cd logos
./tools/logosc.sh build examples/agent-gate/gate.logos -o build/agent-gate
./build/agent-gate < examples/agent-gate/calls.txt; echo "exit=$?"
./tools/logosc.sh check examples/agent-gate/gate.logos     # exit 0, prints nothing
./tools/logosc.sh test  examples/agent-gate/gate.logos     # 9 PASS, 0 leaked
```

The first build also builds the compiler from `src/` with the stage-0 binary,
which takes about 50 s on one 4-core box; every later build is a second. `logosc`
shells out to `clang` at every compile, so `clang` must be on `PATH`
(`apt-get install clang-14 binutils`).

Captured output of exactly this sequence, from a clean clone:
[`EVIDENCE.md`](EVIDENCE.md).

## Input format

One call per line, `tool argument...`. Blank lines are ignored, and the exit
code is the number of denied calls, capped at 125.

| Tool | Allowed when | Example |
| --- | --- | --- |
| `shell` | the command has no `rm -rf`, no `sudo`/`su `, no `>`, `|` or `;` | `shell ls -la` |
| `http` | the method is `GET` and the URL starts with `https://` | `http GET https://example.com` |
| `write` | the path starts with `./` | `write ./notes/todo.md buy milk` |
| `read` | the path is not under `/etc` or `/root` | `read ./README.md` |
| anything else | never | `browser navigate x` → denied |

Denials carry a reason, and an unknown tool is denied rather than ignored, so a
call the policy does not understand cannot slip through.

## What the program shows

| Logos feature | Where |
| --- | --- |
| `(type … (enum …))` and `match` over its variants | `verdict`, `report` |
| a user-defined type as a return type | every `check-*` function |
| byte-level string handling with no standard library | `starts-with`, `contains`, `space-at` |
| `(read-all)`, a `while` loop and `(str-slice)` as a splitter | `main`, `line-end` |
| exit codes as a value | `main` returns the denial count |
| tests inside the source | the nine `(test …)` nodes |

No allocation is released anywhere, because there is nothing to release: `:str`
values are not owners and `str-slice` returns views. The test run reports
`0 leaked`, and the same program behaves identically at `-O0` and `-O2`.

## Remix this

Three extensions that fit in an afternoon:

1. **Policy from a file.** Move the rules out of `check-*` into a text file of
   `tool pattern verdict` lines, read it with `(read-file)` and split it with
   `(use str)` + `string-split`. `string-split` borrows the string it splits and
   returns views into it, so the file's text must outlive every field — a small
   exercise in the language's ownership rule.
2. **JSON output for a machine caller.** Emit one line per call as
   `{"tool":"shell","verdict":"deny","reason":"recursive delete"}`. There is no
   escaping helper: you add one, with a `(test …)` node per case that needs it.
3. **A per-session budget.** Count calls per tool in a `(vec :i64)` and deny
   past a limit, so the gate enforces "ten shell calls per task" as well as
   shape. Threads (`(spawn …)` over a `(shared (atomic :i64))`) turn the counter
   into its concurrency-safe form.

## Rough edges found while writing this

The point of this directory is to be copied, so the frictions are listed rather
than hidden. Items 1 and 2 are compiler errors that were actually hit while
producing `gate.logos`; the rest are properties of the language and the library
that were checked in the documentation while deciding how to write it.

1. **Logos has no comments.** The first draft opened with a `;` header line and
   the compiler said `gate.logos:3:1: E0001: form outside parentheses` — a
   diagnostic that never mentions comments. `src/logosc/lex.md` is explicit
   ("Logos has no comments and no doc form"), but a newcomer learns it from the
   error.
2. **A user type in a signature is spelled differently from a primitive.**
   `(fn judge :i64 …)` but `(fn judge verdict …)`; writing `(fn judge :verdict …)`
   is `agent-gate/judge: E0101: unknown type ':verdict'`, which names a type
   containing a colon no one meant to write. The cheat sheet's signature
   examples are all primitives, so the asymmetry is learned by error.
3. **There is no string-to-integer parse anywhere in the stdlib** (a stated gap
   in `docs/reference/limits.md`), so a rule such as "allow `spend 100`, deny
   `spend 1000`" needs a digit parser written first. That rule is absent here.
4. **A `:str` allocation can never be freed and never appears in the leak
   report** (`docs/reference/language.md`). The language's promise is that every
   allocation is visible and released by hand; strings are the exception, so a
   long-lived gate that builds a reason string per call grows without bound.
   This demo therefore denies with compile-time constant reasons.
5. **The `str` module would have removed ~30 lines** (`string-split`,
   `string-find`, `string-starts-with`) at the cost of an import and a
   two-file program. This demo is one file with no imports on purpose; the
   scanning helpers in it are what a Logos program without the stdlib looks
   like.
6. **`clang` is a dependency of every compile, not only of the compiler's
   build.** `docs/install.md` says so plainly, and this environment has it, so
   the failure was not hit here — on a container without `clang` the front end
   accepts the program and the build dies at the link step.
