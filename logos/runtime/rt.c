/* C runtime for Logos. See runtime/rt.h for the contract.
 *
 * Three rules hold for every function here: write full lengths, never treat a
 * Logos string as NUL terminated, and retry short writes instead of dropping
 * bytes. A write that makes no progress is reported as an error, never
 * swallowed as a short success. Fatal conditions call rt_panic, which exits
 * with status 2.
 */

/* POSIX 2008 gives pthread_mutexattr_settype and the error-checking mutex
 * type. Defining it before any header, rather than relying on the compiler's
 * default, keeps the runtime's declarations the same at -std=c11, which the
 * probes use, and at the driver's default dialect. */
#define _POSIX_C_SOURCE 200809L

#include "rt.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* The environment a child inherits. POSIX declares this in <unistd.h> only
 * under wider feature macros than the runtime defines, so it is stated here. */
extern char **environ;

long rt_write(int fd, const void *buf, size_t len) {
    const unsigned char *p = buf;
    size_t done = 0;

    while (done < len) {
        ssize_t n = write(fd, p + done, len - done);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        if (n == 0) {
            /* A zero-length write would end the loop with a short count, which
             * callers must never mistake for success. */
            errno = EIO;
            return -1;
        }
        done += (size_t)n;
    }

    return (long)done;
}

_Noreturn void rt_panic(const char *path, const char *code, const char *msg) {
    static const char sep[] = ": ";
    static const char newline[] = "\n";
    static const char runtime[] = "<runtime>";
    const char *where = path != NULL ? path : runtime;

    /* One line, exactly `path: code: message`, so the node path leads and the
     * stable runtime code is machine-greppable between it and the prose. A
     * check with no node behind it still names a location: the runtime itself,
     * so the field is never empty and the line never starts with a colon. */
    (void)rt_write(STDERR_FILENO, where, strlen(where));
    (void)rt_write(STDERR_FILENO, sep, sizeof sep - 1);
    if (code != NULL) {
        (void)rt_write(STDERR_FILENO, code, strlen(code));
        (void)rt_write(STDERR_FILENO, sep, sizeof sep - 1);
    }
    if (msg != NULL) {
        (void)rt_write(STDERR_FILENO, msg, strlen(msg));
    }
    (void)rt_write(STDERR_FILENO, newline, sizeof newline - 1);

    exit(2);
}

/* ---------------------------------------------------------------------------
 * Allocation and the leak tracker
 *
 * One record per distinct address the program has allocated, in an
 * open-addressed table with linear probing. `ptr` is the key: a record with a
 * NULL key has never been used, so a probe stops there and every lookup is
 * finite. Records are never removed — a freed block keeps its record with
 * `live` clear — which is what lets the second free report where the block was
 * allocated rather than merely that it was. The table therefore holds one
 * record per address ever allocated, not per address live.
 *
 * LOGOS_DEBUG changes one thing and it is what makes the R0002 check exact:
 * rt_free marks the record dead but does not return the block to malloc, so a
 * freed address cannot be recycled into a fresh live block. A release build
 * frees normally; there a recycled address overwrites the old record and a
 * stale owner of the old block is indistinguishable from the owner of the new
 * one. See rt.h for the limit that leaves open.
 * ------------------------------------------------------------------------- */

typedef struct {
    void *ptr;          /* the key, NULL in an unused slot */
    size_t size;        /* bytes the caller asked for */
    const char *path;   /* the `alloc` node that asked for them */
    unsigned long long seq; /* allocation order, for the report */
    int live;           /* 1 while the block is allocated */
} rt_block;

static rt_block *rt_slots;
static size_t rt_cap;    /* power of two, or 0 before the first allocation */
static size_t rt_used;   /* slots holding a record */
static size_t rt_live;   /* records whose block is still allocated */
static unsigned long long rt_seq;

/* The one lock every tracker operation holds. All of the state above is
 * guarded by it: a thread that allocates while another frees must see one
 * table, and the counters must move with the records they count. It is a
 * debug facility, so the contention is irrelevant beside the malloc each
 * entry already pays for; a per-thread tracker would buy nothing and would
 * still need a merge under a global lock at exit, in allocation order.
 *
 * A failure to lock is a pthread failure like any other: R0005, and the
 * process ends rather than touching the table unguarded. */
static pthread_mutex_t rt_tracker_lock = PTHREAD_MUTEX_INITIALIZER;

static void rt_tracker_enter(void) {
    if (pthread_mutex_lock(&rt_tracker_lock) != 0) {
        rt_panic(NULL, "R0005", "could not lock the leak tracker");
    }
}

static void rt_tracker_leave(void) {
    if (pthread_mutex_unlock(&rt_tracker_lock) != 0) {
        rt_panic(NULL, "R0005", "could not unlock the leak tracker");
    }
}

/* Mix an address into a bucket index. The low bits of a malloc'd address are
 * the ones worth spreading, so the multiply and the shift both use them. */
static size_t rt_hash(const void *p) {
    uintptr_t x = (uintptr_t)p;
    x ^= x >> 33;
    x *= (uintptr_t)0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    return (size_t)x;
}

static void rt_place(void *ptr, size_t size, const char *path,
                     unsigned long long seq, int live) {
    size_t mask = rt_cap - 1;
    size_t i = rt_hash(ptr) & mask;

    while (rt_slots[i].ptr != NULL) {
        if (rt_slots[i].ptr == ptr) {
            break;
        }
        i = (i + 1) & mask;
    }
    if (rt_slots[i].ptr == NULL) {
        rt_used++;
    }
    rt_slots[i].ptr = ptr;
    rt_slots[i].size = size;
    rt_slots[i].path = path;
    rt_slots[i].seq = seq;
    rt_slots[i].live = live;
}

