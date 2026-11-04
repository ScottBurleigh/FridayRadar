#!/usr/bin/env python3
"""Fetch upcoming youth flag / 7v7 tournaments from Flag50 public state hubs.

Only the public state page and its prerendered /tournaments/in/<state>/_payload.json.
Never requests /api/. If Flag50 403s / captcha / Cloudflare, exit non-zero and write nothing.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from blocked import SiteBlocked, looks_blocked  # noqa: E402
from states import parse_states, slug  # noqa: E402

BASE = "https://flag50.com"
UA = "FridayRadarBot/1.0 (+weekly youth football tournament listing; python-urllib)"
SEVEN = re.compile(r"\b7\s*-?\s*(?:v|vs\.?|on|x)\s*-?\s*7\b", re.I)


def get(url, delay):
    if "/api/" in url:
        raise RuntimeError(f"refusing /api/ URL {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
            if looks_blocked(getattr(r, "status", 200), body):
                raise SiteBlocked(f"blocked fetching {url}")
    except SiteBlocked:
        raise
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            raw = ""
        if looks_blocked(e.code, raw):
            raise SiteBlocked(f"HTTP {e.code} fetching {url}") from e
        raise
    time.sleep(delay)
    return body


def devalue(arr):
    """Decode Nuxt's devalue array format into plain Python objects."""
    memo = {}

    def walk(i):
        if not isinstance(i, int) or isinstance(i, bool) or i < 0:
            return None
        if i in memo:
            return memo[i]
        x = arr[i]
        if isinstance(x, dict):
            out = {}
            memo[i] = out
            for k, v in x.items():
                out[k] = walk(v)
            return out
        if isinstance(x, list):
            if x and isinstance(x[0], str) and x[0] in (
                "ShallowReactive",
                "Reactive",
                "Ref",
                "ShallowRef",
                "EmptyRef",
                "EmptyShallowRef",
            ):
                return walk(x[1]) if len(x) > 1 else None
            if x and x[0] in ("Date",):
                return x[1]
            if x and x[0] in ("Set",):
                return [walk(v) for v in x[1:]]
            out = []
            memo[i] = out
            out.extend(walk(v) for v in x)
            return out
        return x

    return walk(0)


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def fetch_state(code, delay):
    page_url = f"{BASE}/tournaments/in/{slug(code)}"
    html = get(page_url, delay)
    m = re.search(r'id="__NUXT_DATA__"[^>]*data-src="([^"]+)"', html) or re.search(
        r'data-src="([^"]+)"[^>]*id="__NUXT_DATA__"', html
    )
    if not m:
        raise RuntimeError(f"{page_url}: no __NUXT_DATA__ payload reference found")
    payload_path = m.group(1).replace("&amp;", "&")
    if "/api/" in payload_path:
        raise RuntimeError(f"refusing /api/ payload path {payload_path!r}")
    if not payload_path.startswith("/tournaments/"):
        raise RuntimeError(f"unexpected payload path {payload_path!r} (not fetching)")
    root = devalue(json.loads(get(BASE + payload_path, delay)))
    feeds = [v for k, v in (root.get("data") or {}).items() if k.startswith("tfeed:hub:")]
    if not feeds:
        raise RuntimeError(f"{page_url}: hub feed not found in payload")
    feed = feeds[0]
    hub = feed.get("hub") or {}
    results = feed.get("results") or []
    print(
        f"flag50 {code}: {len(results)} results (hub.localUpcoming={hub.get('localUpcoming')}, total={feed.get('total')})",
        file=sys.stderr,
    )
    return results, page_url


def zorts_tid(e):
    m = re.match(r"zs(\d+)$", e.get("id") or "")
    if m:
        return m.group(1)
    m = re.search(
        r"zortssports\.com/(?:post/clubHouse\?tid=|join/(?:league|tournament)/)(\d+)",
        e.get("registrationUrl") or "",
    )
    return m.group(1) if m else ""


def to_row(e, code):
    fmts = [f for f in (e.get("format") or []) if f]
    text = " ".join([e.get("name") or "", " ".join(fmts)])
    seven = "7v7" in fmts or bool(SEVEN.search(text))
    flag = any(f in ("5v5", "4v4", "6v6", "8v8", "flag") for f in fmts) or bool(
        re.search(r"flag", e.get("name") or "", re.I)
    )
    cat = "both" if seven and flag else "7v7" if seven else "flag" if flag else ""
    fee = e.get("entryFee")
    venue = ", ".join(x for x in [e.get("venueName"), e.get("address")] if x) or ""
    city_state = ", ".join(x for x in [e.get("city"), e.get("state")] if x)
    genders = ", ".join(g for g in (e.get("genders") or []) if g)
    return dict(
        id=f"flag50-{e['id']}",
        category=cat,
        state=code,
        name=(e.get("name") or "").strip(),
        start_date=e.get("startDate") or "",
        end_date=e.get("endDate") or e.get("startDate") or "",
        city=e.get("city") or "",
        venue=(venue + (", " if venue else "") + city_state) if city_state else venue,
        sport=((genders + " ") if genders else "") + "Football (" + ", ".join(fmts) + ")" if fmts else genders,
        age_groups=e.get("ageGroups") or "",
        divisions="",
        entry_fee=(f"${fee:,.2f} USD per team" if isinstance(fee, (int, float)) else ""),
        registration_ends="",
        organizer=e.get("organizer") or "",
        contact_email="",
        contact_phone="",
        event_url=BASE + (e.get("path") or ("/tournaments/" + (e.get("slug") or ""))),
        clubhouse_url=e.get("registrationUrl") or "",
        source="flag50",
        flag50_id=e["id"],
        flag50_event_type=e.get("eventType") or "",
        registration_platform=e.get("registrationPlatform") or "",
        flag50_is_adult=bool(e.get("isAdult")),
        zorts_tid=zorts_tid(e),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", default="", help="comma-separated state codes (default TX)")
    ap.add_argument("--months", type=int, default=7)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--out", default=str(HERE / "data" / "flag50.json"))
    a = ap.parse_args()
    states = parse_states(a.states)
    today = dt.date.today()
    horizon = add_months(today, a.months)
    rows, raw_count, skipped = [], 0, []
    try:
        for code in states:
            results, _ = fetch_state(code, a.delay)
            raw_count += len(results)
            for e in results:
                r = to_row(e, code)
                why = None
                if (e.get("state") or "").upper() != code:
                    why = f"state {e.get('state')}"
                elif r["flag50_event_type"] not in ("tournament", "review"):
                    why = f"eventType {r['flag50_event_type']}"
                elif not r["category"]:
                    why = f"format {e.get('format')}"
                elif not r["start_date"] or not (today.isoformat() <= r["start_date"] <= horizon.isoformat()):
                    why = "outside date window"
                if why:
                    skipped.append(
                        {"id": r["id"], "name": r["name"], "start_date": r["start_date"], "reason": why}
                    )
                    continue
                rows.append(r)
    except SiteBlocked as e:
        print(f"flag50 blocked ({e}); not writing (not invented)", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "window": [today.isoformat(), horizon.isoformat()],
        "states": states,
        "raw_count": raw_count,
        "count": len(rows),
        "skipped": skipped,
        "tournaments": rows,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"flag50: {raw_count} raw, {len(rows)} kept, {len(skipped)} skipped -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
