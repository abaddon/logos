# Evidence: the quickstart, run from a clean clone

Captured 2026-11-18T19:35Z on the branch this directory was added in, commit
`0faec57`, on x86_64 Linux 5.15 (Ubuntu, 6 cores), `clang 14.0.0`,
`logos 0.2.1`.

`git clone` was pointed at the local branch rather than at GitHub, because the
branch was not published at the time; nothing else differs from the quickstart
in [`README.md`](README.md). The clone was verified to be clean — `git status
--short` printed nothing and `build/` did not exist — so the 53 s below is a
cold compiler build from `bootstrap/logosc`, which is what a first-time reader
pays.

```console
$ git clone --branch wt/t_998fc78c /root/ai-language-program/.worktrees/t_998fc78c logos && cd logos
$ git log --oneline -1
0faec57 examples: add agent-gate, a reference project to fork
$ git status --short | wc -l
0
$ ls build
ls: cannot access 'build': No such file or directory

$ ./tools/logosc.sh build examples/agent-gate/gate.logos -o build/agent-gate
48.39user 4.11system 0:52.90elapsed 99%CPU (0avgtext+0avgdata 1498832maxresident)k
0inputs+57016outputs (0major+469473minor)pagefaults 0swaps
exit=0

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

$ ./tools/logosc.sh check examples/agent-gate/gate.logos; echo "exit=$?"
exit=0

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
exit=0
```

## The two invariants this demo also checks

Same clone, the same program at both optimisation levels and the formatter run
over the source:

```console
$ ./tools/logosc.sh build examples/agent-gate/gate.logos -o build/gate-O0 --opt -O0
$ ./tools/logosc.sh build examples/agent-gate/gate.logos -o build/gate-O2 --opt -O2
$ ./build/gate-O0 < examples/agent-gate/calls.txt > /tmp/o0.out; echo "O0 exit=$?"
O0 exit=5
$ ./build/gate-O2 < examples/agent-gate/calls.txt > /tmp/o2.out; echo "O2 exit=$?"
O2 exit=5
$ cmp /tmp/o0.out /tmp/o2.out && echo "stdout identical"
stdout identical
$ ./tools/logosc.sh fmt examples/agent-gate/gate.logos && git status --short && echo "fmt: no change"
fmt: no change
```

`fmt` rewrites in place only when the source is not canonical; here it printed
nothing, changed no byte and left `git status` empty, so the committed source is
canonical.
