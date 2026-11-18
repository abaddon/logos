# Copy — the two human posts (they are deliberately not the same post)

**DO NOT POST EITHER UNTIL** the endpoint answers (§A1) and the demo runs from a
fresh clone. The map's finding is blunt: a Show HN on a 0★ repo with no callable
surface bounces, because the visitor cannot run the thing and no agent can call
it. HN is one shot per title; spend it when the click pays off.

They are also **two weeks apart, and the second one is not a repost of the
first.** HN rewards a falsifiable claim and a runnable artifact in a crowd of
engineers who will try it. r/LocalLLaMA rewards an argument the sub is already
having, with disclosure up front and no pitch. Pasting HN's body into Reddit is
the single most common way a project gets a "this is an ad" removal.

---

## 1. Show HN

**Title** (78 characters, under HN's 80):

```text
Show HN: Logos – a compiler where allocation and failure are visible in the source
```

**URL:** `https://github.com/abaddon/logos`

**First comment, posted by the author immediately after submitting.** On HN this
comment is the submission: it is what the top of the thread reads, and it must
contain the thing the title promised.

```text
Logos is a small compiled language I built around one question: what would a
language look like if the person reviewing the code could not read all of it?

Not "expressive". The premise is that the volume of code exceeds the review
capacity, so verification has to move into the tool that produces the artifact.

Four things follow from that, and they are the whole language:

- Allocation is a call you can see. There is no implicit heap.
- A call that can fail declares it, and an unhandled failure is a compile error
  (E0602), not a runtime surprise.
- Release is a call you make. There is a leak tracker and the test runner reports
  leaks per case; a program that leaks fails.
- An unused binding is an error (E0107). A dead assignment left behind is exactly
  how a generated diff stops being reviewable.

Diagnostics are the part I would actually point at. Every refusal is a JSON
object with a code and a node path — an address, not a label — and the exit code
says whose fault it was: 2 is your source, 1 is your machine.

    $ logosc build bad.logos --json
    {"schema_version":1,"diagnostics":[{"severity":"error","code":"E0100",
     "message":"let 'x' has type :i64, found :str",
     "node_path":"badtype/main/2","line":0,"col":0}]}

    $ logosc show examples/hello.logos badtype/main/2
    (let x :i64 1)

The program carries its own expectations, in the same file, and `logosc test`
runs them at -O0 and -O2 and fails if the two disagree. There is no harness.

Runnable thing, if you want to see it before reading anything:
https://github.com/abaddon/logos/tree/main/examples/agent-gate — a policy gate
for an agent's proposed tool calls, 174 lines, one file. 9 in-source tests, 0
leaked, and the exit code is the number of denials:

    $ ./build/agent-gate < examples/agent-gate/calls.txt
    ALLOW  shell ls -la
    DENY   shell rm -rf /  -- shell: recursive delete
    DENY   http GET http://example.com  -- http: only an https url is allowed
    ...
    $ echo $?
    5

What it is bad at, since you will find out anyway:

- x86_64 and arm64 **Linux only**. Needs clang at build time of every program,
  because it lowers to LLVM IR text and shells out. If you are on a Mac, there is
  no local install today — that is a real gap, not a roadmap item with a date.
- The standard library is 21 functions. No package manager, no `str` → int parse,
  no regex.
- Pre-1.0, with the open items listed in docs/reference/limits.md rather than
  implied. Names are global across a program, so two modules cannot both declare
  a `point`.
- No comments and no `for`. Intent lives in a `.md` beside each module.
- It is slow to write in for the first week. That is the trade, not a bug.

The compiler is 24,044 lines of Logos and self-hosting: the stage-0 builds gen2,
gen2 builds gen3, and CI requires the two binaries to be byte-identical before it
will cut a release. Which is also the honest answer to "why should I believe it
works" — the proof is a gate, not a claim.

I will be here all day. The questions I expect and do not mind: why not Rust
(guarantees, but it does not treat an unread binding as an error, and it is a
much larger surface to review), why not Zig/C (same, plus no diagnostic-as-data),
why not just better linting on Python (because the failure you care about
survives the linter).
```

**Thread discipline.** Answer everything for the first three hours, including the
dismissive ones. The three questions that will arrive, and the honest answers
already written for them, are objections 1, 2 and 5 in the messaging kit
(`docs/messaging/01-summary/positioning-kit.md` §4) — quote the limit, do not
defend the project. Never ask for stars; the repo link is the ask.

---

## 2. r/LocalLLaMA — two weeks later

**Title** (the sub argues about verification; the title invites that argument
rather than announcing a language):

```text
If a local model writes 400 lines for you, how do you actually check them? (I built a language around that question — disclosure in the post)
```

**Body:**

```text
Disclosure first, because the sub's rules require it: I maintain this project,
and an agent wrote most of the compiler under my direction.

The thing I keep hitting with local models is not generation quality. It is that
I have no cheap way to tell a correct 400-line diff from a plausible one. Reading
it carefully costs more than writing it did. Linters catch style. Tests catch
what you thought to test. Neither catches "this allocation is never released" or
"this error is silently swallowed", because in most languages neither of those is
a thing you can see in the source at all.

So I spent the last months building the language I wanted to point a model at.
Logos is prefix-form, compiles to a native Linux binary through LLVM, and makes
four refusals at compile time: an allocation is a visible call, a fallible call
must be handled (E0602), a binding nobody reads is an error (E0107), and a value
that owns memory moves rather than copies (E0300/E0402). Diagnostics are JSON
with a `node_path`, so a supervisor loop can branch on the code instead of
parsing English, and exit 2 vs exit 1 separates "your code" from "your machine".

The part that is actually about local models: the program carries its own tests
in the same file, and running them executes at -O0 and -O2 and fails if the two
disagree. A model writes the test in the same pass as the function, so it cannot
drift. In my experience that is the single highest-value thing you can ask a
model to produce about its own output.

What it is bad at, up front, because a post that hides this wastes your time:

- Linux x86_64/arm64 only, and clang must be present at build time. No macOS.
- 21 standard-library functions. No regex, no package manager, no int parse.
- Pre-1.0 and the surface can move; the open items are listed, not implied.
- No comments, no `for` loop. The austere version of every feature.
- If a local model has never seen the syntax, it will get it wrong at first —
  that is real. The mitigation is `logosc guide --json` (96 forms, 36 codes) so
  the model can load the grammar instead of guessing it, plus an error message
  that names the node.

Two things I would genuinely like from this sub, rather than a star: (1) if you
run it against a local model, which forms did the model get wrong most often —
that is a training-data-shaped question and I do not have the data; (2) does the
"unused binding is an error" rule survive contact with your workflow, or is it
the first thing you would turn off?

Runnable in one command set, from a fresh clone, no install:
https://github.com/abaddon/logos/tree/main/examples/agent-gate

    ./tools/logosc.sh build examples/agent-gate/gate.logos -o build/agent-gate
    ./build/agent-gate < examples/agent-gate/calls.txt   # 8 verdict lines, exit 5
    ./tools/logosc.sh test examples/agent-gate/gate.logos # 9 passed, 0 failed, 0 leaked
```

**Why the shape differs from HN.** HN gets the mechanism and a claim it can
falsify in a terminal; the Reddit post gets a question the sub already argues
about, the disclosure in line one, and an explicit request for data it can
provide. The sub's self-promotion policy is why an account with history is
required — post from one, and expect the first comment to be a skeptic rather
than a user.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_c0360ffd/docs/messaging/01-summary/positioning-kit.md
 -> §4 the five objections and their limits, quoted in the HN thread guidance
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/verification-log.md
 -> The demo output, the exit code and the `9 passed, 0 leaked` line, all executed from a cold clone