static void rt_grow(void) {
    size_t old_cap = rt_cap;
    rt_block *old = rt_slots;
    size_t cap = old_cap ? old_cap * 2 : 64;
    size_t i;

    rt_slots = calloc(cap, sizeof *rt_slots);
    if (rt_slots == NULL) {
        /* The tracker cannot record the block, so it says so rather than
         * pretending the allocation is tracked. */
        rt_panic(NULL, "R0003", "out of memory in the leak tracker");
    }
    rt_cap = cap;
    rt_used = 0;
    for (i = 0; i < old_cap; i++) {
        if (old[i].ptr != NULL) {
            rt_place(old[i].ptr, old[i].size, old[i].path, old[i].seq,
                     old[i].live);
        }
    }
    free(old);
}

static rt_block *rt_find(void *p) {
    size_t mask;
    size_t i;

    if (rt_cap == 0) {
        return NULL;
    }
    mask = rt_cap - 1;
    i = rt_hash(p) & mask;
    while (rt_slots[i].ptr != NULL) {
        if (rt_slots[i].ptr == p) {
            return &rt_slots[i];
        }
        i = (i + 1) & mask;
    }
    return NULL;
}

void *rt_alloc(size_t n, size_t align, const char *path) {
    void *p;
    rt_block *b;

    if (align == 0 || (align & (align - 1)) != 0) {
        /* Every power of two up to sixteen is all a Logos type asks for, and
         * malloc satisfies all of them; a caller-supplied odd alignment would
         * be a promise this allocator does not keep. */
        rt_panic(path, "R0003", "allocation alignment is not a power of two");
    }
    if (align > 16) {
        /* malloc guarantees max_align_t (sixteen bytes on x86-64). A wider
         * alignment would need aligned_alloc and a matching free, which is a
         * later task's problem; refusing is better than misaligning. */
        rt_panic(path, "R0003", "allocation alignment above sixteen is not supported");
    }
    if (n == 0) {
        /* malloc(0) is allowed to hand back the same non-NULL pointer every
         * time, and two live blocks must have two addresses, so a zero-byte
         * request takes one byte of storage. The record keeps the requested
         * size, 0: the leak report says `LEAK 0 bytes`, which is what the
         * program asked for. */
        p = malloc(1);
    } else {
        p = malloc(n);
    }
    if (p == NULL) {
        rt_panic(path, "R0003", "out of memory");
    }
    rt_tracker_enter();
    /* Keep the table at most three quarters full, so a probe always reaches an
     * unused slot and rt_find/rt_place terminate. */
    if (rt_cap == 0 || (rt_used + 1) * 4 > rt_cap * 3) {
        rt_grow();
    }
    b = rt_find(p);
    if (b == NULL) {
        rt_place(p, n, path, rt_seq++, 1);
        rt_live++;
    } else {
        /* Only a release build can get here: it returns freed blocks to
         * malloc, so a new block may land on an address that had a dead
         * record. The record is reused and the old size and path go with it.
         * A debug build quarantines every freed block, so reuse cannot happen
         * and a stale owner always finds the original dead record. */
        if (!b->live) {
            rt_live++;
        }
        b->size = n;
        b->path = path;
        b->seq = rt_seq++;
        b->live = 1;
    }
    rt_tracker_leave();
    return p;
}

void rt_free(void *p) {
    rt_block *b;

    if (p == NULL) {
        return;
    }
    rt_tracker_enter();
    b = rt_find(p);
    if (b == NULL) {
        /* Nothing was ever allocated here — not a block this process created,
         * and not an address it released. It is not a double free: no block
         * exists to be released twice, so it gets its own code. The runtime is
         * the only location there is to name. */
        rt_panic(NULL, "R0004", "free of a pointer that was never allocated");
    }
    if (!b->live) {
        /* The pointer has been released already. Naming the `alloc` that made
         * it is the only location left: the free site is the caller's, and the
         * block itself no longer exists. */
        rt_panic(b->path, "R0002", "double free");
    }
    b->live = 0;
    rt_live--;
    rt_tracker_leave();
#ifdef LOGOS_DEBUG
    /* Quarantine: the block stays allocated for the life of the process. The
     * address can then never be recycled into a fresh live block, which is
     * what makes a stale owner's second free find this dead record instead of
     * somebody else's live one. */
    (void)p;
#else
    free(p);
#endif
}

/* Whether this address is a live block. The thread handle's join uses it to
 * refuse a handle that was already joined before it reads the handle's own
 * fields: the handle is released by the first join, so the test must be the
 * tracker's, not the freed memory's. */
static int rt_is_live_block(void *p) {
    rt_block *b;
    int live = 0;

    if (p == NULL) {
        return 0;
    }
    rt_tracker_enter();
    b = rt_find(p);
    if (b != NULL && b->live) {
        live = 1;
    }
    rt_tracker_leave();
    return live;
}

size_t rt_leak_count(void) {
    size_t count;

    rt_tracker_enter();
    count = rt_live;
    rt_tracker_leave();
    return count;
}

/* Write a non-negative decimal count, without printf: the runtime formats its
 * own numbers everywhere else, and a leak line must not depend on a locale. */
static void rt_write_size(int fd, size_t v) {
    char digits[20];
    size_t n = 0;

    do {
        digits[n++] = (char)('0' + (int)(v % 10));
        v /= 10;
    } while (v != 0);

    while (n > 0) {
        (void)rt_write(fd, &digits[--n], 1);
    }
}

