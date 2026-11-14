#!/usr/bin/env python3
"""Compare `gen2 build --test NAME` IR with Python's `run_test` IR, per test.

Each `(test …)` in the named file is lowered twice into `build/<stem>.<name>.ll`:
once by the self-hosted compiler's `build --test`, whose flag is the port's own,
and once by Python's `logos.driver.run_test`, which is the reference the port
must reproduce. The two files are moved under `build/test-ir/` and compared byte
for byte, so the claim is the same one `tools/selfhost.sh`'s unit phase makes
for a whole program: the port's lowering of that entry point is Python's.

    python3 tools/test_ir_parity.py tests/exec/closures.logos

The exit status is 0 when every test agrees, 1 when any differs, and 2 when the
port is missing or a build fails on both sides being asked to fail.

This is how W8 step 3c-1 pins `tests/exec/closures.logos` at 17 of 17: the
debug leak report, the `$fnvalue` wrapper and the nine monomorphic copies only
`(test …)` bodies reach all show up as IR differences, not as prose.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logos import driver  # noqa: E402

BIN = ROOT / "build/selfhost/gen2"
OUT = ROOT / "build/test-ir"


def names_of(path: Path) -> list[str]:
    """The test names of ``path``, in source order."""
    return [
        line.split()[1]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("(test ")
    ]


def safe_name(name: str) -> str:
    """Python's `test_ir_path` spelling: `/` and `\\` become `_`."""
    return name.replace("/", "_").replace("\\", "_")


def clear(*paths: Path) -> None:
    """Remove each path so a stale file cannot be read as agreement."""
    for path in paths:
        if path.exists():
            path.unlink()


def one(path: Path, index: int, name: str) -> bool:
    """Compare one test's IR from both sides; report a difference."""
    stem = path.stem
    ll = ROOT / "build" / f"{stem}.{safe_name(name)}.ll"
    tag = f"{index:02d}-{safe_name(name)}"
    mine = OUT / f"{tag}.gen2.ll"
    theirs = OUT / f"{tag}.python.ll"
    clear(ll, mine, theirs)
    run = subprocess.run(
        [str(BIN), "build", str(path), "--test", name,
         "-o", str(OUT / f"{tag}.gen2.bin")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if run.returncode != 0:
        print(f"{name}: gen2 build failed: {run.stderr.strip().splitlines()[:1]}")
        return False
    if not ll.exists():
        print(f"{name}: gen2 wrote no {ll.relative_to(ROOT)}")
        return False
    shutil.move(str(ll), str(mine))
    try:
        driver.run_test(str(path), name, str(OUT / f"{tag}.python.bin"))
    except Exception as error:  # noqa: BLE001 - one failure, not a stopped run
        print(f"{name}: python failed: {error}")
        return False
    if not ll.exists():
        print(f"{name}: python wrote no {ll.relative_to(ROOT)}")
        return False
    shutil.move(str(ll), str(theirs))
    if mine.read_bytes() == theirs.read_bytes():
        return True
    print(f"{name}: IR differs")
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: test_ir_parity.py FILE", file=sys.stderr)
        return 2
    if not BIN.exists():
        print(f"test_ir_parity: no {BIN.relative_to(ROOT)}; build gen2 first",
              file=sys.stderr)
        return 2
    path = Path(argv[1]).resolve()
    names = names_of(path)
    if not names:
        print(f"test_ir_parity: {argv[1]} has no (test …) nodes", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    same = sum(1 for index, name in enumerate(names) if one(path, index, name))
    differ = len(names) - same
    print(f"test-ir: {len(names)} tests, {differ} differences")
    return 0 if differ == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
