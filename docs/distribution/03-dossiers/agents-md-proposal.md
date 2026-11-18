# AGENTS.md — the install-and-run section that needs the owner's approval

`AGENTS.md` is a protected agent-instruction file in this environment: an
unattended worker cannot rewrite it, and the guard refuses the same edit routed
through another path. So this task could not add the section to `AGENTS.md`
itself. The delta is small, exactly specified, and verified below; applying it
takes one edit.

## Why it is worth applying

`AGENTS.md` covers what Logos is, the six gates, the four invariants, the
regress rule, the bootstrap rule and the pull-request rules — the contributor
contract. It does not say how to get a compiler running, and it never points at
`examples/`. An agent that opens `AGENTS.md` first therefore learns the rules
before it learns the loop. `llms.txt` and `docs/quickstart.md` carry the
install path, and the README hero links all three, so the surface is complete
without this change; adding it puts the two commands an agent needs in the file
the agent actually reads first.

## The patch

Insert between the "Read `docs/LOGOS.md` first" paragraph and
`## Done means these six commands pass`:

```markdown
## Get the compiler running

From a checkout — the first call builds the compiler from `src/` (~50 s), and
every command below was run to produce the output beside it:

```sh
./tools/logosc.sh version                                # logos 0.2.2
./tools/logosc.sh build examples/hello.logos              # writes build/hello.ll and build/hello
./build/hello                                            # hello
./tools/logosc.sh test examples/agent-gate/gate.logos     # 9 passed, 0 failed, 0 leaked
```

To use the published compiler instead of building from source, run the
five-command install block in `llms.txt` or `docs/quickstart.md`.
`examples/agent-gate/` is the project to copy when starting something new: one
174-line file with nine `(test …)` nodes. `docs/00-index.md` is the map of every
other page.
```

The three backticked paths are inline links in the real file: link text and
target are the same string (`llms.txt`, `docs/quickstart.md`,
`docs/00-index.md`), which resolve from the repository root. They are left as
plain paths here because `tools/check_doc_links.sh` reads every markdown link in
this repository, including one written inside a code block on a dossier page, and
would resolve them against `docs/distribution/03-dossiers/`.

## The evidence

Run on this tree at `logos 0.2.2`; output copied from the terminal.

```console
$ ./tools/logosc.sh version
logos 0.2.2
$ ./tools/logosc.sh build examples/hello.logos
$ ./build/hello
hello
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

Both relative links the section adds (`llms.txt`, `docs/00-index.md`,
`docs/quickstart.md`) resolve from the repository root and are already covered
by `tools/check_doc_links.sh`.

## SOURCES

| Path | What it establishes |
|---|---|
| `/root/ai-language-program/.worktrees/t_5b93c8fe/AGENTS.md` | the file, unchanged; the anchor paragraphs the patch inserts between |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/llms.txt` | the five-command install block the section points at |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/docs/quickstart.md` | the long form of the same path |
| `/root/ai-language-program/.worktrees/t_5b93c8fe/docs/distribution/03-dossiers/verification-log-2026-11-18.md` | the full transcript this evidence is cut from |
