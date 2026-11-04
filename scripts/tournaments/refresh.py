#!/usr/bin/env python3
"""Zorts + Flag50 fetch and merge. Writes tournaments.json to --outdir.

Public pages only. If either site blocks, exit non-zero and write nothing.
Default states: TX. Weekly path uses --no-find (map + details, skip /season/find).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh merged Zorts + Flag50 tournaments")
    ap.add_argument("--states", default=os.environ.get("STATES", "TX"))
    ap.add_argument("--outdir", default=str(ROOT / "data"))
    ap.add_argument("--workdir", default="/tmp/fridayradar-tournaments")
    ap.add_argument("--no-find", action="store_true", default=True)
    ap.add_argument("--find", action="store_true", help="also crawl Zorts /season/find")
    ap.add_argument("--no-details", action="store_true")
    a = ap.parse_args()
    no_find = False if a.find else True
    work = Path(a.workdir)
    zorts_dir = work / "zorts"
    flag50_path = work / "flag50.json"
    work.mkdir(parents=True, exist_ok=True)
    zorts_dir.mkdir(parents=True, exist_ok=True)

    zorts_cmd = [
        sys.executable,
        str(HERE / "fetch_zorts.py"),
        "--states",
        a.states,
        "--outdir",
        str(zorts_dir),
    ]
    if no_find:
        zorts_cmd.append("--no-find")
    if a.no_details:
        zorts_cmd.append("--no-details")
    flag_cmd = [
        sys.executable,
        str(HERE / "fetch_flag50.py"),
        "--states",
        a.states,
        "--out",
        str(flag50_path),
    ]
    merge_dir = work / "merged"
    merge_dir.mkdir(parents=True, exist_ok=True)
    merge_cmd = [
        sys.executable,
        str(HERE / "merge_tournaments.py"),
        "--zorts",
        str(zorts_dir / "tournaments.json"),
        "--flag50",
        str(flag50_path),
        "--outdir",
        str(merge_dir),
    ]

    for label, cmd in (("zorts", zorts_cmd), ("flag50", flag_cmd)):
        print(f"running {label}: {' '.join(cmd)}", flush=True)
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            print(f"{label} fetch failed (exit {proc.returncode}); not writing", flush=True)
            return proc.returncode or 2

    print(f"running merge: {' '.join(merge_cmd)}", flush=True)
    proc = subprocess.run(merge_cmd, check=False)
    if proc.returncode != 0:
        print(f"merge failed (exit {proc.returncode}); not writing", flush=True)
        return proc.returncode or 2
    src = merge_dir / "tournaments.json"
    if not src.exists():
        print("merge wrote nothing; not writing", flush=True)
        return 2
    dest = Path(a.outdir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "tournaments.json").write_text(src.read_text())
    print(f"wrote {dest / 'tournaments.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