void rt_leak_report(void) {
    struct rt_leak_line {
        size_t size;
        const char *path;
        unsigned long long seq;
    };
    struct rt_leak_line *lines;
    size_t count = 0;
    size_t i;
    size_t j;

    static const char prefix[] = "LEAK ";
    static const char middle[] = " bytes at ";
    static const char newline[] = "\n";

    /* Snapshot the live records while the table is locked, then print with the
     * lock released. Printing under the lock would hold up a thread that is
     * allocating, and holding pointers into the table would be worse: a
     * concurrent rt_alloc may grow it, which frees the table the pointers came
     * from. The snapshot copies the two values and the path literal; nothing
     * in it depends on the table afterwards. */
    rt_tracker_enter();
    if (rt_live == 0) {
        rt_tracker_leave();
        return;
    }
    lines = calloc(rt_live, sizeof *lines);
    if (lines == NULL) {
        /* The report is diagnostics; failing to build it must not change the
         * program's exit status or pretend the blocks are gone. */
        rt_tracker_leave();
        return;
    }
    for (i = 0; i < rt_cap; i++) {
        if (rt_slots[i].ptr != NULL && rt_slots[i].live) {
            lines[count].size = rt_slots[i].size;
            lines[count].path = rt_slots[i].path;
            lines[count].seq = rt_slots[i].seq;
            count++;
        }
    }
    rt_tracker_leave();

    /* Allocation order, so two runs of the same program report in the same
     * order even though the addresses differ. Allocation happens under the
     * lock, so the sequence numbers are a total order across threads. */
    for (i = 1; i < count; i++) {
        struct rt_leak_line held = lines[i];
        j = i;
        while (j > 0 && lines[j - 1].seq > held.seq) {
            lines[j] = lines[j - 1];
            j--;
        }
        lines[j] = held;
    }
    for (i = 0; i < count; i++) {
        (void)rt_write(STDERR_FILENO, prefix, sizeof prefix - 1);
        rt_write_size(STDERR_FILENO, lines[i].size);
        (void)rt_write(STDERR_FILENO, middle, sizeof middle - 1);
        if (lines[i].path != NULL) {
            (void)rt_write(STDERR_FILENO, lines[i].path,
                           strlen(lines[i].path));
        }
        (void)rt_write(STDERR_FILENO, newline, sizeof newline - 1);
    }
    free(lines);
}

/* ---------------------------------------------------------------------------
 * Printing and formatting
 *
 * Output goes through rt_write, so it is exactly the bytes intended: no
 * terminator is trusted, no format string interprets the data, and a NUL
 * inside a string is written like any other byte.
 * ------------------------------------------------------------------------- */

/* The decimal digits of v, most significant first. Returns the count. */
static size_t rt_format_u64(char *out, unsigned long long v) {
    char digits[20];
    size_t n = 0;
    size_t i;

    do {
        digits[n++] = (char)('0' + (int)(v % 10));
        v /= 10;
    } while (v != 0);

    for (i = 0; i < n; i++) {
        out[i] = digits[n - 1 - i];
    }
    return n;
}

/* The decimal text of v, `-` included. Returns the count.
 *
 * The magnitude is taken as an unsigned value: negating INT64_MIN in a signed
 * type is undefined, while `0 - (unsigned)v` is exactly 2^63. */
static size_t rt_format_i64(char *out, long long v) {
    unsigned long long magnitude;

    if (v < 0) {
        out[0] = '-';
        magnitude = 0ULL - (unsigned long long)v;
        return 1 + rt_format_u64(out + 1, magnitude);
    }
    return rt_format_u64(out, (unsigned long long)v);
}

/* The shortest decimal text that reads back as v, and its length.
 *
 * `%g` at fifteen significant digits already round-trips most values; the
 * loop raises the precision until strtod returns the same double, so 0.1
 * prints as `0.1` instead of `0.10000000000000001`. NaN never compares equal
 * to itself, so it is returned as the first spelling tried. */
static size_t rt_format_f64(char *out, size_t cap, double v) {
    int precision;
    size_t last = 0;

    for (precision = 15; precision <= 17; precision++) {
        int written = snprintf(out, cap, "%.*g", precision, v);
        char *end = NULL;

        if (written <= 0 || (size_t)written >= cap) {
            return last;
        }
        last = (size_t)written;
        if (v != v) {
            /* NaN: there is no round trip to ask about. */
            return last;
        }
        if (strtod(out, &end) == v && end != NULL && *end == '\0') {
            return last;
        }
    }
    return last;
}

void rt_print_str(const unsigned char *p, size_t n) {
    if (n != 0) {
        (void)rt_write(STDOUT_FILENO, p, n);
    }
}

void rt_print_i64(long long v) {
    char text[24];
    size_t n = rt_format_i64(text, v);
    (void)rt_write(STDOUT_FILENO, text, n);
}

void rt_print_u64(unsigned long long v) {
    char text[20];
    size_t n = rt_format_u64(text, v);
    (void)rt_write(STDOUT_FILENO, text, n);
}

void rt_print_f64(double v) {
    char text[40];
    size_t n = rt_format_f64(text, sizeof text, v);
    if (n != 0) {
        (void)rt_write(STDOUT_FILENO, text, n);
    }
}

void rt_println(void) {
    static const char newline[] = "\n";
    (void)rt_write(STDOUT_FILENO, newline, sizeof newline - 1);
}

/* ---------------------------------------------------------------------------
 * Strings built by the runtime
 *
 * These are not tracked by the leak tracker; see rt.h for why. A process that
 * builds a string pays one malloc for it and never gives it back, which is
 * the price of `:str` having no owner to hand it to.
 * ------------------------------------------------------------------------- */

/* A fresh, empty buffer with room for `cap` bytes. */
static rt_str rt_str_new(size_t cap) {
    rt_str s;

    s.data = malloc(cap ? cap : 1);
    if (s.data == NULL) {
        rt_panic(NULL, "R0003", "out of memory");
    }
    s.len = 0;
    s.cap = cap;
    return s;
}

unsigned char *rt_str_concat(const unsigned char *a, size_t an,
                             const unsigned char *b, size_t bn,
                             size_t *out_len) {
    rt_str s;
    size_t total;

    if (an > (size_t)-1 - bn) {
        rt_panic(NULL, "R0003", "string length overflows");
    }
    total = an + bn;
    s = rt_str_new(total);
    if (an != 0) {
        memcpy(s.data, a, an);
    }
    if (bn != 0) {
        memcpy(s.data + an, b, bn);
    }
    s.len = total;
    if (out_len != NULL) {
        *out_len = s.len;
    }
    return s.data;
}

