# The Logos language, v1 subset

One page for an agent that must write Logos now: the shape of the language, the
rules that decide whether code compiles, and a verified idiom for each thing
you will actually build. Every `logos` block below is a complete module that
compiles and runs — they were compiled and executed while this page was
written.

- **Exhaustive reference**: [`../LOGOS.md`](../LOGOS.md) — the generated manual:
  cheat sheet, 20 executable chapters, every form, type, operator, reserved
  name and code. It is the ground truth; this page is the fast path into it.
- **Machine-readable surface**: `logosc guide --json` — 96 forms, 16 types, 17
  operators, 2 builtins, the reserved names and the 35 diagnostic codes.
- **Errors**: [`diagnostics.md`](diagnostics.md). **Command line**:
  [`cli.md`](cli.md). **Stdlib**: [`stdlib.md`](stdlib.md).

---

## The model, in five sentences

1. A program is one or more files; each file is one module: `(mod name)` first,
   then `(fn …)`, `(type …)` and `(test …)` definitions.
2. Every construct is a parenthesised form: `(head arg arg …)`. There is no
   infix, no precedence, no statement separator, no comments, and no
   semicolons. The head decides everything.
3. Every definition carries its type in the source: `(fn name :ret ((p :type) …)
   body…)`, `(let name :type expr)`, `(letmut name :type expr)`.
4. Nothing is implicit: no conversion (`(cast T e)` is the only one), no
   allocation on assignment, no hidden copy of an owner, no silent error
   (a `(res …)` must be handled).
5. A function returns with `(ret e)`. The value of the last form is not
   returned.

```logos
(mod shapes)

(fn increment :i64 ((n :i64))
  (ret (+ n 1)))

(fn main :void ()
  (println (increment 41)))
```

```text
42
```

## The ten rules, mapped to the code that enforces them

