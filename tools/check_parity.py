#!/usr/bin/env python3
"""Generate ``‹fixture›.check`` from Python's own check diagnostic.

The check phase in ``tools/selfhost.sh`` used to compare only the ``E####``
code: a reworded message or a wrong node path still passed while ``check.md``
claimed both were pinned. Each fixture in ``tools/selfhost-check.txt`` now has
a sidecar naming the whole line ``gen2 check`` must print — ``‹path›: ‹CODE›:
‹message›`` — and this script writes it from the reference implementation, the
same way ``tools/types_parity.py`` writes the parity table. The expectation
cannot drift from Python because no one types it.

The fixture is resolved and checked here exactly as ``gen2 check`` does it, and
the code the reference prints must agree with the fixture's ``.expect``: that
file stays the corpus's statement of which rule the fixture tests, and a
disagreement means the list names the wrong fixture.

    python3 tools/check_parity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logos.check import check_module  # noqa: E402
from logos.diag import LogosError  # noqa: E402
from logos.driver import load  # noqa: E402


def diagnostic(fixture: Path) -> str:
    """The one line ``gen2 check`` must print for ``fixture``, per Python."""
    try:
        check_module(load(str(fixture)))
    except LogosError as error:
        return f"{error.path}: {error.code}: {error.message}"
    raise SystemExit(f"{fixture}: the reference accepts it; the list names it wrongly")


def main() -> int:
    listed = ROOT / "tools" / "selfhost-check.txt"
    fixtures = [line.strip() for line in listed.read_text().splitlines() if line.strip()]
    if not fixtures:
        raise SystemExit(f"{listed}: names no fixtures")
    for rel in fixtures:
        fixture = ROOT / rel
        line = diagnostic(fixture)
        sidecar = fixture.with_suffix(".check")
        sidecar.write_text(line + "\n", encoding="utf-8")
        code = line.split(": ", 2)[1]
        expect = fixture.with_suffix(".expect").read_text(encoding="utf-8").strip()
        if code != expect:
            raise SystemExit(
                f"{rel}: the reference says {code}, .expect says {expect}"
            )
        print(f"{rel}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
