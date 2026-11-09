# `src/std/io.logos` — create, write, close, read a file

Design §D9 needs the compiler to write its output and the driver to write a
temporary file. Logos has no comments and no doc form, so this file is the
header documentation the source cannot carry. Read it before calling the
module.

## Why the runtime symbols, not libc `creat`

`io-create` and `io-write` call `rt_create` and `rt_write` from
`logos/runtime/rt.c`, which is linked into every binary. **The runtime is the
right declaration here, not merely the convenient one:**

- `rt_create(path, n)` takes exactly what a Logos `:str` is — a pointer and a
  byte count. It copies the bytes, appends the NUL that C needs, opens
  `O_WRONLY | O_CREAT | O_TRUNC` at mode 0644, and releases the copy. libc
  `creat` takes a C string and a `mode_t`; declaring it as
  `((path :str) (mode :i64))` passes a **pair** where C expects a pointer and an
  `int`, so C reads `path` from the data pointer, `mode` from the string's
  length, and the third argument from `mode`. That appeared to work only when
  the `:str` buffer happened to hold a zero after the bytes: a computed path
  with any other byte there creates a different file name or runs off the
  buffer. `rt_create` has no such window, and its mode is 0644 rather than the
  path's length.
- `rt_write(fd, buf, len)` is a full-write loop: it advances over short writes,
  retries `EINTR`, and returns `-1` on the first real error or a zero-length
  write. The libc loop this module used before had to reimplement the progress
  rule and could not retry `EINTR`, because Logos cannot read `errno`.
- `close` stays libc: `int close(int)` takes one integer and no string, so
  `(extern fn close :i32 ((fd :i64)))` is exact. It is declared `:i32` and
  widened with `cast`, because the upper 32 bits of `rax` are undefined for an
  `int` return. `rt_create` and `rt_write` return `long`, so they are `:i64`.

An `extern fn` may name an `rt_` symbol — the runtime owns that definition —
while a `fn` definition of one is still E0003; the manual's "Reserved names"
section states the rule.

## The EINTR limit

The library never reads `errno`, so it cannot classify a failure. `rt_write`
retries `EINTR` inside the runtime; **`rt_create` and `io-close` do not**. An
interrupted `open` or `close` comes back as `-1` and is reported as an
ordinary failure, and the caller cannot tell it from a missing directory or a
bad descriptor. Retrying it would need an errno the language cannot name. For
regular files on Linux this is theoretical, but it is the limit.

## API

| function | returns | meaning |
|---|---|---|
| `io-create path` | `:i64` | open `path` for writing, create it if absent, truncate it if present, mode 0644 less the umask; the descriptor, or `-1` |
| `io-write fd s` | `:i64` | write every byte of `s`; the number written, or `-1` on the first failed write |
| `io-close fd` | `:i64` | `close(fd)`; `0` on success, `-1` on failure |
| `io-read path` | `:str` | the whole file, exactly `(read-file path)`; panics `R0007` if it cannot be read |
| `io-temp-path stem n` | `:str` | `/tmp/<stem>-<n>`, with `n` in decimal |

Everything is a **byte** count or a byte string: `:str` is a pointer and a
length, never NUL terminated, and these functions never assume otherwise. The
one place C needs a terminator is `io-create`, and `rt_create` adds it (below).

```logos
(use io)

(fn save :void ((path :str) (text :str))
  (let fd :i64 (io-create path))
  (if (< fd 0)
    (println "could not create")
    (if (= (io-write fd text) (str-len text))
      (println (io-close fd))
      (println "short write"))))

(fn example :void ()
  (let path :str (io-temp-path "compile" 0))
  (save path "compiled\n")
  (let again :str (io-read path))
  (println (str-len again)))
```

## `io-create`

Creates or truncates, mode 0644 less the process umask (the `open` behind
`rt_create` applies it), and returns the descriptor. The path is **copied**
inside the runtime into a NUL-terminated C string, because `open` takes a C
string and a Logos `:str` is not terminated: passing the raw pointer would let
C run off the end of the buffer. The copy is released before the runtime
returns, so a successful create leaks nothing; the descriptor is the caller's
to close.