int rt_str_eq(const unsigned char *a, size_t an,
              const unsigned char *b, size_t bn) {
    if (an != bn) {
        return 0;
    }
    if (an == 0) {
        /* Two empty strings are equal wherever their data pointers point,
         * including nowhere. */
        return 1;
    }
    return memcmp(a, b, an) == 0;
}

unsigned char *rt_str_from_i64(long long v, size_t *out_len) {
    char text[24];
    size_t n = rt_format_i64(text, v);
    rt_str s = rt_str_new(n);

    memcpy(s.data, text, n);
    s.len = n;
    if (out_len != NULL) {
        *out_len = n;
    }
    return s.data;
}

unsigned char *rt_read_all(size_t *out_len, const char *path) {
    size_t cap = 4096;
    size_t len = 0;
    unsigned char *buffer = malloc(cap);

    if (buffer == NULL) {
        rt_panic(path, "R0003", "out of memory");
    }
    for (;;) {
        ssize_t n;

        if (len == cap) {
            /* Double the buffer, refusing a size that could not wrap back to
             * something meaningful. A failed realloc leaves the old buffer
             * live, so it is freed before the panic rather than at exit. */
            unsigned char *grown;
            if (cap > SIZE_MAX / 2) {
                free(buffer);
                rt_panic(path, "R0003", "standard input is too large");
            }
            grown = realloc(buffer, cap * 2);
            if (grown == NULL) {
                free(buffer);
                rt_panic(path, "R0003", "out of memory");
            }
            buffer = grown;
            cap *= 2;
        }
        n = read(STDIN_FILENO, buffer + len, cap - len);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            free(buffer);
            rt_panic(path, "R0003", "read from standard input failed");
        }
        if (n == 0) {
            break;
        }
        len += (size_t)n;
    }
    if (out_len != NULL) {
        *out_len = len;
    }
    return buffer;
}

/* ---------------------------------------------------------------------------
 * Files, arguments and child processes
 *
 * Every buffer here lives until the process exits and is therefore plain
 * malloc, never rt_alloc: shortcut: process-lifetime buffers are not tracked;
 * upgrade if one ever needs releasing. A tracked block that is never released
 * would print LEAK on every program that reads a file or runs a child, and the
 * corpus asserts `(leaks 0)`.
 * ------------------------------------------------------------------------- */

/* A NUL-terminated copy of n bytes, for the C calls that need one. Returns
 * NULL on an impossible length or failed malloc; the caller decides whether
 * that is a panic or a -1. */
static char *rt_cstr(const unsigned char *p, size_t n) {
    char *s;

    if (n == (size_t)-1) {
        return NULL;
    }
    s = malloc(n + 1);
    if (s == NULL) {
        return NULL;
    }
    if (n != 0) {
        memcpy(s, p, n);
    }
    s[n] = '\0';
    return s;
}

