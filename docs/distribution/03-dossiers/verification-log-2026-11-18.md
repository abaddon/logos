# Verification log — 2026-11-18

Every command the agent-facing docs quote, run in order on this tree, with the
output copied from the terminal. Run from
`/root/ai-language-program/.worktrees/t_5b93c8fe` (branch `wt/t_5b93c8fe`,
`logos 0.2.1`) unless a command says otherwise. Section 7 is the published
release: the same commands, against the artifact GitHub serves.

Page-by-page provenance — which command proves which claim — is in
[`../00-index.md`](../00-index.md).

## 1. The compiler, from the checkout

```console
$ ./tools/logosc.sh version
logos 0.2.1
```

The first invocation built the compiler from `src/` with `bootstrap/logosc`:
47.1 s real on this machine. Every later invocation reused `build/logosc`.

```console
$ ./tools/logosc.sh build examples/hello.logos
$ echo $?
0
$ ./build/hello
hello
```

Silence and exit 0 from the build; `build/hello.ll` and `build/hello` written.

## 2. A program of your own, and the same commands on it

The quickstart has the reader write `hello.logos` in the checkout root:

```console
$ cat > hello.logos <<'EOF'
(mod hello)

(fn main :void ()
  (println "hello from logos"))
EOF
$ ./tools/logosc.sh build hello.logos
$ echo $?
0
$ ./build/hello
hello from logos
```

## 3. The reference project

```console
$ ./tools/logosc.sh build examples/agent-gate/gate.logos -o build/agent-gate
$ ./build/agent-gate < examples/agent-gate/calls.txt; echo "exit=$?"
ALLOW  shell ls -la
DENY   shell rm -rf /  -- shell: recursive delete
ALLOW  http GET https://example.com/docs
DENY   http GET http://example.com  -- http: only an https url is allowed
ALLOW  write ./notes/todo.md buy milk
DENY   write /etc/passwd root  -- write: path must start with ./
DENY   read /root/.ssh/id_rsa  -- read: system and home paths are off limits
DENY   browser navigate x  -- unknown tool
exit=5
```

Five denials, and the exit status is the denial count — that is how
`agent-gate < proposed.txt || stop` gates a shell.

```console
$ ./tools/logosc.sh test examples/agent-gate/gate.logos
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

No `--opt` flag: every case ran at `-O0` and `-O2`.

## 4. A failure, as text and as data

```console
$ cat > broken.logos <<'EOF'
(mod broken)

(fn main :void ()
  (println (+ 1 "x")))
EOF
$ ./tools/logosc.sh build broken.logos
broken/main/2/0: E0100: '+' needs numbers, found :str
    (+ 1 "x")
$ echo $?
2
$ ./tools/logosc.sh check broken.logos
broken/main/2/0: E0100: '+' needs numbers, found :str
    (+ 1 "x")
$ echo $?
2
$ ./tools/logosc.sh check broken.logos --json
{"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100","message":"'+' needs numbers, found :str","node_path":"broken/main/2/0","file":"broken.logos","line":0,"col":0}]}
$ echo $?
2
$ ./tools/logosc.sh show broken.logos broken/main/2
(println (+ 1 "x"))
$ echo $?
0
```

The JSON object is one line from the compiler; `file` echoes the path it was
given, so a script that wants to map it back should pass an absolute path.

## 5. The language, as data

```console
$ ./tools/logosc.sh guide --json | jq -c '{forms:(.forms|length),types:(.types|length),operators:(.operators|length),builtins:(.builtins|length),codes:(.codes|length),categories:(.categories|length)}'
{"forms":96,"types":16,"operators":17,"builtins":2,"codes":36,"categories":8}
```

36 diagnostic codes — the number `docs/00-index.md` used to state as 35, which
this task corrects.

## 6. The fast corpus

```console
$ ./tools/logosc.sh test tests --only regress
PASS regress/alloc-enum-in-struct -
PASS regress/alloc-enum -
PASS regress/alloc-fn -
PASS regress/arity-in-import/program -
PASS regress/closure-escape -
PASS regress/div-zero/division-by-zero-panics -
PASS regress/enum-payload-struct/program/program -
PASS regress/extern-rt/program/runtime-file -
PASS regress/float-finite/large-but-finite-literals-are-accepted -
PASS regress/float-leading-zeros/leading-zeros-do-not-shift-the-exponent -
PASS regress/float-literal-compare/all-literal-comparisons-are-float -
PASS regress/float-range-f32 -
PASS regress/float-range -
PASS regress/generic-vector -
PASS regress/int-overflow/int-min-divided-by-minus-one-wraps -
PASS regress/libc-interposition/a-user-write-does-not-take-over-printing -
PASS regress/loop-condition -
PASS regress/loop-release -
PASS regress/main-call -
PASS regress/move-join -
PASS regress/move-set -
PASS regress/multi-module/program/program -
PASS regress/owner-place-read -
PASS regress/print-small-numbers/every-small-width -
PASS regress/recursive-enum -
PASS regress/ref-as-type-argument/a-ref-argument-instantiates-a-generic -
PASS regress/ref-channel-element -
PASS regress/ref-escape-send -
PASS regress/ref-escape-spawn -
PASS regress/ref-to-function-value -
PASS regress/reserved-name -
PASS regress/result-foreign-enum/program/program -
PASS regress/rt-definition -
PASS regress/runtime-locate/runtime-locate -
PASS regress/str-concat-overflow/concatenation-keeps-every-byte -
PASS regress/struct-owner-mismatch/program -
PASS regress/test-helper-duplicate -
PASS regress/test-helper-generic -
PASS regress/test-local-helper/uses-a-helper -
PASS regress/vec-arr-set-after-move -
PASS regress/vec-arr-set-move/move-a-vector-into-an-element-then-free-it -
PASS regress/vec-arr-set-record-after-move -
PASS regress/vec-arr-set-record-uaf -
PASS regress/vec-arr-set-reinit/free-then-arr-set-reinitialises-the-element -
PASS regress/vec-array-element/push-one-element-and-free-both -
PASS regress/vec-field-after-free -
PASS regress/vec-field-copy -
PASS regress/vec-field-double-free -
PASS regress/vec-field-place/push-grow-read-free-through-a-field-place -
PASS regress/vec-field-place/free-then-set-field-reinitialises -
PASS regress/vec-field-place/free-then-push-starts-an-empty-vector -
PASS regress/vec-field-read -
PASS regress/vec-foreign-struct/program/program -
PASS regress/vec-place-copy -
PASS regress/vec-push-after-move-join-free-else -
PASS regress/vec-push-after-move-join-free-then -
PASS regress/vec-push-after-move -
PASS regress/vec-push-after-set-field -
PASS regress/vec-set-after-move -
59 passed, 0 failed, 0 leaked
baseline tests/summary.txt: 0 regression(s)
```

The full corpus is `./tools/logosc.sh test tests`: the same cases at `-O0` and
`-O2`, compared with each other.
