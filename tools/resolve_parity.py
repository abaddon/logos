#!/usr/bin/env python3
"""Write every ``tests/parse/**/*.expect`` from Python's own diagnostic.

The resolve phase in ``tools/selfhost.sh`` compares the code ``gen2 resolve``
prints with the fixture's ``.expect``. That sidecar is a single code, and it was
typed by hand, so it could drift from the reference implementation it exists to
pin — a reworded rule or a fixture that changed code without its sidecar would
still agree with itself. This script writes the code from the reference, the way
``tools/check_parity.py`` writes the checker's ``.check`` sidecars, and prints
the whole diagnostic behind it so the location is visible even though only the
code is pinned.

A fixture whose source must fail to lex or parse cannot be a ``*.logos`` file:
``tools/accept.sh`` formats every one in the tree, so the malformed source has no
legal name. Such a fixture keeps its sources as ``*.logos.txt``, and this script
materializes them under ``build/`` exactly as ``tools/selfhost.sh`` does before
asking the reference.

    python3 tools/resolve_parity.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logos.diag import LogosError  # noqa: E402
from logos.driver import load  # noqa: E402

#: Where a fixture with ``*.logos.txt`` sources is materialized. Under
#: ``build/`` so no formatter, no corpus runner and no gate sees the copy.
WORK = ROOT / "build" / "parse-parity"
CORPUS = ROOT / "tests" / "parse"


def fixture(expect: Path) -> Path:
    """The root file of the fixture ``expect`` names, materialized if needed."""
    stem = expect.with_suffix("")
    beside = stem.with_suffix(".logos")
    if beside.is_file():
        return beside
    at = WORK / stem.parent.relative_to(CORPUS)
    if at.exists():
        shutil.rmtree(at)
    at.mkdir(parents=True)
    for source in stem.parent.glob("*.logos.txt"):
        shutil.copy(source, at / source.name[: -len(".txt")])
    return at / (stem.name + ".logos")


def main() -> int:
    expects = sorted(CORPUS.rglob("*.expect"))
    if not expects:
        raise SystemExit(f"{CORPUS}: names no fixtures")
    for expect in expects:
        path = fixture(expect)
        try:
            load(str(path))
        except LogosError as error:
            expect.write_text(error.code + "\n", encoding="utf-8")
            print(f"{path.relative_to(ROOT)}: {error.render().replace(str(ROOT) + '/', '')}")
            continue
        raise SystemExit(f"{path}: the reference accepts it; the corpus names it wrongly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
