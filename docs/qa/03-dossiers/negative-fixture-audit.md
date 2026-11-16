# Negative-fixture audit — 147 sidecars, and who judged each one

Measured with `python3 -m unittest tests.test_qa` plus the scratch sweep that
numbers it: every `*.expect` sidecar under `tests/` was paired with its source,
the source was built with `build --json` (materializing `‹name›.logos.txt` into a
scratch copy first, exactly as the resolver phase of `tools/selfhost.sh` does),
and the emitted code was compared with the sidecar.

## The numbers

| Population | Count |
|---|---|
| `*.expect` sidecars | 147 |
| Sources that carry a `.logos` suffix | 145 |
| Sources that must not (lex/parse errors), kept as `.logos.txt` | 2 |
| Compiler emits exactly the claimed code | **144** |
| Compiler disagrees | **3** |
| Registered as agreeing-but-unjudged before this pass | 3 (`unbound`, `struct-owner-mismatch/program`, `unknown-field`) |
| Judged by `tools/selfhost.sh`'s checker phase (listed in `tools/selfhost-check.txt`) | 126 |
| Judged by `tools/selfhost.sh`'s resolver phase (`tests/parse/**`) | 13 |
| Judged by **neither** gate before this pass | **6** |

The six: `tests/generics/limit.logos`, `tests/generics/unbound.logos`,
`tests/regress/generic-vector.logos`, `tests/regress/owner-place-read.logos`,
`tests/regress/struct-owner-mismatch/program.logos`,
`tests/type/unknown-field.logos` (the last was added by this pass).

## The three disagreements, verbatim

### `tests/generics/limit.logos` — claims `E0500`, compiler accepts the program

```console
$ ./build/logosc build tests/generics/limit.logos --opt -O0 --json ; echo $?
0
$ ./build/logosc build tests/generics/limit.logos --opt -O2 --json ; echo $?
0
$ ./build/logosc check tests/generics/limit.logos --json ; echo $?
0
```

`E0500` ("instantiation limit reached", `check_test.logos:790` pins a case that
does emit it) is real. This fixture does not reach it: it is 10 KB of repeated
generic instantiations, and the checker's 256-instantiation limit is not
tripped by them as written. The case has been reported `PASS` since it was
added, because the harness short-circuits on a sidecar.

### `tests/regress/generic-vector.logos` — claims `E0402`, compiler says `E0104`

```console
$ ./build/logosc build tests/regress/generic-vector.logos --json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0104",
"message":"cannot free immutable binding 'w'","node_path":"generic-vector/f/3",
"file":"tests/regress/generic-vector.logos","line":0,"col":0}]}
$ echo $?
2
```

The fixture binds `w` with `let` and then calls `(vec-free w)`:

```logos
(fn f :i64 ()
  (let w (same (make (vec :i64))))
  (vec-free w)
  (ret 0))
```

`E0104` is the first error the checker finds, so the case never reaches the
`E0402` ("vector value not copyable") it was written for. The case means to pin
copyability, and today it pins nothing — it would pass with either behaviour.

### `tests/regress/owner-place-read.logos` — claims `E0402`, and neither verb says it

```console
$ ./build/logosc check tests/regress/owner-place-read.logos ; echo $?
0
$ ./build/logosc build tests/regress/owner-place-read.logos --json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0103",
"message":"no 'main' function to build","node_path":"owner-place-read.logos",
"file":"tests/regress/owner-place-read.logos","line":0,"col":0}]}
```

The program is one function that dereferences a `(ptr (own :i64))` parameter.
`check` accepts it — which is the point of a regression case for a defect where
reads through an owner place were once mis-handled — and `build` stops before
the body because there is no entry point. So the sidecar's `E0402` is what
neither verb says: for this program it belongs to a different shape of case.
It is a *positive* case carrying a negative sidecar, and it is judged by nothing.

## The one code-level gap

`E0201` is published in `logosc guide --json` ("field type mismatch") and emitted
by no code in `src/`:

```console
$ ./build/logosc build /tmp/field.logos --json     # (type point (struct (x :i64))) ... (make point "not a number")
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100",
"message":"field 'x' of 'point' expects :i64, found :str", ...}]}
$ grep -rn 'E0201' src/logosc/*.logos
src/logosc/guide.logos:48:  (vec-push out "E0201")
```

The table advertises a code the compiler cannot produce. Either the checker
should use `E0201` for that message, or the table should drop the row; both are
compiler changes and are out of scope for a QA pass.

## What the sweep found while it was being written

- `tests/generics/unbound.logos` claims `E0501`; `logosc build` emits it and
  `logosc check` does not (the unbound type variable is only detected when the
  generic is instantiated while lowering). The fixture is correct; the sweep
  uses `build` for exactly this reason.
- `tests/parse/unbalanced.logos` was first added as a `.logos` file and the
  corpus reported `FAIL parse/unbalanced parse failed: unbalanced '('` — because
  the *harness* has to parse the fixture to find its directives. That is why the
  repository keeps such fixtures as `.logos.txt`; the sweep materializes them.
- `tests/regress/struct-owner-mismatch/program.logos` disagrees with nothing; it
  was simply in the neither-gate hole, and it agrees under both verbs.

## What is still not measured

The *message text* of a diagnostic is pinned by the checker suites
(`src/logosc/check_test.logos`, 81 cases) and by the `.check` sidecars the
self-hosting gate compares, not by this sweep. The sweep pins the code, the
shape and the locatability of the document — the machine surface, which is what
an agent parses.

SOURCES (LAYER 3 — EVIDENCE)

/root/ai-language-program/.worktrees/t_5bd6660b/tests/test_qa.py
 -> The sweep itself: `negative_fixtures`, `materialize`, `judged`.

/root/ai-language-program/.worktrees/t_5bd6660b/tools/qa-known-gaps.txt
 -> The four registered disagreements with the same measurements, and the rule
    that the register may shrink but not grow.

/root/ai-language-program/.worktrees/t_5bd6660b/tools/selfhost-check.txt
 -> The 126 fixtures whose whole diagnostic line the self-hosting gate compares.

/root/ai-language-program/.worktrees/t_5bd6660b/src/logosc/harness.logos
 -> `h-file-parsed`: the short-circuit that made these cases unable to fail.
