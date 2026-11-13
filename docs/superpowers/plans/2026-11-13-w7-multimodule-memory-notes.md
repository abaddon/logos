# W7 multi-module memory blow-up — notes (2026-11-13)
Diagnosis only: no tracked source changed; experiments ran on a copy of `src/logosc` under
`/root/.hermes/cache/scratch/mem2/`.
## 1. Reproducer, and one correction
`gen2c2b build fmt lex main` is **11 modules**, not 18: `fmt tree lex main resolve map check types
lower ir emit` (`main.logos` pulls the closure in; the earlier-failing roots fail with `E0103: no
'main'`). Capped: 2,987,608 KB peak, 7.92 s, rc 2, `<runtime>: R0003: out of memory`. Python builds
the same modules in 33.4 s at 191 MB: the design is bounded, the port's lowering is not. The growth
is one `rw-p [heap]` mapping (2.78 GB at t=8.0 s), `Threads: 1`, `VmStk: 132 kB` — allocator volume.
## 2. Which pass allocates: pass 4, the body walk
Instrumented copy: a `probe-mark` writing `tag n` plus `(read-file "/proc/self/statm")` to fd 2 (no
RSS primitive exists, but `read-file` reads `/proc`; field 2 is resident pages); marks per stage in
`main-built`, per module in `main-load-module`, per module and per function at
`lower.logos:4827/4838/4849/4860/4870`.

| stage | RSS |
|---|---|
| after lex / tree / resolve / check (root) | 1.2 / 2.0 / 29.5 / 12.8 MB |
| after loading 11 modules (`main.logos:246-249`) | 47.4 MB |
| passes 1-3 (`lo-scan-types1/2`, `lo-scan-sigs`) | flat, 47.4 MB |
| pass 4, module 6 = `check` (363 fns, 41,617 node ids) | 151 MB → 3042 MB, OOM |

Only **pass 4** allocates: `lo-one-fn`, `lower.logos:4860-4876`, via `lo-fn`/`lo-fn-pass`/`lo-body`/`lo-stmt`. `lo-refill`/`lo-refill-texts` (`lower.logos:4705-4719`) copy exactly
`[mstarts[2m], mends[2m])` once per module and `main-append` (`main.logos:143-156`) pushes
non-overlapping ranges: the overlapping-refill suspicion is **refuted** (RSS flat across the refill
mark). The dry pass (`:3401`) and emitting pass (`:3420`) cost the same — `body-match` 214 MB each —
so the cost is in the body walk, not `lo-w-*`/`ir-*` emission and not `emit.logos`.
Per-statement cost tracks the **current length of the type table** (a mark per statement in
`lo-body`, `lower.logos:2248-2254`):

| `vec-len tags` | stmts | mean RSS delta/statement |
|---|---|---|
| 40-60k | 218 | 0.00 MB |
| 60-80k | 1849 | 0.06 MB |
| 80-100k | 2063 | 0.47 MB |
| 100-120k | 1216 | 1.36 MB |
| 120k+ | 146 | 1.76 MB |
Memory is O(visits × table) = **O(n²)**: `tags` holds 122,395 rows for 41,617 nodes (~2.9/node) because
`type-add` (`types.logos:69-76`) appends unconditionally and every constructor is reached per *visit*
via `lo-prim`/`lo-ptr`/`lo-own` (`lower.logos:295-306`). Interning only
`type-prim`/`type-ptr` (a `type-find2` scan, `types.logos:78-89`) did **not** move the peak
(2,988 MB at 12.0 s — slower, not smaller), so the per-visit growth is dominated by the constructors
left alone (`type-own/vec/ref/opt/shared/chan/atomic/arr/res`, `types.logos:84-109`) or by a second
statement-grown table: `bindn/bindt/binds` (`lo-bind-row` `:590-596`; only `binda` flags cleared,
`lo-close-scope` `:610-618`) and `plan/planty` (`lo-slot-dry` `:625-637`).
## 3. The exponent, and the candidate
Same binary, synthetic roots importing a prefix of the compiler, all under `ulimit -v 3000000`:

| modules | fns | source | peak RSS | wall |
|---|---|---|---|---|
| 2 | 33 | 8.7 KB | 15.9 MB | 0.08 s |
| 4 | 79 | 23.6 KB | 37.6 MB | 0.19 s |
| 6 | 159 | 60.1 KB | 117.5 MB | 0.42 s |
| 8 (+`check`) | 643 | 481 KB | 2,988 MB (cap, OOM) | 9.46 s |
| 11 (real roots) | 1120 | 1.22 MB | 2,988 MB (cap, OOM) | 5.56 s |

