# Install `logosc`

`logosc` is one directory. Unpack it, run `bin/logosc` from inside it, and it
compiles Logos to native x86_64 Linux binaries. Nothing is installed
system-wide, nothing is added to `PATH` unless you add it, and uninstalling is
`rm -rf` on that directory.

This page is for someone who wants to use the compiler. To build the compiler
from source, or to cut a release, read `AGENTS.md` and `docs/release.md`.

## What you need

| Requirement | Why | Version |
|---|---|---|
| x86_64 Linux | the only target the compiler emits | — |
| glibc | the shipped binary is dynamically linked against it | 2.35 or newer (built on Ubuntu 22.04) |
| `clang` | **at build time of every program**, not only of the compiler — `logosc` shells out to clang for each binary it produces | 14, matching the recorded toolchain |
| `binutils` (`ld`) | clang links with it | 2.38 |

`clang` is the one requirement that surprises people: `logosc` lowers Logos to
LLVM IR text and then runs `clang {opt} -target x86_64-unknown-linux-gnu
build/<stem>.ll logos/runtime/rt.c -o <out> -lpthread -lm`. If `clang` is not on
`PATH`, every build fails with `logos: clang failed:` and the command it tried.
Python is **not** required: the compiler is written in Logos and the C runtime is
compiled by clang.

On Debian and Ubuntu:

```sh
sudo apt-get install -y clang-14 lld-14 binutils
```

## Download

Releases are published on the GitHub releases page as
`logos-<version>-x86_64-linux.tar.gz` plus a `SHA256SUMS`. With the `gh` CLI:

```sh
gh release download --repo abaddon/logos --pattern 'logos-*-x86_64-linux.tar.gz' --pattern SHA256SUMS
```

or take the tarball and `SHA256SUMS` from the release page with any HTTP client.

## Verify, then unpack

```sh
sha256sum -c SHA256SUMS
tar -xzf logos-1.0.0-x86_64-linux.tar.gz
cd logos-1.0.0-x86_64-linux
```

The tarball unpacks to a single directory holding:

```
bin/logosc                     the compiler
logos/runtime/rt.c rt.h        the C runtime clang links into every program
src/std/{io,map,str}.logos     the standard library source the loader reads
share/doc/LOGOS.md             the generated manual
share/doc/{LICENSE,README,CHANGELOG}
INSTALL.md                     this page
VERSION                        version, commit, and the toolchain it was built with
```

## Use it

```sh
cat > hello.logos <<'EOF'
(mod hello)

(fn main :void ()
  (println "hello"))
EOF

./bin/logosc build hello.logos -o hello
./hello
```

`hello` prints `hello`. The standard library resolves from the same directory:

```sh
cat > greet.logos <<'EOF'
(mod greet)

(use str)

(fn main :void ()
  (if (string-starts-with "logos" "lo")
    (println "std ok")
    (println "std broken")))
EOF

./bin/logosc build greet.logos -o greet
./greet
```

## Run it from the unpacked directory

The compiler resolves two paths relative to the **working directory**, not
relative to its own binary: the runtime at `logos/runtime/rt.c` and the standard
library at `src/std/<name>.logos`. That is why the tarball ships them at those
exact paths and why the examples above are run with the prefix as the working
directory.

Run `bin/logosc` from outside the directory with a file that imports anything,
and you get a diagnostic that looks like a typo rather than a path problem:

```
$ cd /tmp && ~/logos-1.0.0-x86_64-linux/bin/logosc build ~/greet.logos -o greet
greet.logos/0: E0005: unknown module 'str'
```

Resolving those two paths relative to `/proc/self/exe` (with `LOGOS_ROOT` and
`LOGOS_PATH` overrides) is the compiler change that lifts this constraint, and
it is tracked in the v1.1 workstream. Until it lands, either run the compiler
with the unpacked directory as the working directory, or keep a copy of
`logos/runtime/` and `src/std/` beside the program you are building.

Two consequences worth knowing:

- the compiler writes its IR to `build/<stem>.ll` in the working directory, so
  a build inside the unpacked prefix creates `build/` there;
- `.logos` files beside the source you build shadow the standard library of the
  same name, which is the documented shadowing rule, not a bug.

## Verify the copy you have

```sh
./bin/logosc version        # logos <version>, matching VERSION and the release page
cat VERSION                 # version, commit, the clang and ld recorded in the repository
./bin/logosc guide --json   # the machine-readable language manifest
./bin/logosc --help         # every verb
```

## Uninstall

```sh
rm -rf logos-1.0.0-x86_64-linux
```

Nothing else was modified: no files outside the directory, no `PATH` entry, no
system package.
