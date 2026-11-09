# Self-hosted `logosc`, wave W1: the `(ref T)` parameter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a function can take a non-owning reference to a caller's vector, read it, grow it and free it, without the call moving the caller's binding — which is what lets a compiler keep its arenas in `main` and pass them to helpers.

**Architecture:** `(ref (vec T))` is a new type form and a new kind of parameter. At the call the caller passes the address of its own descriptor slot, so the callee mutates the caller's descriptor in place; nothing is copied and nothing moves. A ref cannot leave the call: it cannot be returned, stored, captured, or handed to a form that keeps a value.

**Tech Stack:** Python 3.14 standard library, `unittest`, LLVM IR text, clang, the C runtime unchanged.

**Spec:** `docs/superpowers/specs/2026-11-08-self-hosted-logosc-design.md` (D5's `(ref T)` paragraph) and `docs/superpowers/specs/2026-11-06-ai-language-design.md`.

## Global Constraints

- Every commit carries `Signed-off-by:` matching its author (`git commit -s`).
- `(ref T)` names a **vector only**. `(ref :i64)` and `(ref point)` are refused; refusing is the rule, not a missing feature.
- A ref is legal in exactly one position: a source function's parameter. Not a return type, not a binding's type, not a struct field, not a generic argument, not an `extern` parameter.
- The argument must be a `letmut` binding or another `(ref …)` parameter. Passing it does not move it, and the caller may use and free it afterwards.
- A ref must not escape its call. One predicate, applied at every site that keeps a value: return, struct field, `vec-push`, enum payload, closure capture, `set-field`, `alloc` element, and an argument to a parameter that is not itself a ref.
- Two new diagnostic codes: **E0304** "a ref argument must be a mutable binding", **E0305** "a ref cannot escape the call". Both enter `diag.CODES`, the generated manual, and a regress case.
- No behaviour change for source without `(ref …)`: the corpus must stay green, and the existing IR of every corpus file must be unchanged.
- Every task ends with `make test` and the corpus green for what exists so far.

## Review Focus

1. A helper pushes through a ref and the caller's `vec-len` grows; the caller then frees it. (Task 4)
2. A ref argument that is not `letmut` is E0304 at the argument, not a move. (Task 3)
3. A ref returned from its function is E0305 at the `ret`, and the program still checks when the result is a plain vector. (Task 3)
4. A ref captured by a closure inside the function is E0305 at the captured use, because the frame dies before the closure could run. (Task 3)
5. Two ref parameters of one function, one pushed through each: the right descriptor grows each time. (Task 4)

---

### Task 1: The spec paragraph, the manual chapter, and the failing case

**Files:**
- Modify: `docs/superpowers/specs/2026-11-06-ai-language-design.md`
- Create: `docs/manual/18-ref-parameters.logos`
- Create: `tests/exec/ref-param.logos`

**Interfaces:**
- Consumes: nothing.
- Produces: the case `exec/ref-param/ref-param` that Tasks 3 and 4 must turn green, and the manual chapter `docs/LOGOS.md` will carry as chapter 18.

- [ ] **Step 1: Write the spec section**

Add a section after the one that describes vectors:

> A function may take `(ref (vec T))`, a non-owning reference to a caller's vector. The
> call passes the caller's own descriptor, so a `vec-push`, `vec-set` or `vec-free` inside
> the callee acts on the caller's vector and the caller keeps using it afterwards. The
> argument must be a mutable binding or another ref parameter. A ref is a parameter kind
> and nothing else: it cannot be returned, stored in a field or a container, held in an
> enum payload, captured by a closure, or passed where a value is expected. A ref is how
> a program keeps one arena in one function and lets helpers grow it.

- [ ] **Step 2: Write the manual chapter**

`docs/manual/18-ref-parameters.logos` — a module with one helper that pushes through a
ref, one test that shows the caller's length after the call, and the expected output in
the test's `(expect …)` directive. It must be `fmt`-canonical and it must run once Task 4
lands. Model it on `docs/manual/08-vectors.logos`.

- [ ] **Step 3: Write the failing corpus case**

`tests/exec/ref-param.logos`:

```logos
(mod ref-param)

(fn grow :void ((v (ref (vec :i64))))
  (vec-push v 7))

(test ref-param
  (expect (out "2\n7\n") (code 0) (leaks 0))
  (letmut v (vec :i64) (make (vec :i64)))
  (vec-push v 1)
  (grow v)
  (println (vec-len v))
  (println (vec-get v 1))
  (vec-free v))
```

- [ ] **Step 4: Record the failure**

Run: `python3 -m logos test --only exec 2>&1 | grep ref-param`
Expected: `FAIL exec/ref-param/ref-param -O0: build failed: ...` naming an unknown type or
an unknown form, because neither the type nor the parameter kind exists yet. Copy the
exact line into the commit message.

- [ ] **Step 5: Commit**

The plan itself is untracked; it travels in this branch.

```bash
git switch -c feat/selfhost-w1-ref
git add docs/superpowers/plans/2026-11-09-selfhosted-logosc-w1-ref.md docs/superpowers/specs/2026-11-06-ai-language-design.md docs/manual/18-ref-parameters.logos tests/exec/ref-param.logos
git commit -s -m "docs: spec and manual chapter for non-owning ref parameters, with the failing case"
```

Do not regenerate `docs/LOGOS.md` in this commit; Task 3 regenerates it once the type
form exists in the compiler tables.

---

### Task 2: The `Ref` type

**Files:**
- Modify: `logos/types.py` (`FORMS`, a `Ref` dataclass, `parse_type`, `compatible`)
- Test: `tests/test_types.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `types.Ref(elem: Ty)`, frozen and slotted, printed as `(ref <elem>)`;
  `parse_type` accepting `(ref (vec T))` and nothing else; `compatible` comparing two
  refs by their element and a ref against anything else as false.

- [ ] **Step 1: Write the failing tests**

In `tests/test_types.py`, following the file's existing helpers:

```python
def test_a_ref_of_a_vector_parses(self):
    ty = parse_type("(ref (vec :i64))")
    self.assertEqual(ty, Ref(Vec(Prim("i64"))))
    self.assertEqual(str(ty), "(ref (vec :i64))")

def test_a_ref_of_a_primitive_is_refused(self):
    with self.assertRaises(LogosError) as caught:
        parse_type("(ref :i64)")
    self.assertEqual(caught.exception.code, "E0100")

def test_two_refs_are_compatible_only_with_the_same_element(self):
    self.assertTrue(compatible(Ref(Vec(Prim("i64"))), Ref(Vec(Prim("i64")))))
    self.assertFalse(compatible(Ref(Vec(Prim("i64"))), Vec(Prim("i64"))))
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `python3 -m unittest tests.test_types -k ref -v`
Expected: FAIL, `Ref` is not defined.

- [ ] **Step 3: Add the type**

Add `"ref"` to `FORMS`. Add the `Ref` dataclass beside `Vec`, with `elem: Ty` and
`__str__` returning `f"(ref {self.elem})"`. In `parse_type`, the `ref` head takes exactly
one type item and it must parse to a `Vec`; anything else raises `diag(E0100, path,
"a ref may name a vector only")`. In `compatible`, `Ref` compares its element and a `Ref`
against any other kind is false.

- [ ] **Step 4: Run the tests and the suite**

Run: `python3 -m unittest tests.test_types -v` then `make test`
Expected: PASS. `FORMS` feeds the manual's type table, so `docs/LOGOS.md` now differs:
regenerate it here with `python3 -m logos guide > docs/LOGOS.md` and confirm
`python3 -m logos guide --check` exits 0. Each commit keeps the generated manual current;
Task 3 regenerates again when the two codes arrive.

- [ ] **Step 5: Commit**

```bash
git add logos/types.py tests/test_types.py docs/LOGOS.md
git commit -s -m "feat: a (ref (vec T)) type"
```

---

### Task 3: The checker: ref parameters, the argument rule, and the escape refusals

**Files:**
- Modify: `logos/diag.py` (E0304, E0305), `logos/check.py` (`_Var`, `_check_fn`, `_arguments`, `_vec_target`, and one refusal at each storage site)
- Create: `tests/type/ref-not-mutable.logos`, `tests/type/ref-escapes-return.logos`, `tests/type/ref-escapes-capture.logos`, `tests/type/ref-not-a-vector.logos` (each with a `.expect` holding its code)
- Test: `tests/test_ref.py` (new)

**Interfaces:**
- Consumes: `types.Ref` from Task 2.
- Produces: `_Var.ref: bool`; a `(ref (vec T))` parameter accepted; `_ref_arg(node, env, index)` returning the argument's `_Var` or raising E0304; `_refuse_ref(ty, where, what)` raising E0305; `_vec_target` accepting a ref variable and returning the underlying `Vec`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ref.py`, built like `tests/test_link.py`'s single-module cases: one helper that
checks a source string and returns the diagnostic, one that checks cleanly.

```python
GOOD = """(mod r)
(fn grow :void ((v (ref (vec :i64)))) (vec-push v 1))
(fn main :i64 () (letmut v (vec :i64) (make (vec :i64))) (grow v) (vec-free v) (ret 0))
"""
```

Assert: `GOOD` checks clean; the same call with `(let v …)` raises E0304 at the argument;
`(fn f (ref (vec :i64)) ((v (ref (vec :i64)))) (ret v))` raises E0305 at the `ret`; a
closure `(fn :i64 () (vec-len v))` inside a ref-taking function raises E0305 at `v`; and
`(fn g :void ((v (ref point))))` raises E0100 at the parameter's type.

- [ ] **Step 2: Run them and confirm they fail**

Run: `python3 -m unittest tests.test_ref -v`
Expected: FAIL on the first case — the parameter type is an unknown form.

- [ ] **Step 3: Add the codes**

`E0304` "a ref argument must be a mutable binding", `E0305` "a ref cannot escape the
call", in the ownership family beside E0300. Each gets its line in the code table, and
`docs/LOGOS.md` is regenerated at the end of this task.

- [ ] **Step 4: Accept the parameter and the call**

`_check_fn` defines a ref parameter with `ref=True`, `param=True`, `mutable=False`.
`_arguments` matches a `(ref (vec T))` parameter against an argument that is an `ATOM`
naming a variable with `var.mutable or var.ref`; otherwise E0304 at the argument. The
argument is marked used, not moved.

- [ ] **Step 5: Refuse every escape**

One predicate, `_refuse_ref(ty, where, what)`, called wherever a value is kept or
transmitted: `_ret`; the value side of `vec-push`; `_make` (struct construction) and
`_set_field`; an enum payload argument; `alloc`'s element; a closure's capture in
`_Env.lookup(where)`; and `_arguments` when the parameter is not a ref. Each raises
E0305 with the node path and the site in the message.

- [ ] **Step 6: Let the container forms act through a ref**

`_vec_target` unwraps `Ref(Vec)` and returns the `Vec`; a ref variable passes the
mutability test through `var.ref`. `set` and `set-field` keep refusing a parameter.

- [ ] **Step 7: Add the negative corpus**

Four files under `tests/type/`, each with its `.expect`: a non-`letmut` argument (E0304),
a returned ref (E0305), a captured ref (E0305), and `(ref point)` (E0100). They must be
`fmt`-canonical.

- [ ] **Step 8: Regenerate the manual and run the gates**

Run: `python3 -m logos guide > docs/LOGOS.md`, then `python3 -m logos guide --check`
Expected: exit 0. The manual now lists the `ref` form and the two codes.

Run: `python3 -m unittest tests.test_ref -v && make test`
Expected: PASS, with the four new negative cases passing in the corpus.

- [ ] **Step 9: Commit**

```bash
git add logos/diag.py logos/check.py docs/LOGOS.md tests/test_ref.py tests/type
git commit -s -m "feat: check ref parameters, their argument and their escape rules (E0304, E0305)"
```

---

### Task 4: Lowering: a ref is the address of the caller's descriptor

**Files:**
- Modify: `logos/lower.py` (`use_type`, `vec_binding`, the five vector forms, and the call's parameter passing)
- Test: `tests/test_ref.py`, `tests/exec/ref-param.logos`

**Interfaces:**
- Consumes: the checker's `_Var.ref` and `types.Ref`.
- Produces: a `(ref (vec T))` parameter whose slot holds a pointer to the caller's
  descriptor; `vec_binding` returning `(Vec, slot, through_pointer: bool)`; a call that
  passes the address of the argument's slot for a ref parameter.

- [ ] **Step 1: Write the failing IR test**

In `tests/test_ref.py`, lower and emit `GOOD` and assert the helper's parameter is a
pointer and that the push loads through it twice:

```python
self.assertIn("define void @lg.r.grow(ptr", text)   # the exact LLVM spelling may differ; pin what you emit
self.assertIn("call i64 @lg.r.grow(", text)
self.assertIn(".addr", text)                        # the caller passes a slot address
```

Pin the real spelling from a first run rather than guessing it; the point is that the
test fails before the change and pins the shape after it.

- [ ] **Step 2: Run it and confirm it fails**

Run: `python3 -m unittest tests.test_ref -v`
Expected: FAIL, the call passes a descriptor instead of an address.

- [ ] **Step 3: Teach the emitter the ref type**

`use_type(Ref(Vec))` returns a pointer to the vector's descriptor type. A ref parameter's
alloca holds that pointer; the function's `ret` and the entry store keep working.

- [ ] **Step 4: Pass the address at the call**

For a ref parameter, the call argument is the argument binding's slot address, not a
loaded descriptor. Nothing is copied and no descriptor is cleared.

- [ ] **Step 5: Make the five vector forms load through the pointer**

`vec_binding` reports whether the slot holds a pointer. `vec-len`, `vec-get`, `vec-set`,
`vec-push` and `vec-free` load the pointer, then the descriptor, and store a rewritten
descriptor back through the pointer. A ref to a vector and a vector behave identically
from the form's point of view.

- [ ] **Step 6: Run the case and the suite**

Run: `python3 -m unittest tests.test_ref -v`, `python3 -m logos test --only exec 2>&1 | grep ref-param`, `make test`
Expected: the IR test passes, `PASS exec/ref-param/ref-param`, whole suite PASS. Run the
case at both `-O0` and `-O2` (the corpus does this by default).

Also add one unit case to `tests/test_ref.py` for Review Focus 5: a function with two
`(ref (vec :i64))` parameters that pushes a different value through each, built and run,
printing both lengths — the right descriptor grows each time.

- [ ] **Step 7: Confirm nothing else moved**

Lower every corpus file at the previous commit and at this one and diff the IR: zero
differences for files that use no `(ref …)`. Record the unit count in the commit message.

- [ ] **Step 8: Commit**

```bash
git add logos/lower.py tests/test_ref.py
git commit -s -m "feat: pass a ref as the address of the caller's descriptor"
```

---

### Task 5: The baseline, the gates, and the pull request

**Files:**
- Modify: `tests/summary.txt` (regenerated), `docs/LOGOS.md` if a table moved.

- [ ] **Step 1: Record the new cases**

Run: `python3 -m logos test --update-baseline`, then `git diff --stat tests/summary.txt`
Expected: one line per new case (the exec case and the four negative ones), leak total
unchanged.

- [ ] **Step 2: Regenerate and verify the manual**

Run: `python3 -m logos guide > docs/LOGOS.md && python3 -m logos guide --check`
Expected: exit 0.

- [ ] **Step 3: Run the gate**

Run: `bash tools/pr_gate.sh`
Expected: `PASS sign-off` then 5/5 gates.

- [ ] **Step 4: Commit and open the pull request**

```bash
git add tests/summary.txt docs/LOGOS.md
git commit -s -m "test: record the ref cases in the baseline"
git push -u origin feat/selfhost-w1-ref
gh pr create --base main --title "feat: W1 the (ref T) parameter" --body-file .github/PULL_REQUEST_TEMPLATE.md
```

Fill every section of the template, including the baseline reason (five new cases, same
leak total) and the invariant statement: a ref is checked so that it cannot be read after
the call returns, which is the invariant that makes a non-owning parameter safe.

## Later waves

W2 is the six new forms and three runtime helpers; W3 the Logos standard library; W4 to
W9 the compiler itself. Each gets its plan when the previous one merges.
