# `src/logosc/sys.logos` — the prefix the compiler is running from

The twelfth module of the self-hosted compiler, and the only one that is not
a port of anything: it answers one question — *which directory is the compiler's
installation?* — and it exists so `main.logos` and `resolve.logos` answer it the
same way instead of one each. Logos has no comments and no doc form, so this
file is the header documentation the source cannot carry.

The two lookups that need it are the C runtime `main-link` hands clang and the
standard library the loader reads for a `(use name)`. Both used to be relative
paths (`"logos/runtime/rt.c"`, `"src/std"`), which named the *caller's*
directory; both now start at the prefix. The design and the search orders are
`docs/superpowers/specs/2026-11-15-runtime-and-library-lookup.md`.

## API

```logos
(fn sys-root :str ())                       ;; LOGOS_ROOT, else the prefix of /proc/self/exe
(fn sys-join :str ((dir :str) (base :str))) ;; dir/base, one slash, "" dir is the base
(fn sys-dir :str ((path :str)))             ;; dirname; "/" for a top-level path, "" for a bare name
(fn sys-trim :str ((s :str)))               ;; drop trailing slashes, keep "/"
(fn sys-split-paths :void ((out (ref (vec :str))) (s :str)))  ;; colon-separated, empties dropped
(fn sys-list :str ((items (ref (vec :str)))))                 ;; "a, b, c" for a diagnostic
(fn sys-env :str ((name :str)))             ;; a variable, "" when unset or empty
(fn sys-exe :str ())                        ;; the running program, resolved, "" when unknowable
```

## The two runtime primitives

```logos
(extern fn rt_exe_path :str ())
(extern fn rt_getenv :str ((name :str)))
```

These are the only two facts the language cannot produce on its own. Both are
runtime functions, not builtins, because the `extern` mechanism already binds a
C symbol and needs no front-end change: a `:str` argument crosses the boundary as
a `(ptr, len)` pair, and this change stated the return half of that rule — a
`:str` *result* is one `{ i8*, i64 }` struct — which is what the emitter already
produces for a Logos function that returns a string. `rt.h` carries both
contracts in full.

The buffers are process-lifetime and untracked, like every other string the
runtime builds: a `:str` owns nothing, so there is no owner a `str-free` could be
called on. `rt_exe_path` reads `/proc/self/exe` with `readlink` and grows its
buffer until the answer fits, so a path longer than `PATH_MAX` is a longer path
and not a prefix of one; it answers `""` — never a guess — when the kernel will
not say. `rt_getenv` copies the value out, so a later `setenv` cannot move it,
and it answers `""` both for a variable that is unset and for one set to the
empty string: an empty `LOGOS_ROOT` is not a prefix to honour.

## Why the prefix is the executable's grandparent

`/proc/self/exe` is an absolute path with every symlink already resolved, so
`~/.local/bin/logosc -> /opt/logos/bin/logosc` still names `/opt/logos`. The
directory *above* the binary's own directory is the prefix, which covers the two
layouts that exist:

| the binary | the prefix | which |
|---|---|---|
| `<prefix>/bin/logosc` | `<prefix>` | an install, `tools/dist.sh`'s layout |
| `<repo>/build/logosc` | `<repo>` | a checkout, built by `tools/logosc.sh` |

`LOGOS_ROOT` overrides it when set and non-empty. Nothing else is consulted: not
`argv[0]`, which a shell or a wrapper may have rewritten, and not the working
directory, which is whatever the caller had.

`sys-root` is a *string* and says nothing about whether the paths under it
exist. The two callers each probe in their own order, and both end with the
working directory, because the repository's gates and fixtures build with
relative paths. That is the one thing this module deliberately does not decide.