long rt_create(const unsigned char *path, size_t n) {
    char *cpath = rt_cstr(path, n);
    int fd;

    if (cpath == NULL) {
        return -1;
    }
    fd = open(cpath, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    free(cpath);
    return fd < 0 ? -1 : (long)fd;
}

/* A node path as rt_panic wants it: NULL when there is none, so the fallback
 * `<runtime>` is printed rather than a line that starts with a colon. An empty
 * literal is the shape a missing path degrades to, so it counts as none. */
static const char *rt_node_path(const char *path) {
    if (path == NULL || path[0] == '\0') {
        return NULL;
    }
    return path;
}

/* R0007 for a path that could not be read. The message names the file; the
 * location is the node that asked, like a compile error. */
static _Noreturn void rt_read_file_panic(const unsigned char *path, size_t n,
                                         const char *node_path) {
    static const char prefix[] = "could not read ";
    char *cpath = rt_cstr(path, n);
    char *msg;
    size_t plen = sizeof prefix - 1;

    if (cpath == NULL || n > (size_t)-1 - sizeof prefix) {
        rt_panic(rt_node_path(node_path), "R0003", "out of memory");
    }
    msg = malloc(sizeof prefix + n);
    if (msg == NULL) {
        rt_panic(rt_node_path(node_path), "R0003", "out of memory");
    }
    memcpy(msg, prefix, plen);
    memcpy(msg + plen, cpath, n);
    msg[plen + n] = '\0';
    rt_panic(rt_node_path(node_path), "R0007", msg);
}

size_t rt_read_file(const unsigned char *path, size_t n,
                    const unsigned char **out, const char *node_path) {
    char *cpath = rt_cstr(path, n);
    struct stat st;
    unsigned char *buffer;
    size_t cap = 4096;
    size_t len = 0;
    int fd;

    if (cpath == NULL) {
        rt_panic(rt_node_path(node_path), "R0003", "out of memory");
    }
    fd = open(cpath, O_RDONLY);
    if (fd < 0) {
        free(cpath);
        rt_read_file_panic(path, n, node_path);
    }
    /* A regular file's size is a good first guess and saves the growth loop
     * for the common case. /proc reports zero, so the guess stays 4096 there
     * and the read loop grows; a file that changes size underneath us is still
     * read to its actual end. */
    if (fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_size > 0 &&
        (unsigned long long)st.st_size < (unsigned long long)(size_t)-1) {
        cap = (size_t)st.st_size + 1;
    }
    buffer = malloc(cap);
    if (buffer == NULL) {
        close(fd);
        free(cpath);
        rt_panic(rt_node_path(node_path), "R0003", "out of memory");
    }
    for (;;) {
        ssize_t got;

        if (len == cap) {
            unsigned char *grown;
            if (cap > (size_t)-1 / 2) {
                free(buffer);
                close(fd);
                free(cpath);
                rt_panic(rt_node_path(node_path), "R0003",
                         "file is too large");
            }
            grown = realloc(buffer, cap * 2);
            if (grown == NULL) {
                free(buffer);
                close(fd);
                free(cpath);
                rt_panic(rt_node_path(node_path), "R0003", "out of memory");
            }
            buffer = grown;
            cap *= 2;
        }
        got = read(fd, buffer + len, cap - len);
        if (got < 0) {
            if (errno == EINTR) {
                continue;
            }
            free(buffer);
            close(fd);
            free(cpath);
            rt_read_file_panic(path, n, node_path);
        }
        if (got == 0) {
            break;
        }
        len += (size_t)got;
    }
    close(fd);
    free(cpath);
    if (out != NULL) {
        *out = buffer;
    }
    return len;
}

/* The command line, filled once by a constructor so the emitted `main` keeps
 * its fixed signature. Both the bytes and the array of pairs live until the
 * process exits; they are plain malloc for the reason in the section comment
 * above. */
static rt_arg *rt_argv;
static size_t rt_argv_count;

__attribute__((constructor)) static void rt_args_init(void) {
    unsigned char *raw;
    size_t cap = 4096;
    size_t len = 0;
    size_t count = 0;
    size_t i;
    int fd;

    fd = open("/proc/self/cmdline", O_RDONLY);
    if (fd < 0) {
        return;
    }
    raw = malloc(cap);
    if (raw == NULL) {
        close(fd);
        return;
    }
    for (;;) {
        ssize_t got;

        if (len == cap) {
            unsigned char *grown;
            if (cap > (size_t)-1 / 2) {
                free(raw);
                close(fd);
                return;
            }
            grown = realloc(raw, cap * 2);
            if (grown == NULL) {
                free(raw);
                close(fd);
                return;
            }
            raw = grown;
            cap *= 2;
        }
        got = read(fd, raw + len, cap - len);
        if (got < 0) {
            if (errno == EINTR) {
                continue;
            }
            free(raw);
            close(fd);
            return;
        }
        if (got == 0) {
            break;
        }
        len += (size_t)got;
    }
    close(fd);

    /* The kernel writes each argument followed by NUL, so the number of
     * arguments is the number of NULs — plus a final segment if the file did
     * not end on one. An empty argument still has its own NUL and counts. */
    for (i = 0; i < len; i++) {
        if (raw[i] == '\0') {
            count++;
        }
    }
    if (len != 0 && raw[len - 1] != '\0') {
        count++;
    }
    if (count != 0) {
        rt_arg *args = malloc(count * sizeof *args);
        if (args == NULL) {
            /* The pair is all or nothing: with no array there is no count. */
            free(raw);
            rt_argv = NULL;
            rt_argv_count = 0;
            return;
        }
        i = 0;
        for (size_t k = 0; k < count; k++) {
            size_t start = i;
            while (i < len && raw[i] != '\0') {
                i++;
            }
            args[k].ptr = raw + start;
            args[k].len = i - start;
            i++; /* the NUL, or one past the end after a final unterminated run */
        }
        rt_argv = args;
        rt_argv_count = count;
        return;
    }
    rt_argv = NULL;
    rt_argv_count = 0;
}

size_t rt_args(const rt_arg **args) {
    /* Never a count without an array: a caller reads *args only when the
     * count it gets back is non-zero. */
    if (rt_argv == NULL) {
        if (args != NULL) {
            *args = NULL;
        }
        return 0;
    }
    if (args != NULL) {
        *args = rt_argv;
    }
    return rt_argv_count;
}

struct rt_run {
    long status;
    unsigned char *out;
    size_t out_len;
    size_t out_cap;
    unsigned char *err;
    size_t err_len;
    size_t err_cap;
};

/* How long a child may run before it is killed. A constant, not a parameter:
 * a test that hangs is a bug in the program, and 124 is the shell's code for a
 * command that timed out. The guard lets the timeout probe build a short
 * budget; nothing in the compiler defines it. */
#ifndef RT_RUN_TIMEOUT_MS
#define RT_RUN_TIMEOUT_MS 30000
#endif

/* A child that wrote nothing still gives a `:str` a valid pointer. */
static const unsigned char rt_run_empty[1] = {0};

static long long rt_monotonic_ms(void) {
    struct timespec ts;

    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }
    return (long long)ts.tv_sec * 1000 + (long long)ts.tv_nsec / 1000000;
}

/* R0006 for a child that could not be started, naming the program and located
 * at the `run` node that asked. */
static _Noreturn void rt_run_spawn_panic(const char *prog,
                                         const char *call_path) {
    static const char prefix[] = "could not start ";
    size_t plen = sizeof prefix - 1;
    size_t n = strlen(prog);
    char *msg = malloc(sizeof prefix + n);

    if (msg == NULL) {
        rt_panic(rt_node_path(call_path), "R0006",
                 "could not start a program");
    }
    memcpy(msg, prefix, plen);
    memcpy(msg + plen, prog, n + 1);
    rt_panic(rt_node_path(call_path), "R0006", msg);
}

/* Add a close action for fd unless the descriptor is one of the two the child
 * keeps open; a pipe that landed on 1 or 2 must not be closed after the dup. */
static int rt_spawn_close(posix_spawn_file_actions_t *actions, int fd,
                          int keep_a, int keep_b) {
    if (fd == keep_a || fd == keep_b) {
        return 0;
    }
    return posix_spawn_file_actions_addclose(actions, fd);
}

/* Append n bytes to a growing process-lifetime buffer. */
static void rt_append(unsigned char **buf, size_t *len, size_t *cap,
                      const unsigned char *data, size_t n) {
    size_t need;
    size_t want;
    unsigned char *grown;

    if (n > (size_t)-1 - *len) {
        rt_panic(NULL, "R0003", "output is too large");
    }
    need = *len + n;
    if (need > *cap) {
        want = *cap != 0 ? *cap : 64;
        while (want < need) {
            if (want > (size_t)-1 / 2) {
                want = need;
                break;
            }
            want *= 2;
        }
        grown = realloc(*buf, want);
        if (grown == NULL) {
            rt_panic(NULL, "R0003", "out of memory");
        }
        *buf = grown;
        *cap = want;
    }
    if (n != 0) {
        memcpy(*buf + *len, data, n);
        *len = need;
    }
}

