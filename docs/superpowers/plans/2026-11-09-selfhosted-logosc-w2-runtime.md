# Self-hosted `logosc`, wave W2: the six forms and the runtime behind them

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a Logos program can read a file, see its own arguments, walk a string byte by byte, turn an integer into text, take a float's bits, and run a child process and read what it said — the six capabilities the Logos-written compiler needs before a single line of it can be written.

**Architecture:** four of the six are small forms over the existing C runtime; `read-file` builds a result; `run` returns a new opaque handle `:run` with three accessors, the same shape `:thread`, `:mutex` and `:chan` already have. The C runtime gains four functions: an open-for-writing, a whole-file read by path, the process arguments, and a spawn-with-two-pipes-and-a-wait.

**Tech Stack:** Python 3.14 standard library, `unittest`, LLVM IR text, clang, `logos/runtime/rt.c` (POSIX).

**Spec:** `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md` D5 and D10.

## Global Constraints

- Every commit carries `Signed-off-by:` matching its author (`git commit -s`).
- Six forms and one new primitive type, exactly: `(read-file p)`, `(args)`, `(str-byte s i)`, `(str-from-i64 v)`, `(f64-bits v)`, `(run prog args)`, and `:run` with `(run-status r)`, `(run-out r)`, `(run-err r)`.
- `(read-file p)` is `(res :str :i64)`: the ok arm is the whole file, the err arm is `errno`. It panics on nothing.
- `(run prog args)` takes a `:str` and a `(vec :str)`; no shell; the args vec is moved. `status` is the exit code, or `128 + signal`. A spawn failure is `R0006` with the program name. The child is killed after 30 s and reports 124.
- A new runtime function never prints and never exits: it returns, or it calls `rt_panic` with a code and a path.
- Every form rejects a wrong argument type with `E0100` at the argument, and a wrong arity with `E0102`.
- No IR change for a program that uses none of these forms.
- One manual chapter, number 19, runnable, in `docs/manual/`.

## Review Focus

1. `(read-file "/dev/null")` is the empty string with errno 0, and a missing path is the err arm, not a panic. (Task 3)
2. A file of 1 MiB reads back byte for byte, and the runtime's buffer is not leaked into the report. (Task 2)
3. `(run "sh" ["-c" "echo hi"])` gives status 0 and out `hi\n`; `(run "false" …)` gives 1; a chatty child on both streams does not deadlock. (Task 2)
4. `(run "definitely-not-a-program" …)` is `R0006` with the name and the node path. (Task 2)
5. `(args)` has at least one element (the program) and reads back what the shell passed it. (Task 3)
6. `(f64-bits 1.5)` equals `4609434218613702656`, the same bits the emitter writes as hex. (Task 3)

---

### Task 1: The spec, chapter 19, and the failing cases