Each rule is a compile error, not a convention. The full statement of each is
the cheat sheet in [`../LOGOS.md`](../LOGOS.md#cheat-sheet).

| # | Rule | Enforced as |
|---|---|---|
| 1 | One canonical spelling per construct | `E0002` unknown node, `E0102` wrong arity |
| 2 | No implicit conversion; `(cast T e)` is the only one | `E0100` type mismatch |
| 3 | A binding is block-scoped (function body, if branch, while body, match arm) | `E0005` name not found |
| 4 | A vector or owner-containing value **moves**; it is never copied | `E0300` use after move, `E0402` vector value not copyable |
| 5 | A value cannot be read out of a place when it owns memory | `E0402` |
| 6 | A release inside a loop is refused for a binding declared outside it | `E0303` |
| 7 | A capturing closure cannot cross a call boundary | `E0502` closure escapes its function |
| 8 | A result must be handled: matched, `try`'d, returned or passed on | `E0602` unhandled result |
| 9 | Shared state must carry `(shared …)`, checked through aggregates | `E0700` |
| 10 | A form the checker accepts, the backend can emit | (invariant, not a diagnostic) |

Two more that surprise every newcomer: **`E0107 unused binding` is an error**,
so a binding nobody reads fails the build; and a function that declares a
non-`void` return must `ret` on every path (`E0105`).

## Idioms

### Bindings, mutation and casts

`let` binds immutably, `letmut` binds mutably, and `(set name expr)` reassigns a
`letmut`. The type is part of the binding.

```logos
(mod bindings)

(fn main :void ()
  (let small :u8 200)
  (let wide :i64 (cast :i64 small))
  (letmut b :i64 3)
  (set b (+ b wide))
  (println b))
```

```text
203
```

Casting is explicit and unchecked: `(cast :u8 300)` compiles and prints `44`,
because it truncates to the low byte. A conversion that must not lose data is
your check to write, not the compiler's.

### Branching and loops

`if` is an expression with two branches. `while` is the only loop; there is no
`for`. `match` covers values and enum variants and must be exhaustive.

```logos
(mod control)

(fn classify :str ((n :i64))
  (ret (match n (0 "zero") (-1 "minus") (_ "many"))))

(fn main :void ()
  (letmut i :i64 0)
  (while (< i 3)
    (println i)
    (set i (+ i 1)))
  (println (if (< i 3) "small" "big"))
  (println (classify 0))
  (println (classify -1))
  (println (classify 9)))
```

```text
0
1
2
big
zero
minus
many
```

### Structs

`(type name (struct (field :type) …))` declares a C-layout record.
`(make name v …)` constructs, `(get v field)` reads, `(set-field v field v2)`
writes a `letmut`.

```logos
(mod records)

(type point (struct (x :i64) (y :i64)))

(fn total :i64 ((p point))
  (ret (+ (get p x) (get p y))))

(fn main :void ()
  (letmut p point (make point 1 2))
  (println (total p))
  (set-field p x 5)
  (println (total p)))
```

```text
3
7
```

A struct field may be a scalar, `:str`, a fixed array, an enum, an `(opt T)`, a
function value or a `(vec T)`. It may **not** hold a result or an owner — those
two are `E0002`, with messages that name the rejected field (`result fields are
not supported yet`, `owning fields are not supported yet`).

A vector field makes the record the owner of a buffer, so the field is reached
through a **place**, and the five vector operations take that place:
`(vec-push (get b items) x)`, `(vec-set (get b items) i x)`,
`(vec-len (get b items))`, `(vec-get (get b items) i)` and
`(vec-free (get b items))`. The record must be a `letmut` (or a `(ref …)`
parameter) for the operations that write it to be legal.

```logos
(mod records)

(type bucket (struct (items (vec :i64)) (label :i64)))

(fn main :void ()
  (letmut empty (vec :i64) (make (vec :i64)))
  (letmut b bucket (make bucket empty 0))
  (vec-push (get b items) 4)
  (vec-push (get b items) 5)
  (println (vec-len (get b items)))
  (vec-free (get b items))
  (set-field b items (make (vec :i64)))
  (println (vec-len (get b items)))
  (vec-free (get b items)))
```

```text
2
0
```

Freeing through the field **moves** it: the field is uninitialised afterwards,
a read of it is `E0300` (use after move), and `set-field` is how it is filled
again — `set-field` writes without reading, so it works on a field that was
freed. Reading a live vector field as a value (`(let c (get b items))`) is
`E0402`: a descriptor is never copied out of a place.

A struct that holds a vector, at any depth, is **moved, never copied**, exactly
like a bare vector: `(let c b)` moves `b`, passing it by value moves it, and any
attempt to copy it is `E0402`. `(ref b)` borrows the record instead, and a vector
operation through `(get r items)` mutates the caller's record. A record that
holds a vector is a `letmut`, because a `let` binding can be neither written nor
freed (`E0104`) and its buffer would leak.

### Vectors — allocate, fill, free

`(make (vec T))` allocates an empty vector, `(vec-push v x)` appends,
`(vec-len v)` counts, `(vec-get v i)` reads, `(vec-set v i x)` writes,
`(vec-free v)` releases. **You free it**, exactly once, and a vector expression
is never implicitly copied.

```logos
(mod vectors)

(fn sum :i64 ((v (ref (vec :i64))))
  (letmut i :i64 0)
  (letmut total :i64 0)
  (while (< i (vec-len v))
    (set total (+ total (vec-get v i)))
    (set i (+ i 1)))
  (ret total))

(fn main :void ()
  (letmut v (vec :i64) (make (vec :i64)))
  (vec-push v 10)
  (vec-push v 32)
  (println (sum v))
  (vec-free v))
```

```text
42
```

`(ref T)` is spelled **only in the signature**; the caller passes the binding
itself (`(sum v)`, not `(sum (ref v))`), and it must be a `letmut`
(`E0304` otherwise). Passing `v` to a plain `(vec :i64)` parameter would move
it and make the later `vec-free` `E0300`.

### Strings

A `:str` is a pointer and a byte count, never NUL-terminated. `(str-concat a b)`
allocates a new string that lives until the process exits — it is not in the
leak report and cannot be freed. `(str-from-i64 n)` renders a number.

```logos
(mod strings)

(fn main :void ()
  (let name :str "logos")
  (let n :i64 42)
  (println (str-concat name (str-concat " " (str-from-i64 n))))
  (println (str-len name))
  (println (str-slice name 1 3)))
```

```text
logos 42
5
og
```

Byte indexing only: `(str-len "é")` is 2. Use the `str` module for split, join
and find — see [`stdlib.md`](stdlib.md).

### Results and `try`

`(res :T :E)` is a declared-in-source result whose error type is an **enum you
declare**. `(ok v)` and `(err e)` construct; `(try e)` unwraps or returns early;
`match` handles both. An unhandled result is `E0602`.

```logos
(mod results)

(type parse-error (enum (bad :i64) (empty)))

(fn checked :(res :i64 parse-error) ((n :i64))
  (if (> n 0)
    (ret (ok n))
    (ret (err (bad n)))))

(fn doubled :(res :i64 parse-error) ((n :i64))
  (ret (ok (* 2 (try (checked n))))))

(fn main :void ()
  (match (doubled 21)
    ((ok v) (println v))
    ((err _) (println 0)))
  (match (doubled -1)
    ((ok v) (println v))
    ((err e) (match e ((bad n) (println n)) (empty (println 0))))))
```

```text
42
-1
```

### Optionals

`(opt :T)` with `(some v)` and `(none)`; `match` both arms, `_` for the value
you ignore.

```logos
(mod optionals)

(fn first-positive :(opt :i64) ((v :i64))
  (if (> v 0)
    (ret (some v))
    (ret (none))))

(fn main :void ()
  (match (first-positive 5) ((some v) (println v)) ((none) (println 0)))
  (match (first-positive -1) ((some v) (println v)) ((none) (println 0))))
```

```text
5
0
```

### Generics and closures

A type variable is a `:T` in a signature; the compiler monomorphises, so each
instantiation is a separate function (`E0500` bounds the count). A closure is
`(fn :T ((p :P) …) body…)` with no name; it may capture, but may not cross a
call boundary if it captures (`E0502`).

```logos
(mod generic)

(fn id :T ((x :T))
  (ret x))

(fn apply :U ((f (fn (:T) :U)) (x :T))
  (ret (f x)))

(fn main :void ()
  (println (id 42))
  (let k :i64 10)
  (let add (fn :i64 ((n :i64))
             (ret (+ n k))))
  (println (add 5))
  (println (apply (fn :i64 ((n :i64)) (ret (* n 3))) 4)))
```

```text
42
15
12
```

### Threads, mutexes, atomics

`(spawn fn arg …)` starts a thread, `(join h)` waits. State shared across
threads must be marked `(shared T)` and the marker is checked through
aggregates. `(atomic :i64 v)` is the only atomic type; `(atomic-add a n)`,
`(atomic-load a)`.

```logos
(mod threads)

(fn worker :void ((total (shared (atomic :i64))) (n :i64))
  (letmut i :i64 0)
  (while (< i n)
    (atomic-add total 1)
    (set i (+ i 1))))

(fn main :void ()
  (letmut total (atomic :i64 0))
  (let a (spawn worker total 1000))
  (let b (spawn worker total 1000))
  (join a)
  (join b)
  (println (atomic-load total)))
```

```text
2000
```

### Runtime access: arguments, files, children

`(args)` returns the command line as `(vec :str)` — you free it.
`(read-file path)` panics `R0007` on failure; `(read-all)` reads stdin.
`(run prog args)` starts a child inside a 90-second budget and returns a record
read with `(run-status r)`, `(run-out r)`, `(run-err r)`.

```logos
(mod runtime)

(fn main :void ()
  (letmut argv (vec :str) (args))
  (println (vec-len argv))
  (vec-free argv)
  (letmut a (vec :str) (make (vec :str)))
  (vec-push a "-c")
  (vec-push a "echo hi")
  (let r (run "sh" a))
  (println (run-status r))
  (print (run-out r)))
```

```text
1
0
hi
```

`(run …)` takes ownership of the argument vector: it moves `a`, so do not free
it afterwards (that is `E0300`), and no leak is recorded for it.

### Modules

`(use name)` imports `name.logos` beside the asking file, or `src/std/name.logos`
relative to the **working directory**. Imports are not transitive and names are
global across the whole program, so every top-level definition in every module
must be unique.

```logos
(mod modules)

(use map)

(fn main :void ()
  (letmut keys (vec :str) (make (vec :str)))
  (letmut vals (vec :i64) (make (vec :i64)))
  (letmut slots (vec :i64) (make (vec :i64)))
  (map-init slots 8)
  (map-put keys vals slots "answer" 42)
  (println (map-get keys vals slots "answer"))
  (vec-free keys) (vec-free vals) (vec-free slots))
```

```text
42
```

Build that one anywhere; `(use map)` resolves from the installation (see
[`limits.md`](limits.md)).

### Tests are part of the language

A `(test NAME (expect ...) body...)` node declares its own output, exit code and
leak count; `logosc test FILE` builds and runs it at `-O0` and `-O2` and fails if
the two levels disagree. This is how you prove a program works without a
driver script.

```logos
(mod checkable)

(fn double :i64 ((n :i64))
  (ret (* 2 n)))

(test double
  (expect (out "84\n") (code 0) (leaks 0))
  (println (double 42)))
```

```sh
logosc test tests/exec/checkable.logos     # PASS exec/checkable/double -
```

A file with only `(test …)` nodes has no `main`, so `build` refuses it
(`E0103`) while `test` runs it — that is the normal shape of a corpus case.

## What v1 does not have

Do not design around these; they are refused, not missing (details in
[`limits.md`](limits.md)): comments, namespaces, `patch`, `for` loops, integer
or float formatting beyond `println`, string→number parsing, sorting, JSON
encode/decode as a library, unlink/stat/getenv, 32-bit atomics, generic
containers, a `run` verb, a second target.

If you need one of them, write it in Logos over what is listed here — the
compiler itself is 400 KB of Logos written against exactly this surface.