rt_run *rt_run_start(const unsigned char *prog, size_t pn,
                     const unsigned char **argv, const size_t *argn,
                     size_t argc, const char *call_path) {
    char *cprog = rt_cstr(prog, pn);
    char **cargv;
    rt_run *r;
    int out_pipe[2];
    int err_pipe[2];
    posix_spawn_file_actions_t actions;
    pid_t pid;
    size_t i;
    int rc;

    if (cprog == NULL) {
        rt_panic(rt_node_path(call_path), "R0003", "out of memory");
    }
    /* execve needs C strings and the child needs them for as long as it lives,
     * so each is a process-lifetime copy; the caller's Logos strings are only
     * read. cargv[0] is the program, then the arguments, then NULL. */
    cargv = malloc((argc + 2) * sizeof *cargv);
    if (cargv == NULL) {
        rt_panic(rt_node_path(call_path), "R0003", "out of memory");
    }
    cargv[0] = cprog;
    for (i = 0; i < argc; i++) {
        cargv[i + 1] = rt_cstr(argv[i], argn[i]);
        if (cargv[i + 1] == NULL) {
            rt_panic(rt_node_path(call_path), "R0003", "out of memory");
        }
    }
    cargv[argc + 1] = NULL;

    r = malloc(sizeof *r);
    if (r == NULL) {
        rt_panic(rt_node_path(call_path), "R0003", "out of memory");
    }
    r->status = 0;
    r->out = NULL;
    r->out_len = 0;
    r->out_cap = 0;
    r->err = NULL;
    r->err_len = 0;
    r->err_cap = 0;

    if (pipe(out_pipe) != 0 || pipe(err_pipe) != 0) {
        rt_run_spawn_panic(cprog, call_path);
    }
    if (posix_spawn_file_actions_init(&actions) != 0) {
        rt_run_spawn_panic(cprog, call_path);
    }
    rc = posix_spawn_file_actions_adddup2(&actions, out_pipe[1], STDOUT_FILENO);
    if (rc == 0) {
        rc = posix_spawn_file_actions_adddup2(&actions, err_pipe[1],
                                              STDERR_FILENO);
    }
    if (rc == 0) {
        rc = rt_spawn_close(&actions, out_pipe[0], STDOUT_FILENO, STDERR_FILENO);
    }
    if (rc == 0) {
        rc = rt_spawn_close(&actions, err_pipe[0], STDOUT_FILENO, STDERR_FILENO);
    }
    if (rc == 0) {
        rc = rt_spawn_close(&actions, out_pipe[1], STDOUT_FILENO, STDERR_FILENO);
    }
    if (rc == 0) {
        rc = rt_spawn_close(&actions, err_pipe[1], STDOUT_FILENO, STDERR_FILENO);
    }
    if (rc != 0) {
        posix_spawn_file_actions_destroy(&actions);
        rt_run_spawn_panic(cprog, call_path);
    }
    /* posix_spawnp, not posix_spawn: the program is named the way a shell
     * names it, and the corpus runs `sh` and `false` without a path. */
    rc = posix_spawnp(&pid, cprog, &actions, NULL, cargv, environ);
    posix_spawn_file_actions_destroy(&actions);
    if (rc != 0) {
        rt_run_spawn_panic(cprog, call_path);
    }
    /* The child holds the write ends now. Keeping ours would make the read
     * ends never see EOF, which is exactly the deadlock this loop avoids. */
    close(out_pipe[1]);
    close(err_pipe[1]);

    {
        struct pollfd fds[2];
        int open_count = 2;
        long long deadline = rt_monotonic_ms() + RT_RUN_TIMEOUT_MS;
        int timed_out = 0;

        fds[0].fd = out_pipe[0];
        fds[0].events = POLLIN;
        fds[0].revents = 0;
        fds[1].fd = err_pipe[0];
        fds[1].events = POLLIN;
        fds[1].revents = 0;

        while (open_count > 0) {
            long long remaining = deadline - rt_monotonic_ms();
            int ready;
            int idx;

            if (remaining <= 0) {
                timed_out = 1;
                break;
            }
            /* Both pipes are drained by one poll, so neither stream can fill
             * and block the child while the other is read. */
            if (remaining > 1000000) {
                remaining = 1000000;
            }
            ready = poll(fds, 2, (int)remaining);
            if (ready < 0) {
                if (errno == EINTR) {
                    continue;
                }
                /* A failed poll on the runtime's own pipes is not something a
                 * program can act on; stop reading and reap what there is. */
                break;
            }
            for (idx = 0; idx < 2; idx++) {
                char chunk[65536];
                ssize_t got;

                if (fds[idx].fd < 0 || fds[idx].revents == 0) {
                    continue;
                }
                got = read(fds[idx].fd, chunk, sizeof chunk);
                if (got < 0) {
                    if (errno == EINTR) {
                        continue;
                    }
                    close(fds[idx].fd);
                    fds[idx].fd = -1;
                    open_count--;
                    continue;
                }
                if (got == 0) {
                    close(fds[idx].fd);
                    fds[idx].fd = -1;
                    open_count--;
                    continue;
                }
                if (idx == 0) {
                    rt_append(&r->out, &r->out_len, &r->out_cap,
                              (const unsigned char *)chunk, (size_t)got);
                } else {
                    rt_append(&r->err, &r->err_len, &r->err_cap,
                              (const unsigned char *)chunk, (size_t)got);
                }
            }
        }

        for (i = 0; i < 2; i++) {
            if (fds[i].fd >= 0) {
                close(fds[i].fd);
                fds[i].fd = -1;
            }
        }

        {
            int st = 0;
            pid_t reaped = -1;
            int reaped_ok = 0;
            int killed = 0;

            if (timed_out) {
                /* The pipes outlived the budget. Kill the child now; the loop
                 * below still does the reaping. */
                (void)kill(pid, SIGKILL);
                killed = 1;
            }
            /* The deadline bounds the child, not just its output: a child that
             * closed both streams and then kept running would block a plain
             * waitpid forever. Poll WNOHANG against the same deadline, and on
             * expiry SIGKILL and reap, so nothing is left as a zombie behind a
             * status the program can see. */
            for (;;) {
                long long remaining = deadline - rt_monotonic_ms();
                struct timespec nap;

                reaped = waitpid(pid, &st, WNOHANG);
                if (reaped == pid) {
                    reaped_ok = 1;
                    break;
                }
                if (reaped < 0) {
                    if (errno == EINTR) {
                        continue;
                    }
                    break; /* ECHILD: there is nothing left to reap. */
                }
                if (remaining <= 0) {
                    (void)kill(pid, SIGKILL);
                    killed = 1;
                    break;
                }
                /* A short nap, capped by the time left, so the loop costs
                 * almost nothing over 30 seconds and still lands near the
                 * deadline. */
                nap.tv_sec = 0;
                nap.tv_nsec = (long)(remaining < 10 ? remaining : 10) *
                              1000000L;
                (void)nanosleep(&nap, NULL);
            }
            if (!reaped_ok) {
                /* After SIGKILL the child is going away; reap it so the
                 * status is collected rather than leaked to init. */
                do {
                    reaped = waitpid(pid, &st, 0);
                } while (reaped < 0 && errno == EINTR);
                reaped_ok = reaped == pid;
            }

            if (timed_out || killed) {
                r->status = 124;
            } else if (reaped_ok && WIFEXITED(st)) {
                r->status = WEXITSTATUS(st);
            } else if (reaped_ok && WIFSIGNALED(st)) {
                r->status = 128 + WTERMSIG(st);
            } else {
                r->status = 0;
            }
        }
    }

    return r;
}

