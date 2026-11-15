# Release and publish

How a Logos compiler release is built, proved and published. `docs/install.md`
is the consumer's page; this one is the maintainer's.

The pipeline is four files and no service: `tools/dist.sh` assembles the
artifact, `tools/verify_install.sh` proves it installs, `tools/release.sh`
rehearses or publishes, and `.github/workflows/release.yml` runs the same steps
when a `v*` tag is pushed.

## The version has one source

`logosc version` prints `logos <version>`, and the string lives in exactly one
place: `main-version` in `src/logosc/main.logos`. A release is named after it —
tag `v<version>` — and the pipeline refuses to publish when the tag and the
compiler disagree:

```
$ make release
release: version 0.1.0 from 9194412
...
$ gh release create v0.1.0 ...
```

Nothing else in the repository carries a version, so there is no file to forget.

## Rehearse

```sh
make release
```

It builds the tarball **twice** and requires the two SHA-256 sums to match, then
unpacks the tarball into a scratch directory and compiles three programs from it
— hello world, a standard-library import, and a program with a type error that
must be refused with a diagnostic code. Measured on `9194412`:

```
release: version 0.1.0 from 9194412
dist: dist/logos-0.1.0-x86_64-linux.tar.gz (510545 bytes)
dist: 6f5984632f4dcd2659f49117dec625da8229a3f2e68968b13f1cd6d3f9335698  logos-0.1.0-x86_64-linux.tar.gz
release: tarball reproducible, sha256 6f5984632f4dcd2659f49117dec625da8229a3f2e68968b13f1cd6d3f9335698
PASS layout: the compiler, the runtime, the standard library and VERSION
PASS version: 0.1.0
PASS build: hello world compiles and prints
PASS stdlib: (use str) resolves and links
PASS diagnostics: bad/main/2: E0100: let 'x' has type :i64, found :str

5/5 install checks passed
```

A rehearsal publishes nothing and is allowed on a dirty tree — it is how the
pipeline is tested before the change is committed. Publishing is not.

## Publish

```sh
git tag -s v0.1.0 -m "Logos 0.1.0"     # on the commit to release
git push origin v0.1.0                  # this is what starts the workflow
```

The tag push runs `.github/workflows/release.yml`:

| Job | What it proves |
|---|---|
| `verify` | the six gates pass on the tagged commit — the same `tools/pr_gate.sh` a contributor runs, so a release cannot ship a commit the pull request gate would refuse |
| `build` | the tarball builds and its `verify_install` checks pass; the artifact is uploaded |
| `reproduce` | a **second, fresh runner** builds the tarball from the same tag and the two SHA-256 sums must be equal — the reproducibility claim measured, not asserted |
| `publish` | the tag equals `v<version>`, then `gh release create ... --verify-tag` attaches the tarball and `SHA256SUMS`, and the release is read back to confirm its assets |

`make publish` (`bash tools/release.sh --publish`) does the same thing from a
machine with `gh` authenticated, for the case where CI is unavailable. It
refuses a dirty tree, a missing tag, and a tag that does not point at `HEAD`.

The notes come from the `CHANGELOG.md` section for that version when the
changelog has one, and from the commit subjects since the previous tag when it
does not — a release never ships blank notes.

## What the artifact is

```
logos-<version>-x86_64-linux/
├── bin/logosc
├── logos/runtime/rt.c, rt.h
├── src/std/{io,map,str}.logos
├── share/doc/{LOGOS.md,README.md,LICENSE,CHANGELOG.md}
├── INSTALL.md
└── VERSION            version, commit, and the recorded clang and ld
```

The paths are not a packaging convention: the compiler looks for the runtime at
`logos/runtime/rt.c` and the standard library at `src/std/<name>.logos` relative
to the working directory, so the tarball mirrors the repository. Making those
paths resolve relative to the executable (`/proc/self/exe`, with `LOGOS_ROOT`
and `LOGOS_PATH` overrides) is a compiler change — tracked for v1.1 — and the
layout stays valid when it lands, because it is still the same two paths.

## Why the tarball is byte-reproducible

`tools/dist.sh` fixes every input a tarball normally leaks:

- file order: `tar --sort=name`;
- ownership: `--owner=0 --group=0 --numeric-owner`;
- mtime: `--mtime` set to the **commit** date, never the wall clock;
- compression: `gzip -9 -n`, so no filename or timestamp in the gzip header;
- `VERSION`: the toolchain recorded in `bootstrap/toolchain.txt`, not the host's.

The compiler binary inside it is the one the gates test: `tools/logosc.sh`
rebuilds it from `src/` when the source is newer, and the self-hosting gate
proves that binary and the committed stage-0 are the same compiler byte for
byte.

## The toolchain is part of the claim

`bootstrap/logosc` is a byte-identity claim, and clang writes its own version
into every binary it produces. That claim is only measurable with the clang the
stage-0 was built with, which `bootstrap/toolchain.txt` records:

```
clang: Ubuntu clang version 14.0.0-1ubuntu1.1
ld: GNU ld (GNU Binutils for Ubuntu) 2.38
```

`tools/toolchain.sh --check` compares that record with the host, and both the
pull request gate and the release workflow run it **before** the six gates, so a
host that cannot reproduce the stage-0 is told so by name in seconds instead of
failing the self-hosting gate an hour later with rebuild advice that would not
help. `tools/toolchain.sh --install` installs the recorded clang on Debian and
Ubuntu.

Changing either recorded line is a release decision: rebuild the bootstrap with
the new toolchain and record it in the same commit.

## What this pipeline deliberately does not do

- **No container image.** The compiler shells out to `clang` on the host, so an
  image would have to ship a C toolchain and still could not compile for a host
  without one; the `ubuntu-22.04` runner is already the pinned environment the
  release is built in. Revisit if a `musl` static build replaces the glibc floor.
- **No npm or PyPI package.** The artifact is a native binary plus its runtime
  source; there is no interpreter ecosystem to publish into, and a registry adds
  a maintainer and a mirror without removing a step for the consumer.
- **No install to `~/.local`.** Copying the tree into a prefix would not change
  how the compiler finds its runtime and stdlib (see above), so it would add a
  second layout to document without adding a capability. Unpacking *is* the
  install.
- **No diverse double-compiling of the stage-0.** `bootstrap/logosc.sha256`
  proves integrity, not origin. The release notes name this as a known
  limitation; the mitigation is the recorded toolchain and the `reproduce` job,
  which together prove the tag builds the artifact everywhere the project tests.