A path that cannot be opened — a missing directory, a read-only filesystem, a
name too long — returns `-1`, and **the program continues**. That is the whole
reason the return is an `:i64` and not a panic: a compiler that cannot write its
output must be able to say so. The caller checks `< 0`; `-1` is the only failure
value.

A path containing a zero byte creates the file its prefix names, because C ends
the string there. A path is not a binary blob.

## `io-write`

Writes the whole of `s`, starting at byte `0`, and returns the total byte count.
`rt_write` owns the loop: a short write advances the runtime's pointer by the
returned count, `EINTR` is retried, and a zero-length result is an error rather
than a short success. A zero-length `s` returns `0` without a write.

The return is `-1` on the first real error, or the total once every byte is
written. `io-write` is **not** atomic and **not** a whole-file operation: bytes
written by earlier calls are already in the file when a later call fails. `fd`
may be any descriptor, including `1`, so this is also the way to write raw
bytes to a pipe; it is not `println`.

## `io-close`

Calls `close` and widens its result. `0` is success, `-1` is failure. **Closing
a descriptor twice is the caller's error and is not detected or tested**: the
second call is a libc `EBADF` that this module reports as `-1`, and on a reused
descriptor number it would close somebody else's file. Close once, on every
path out of the function, and do not touch the descriptor afterwards.

## `io-read`

Exactly `(read-file path)`: the whole file as a fresh `:str`, a zero-length file
as `""`, and a file that cannot be read as a panic `R0007` at the call, naming
the path. The runtime's buffer is process-lifetime and untracked, so reading
never appears in a leak report and the caller has nothing to free. Reading the
file the module just wrote is the round trip the tests pin.

## `io-temp-path`

Builds **`/tmp/<stem>-<n>`** with two `str-concat` calls and `str-from-i64`. It
does not create anything, does not check whether the name exists, and does not
consult the environment:

- `getenv` cannot be declared, because it takes a C string rather than a
  `(pointer, length)` pair and its result has no length. `/tmp` is the temp
  directory this module promises; the design's Linux target makes that the same
  directory `$TMPDIR` usually names.
- No `mkstemp` randomness: the caller's `n` is the uniqueness. Two calls with
  different `n` always differ (`/tmp/x-7` and `/tmp/x-8`); two calls with the
  same `stem` and `n` are the same name, and two processes that both pass `0`
  collide. A caller that needs uniqueness keeps a counter and increments it per
  file, which is exactly what the driver and the 1 MB test do.
- `n` is formatted decimal, not hashed, so the string is predictable: negative
  values give `/tmp/<stem>--5`.

The result is a fresh `str-concat` buffer, process-lifetime and untracked like
every built string; it owns nothing and needs no release.

## What it does not do

- No append, seek, positional read, `fsync`, rename, stat or **unlink**. The
  compiler writes one output file per run and exits; a file that should be
  removed is removed by whatever invoked it. The library has no `unlink`, so
  `io_test.logos` **does not clean up**: the round-trip case leaves
  `/tmp/round-1`, the fragment case `/tmp/frag-2` and the empty-file case
  `/tmp/empty-3`. Each case owns its own name and a repeated run truncates it,
  so the suite is re-runnable; it is not hermetic on a shared `/tmp`.
- No directory creation: a path whose parent is missing is `-1` from
  `io-create`, not a `mkdir -p`.
- No buffered writer, no error type. `-1` is the whole error vocabulary,
  because the language has no way to carry errno out of libc.
- No `io-run`: the plan offered one, then dropped it. `(run prog args)` from W2
  already starts a child, captures both pipes and reports `124` on timeout, so a
  second wrapper would be a second contract for the same form.

`src/std/io_test.logos` pins five cases: the round trip with a middle empty
write, 1 MB (1,048,576 bytes) written through 1,024 fragments of 1 KB and read
back with the exact length and byte sum, an empty file, a create in a missing
directory that returns `-1` and lets the program continue, and four
temp-path comparisons. Every case is `(leaks 0)` at `-O0` and `-O2`. The
round-trip, fragment and empty-file paths are computed by `io-temp-path`, not
written as literals, and each case uses a distinct counter value so no case
can truncate another's file.
