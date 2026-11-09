# `src/std/io.logos` — create, write, close, read a file

Design §D9 needs the compiler to write its output and the driver to write a
temporary file. Logos has no comments and no doc form, so this file is the
header documentation the source cannot carry. Read it before calling the
module.

## The declarations the brief asked for do not compile

The plan names `rt_create` and `rt_write` as the two entry points. **Neither can
be declared from Logos on this branch**, because the checker reserves every name
beginning `rt_` for the runtime:

```
(mod t)
(extern fn rt_create :i64 ((path :str)))

FAIL exec/t/c -O0: build failed: E0003 t/rt_create: rt_ names are reserved
```

The rule lives in `logos/check.py` in `_extern_signature` (and again for program
`fn` definitions), and `tests/test_extern.py::test_an_rt_name_is_refused` pins
it. The reservation exists so a program cannot emit a symbol the linked runtime
already owns: an `extern fn rt_create` would `declare` the very symbol `rt.c`
defines, which is safe at the linker but not the namespace this language chose.
W3 may not change the checker, so the module reaches the same C behaviour
through libc:

| wanted | declared here | C signature | why equivalent |
|---|---|---|---|
| `rt_create` | `creat` | `int creat(const char *path, mode_t mode)` | `rt_create` is `open(path, O_WRONLY \| O_CREAT \| O_TRUNC, 0644)`; `creat` is exactly that call |
| `rt_write` | `write` | `ssize_t write(int fd, const void *buf, size_t len)` | `rt_write` is a full-write loop over `write`; `io-write` loops in Logos |
| `close` | `close` | `int close(int fd)` | the same libc call the brief names |

The visible contract is unchanged: create-or-truncate at mode 0644, write every
byte, return `-1` on failure. Two differences are worth knowing:

- `io-create` builds the NUL-terminated copy C needs with `alloc`, so an
  impossible length is the allocator's panic, not `rt_create`'s `-1`. Every real
  path length fits.
- `io-write` cannot see `errno`, so it retries **short** writes but reports the
  first negative or zero write as `-1` without retrying `EINTR`. `rt_write`
  retries `EINTR`. Nothing else differs; see the two functions below.

`creat` and `close` return C `int`, so they are declared `:i32` and widened with
`cast`; declaring them `:i64` would read the upper 32 bits of `rax`, which the
C ABI leaves undefined for an `int` return. `write` returns `ssize_t`, which is
64-bit, so it is declared `:i64`.

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
one place C needs a terminator is `io-create`, which copies the path and adds
one (below).

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
`creat` applies it), and returns the descriptor. The path is
**copied** into an `alloc` block with a trailing zero byte, because `creat` takes
a C string and a Logos `:str` is not terminated: passing the raw pointer lets C
run off the end of the literal and into whatever the data section holds next.
The copy is released with `free` before returning, so a successful create leaks
nothing; the descriptor is the caller's to close.

A path that cannot be opened — a missing directory, a read-only filesystem, a
name too long — returns `-1`, and **the program continues**. That is the whole
reason the return is an `:i64` and not a panic: a compiler that cannot write its
output must be able to say so. The caller checks `< 0`; `-1` is the only failure
value.

A path containing a zero byte creates the file its prefix names, because C ends
the string there. That is the same behaviour `rt_create` has; a path is not a
binary blob.

## `io-write`

Writes the whole of `s`, starting at byte `0`, and returns the total byte count.
`write` may accept fewer bytes than it was handed, so the loop advances by the
returned count and calls again with a `str-slice` view of the remainder — it
does not allocate and it does not copy. A zero-length `s` returns `0` without
calling `write`.

- A return of `w > 0` is progress; the loop continues.
- A return of `0` is a failed write, not a short success: `bad` is set and `-1`
  is returned.
- A return of `< 0` is a failed write; `-1` is returned.

`io-write` is **not** atomic and **not** a whole-file operation: bytes written by
earlier calls are already in the file when a later call fails. `fd` may be any
descriptor, including `1`, so this is also the way to write raw bytes to a pipe;
it is not `println`.

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

- No append, seek, positional read, `fsync`, rename, stat or unlink. The
  compiler writes one output file per run and exits; a file that should be
  removed is removed by whatever invoked it.
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
temp-path comparisons. Every case is `(leaks 0)` at `-O0` and `-O2`.