long rt_run_status(rt_run *r) {
    if (r == NULL) {
        rt_panic(NULL, "R0005", "run handle is null");
    }
    return r->status;
}

const unsigned char *rt_run_out(rt_run *r, size_t *n) {
    if (r == NULL) {
        rt_panic(NULL, "R0005", "run handle is null");
    }
    if (n != NULL) {
        *n = r->out_len;
    }
    return r->out != NULL ? r->out : rt_run_empty;
}

const unsigned char *rt_run_err(rt_run *r, size_t *n) {
    if (r == NULL) {
        rt_panic(NULL, "R0005", "run handle is null");
    }
    if (n != NULL) {
        *n = r->err_len;
    }
    return r->err != NULL ? r->err : rt_run_empty;
}

/* ---------------------------------------------------------------------------
 * Concurrency
 *
 * The handles are opaque to generated code: every function here takes and
 * returns `void *`-shaped pointers, and the runtime is the only thing that
 * knows what they point at. The one shared piece of state is the leak tracker,
 * which takes its own lock in every entry point above.
 *
 * A mutex, a channel and an atomic are malloc'ed without rt_alloc and never
 * released: the language has no destroy form, so tracking them would turn
 * every program that uses one into a leak report no program could fix. A
 * thread is different — `join` is its release — so its handle is an rt_alloc
 * block, and a thread nobody joins is reported at the `spawn` that made it.
 * ------------------------------------------------------------------------- */

/* The signature pthread_create wants: one opaque argument, one opaque result.
 * The generated thunk has exactly this shape. */
typedef void *(*rt_thread_body)(void *);

typedef struct {
    rt_thread_body entry;
    void *arg;
} rt_thread_start;

struct rt_thread {
    pthread_t thread;
};

struct rt_mutex {
    pthread_mutex_t lock;
};

struct rt_chan {
    pthread_mutex_t lock;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
    unsigned char *buffer;
    size_t elem;   /* bytes per element, never zero */
    size_t cap;    /* elements the ring holds */
    size_t head;   /* index of the next slot to write */
    size_t count;  /* elements currently in the ring */
};

struct rt_atomic {
    long long value;
};

/* The thread's real entry point. `start` is the runtime's own record, the only
 * allocation here that is not the tracker's business; the argument record came
 * from rt_alloc and is released now that the target has returned. */
static void *rt_thread_main(void *raw) {
    rt_thread_start *start = raw;
    void *result = start->entry(start->arg);

    rt_free(start->arg);
    free(start);
    return result;
}

rt_thread *rt_thread_new(const char *path, void *(*entry)(void *), void *arg) {
    rt_thread_start *start;
    rt_thread *t;

    if (entry == NULL) {
        rt_panic(path, "R0005", "a thread needs an entry point");
    }
    start = malloc(sizeof *start);
    if (start == NULL) {
        rt_panic(path, "R0003", "out of memory");
    }
    /* The handle is tracked under the spawn's path: a thread never joined is
     * a live block, and the report says where it was started. */
    t = rt_alloc(sizeof *t, 8, path);
    start->entry = entry;
    start->arg = arg;
    if (pthread_create(&t->thread, NULL, rt_thread_main, start) != 0) {
        /* The thread never started, so it never ran `rt_thread_main` and does
         * not own the argument record. Release both before ending the
         * process, so a debug run does not report leaks caused by the failure
         * itself. */
        free(start);
        rt_free(arg);
        rt_free(t);
        rt_panic(path, "R0005", "could not start a thread");
    }
    return t;
}

void rt_join(rt_thread *t, const char *path) {
    /* The liveness test comes first: a second join is handed a handle the
     * first one released, and reading `t->thread` from it would be a read of
     * freed memory before the tracker could say anything. The debug build
     * quarantines the block, so the test is exact there; a release build can
     * only be best effort, like every other stale-pointer check. */
    if (!rt_is_live_block(t)) {
        rt_panic(path, "R0005", "thread is not running");
    }
    if (pthread_join(t->thread, NULL) != 0) {
        rt_panic(path, "R0005", "could not join a thread");
    }
    rt_free(t);
}