2→4 is ×2 modules for ×2.4 RSS, 4→6 ×1.5 for ×3.1, 6→8 ×8 source for ≥×25 (capped, so truly larger).
One module dominates: adding `check` takes 117 MB to OOM — an O(size²) term once a module outweighs
fixed costs, and §2 measures the exponent inside `check`.

Refuted: refill overlap, and a scan over the module list — each pass refills one module's slice with
`root 0` (`lower.logos:4829-4835`) and `lo-child`/`lo-lookup` (`:78-104`, `:576-588`) cost time, not
memory. Confirmed: a **per-visit arena** — `tags` grows with visits because `type-add` is append-only.
Residual: which table the cost is charged to — `tags` is measured, `bindn`/`plan` are collinear.
## 4. The fix
Intern the type table structurally instead of chronologically: give `type-add` (`types.logos:69-76`)
a lookup keyed `(tag, name-or-child, second)` and route every constructor in `types.logos:78-109`
through it, so `lo-prim`/`lo-ptr`/`lo-own` (`lower.logos:295-306`) stop appending a row per visit and
`|tags|` becomes the count of *distinct* types (hundreds), not visits (122,395). Per-visit cost is
measured linear in `|tags|` (§2), so collapsing the table turns O(n²) back into O(n); the prim/ptr
attempt shows the fix must cover *all* constructors. If `|tags|` collapses and the peak
does not follow, bound the per-function tables at `lower.logos:3386`/`:3414-3419` — truncate
`bindn/bindt/binds` and `plan/planty` to the `base`/`planbase` that `lo-fn` already computes — so no
per-visit table is walked at module scale. Verify with the same marks: `|tags|` per module plus peak
RSS on the 8- and 11-module cases.
## 5. What must not change
- The 50 entries of `tools/selfhost-ir.txt` (46 fixtures, set-equal to `src/logosc/fixtures/ir-lower`,
  plus 4 examples) stay byte-identical; `.refuse` sidecars keep the same first line.
- `fmt lex main` builds bounded — target the oracle's 191 MB, not "under 3 GB" — the 2/4/6 rows do not
  regress, and the 122 checker plus 14 resolver fixtures stay clean.
## 6. Commands run (every build capped)
```
cd /root/ai-language-program
(ulimit -v 3000000; /usr/bin/time -v ./build/selfhost/gen2c2b build src/logosc/fmt.logos src/logosc/lex.logos \
  src/logosc/main.logos -o /tmp/x.ll) 2>&1 | tail -30                       # 2987608 KB, 7.92 s, rc 2
(ulimit -v 3000000; /usr/bin/time -f "%e %M" python3 -m logos build src/logosc/fmt.logos src/logosc/lex.logos \
  src/logosc/main.logos -o /tmp/y.ll)                                       # 33.39 s, 191080 KB
cp -r src /root/.hermes/cache/scratch/mem2/src && cd /root/.hermes/cache/scratch/mem2 && python3 patch.py
(ulimit -v 3000000; PYTHONPATH=/root/ai-language-program /usr/bin/time -f "%e %M" python3 -m logos build \
  src/logosc/fmt.logos src/logosc/lex.logos src/logosc/main.logos -o /tmp/gen2-instr3)   # 32.5 s, 191 MB
cd /root/ai-language-program && (ulimit -v 3000000; /usr/bin/time -f "%e %M %x" /tmp/gen2-instr3 build \
  src/logosc/fmt.logos src/logosc/lex.logos src/logosc/main.logos -o /tmp/x4.ll) 2> run3.log  # 8.58 s, 2979004 KB
cd /root/.hermes/cache/scratch/mem2 && python3 table.py && timeout 60 python3 sample.py  # 2/4/6/8 modules, heap shape
(ulimit -v 3000000; PYTHONPATH=/root/ai-language-program /usr/bin/time -f "%e %M" python3 -m logos build \
  src/logosc/fmt.logos src/logosc/lex.logos src/logosc/main.logos -o /tmp/gen2-intern)   # interned build
cd /root/ai-language-program && (ulimit -v 3000000; /usr/bin/time -f "%e %M %x" /tmp/gen2-intern build \
  src/logosc/fmt.logos src/logosc/lex.logos src/logosc/main.logos -o /tmp/interned.ll)  # 11.97 s, 2987628 KB
```
`patch.py` inserts a `probe` module (an `rt_write` shim — an extern in two modules is `E0003 duplicate
definition`, and `_` binds once per function), so the instrumented build is 12 modules.
