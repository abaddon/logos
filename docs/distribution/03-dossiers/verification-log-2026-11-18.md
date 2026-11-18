# Verification log — 2026-11-18

Every command the agent-facing docs quote, run in order on this tree, with the
output copied from the terminal. Run from
`/root/ai-language-program/.worktrees/t_5b93c8fe` (branch `wt/t_5b93c8fe`,
`logos 0.2.2`) unless a command says otherwise. Section 7 is the published
release: the same commands, against the artifact GitHub serves. Section 8
re-fetches every URL `llms.txt` publishes.

Page-by-page provenance — which command proves which claim — is in
[`../00-index.md`](../00-index.md).

## 1. The compiler, from the checkout

```console
$ ./tools/logosc.sh version
logos 0.2.2
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

## 7. The published release

`v0.2.2` was published at 2026-11-18T22:42:57Z by the release workflow, which
ran the six gates on the tag, built the tarball on two runners and required one
SHA-256 for both:

```console
$ gh release view v0.2.2 --repo abaddon/logos --json url,assets --jq '.url, (.assets[] | "\(.name) \(.size) bytes")'
https://github.com/abaddon/logos/releases/tag/v0.2.2
logos-0.2.2-x86_64-linux.tar.gz 875863 bytes
SHA256SUMS 98 bytes
```

...and the block from `README.md` then run verbatim, in an empty directory,
against that artifact rather than a locally built one
(`docs/distribution/03-dossiers/verify-published-release.sh` waits for the
release and executes it):

```console
$ gh release download v0.2.2 --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
[exit 0]
$ ls -l
-rw-r--r-- 1 root root     98 Nov 18 22:43 SHA256SUMS
-rw-r--r-- 1 root root 875863 Nov 18 22:43 logos-0.2.2-x86_64-linux.tar.gz

$ sha256sum -c SHA256SUMS
logos-0.2.2-x86_64-linux.tar.gz: OK
[exit 0]

$ tar -xzf logos-0.2.2-x86_64-linux.tar.gz && cd logos-0.2.2-x86_64-linux
[exit 0]

$ cat > hello.logos <<'EOF'          # the heredoc README.md prints
(mod hello)

(fn main :void ()
  (println "hello from logos"))
EOF
[exit 0]

$ ./bin/logosc build hello.logos -o hello && ./hello
hello from logos
[exit 0]

$ ./bin/logosc version
logos 0.2.2
[exit 0]
```

The two files agree, and they are the same tarball the second runner built:

```console
$ sha256sum logos-0.2.2-x86_64-linux.tar.gz && cat SHA256SUMS
77e4895dbd7aad01a74e45abad6a5c5778e0b239bd01755b361f498f85da0f7c  logos-0.2.2-x86_64-linux.tar.gz
77e4895dbd7aad01a74e45abad6a5c5778e0b239bd01755b361f498f85da0f7c  logos-0.2.2-x86_64-linux.tar.gz
```

### 7.1 The pages the README and `llms.txt` link, inside the artifact

A link into a directory the tarball does not carry is exactly the dead end
`tools/verify_install.sh` exists to prevent, so the unpacked tree is checked for
them by name:

```console
$ ls
AGENTS.md  CHANGELOG.md  CONTRIBUTING.md  INSTALL.md  LICENSE  README.md
VERSION  bin  build  docs  examples  hello  hello.logos  llms.txt  logos  src

$ ls examples/agent-gate/
EVIDENCE.md  README.md
```

`llms.txt` is at the root and the reference project's two pages are under
`examples/agent-gate/` — the paths the repository URLs use, so every link an
agent follows from the artifact also resolves on GitHub.

### 7.2 The language, as the shipped compiler states it

```console
$ ./bin/logosc guide --json | jq -c '{schema_version, forms:(.forms|length), types:(.types|length), operators:(.operators|length), codes:(.codes|length)}'
{"schema_version":1,"forms":96,"types":16,"operators":17,"codes":36}
```

## 8. Every URL `llms.txt` publishes

The file an agent fetches first is only useful if its targets exist. All 21 were
fetched from `raw`/`github.com` on `main` at 22:20Z — `200` for every one:

```console
$ for u in $(grep -oE '\(https://[^)]+\)' llms.txt | tr -d '()' | sort -u); do
    printf '%s  %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -m 25 "$u")" "$u"; done
200  https://github.com/abaddon/logos/blob/main/AGENTS.md
200  https://github.com/abaddon/logos/blob/main/CHANGELOG.md
200  https://github.com/abaddon/logos/blob/main/CONTRIBUTING.md
200  https://github.com/abaddon/logos/blob/main/README.md
200  https://github.com/abaddon/logos/blob/main/docs/00-index.md
200  https://github.com/abaddon/logos/blob/main/docs/LOGOS.md
200  https://github.com/abaddon/logos/blob/main/docs/challenge/01-summary/program.md
200  https://github.com/abaddon/logos/blob/main/docs/history/build-ledger.md
200  https://github.com/abaddon/logos/blob/main/docs/install.md
200  https://github.com/abaddon/logos/blob/main/docs/quickstart.md
200  https://github.com/abaddon/logos/blob/main/docs/reference/agent-contract.md
200  https://github.com/abaddon/logos/blob/main/docs/reference/cli.md
200  https://github.com/abaddon/logos/blob/main/docs/reference/diagnostics.md
200  https://github.com/abaddon/logos/blob/main/docs/reference/language.md
200  https://github.com/abaddon/logos/blob/main/docs/reference/limits.md
200  https://github.com/abaddon/logos/blob/main/docs/reference/stdlib.md
200  https://github.com/abaddon/logos/blob/main/docs/release.md
200  https://github.com/abaddon/logos/blob/main/examples/agent-gate/README.md
200  https://github.com/abaddon/logos/blob/main/examples/json.logos
200  https://github.com/abaddon/logos/blob/main/examples/matrix.logos
200  https://github.com/abaddon/logos/blob/main/examples/wc.logos
```

`tools/check_doc_links.sh .` covers the relative links in the same pass: 278
files, 557 links, 0 broken.