rt_mutex *rt_mutex_new(const char *path) {
    pthread_mutexattr_t attr;
    rt_mutex *m = malloc(sizeof *m);

    if (m == NULL) {
        rt_panic(path, "R0003", "out of memory");
    }
    if (pthread_mutexattr_init(&attr) != 0) {
        free(m);
        rt_panic(path, "R0005", "could not create a mutex");
    }
    /* Error checking, so a lock the calling thread already holds reports
     * EDEADLK instead of deadlocking, and an unlock by a non-owner reports
     * EPERM. Both become R0005 at the node that asked, which is the only
     * observable way a program can misuse a mutex. */
    if (pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_ERRORCHECK) != 0) {
        pthread_mutexattr_destroy(&attr);
        free(m);
        rt_panic(path, "R0005", "could not create a mutex");
    }
    if (pthread_mutex_init(&m->lock, &attr) != 0) {
        pthread_mutexattr_destroy(&attr);
        free(m);
        rt_panic(path, "R0005", "could not create a mutex");
    }
    pthread_mutexattr_destroy(&attr);
    return m;
}

void rt_mutex_lock(rt_mutex *m, const char *path) {
    if (m == NULL) {
        rt_panic(path, "R0005", "mutex is not running");
    }
    if (pthread_mutex_lock(&m->lock) != 0) {
        rt_panic(path, "R0005", "could not lock a mutex");
    }
}

void rt_mutex_unlock(rt_mutex *m, const char *path) {
    if (m == NULL) {
        rt_panic(path, "R0005", "mutex is not running");
    }
    if (pthread_mutex_unlock(&m->lock) != 0) {
        rt_panic(path, "R0005", "could not unlock a mutex");
    }
}

rt_chan *rt_chan_new(size_t elem, long long capacity, const char *path) {
    rt_chan *c;

    if (capacity <= 0) {
        rt_panic(path, "R0003", "channel capacity must be positive");
    }
    if (elem == 0) {
        /* An empty element still occupies a slot; one byte keeps the ring's
         * arithmetic away from a zero stride. */
        elem = 1;
    }
    if ((unsigned long long)capacity > (unsigned long long)((size_t)-1) / elem) {
        rt_panic(path, "R0003", "channel capacity overflows");
    }
    c = malloc(sizeof *c);
    if (c == NULL) {
        rt_panic(path, "R0003", "out of memory");
    }
    c->buffer = malloc(elem * (size_t)capacity);
    if (c->buffer == NULL) {
        free(c);
        rt_panic(path, "R0003", "out of memory");
    }
    c->elem = elem;
    c->cap = (size_t)capacity;
    c->head = 0;
    c->count = 0;
    if (pthread_mutex_init(&c->lock, NULL) != 0) {
        free(c->buffer);
        free(c);
        rt_panic(path, "R0005", "could not create a channel");
    }
    if (pthread_cond_init(&c->not_empty, NULL) != 0 ||
        pthread_cond_init(&c->not_full, NULL) != 0) {
        pthread_mutex_destroy(&c->lock);
        free(c->buffer);
        free(c);
        rt_panic(path, "R0005", "could not create a channel");
    }
    return c;
}

void rt_chan_send(rt_chan *c, const void *value, const char *path) {
    size_t slot;

    if (c == NULL) {
        rt_panic(path, "R0005", "channel is not running");
    }
    if (pthread_mutex_lock(&c->lock) != 0) {
        rt_panic(path, "R0005", "could not lock a channel");
    }
    while (c->count == c->cap) {
        if (pthread_cond_wait(&c->not_full, &c->lock) != 0) {
            rt_panic(path, "R0005", "could not wait on a channel");
        }
    }
    slot = c->head;
    memcpy(c->buffer + slot * c->elem, value, c->elem);
    c->head = (c->head + 1) % c->cap;
    c->count++;
    if (pthread_cond_signal(&c->not_empty) != 0) {
        rt_panic(path, "R0005", "could not wake a channel");
    }
    if (pthread_mutex_unlock(&c->lock) != 0) {
        rt_panic(path, "R0005", "could not unlock a channel");
    }
}

void rt_chan_recv(rt_chan *c, void *out, const char *path) {
    size_t slot;

    if (c == NULL) {
        rt_panic(path, "R0005", "channel is not running");
    }
    if (pthread_mutex_lock(&c->lock) != 0) {
        rt_panic(path, "R0005", "could not lock a channel");
    }
    while (c->count == 0) {
        if (pthread_cond_wait(&c->not_empty, &c->lock) != 0) {
            rt_panic(path, "R0005", "could not wait on a channel");
        }
    }
    /* The oldest element: the ring is `count` long, so its tail is `count`
     * slots behind the head. */
    slot = (c->head + c->cap - c->count) % c->cap;
    memcpy(out, c->buffer + slot * c->elem, c->elem);
    c->count--;
    if (pthread_cond_signal(&c->not_full) != 0) {
        rt_panic(path, "R0005", "could not wake a channel");
    }
    if (pthread_mutex_unlock(&c->lock) != 0) {
        rt_panic(path, "R0005", "could not unlock a channel");
    }
}

rt_atomic *rt_atomic_new(long long value) {
    rt_atomic *a = malloc(sizeof *a);

    if (a == NULL) {
        rt_panic(NULL, "R0003", "out of memory");
    }
    __atomic_store_n(&a->value, value, __ATOMIC_SEQ_CST);
    return a;
}

long long rt_atomic_add(rt_atomic *a, long long delta) {
    if (a == NULL) {
        rt_panic(NULL, "R0005", "atomic handle is null");
    }
    return __atomic_add_fetch(&a->value, delta, __ATOMIC_SEQ_CST);
}

long long rt_atomic_load(rt_atomic *a) {
    if (a == NULL) {
        rt_panic(NULL, "R0005", "atomic handle is null");
    }
    return __atomic_load_n(&a->value, __ATOMIC_SEQ_CST);
}

void rt_atomic_store(rt_atomic *a, long long value) {
    if (a == NULL) {
        rt_panic(NULL, "R0005", "atomic handle is null");
    }
    __atomic_store_n(&a->value, value, __ATOMIC_SEQ_CST);
}
