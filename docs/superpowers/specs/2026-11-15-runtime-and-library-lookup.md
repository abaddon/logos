# The runtime and the standard library are found by the compiler's location — design

Design document. 2026-11-15. Status: implemented in this change.

This is D2, D3 and D-1 of the v1 readiness audit (the last three of the seven
S1 gaps). It changes no syntax, no AST and no IR shape: it changes where the
compiler looks for the two files it needs, and gives the failure a code.

## Intent

The compiler was packaged, released and installable before this change, and
installing it still meant *running it from the unpacked directory*. Both
lookups were resolved from the working directory:

```
$ cd /tmp && /prefix/logos-0.1.0-x86_64-linux/bin/logosc build /prefix/hello.logos -o hello
hello/0: E0005: unknown module 'str'

$ cd /tmp && /prefix/logos-0.1.0-x86_64-linux/bin/logosc build /prefix/hello.logos -o hello
logos: runtime not found: logos/runtime/rt.c          # exit 1, no code, no node
```

`main-runtime` returned the literal `"logos/runtime/rt.c"` and `resolve-stdlib`
was `resolve-sibling` over the literal `"src/std"`. Both are relative paths, so
both named the *caller's* directory. Inside the prefix the paths happen to be
right, which is why `tools/verify_install.sh` was 5/5 and every gate was green.

The second line is the worse one. It is the only failure an agent cannot
classify: no diagnostic code, no node path, and a message that reads as if the
user's program were at fault. Everything else the compiler refuses carries an
`E0xxx` code and a location.

## Goals

1. Both lookups resolve relative to the executable, so the binary alone decides
   which runtime and which library it uses.
2. `LOGOS_ROOT` overrides the prefix, and `LOGOS_PATH` adds module directories.
3. The working directory stays the *last* entry in both search orders: the
   repository's own gates, fixtures and `tests/` build with relative paths.
4. A failure prints the order it searched, with a code and a location.
5. No new language form: the repository's `extern` mechanism is enough, so the
   compiler's source, the corpus and the 90-file IR parity list are untouched.

## Non-goals

- An installed layout under `share/logos/`. `tools/dist.sh` already stages the
  runtime at `logos/runtime/rt.c` and the library at `src/std/` inside the
  prefix, exactly as the checkout spells them, so one rule serves both.
- A config file, a `--prefix` flag or per-project resolution. Three inputs are
  enough to look at when a build cannot find its files: the executable's path,
  one override, and the working directory.
- Making the *produced* program environment-dependent. The lookup is the
  compiler's; a compiled binary embeds nothing.
- Windows or macOS. `/proc/self/exe` is Linux, and so is the only target the
  compiler emits.

## The rule

The prefix (`root`) is `LOGOS_ROOT` when it is set and non-empty, otherwise the
parent of the directory holding the executable, taken from `/proc/self/exe`:

```
/prefix/bin/logosc      ->  /prefix          (an install, and a symlink to one)
/repo/build/logosc      ->  /repo            (a checkout, built by tools/logosc.sh)
```

`/proc/self/exe` is the kernel's answer, so every symlink in the path is already
resolved: a `logosc` linked into `~/.local/bin` still names the prefix it really
lives in. `argv[0]` would not do, because a shell, a wrapper script or `execvp`'s
own search may rewrite it.

**The runtime**, first regular file wins:

1. `<root>/logos/runtime/rt.c`
2. `logos/runtime/rt.c` — the working directory, last

**A module for `(use name)`**, first regular file wins:

1. `<dir of the asking file>/<name>.logos` — a local module shadows the library
2. `<entry 1 of LOGOS_PATH>/<name>.logos` … `<entry n>` — skipped when unset;
   empty entries are dropped, as `$PATH` drops them
3. `<root>/src/std/<name>.logos`
4. `src/std/<name>.logos` — the working directory, last

`LOGOS_PATH` entries and the two cwd-relative entries may be relative; they are
then relative to the working directory like any other path the compiler is
given. `<root>` is not normalised beyond dropping trailing slashes.

