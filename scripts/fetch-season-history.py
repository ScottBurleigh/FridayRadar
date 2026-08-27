#!/usr/bin/env python3
"""MaxPreps season win-loss history → data/raw/maxpreps/season-history.json.

Each MaxPreps team schedule page carries TWO seasons in its embedded
__NEXT_DATA__: `standingsData` (the season in the URL) and
`lastYearStandingsData` (the one before it). So three fetches per school
cover five seasons:

    /football/26-27/schedule/  ->  26-27, 25-26
    /football/24-25/schedule/  ->  24-25, 23-24
    /football/23-24/schedule/  ->  23-24, 22-23

robots.txt note: MaxPreps disallows crawling season paths 22-23 and older
(`Disallow: /*22-23/` … `/*03-04/`). Every URL fetched here is an allowed
season; 22-23 is only ever read from the prior-year block that the allowed
23-24 page volunteers. Do not add a /22-23/ (or older) fetch URL.

Resumable: results are merged into the output file after every school, so a
re-run skips schools already covering all wanted seasons.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
OUT = ROOT / "data/raw/maxpreps/season-history.json"

# Fetched season -> (season it reports, season its lastYear block reports).
FETCH_SEASONS = ["26-27", "24-25", "23-24"]
WANT_SEASONS = ["26-27", "25-26", "24-25", "23-24", "22-23"]

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

NEXT_DATA = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
RECORD = re.compile(r"^\d+-\d+(-\d+)?$")

WORKERS = 6
SLEEP = 0.25  # polite pause per request, per worker

_lock = Lock()


def prior_season(season: str) -> str:
    """'24-25' -> '23-24'."""
    a, b = season.split("-")
    return f"{int(a) - 1:02d}-{int(b) - 1:02d}"


def http_get(url: str, timeout: int = 25) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def school_root(school: dict) -> str | None:
    """MaxPreps school root URL, season segment stripped. Never invented.

    scheduleUrl first, deliberately: many stored canonicalUrls drop the mascot
    segment (".../az/goodyear/desert-edge/" vs the real
    ".../az/goodyear/desert-edge-scorpions/") and 404. scheduleUrl is the one
    the schedule scraper actually fetches, so it is the trustworthy field.
    """
    mp = school.get("maxpreps") or {}
    for key in ("scheduleUrl", "footballUrl", "canonicalUrl"):
        url = (mp.get(key) or "").strip()
        if not url:
            continue
        # .../img-academy-ascenders/football/25-26/schedule/ -> .../img-academy-ascenders/
        url = re.sub(r"/football(/\d\d-\d\d)?(/schedule)?/?$", "/", url)
        if not url.endswith("/"):
            url += "/"
        if "/football" in url:
            continue
        return url
    return None


def parse_records(html: str) -> tuple[str | None, str | None]:
    """(this season, prior season) overall W-L from the page's embedded JSON."""
    m = NEXT_DATA.search(html)
    if not m:
        return None, None
    try:
        data = json.loads(m.group(1))
    except Exception:
        return None, None
    tc = ((data.get("props") or {}).get("pageProps") or {}).get("teamContext") or {}

    def pick(block: str) -> str | None:
        node = tc.get(block) or {}
        overall = node.get("overallStanding") or {}
        rec = overall.get("overallWinLossTies")
        if isinstance(rec, str) and RECORD.match(rec.strip()):
            return rec.strip()
        return None

    return pick("standingsData"), pick("lastYearStandingsData")


def fetch_school(school: dict) -> tuple[str, dict[str, str]]:
    sid = school["id"]
    root = school_root(school)
    if not root:
        return sid, {}
    found: dict[str, str] = {}
    for season in FETCH_SEASONS:
        url = f"{root}football/{season}/schedule/"
        status, html = http_get(url)
        time.sleep(SLEEP)
        if status != 200 or not html:
            continue
        cur, prev = parse_records(html)
        if cur:
            found.setdefault(season, cur)
        if prev:
            found.setdefault(prior_season(season), prev)
        if all(s in found for s in WANT_SEASONS):
            break
    return sid, {s: found[s] for s in WANT_SEASONS if s in found}


def main() -> int:
    schools = json.loads((SITE / "schools.json").read_text())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, str]] = {}
    if OUT.exists():
        try:
            out = json.loads(OUT.read_text()).get("records", {})
        except Exception:
            out = {}

    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    todo = [s for s in schools if school_root(s) and not out.get(s["id"])]
    if limit:
        todo = todo[:limit]
    print(f"{len(schools)} schools, {len(out)} already cached, fetching {len(todo)}", flush=True)

    def flush() -> None:
        OUT.write_text(
            json.dumps(
                {
                    "source": "maxpreps_team_schedule_standings",
                    "seasons": WANT_SEASONS,
                    "count": len(out),
                    "records": out,
                },
                indent=0,
            )
        )

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(fetch_school, s): s["id"] for s in todo}
        for fut in as_completed(futs):
            done += 1
            try:
                sid, rec = fut.result()
            except Exception as e:
                print(f"  fail {futs[fut]}: {e}", flush=True)
                continue
            if rec:
                with _lock:
                    out[sid] = rec
            if done % 25 == 0:
                with _lock:
                    flush()
                print(f"  {done}/{len(todo)} — {len(out)} with history", flush=True)

    flush()
    got = sum(1 for v in out.values() if v)
    print(f"done: {got} schools with season history -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
