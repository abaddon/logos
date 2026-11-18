# Copy — Hugging Face Space and the Docker MCP Catalog entry

**DO NOT PUBLISH UNTIL** the image builds and runs on a host with Docker (this
host has none: `docker info` fails, see
[`../../03-dossiers/verification-log.md`](../../03-dossiers/verification-log.md)).
Both of these ship a container, so both are gated on the same artifact — build it
once, publish it twice.

They are grouped in one file because they are the same artifact with two front
doors, and the mistake to avoid is describing them the same way. The Space is for
a **human** who wants to see it run without installing anything. The catalog entry
is for an **agent** whose gateway pulls `server.yaml` and never renders a page.

---

## 1. The image (build this first, once)

```dockerfile
# docker/Dockerfile — a Linux toolchain and the compiler built from source
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang-14 lld-14 binutils make ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/logos
# build logosc from the tag inside the image: the release tarball's binary is
# glibc-bound to its build host, and building here keeps the image honest about
# what it contains.
ARG LOGOS_REF=v0.2.1
RUN curl -sL "https://github.com/abaddon/logos/archive/refs/tags/${LOGOS_REF}.tar.gz" \
      | tar -xz --strip-components=1 \
 && ./tools/logosc.sh version \
 && install -m 0755 build/logosc /usr/local/bin/logosc
WORKDIR /work
ENTRYPOINT ["logosc"]
```

Pin `LOGOS_REF` to a tag, never to `main`: an image that rebuilds differently
every day is an image whose failure nobody can reproduce. `logging` the version
into the build output is deliberate — when a user reports a bug, the first question
is which compiler they ran.

## 2. Hugging Face Space — `logos-playground`

`README.md` at the Space root (frontmatter is what makes it render as a Space):

```markdown
---
title: Logos Playground
emoji: 🔒
colorFrom: gray
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Logos Playground

Paste a Logos program, see what the compiler refuses.

Logos is a small compiled language for code an agent writes and a human still has
to trust: allocation is a visible call, a fallible call declares itself, and an
unhandled failure is a compile error rather than a runtime surprise. This Space
runs the real `logosc` — the same binary the release ships — so what you see here
is the compiler's own output, not a re-implementation.

Four buttons, one per example: the `agent-gate` policy gate, `wc`, the JSON
parser, the four-thread matrix multiply. Each one prints **source, then IR, then
the run**, because the point is not that it runs — it is that you can read what
it will do.

## What is not here

- No macOS or Windows compiler: the target is a native Linux ELF and `clang`
  links it.
- 21 standard-library functions, pre-1.0, and the open items are listed in
  `docs/reference/limits.md` rather than implied.
- No comments, no `for`. Both are design decisions, not omissions.

Source and installation: https://github.com/abaddon/logos
```

**Why this framing and not a landing page.** The Space's job is one click to a
real compiler output. A visitor arriving from HN or Reddit has already read the
claim; the page that converts them is the one where they can break something and
read the diagnostic. The "what is not here" section exists because the first
question in the comments will be "does it work on my Mac", and answering it on
the page is cheaper than answering it forty times in a thread.

## 3. Docker MCP Catalog — `servers/abaddon-logos/`

PR to `docker/mcp-registry` (3,206 forks; submission is a PR, not a form). Two
files, and the `server.yaml` is the one that gets reviewed:

```yaml
name: logos
image: ghcr.io/abaddon/logos-mcp:0.2.1
type: server
meta:
  category: dev-tools
  tags: [compiler, language, type-check, diagnostics]
about:
  title: Logos
  description: Type-check, compile, format and run Logos programs. Diagnostics return as JSON with a code and a node path.
  icon: https://raw.githubusercontent.com/abaddon/logos/main/docs/assets/icon.svg
source:
  project: https://github.com/abaddon/logos
  commit: <the tag's commit sha>
config:
  description: No credentials. The compiler is self-contained in the image.
  env: []
  secrets: []
```

```json
{
  "check_program": {
    "description": "Type-check Logos source without compiling. Returns {ok, diagnostics[]} with code, message, node_path, line, col per diagnostic.",
    "arguments": ["source", "filename?"]
  },
  "compile_program": {
    "description": "Compile Logos source to LLVM IR; returns the IR text, the binary SHA-256 and any diagnostics.",
    "arguments": ["source", "optimize?"]
  },
  "format_source": {
    "description": "Rewrite Logos source in canonical form; the output is byte-stable.",
    "arguments": ["source"]
  },
  "run_example": {
    "description": "Build and run a repository example; returns stdout, exit code and leak count.",
    "arguments": ["name"]
  },
  "get_language_reference": {
    "description": "Return the language as JSON: 96 forms, 16 types, 17 operators, 36 codes, schema_version 1.",
    "arguments": []
  }
}
```

`secrets: []` and `env: []` are the strongest part of this entry and worth stating
in the PR body: a compiler has no credentials to hold, so the security review is
short. What does need saying in the PR body, unprompted: **this image executes
model-authored source**, so the server runs with a per-request timeout, a rate
limit and a scratch workdir per call, and it is not intended to be given network
egress beyond what `clang` and the libc need. A reviewer will ask; answering first
is the difference between a merged PR and a two-week thread.

SOURCES (LAYER 3 NAVIGATION)
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/03-dossiers/owner-actions.md
 -> §A6 Docker build/push/PR commands and §A7 the Space creation commands
/root/ai-language-program/.worktrees/t_669498b1/docs/launch/02-analysis/launch-checklist.md
 -> Where these sit in the waves, and why neither is a wave-1 move
