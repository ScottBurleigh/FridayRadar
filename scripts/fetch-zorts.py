#!/usr/bin/env python3
"""Deprecated entry point. One path: scripts/tournaments (Zorts + Flag50 merge)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFRESH = HERE / "tournaments" / "refresh.py"


def main() -> int:
    print(
        "scripts/fetch-zorts.py now runs the Zorts + Flag50 merge "
        "(scripts/tournaments/refresh.py).",
        file=sys.stderr,
    )
    cmd = [sys.executable, str(REFRESH), *sys.argv[1:]]
    if not any(a == "--outdir" or a.startswith("--outdir=") for a in sys.argv[1:]):
        cmd += ["--outdir", str(HERE.parent / "data")]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