Order matters and is the whole design. A local module still shadows the library
(unchanged behaviour, pinned by the `origins` and `dup` fixtures), an explicit
`LOGOS_PATH` beats the shipped library (that is what an override is for), and
the working directory is consulted only after everything the compiler knows
about itself and its environment has been tried — so a stale `src/std/` in the
caller's directory can no longer win over the library the binary shipped with.

## How the compiler reaches those two facts

The language had no way to read the environment or its own path, and adding a
builtin would have changed the front end, the guide table, the manual and every
fixture that enumerates reserved forms. It does not have to: `(extern fn …)`
already binds a C symbol, and a `:str` crossing the boundary as an argument is
documented as a `(ptr, len)` pair. This change states the return half of that
rule and uses it:

```c
typedef struct { unsigned char *data; size_t len; } rt_slice;

rt_slice rt_exe_path(void);                       /* /proc/self/exe, resolved */
rt_slice rt_getenv(const unsigned char *name, size_t n);
```

An `extern fn … :str` lowers to exactly `{ i8*, i64 }` in the IR, so a runtime
function can build a string and hand it back with no out-pointer and no compiler
change. Both buffers are process-lifetime and untracked, like every other string
the runtime builds: a `:str` owns nothing, so there is no owner to free it for.

`src/logosc/sys.logos` is the one module that declares those two externs and
turns them into the policy above (`sys-root`, `sys-join`, `sys-split-paths`,
`sys-list`), so `main.logos` and `resolve.logos` share one answer to "what is
the prefix" instead of two.

## The diagnostics

| failure | before | after |
|---|---|---|
| a missing module | `greet/0: E0005: unknown module 'str'` | `greet/0: E0005: unknown module 'str'; searched: /abs/str.logos, /nope/src/std/str.logos, src/std/str.logos` |
| a missing runtime | `logos: runtime not found: logos/runtime/rt.c`, exit 1 | `<file>: E0800: runtime not found; searched: /nope/logos/runtime/rt.c, logos/runtime/rt.c`, exit 1 |

`E0800` is new and is the reason this change is worth making even where the
lookup order is unchanged: `runtime not found` was the one failure shape with no
code and no location, so an agent could not tell "your program is wrong" from
"this installation is wrong" by reading it. It is printed at the file being
built, with the exit status the exit-code table already gives a toolchain
failure, exactly like `E0103: no 'main' function to build` — a diagnostic with
no source node names the file, not a node path it does not have.

The `E0005` message gains the searched list and keeps its code and its `use`
node path. Both messages end with the working-directory entry, which is what
tells a reader the file they can see in front of them was *not* the one used.

## What this costs

- Up to three child processes per uncached import instead of two: the sibling,
  the prefix's library, the working directory. `resolve-exists` still asks `test
  -f`, and the cwd entry is only probed when the others miss. In the repository
  every import now probes `<repo>/src/std/<name>.logos` and stops, so the extra
  probe is one `test -f` per uncached import — measured at under a millisecond
  each in the suites' own runs.
- A build outside every layout still pays one `readlink` and two `getenv`s at
  process start, in the runtime, at no visible cost.
- Two functions in every linked program's runtime, whether it calls them or not.

## How it is pinned

| claim | test |
|---|---|
| both paths resolve with the binary alone, from any cwd | `tests/test_install.py::InstallLayoutTest` |
| a symlink to the binary names the real prefix | `…::test_a_symlinked_compiler_resolves_to_its_real_prefix` |
| `LOGOS_ROOT` overrides, `LOGOS_PATH` adds | `…::test_logos_root_overrides_the_prefix`, `…::test_logos_path_adds_a_module_directory` |
| the working directory is still last | `…::test_the_working_directory_is_still_the_last_entry` |
| a missing module prints the order | `tests/test_install.py::DiagnosticTest` |
| a missing runtime is `E0800` with the order, and leaves no IR | `…::test_a_missing_runtime_is_a_classified_diagnostic` |
| the two runtime functions, from Logos | `tests/regress/runtime-locate.logos` |
| the policy functions | `src/logosc/sys_test.logos` (10 cases) |
| the tarball still installs and now builds from outside itself | `tools/verify_install.sh` check 6 |
| `(use map)` from the manual still resolves | `docs/manual/20-modules.logos` in the corpus |