**Files:**
- Modify: `docs/superpowers/specs/2026-11-06-ai-language-design.md` (a "Runtime access" section) and `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md` (D5's `run` row: an opaque handle with three accessors, not a struct)
- Create: `docs/manual/19-runtime-access.logos`
- Create: `tests/exec/read-file.logos`, `tests/exec/args.logos`, `tests/exec/str-tools.logos`, `tests/exec/run.logos`

**Interfaces:**
- Consumes: nothing.
- Produces: the four cases the rest of the wave turns green, and chapter 19.

- [ ] **Step 1: Write the spec sections**

Add to the language spec, after the string section:

> A program can read a file, see its arguments, and run a child process. `(read-file p)` is a
> result: the ok arm holds the whole file, the err arm an `errno`. `(args)` is the command
> line, the program's own path first. `(run prog args)` starts a process with no shell,
> captures its output, and returns a `:run` handle whose status, stdout and stderr are read by
> `(run-status r)`, `(run-out r)` and `(run-err r)`. Nothing here hides a failure: a file
> that cannot be read is a value, and a program that cannot start is a diagnostic.

And in D5's table row for `run`, replace the struct with the handle and its three accessors.

- [ ] **Step 2: Write chapter 19**

`docs/manual/19-runtime-access.logos`: one module that prints its own argument count, reads
`/dev/null` and shows the empty result, prints one byte of a literal, prints
`(str-from-i64 -42)`, prints `(f64-bits 1.5)`, and runs `sh -c "echo hi"` and prints the
status and the output. One `(test …)` with the full expected stdout. It must be
`fmt`-canonical and it joins the generated manual as chapter 19.

- [ ] **Step 3: Write the four failing cases**

`tests/exec/str-tools.logos`:

```logos
(mod str-tools)

(test str-tools
  (expect (out "98\n-42\n4609434218613702656\n") (code 0) (leaks 0))
  (println (str-byte "abc" 1))
  (println (str-from-i64 -42))
  (println (f64-bits 1.5)))
```

`tests/exec/read-file.logos`: read `/dev/null` and assert `(str-len (ok (read-file "/dev/null")))` is 0, then read a missing path and assert the err arm is nonzero. `tests/exec/args.logos`: assert `(vec-len (args))` is at least 1. `tests/exec/run.logos`: `(run "sh" […])` is not directly writable, because the args argument is a `letmut (vec :str)` — build it with `vec-push`, run `sh -c "echo hi"`, print the status and the output. Model each on `tests/exec/read/*.logos` and the strings chapter.

- [ ] **Step 4: Record the failures**

Run: `python3 -m logos test --only exec 2>&1 | grep -E "read-file|args|str-tools|run/"`.
Expected: four FAIL lines, each naming an unknown function or an unknown type form.

- [ ] **Step 5: Commit**

```bash
git switch -c feat/selfhost-w2-runtime
git add docs/superpowers/plans/2026-11-09-selfhosted-logosc-w2-runtime.md docs/superpowers/specs docs/manual/19-runtime-access.logos tests/exec/read-file.logos tests/exec/args.logos tests/exec/str-tools.logos tests/exec/run.logos logos/guide.py
git commit -s -m "docs: spec and chapter 19 for the runtime forms, with the failing cases"
```

`logos/guide.py` gains the chapter title, as chapter 18 did.

---

### Task 2: The runtime functions

**Files:**
- Modify: `logos/runtime/rt.c`, `logos/runtime/rt.h`
- Test: `tests/exec/run.logos`, `tests/exec/read-file.logos` (they go green in Tasks 3 and 4)

**Interfaces:**
- Produces, in `rt.h`:
  - `long rt_create(const unsigned char *path, size_t n)`
  - `size_t rt_read_file(const unsigned char *path, size_t n, int *err)`
  - `size_t rt_args(size_t *count)` filling a process-lifetime array of `(ptr,len)` pairs
  - `rt_run *rt_run_start(const unsigned char *prog, size_t pn, const unsigned char **argv, const size_t *argn, size_t argc)`
  - `long rt_run_status(rt_run *r)`, `const unsigned char *rt_run_out(rt_run *r, size_t *n)`, the same for `err`

- [ ] **Step 1: Write the runtime, in one commit**

`rt_create` opens with `O_WRONLY|O_CREAT|O_TRUNC, 0644`. `rt_read_file` opens, `fstat`s, reads
in a loop, and returns the buffer with `err` set. `rt_args` reads `/proc/self/cmdline` from a
constructor, so the emitted `main` signature does not change. `rt_run_start` uses
`posix_spawn` with two pipes, drains both with one `poll` loop until both reach EOF, then
`waitpid`, kills after 30 s and reports 124. Every allocation is `rt_alloc` with a path
argument so the leak tracker sees it; the pipeline frees the child's buffers when the handle
is freed by the caller's `vec-free`-equivalent? No: the handle lives for the process, and the
design records that (`shortcut: a run handle is process-lifetime; upgrade if a compiler ever
runs a million processes`).

- [ ] **Step 2: Prove the runtime still links and builds clean**

Run: `make test` and `python3 -m logos test --only exec 2>&1 | tail -3`
Expected: unchanged results. Nothing calls the new functions yet, so this step proves
`rt.c` compiles under both `-DLOGOS_DEBUG` and release, and that no existing program's
behaviour moved. The new functions are exercised by the cases in Tasks 3 and 4.

- [ ] **Step 3: Commit**

```bash
git add logos/runtime/rt.c logos/runtime/rt.h
git commit -s -m "feat: runtime for files, arguments and child processes"
```

---

### Task 3: The five simple forms

**Files:**
- Modify: `logos/check.py`, `logos/lower.py`, `logos/llvm.py` if a type is needed
- Test: `tests/test_runtime_forms.py` (new), `tests/exec/{read-file,args,str-tools}.logos`

**Interfaces:**
- Produces: `(read-file p) :(res :str :i64)`, `(args) :(vec :str)`, `(str-byte s i) :u8`, `(str-from-i64 v :i64) :str`, `(f64-bits v :f64) :i64`.

- [ ] **Step 1: Failing unit tests**, one per form, in `tests/test_runtime_forms.py`, each asserting the type the checker gives the form and the wrong-argument diagnostic (`E0100`) and wrong arity (`E0102`).

- [ ] **Step 2: Add the forms to the checker**, in the family that already holds `str-len`, `str-concat`, `str-eq`, `str-slice`: `str-byte` takes `(str, integer)` and returns `:u8`; `str-from-i64` takes an integer and returns `:str`; `f64-bits` takes `:f64` and returns `:i64`; `read-file` takes a `:str` and returns `(res :str :i64)`; `args` takes nothing and returns `(vec :str)`.

- [ ] **Step 3: Add their lowering**, `read-file` through `rt_read_file` building both arms of the result, `args` through `rt_args` building a vector of fat pointers, `str-byte` a `load i8` through the string's data pointer with a bounds check that panics `R0003`, `str-from-i64` through `rt_str_from_i64`, `f64-bits` a `bitcast`.

- [ ] **Step 4: Run the three cases and the suite**, at both levels.

- [ ] **Step 5: Commit**

---

### Task 4: `(run …)` and `:run`

**Files:**
- Modify: `logos/types.py` (the `:run` primitive), `logos/check.py` (the form and the three accessors), `logos/lower.py` (the calls and the handle type), `logos/llvm.py` (the handle's IR type), `logos/diag.py` (`R0006`)
- Test: `tests/test_run_form.py` (new), `tests/exec/run.logos`

**Interfaces:**
- Produces: `(run prog args) :(:run)`, `(run-status r) :i64`, `(run-out r) :str`, `(run-err r) :str`, and `R0006` "a program could not be started".

- [ ] **Step 1: Failing tests** for the form's types, the accessors' types, `E0100` for a non-`(vec :str)` second argument, and the moved-argument rule (the args vec is consumed).

- [ ] **Step 2: `:run` as an opaque primitive**, beside `:thread` and `:mutex`, with its IR type a pointer to the runtime's struct.

- [ ] **Step 3: The form and the accessors**, lowered to `rt_run_start` and the three readers.

- [ ] **Step 4: `R0006`**, with the code table line and the manual regeneration.

- [ ] **Step 5: Run `tests/exec/run.logos`** at both levels, plus the chatty-child case from Review Focus 3 as a unit test with a program that writes 200 KiB to both streams.

- [ ] **Step 6: Commit**

---

### Task 5: The baseline, the gates, the pull request

- [ ] **Step 1: `python3 -m logos test --update-baseline`**, name the new cases in the commit.
- [ ] **Step 2: `python3 -m logos guide > docs/LOGOS.md`** and `--check`.
- [ ] **Step 3: `bash tools/pr_gate.sh`** → 5/5.
- [ ] **Step 4: push, open the PR with the template filled, and squash-merge with the admin bypass** once its CI gate passes. That is the standing instruction for this repository.

## Later waves

W3 is the Logos standard library; W4 to W9 the compiler itself.
