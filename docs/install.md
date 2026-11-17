# Install `logosc`

`logosc` is one directory. Unpack it, run `bin/logosc`, and it compiles Logos to
native x86_64 Linux binaries from any working directory. Nothing is installed
system-wide, nothing is added to `PATH` unless you add it, and uninstalling is
`rm -rf` on that directory.

This page is for someone who wants to use the compiler. To build the compiler
from source, or to cut a release, read `AGENTS.md` and `docs/release.md`.

## What you need

| Requirement | Why | Version |
|---|---|---|
| x86_64 Linux | the host the shipped binary runs on, and the default target | — |
| (`gcc-aarch64-linux-gnu`, `libc6-dev-arm64-cross`, `qemu-user-static`) | only for `--target aarch64-unknown-linux-gnu` and `test --target`: the sysroot clang links arm64 against, and the emulator that runs it | — |
| glibc | the shipped binary is dynamically linked against it | 2.35 or newer (built on Ubuntu 22.04) |
| `clang` | **at build time of every program**, not only of the compiler — `logosc` shells out to clang for each binary it produces | 14, matching the recorded toolchain |
| `binutils` (`ld`) | clang links with it | 2.38 |

`clang` is the one requirement that surprises people: `logosc` lowers Logos to
LLVM IR text and then runs `clang {opt} -target x86_64-unknown-linux-gnu
build/<stem>.ll logos/runtime/rt.c -o <out> -lpthread -lm`. If `clang` is not on
`PATH`, every build fails with `logos: clang failed:` and the command it tried.
`--target aarch64-unknown-linux-gnu` keeps that command and adds `-static
-fuse-ld=lld`; clang finds `/usr/aarch64-linux-gnu` through the
`aarch64-linux-gnu` GCC triplet, which is why `gcc-aarch64-linux-gnu` and
`libc6-dev-arm64-cross` are the build requirement for arm64.
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
tar -xzf logos-0.2.1-x86_64-linux.tar.gz
cd logos-0.2.1-x86_64-linux
```

The tarball unpacks to a single directory holding:

```
bin/logosc                     the compiler
logos/runtime/rt.c rt.h        the C runtime clang links into every program
src/std/{io,map,str}.logos     the standard library source the loader reads
INSTALL.md                     this page
README.md                      the front page: what Logos is, and the route in
CHANGELOG.md                   what each version changed
LICENSE                        MIT
AGENTS.md, CONTRIBUTING.md     the contributor contract, and the short human route
docs/                          the manual (docs/LOGOS.md) and every page the README links to
VERSION                        version, commit, and the toolchain it was built with
```

The pages sit where they sit in the repository, so a link that works in the
checkout works in the unpacked directory with nothing online: `README.md` links
`docs/00-index.md`, `docs/reference/cli.md` and `AGENTS.md` by those paths, and
they are all there. `tools/check_doc_links.sh` is the check that says so, and
`tools/verify_install.sh` runs it on the tarball.

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

## Run it from anywhere

The compiler finds its own parts: the runtime at `logos/runtime/rt.c` (or
`share/logos/runtime/rt.c` in an installed tree) and the standard library at
`src/std/<name>.logos` (or `share/logos/std/`), resolved **from the directory
that holds `bin/logosc`**, not from the working directory. Unpack the tarball
anywhere, call it from anywhere, and both work:

```sh
$ cd /tmp && ~/logos-0.2.1-x86_64-linux/bin/logosc build ~/greet.logos -o greet
$ ./greet
std ok
```

`<prefix>` below is the directory above `bin/`. The two lookups, in the order
they are tried:

| what | order |
|---|---|
| the runtime | `<prefix>/share/logos/runtime/rt.c`, `<prefix>/logos/runtime/rt.c`, then `logos/runtime/rt.c` in the working directory |
| a module `(use name)` reads | `<dir of the asking file>/<name>.logos`, the `LOGOS_PATH` entries, `<prefix>/share/logos/std/<name>.logos`, `<prefix>/src/std/<name>.logos`, then `src/std/<name>.logos` in the working directory |

Two environment variables override the prefix and extend the module path:

| variable | meaning |
|---|---|
| `LOGOS_ROOT` | the prefix to use instead of the one derived from the executable. Point it at an unpacked tarball, a checkout, or a copy staged somewhere else. Unset or empty means "ask the executable". |
| `LOGOS_PATH` | extra directories to search for modules, colon-separated, tried in order after the asking file's own directory and before the shipped library. Empty entries are ignored, as `$PATH` ignores them. |

```sh
# a compiler copied out of its prefix, pointed back at it
LOGOS_ROOT=~/logos-0.2.1-x86_64-linux ~/bin/logosc build hello.logos -o hello

# your own modules, from any directory
LOGOS_PATH=~/logos-mods:./vendor/logos ./bin/logosc build app.logos -o app
```

Neither variable is needed for a normal install, and the working directory is
still consulted last, so a build started inside a checkout behaves exactly as it
did before. What does not work is splitting the tree up: `bin/logosc` on its own
has no runtime to link against and no standard library to resolve, and the
diagnostic prints the paths it tried rather than saying "runtime not found" and
leaving you to guess.

```sh
$ bin/logosc build greet.logos -o greet
greet.logos: E0800: runtime not found; searched: <prefix>/share/logos/runtime/rt.c, <prefix>/logos/runtime/rt.c, logos/runtime/rt.c

$ bin/logosc build greet.logos -o greet
greet/0: E0005: unknown module 'nope'; searched: <dir of greet.logos>/nope.logos, <prefix>/share/logos/std/nope.logos, <prefix>/src/std/nope.logos, src/std/nope.logos
```

Both are errors, exit 1, and both are one JSON object per line when `--json` is
on — the same guarantee every other diagnostic gives.

Two consequences worth knowing:

- the compiler writes its IR to `build/<stem>.ll` in the **working** directory,
  so a build run from inside the unpacked prefix creates `build/` there;
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
rm -rf logos-0.2.1-x86_64-linux
```

Nothing else was modified: no files outside the directory, no `PATH` entry, no
system package.
