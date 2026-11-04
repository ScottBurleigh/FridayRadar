#!/usr/bin/env python3
"""Fetch upcoming Texas youth 7v7 / flag tournaments from public Zorts pages.

Stdlib only. Public pages only — no login, cookies-from-credentials, or secrets.
If Zorts returns 403 / captcha / Cloudflare, exit non-zero and write nothing
(keep the on-disk file). Never invent events.

Sources:
  POST /season/map  sport=FOOTBALL | FLAG_FOOTBALL | FLAG_FOOTBALL_1V1
  GET  /season/map  (all sports)
  GET  /season/find?types=TOURNAMENT&search=<kw>&offset=N
  GET  /join/tournament/<id>  detail (cost, divisions, contact, venue)
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import html
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.zortssports.com"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)
FLAG = re.compile(r"flag", re.I)
MAP_SPORTS = ["FOOTBALL", "FLAG_FOOTBALL", "FLAG_FOOTBALL_1V1"]
SEVEN = re.compile(r"\b7\s*-?\s*(?:v|vs\.?|on|x)\s*-?\s*7\b|\bseven\s*on\s*seven\b", re.I)
TEXAS = re.compile(r"(,\s*TX\b|\bTexas\b)", re.I)
MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        1,
    )
}
BLOCKED_MARKERS = (
    "cf-browser-verification",
    "cdn-cgi/challenge",
    "just a moment",
    "attention required! | cloudflare",
    "g-recaptcha",
    "hcaptcha",
    "cf-challenge",
    "enable javascript and cookies to continue",
)

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


class ZortsBlocked(RuntimeError):
    """Zorts refused the public scrape. Do not work around."""


def _looks_blocked(status: int | None, body: str) -> bool:
    if status in (401, 403, 429):
        return True
    low = (body or "")[:8000].lower()
    return any(m in low for m in BLOCKED_MARKERS)


def get(url, data=None, tries=3):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
            with opener.open(req, timeout=60) as r:
                page = r.read().decode("utf-8", "replace")
                if _looks_blocked(getattr(r, "status", 200), page):
                    raise ZortsBlocked(f"blocked fetching {url}")
                return page
        except ZortsBlocked:
            raise
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", "replace")
            except Exception:
                raw = ""
            if _looks_blocked(e.code, raw):
                raise ZortsBlocked(f"HTTP {e.code} fetching {url}") from e
            last = e
        except Exception as e:
            last = e
        if i == tries - 1:
            raise last if last else RuntimeError(f"fetch failed {url}")
        time.sleep(2 * (i + 1))
    raise last if last else RuntimeError(f"fetch failed {url}")


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def js_unescape(s):
    return clean(s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\"))


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_long(s, fallback_year=None):
    """'February 27, 2027' or 'February 27' (year taken from fallback)."""
    m = re.match(r"\s*([A-Za-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?", s or "")
    if not m or m.group(1).lower() not in MONTHS:
        return None
    y = int(m.group(3)) if m.group(3) else fallback_year
    return dt.date(y, MONTHS[m.group(1).lower()], int(m.group(2))) if y else None


def parse_short(s):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s.strip())
    if not m:
        return None
    y = int(m.group(3))
    y += 2000 if y < 100 else 0
    return dt.date(y, int(m.group(1)), int(m.group(2)))


STR = r"'((?:[^'\\]|\\.)*)'"


def parse_map(page):
    out = {}
    for blk in re.split(r"var latLng = new google\.maps\.LatLng", page)[1:]:
        f = dict(re.findall(r'\.replace\("#(\d)",\s*' + STR + r"\)", blk))
        sd = re.search(r"var startDate = " + STR, blk)
        ed = re.search(r"var endDate = " + STR, blk)
        ll = re.match(r"\(\s*([-\d.]+),\s*([-\d.]+)", blk)
        if "9" not in f:
            continue
        end_s, start_s = js_unescape(ed.group(1)) if ed else "", js_unescape(sd.group(1)) if sd else ""
        end = parse_long(end_s)
        start = parse_long(start_s, end.year if end else None)
        if start and end and start > end:  # e.g. 'December 30' .. 'January 2, 2027'
            start = start.replace(year=start.year - 1)
        out[f["9"]] = dict(
            id=f["9"],
            organizer=js_unescape(f.get("2")),
            name=js_unescape(f.get("3")),
            type=js_unescape(f.get("4")),
            sport=js_unescape(f.get("5")),
            age_groups=js_unescape(f.get("6")),
            location=js_unescape(f.get("7")),
            start=start,
            end=end or start,
            lat=ll.group(1) if ll else "",
            lng=ll.group(2) if ll else "",
            source="map",
        )
    return out


def parse_find(page):
    out = {}
    body = page.split("<tbody>", 1)[-1]
    for row in re.findall(r"(?s)<tr class=\"(?:odd|even)\">(.*?)</tr>\s*(?=<tr class=|</tbody>)", body):
        tid = re.search(r"clubHouse\?tid=(\d+)", row)
        if not tid:
            continue
        name_cell = re.search(r"(?s)vertical-align: top;\">(.*?)</td>", row)
        parts = [clean(p) for p in re.split(r"<br\s*/?>", name_cell.group(1))] if name_cell else ["", ""]
        dates = re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", row)
        flat = re.sub(r"(?s)<table.*?</table>", "", row)
        cells = [clean(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", flat)]
        loc = cells[2] if len(cells) > 2 else ""
        typ = cells[3] if len(cells) > 3 else ""
        sport = cells[4] if len(cells) > 5 else ""
        div = cells[5] if len(cells) > 5 else (cells[4] if len(cells) > 4 else "")
        start = parse_short(dates[0]) if dates else None
        end = parse_short(dates[1]) if len(dates) > 1 else start
        out[tid.group(1)] = dict(
            id=tid.group(1),
            organizer=parts[0],
            name=" ".join(parts[1:]).strip(),
            type="Tournament" if "Tournament" in typ else typ,
            sport=(typ.replace("Tournament", "").strip() + " " + sport).strip(),
            age_groups=div,
            location=loc,
            start=start,
            end=end,
            lat="",
            lng="",
            source="find",
        )
    return out


def section(page, title):
    m = re.search(r"(?s)<h5[^>]*>\s*" + re.escape(title) + r"\s*</h5>(.*?)(?=<h5|<h4|</section>)", page)
    return m.group(1) if m else ""


def parse_detail(page):
    d = {}
    cost = section(page, "Cost")
    lis = [clean(x) for x in re.findall(r"(?s)<li>(.*?)</li>", cost)]
    d["entry_fee"] = next((x for x in lis if "USD" in x and "per" in x and "late fee" not in x), "")
    d["registration_ends"] = next(
        (x.replace("Registration ends", "").strip() for x in lis if x.startswith("Registration ends")),
        "",
    )
    contact = section(page, "Contact")
    d["contact_email"] = "; ".join(sorted(set(html.unescape(e) for e in re.findall(r'mailto:([^?"]+)', contact))))
    d["contact_phone"] = "; ".join(sorted(set(re.findall(r'href="tel:([^"]+)"', contact))))
    d["venue"] = clean(section(page, "Location").split("</div>")[0])
    d["sport_detail"] = clean(section(page, "Sport").split("</div>")[0])
    divs = section(page, "Divisions")
    d["divisions"] = "; ".join(clean(x) for x in re.findall(r"(?s)<li>\s*([^<]+?)\s*<ul>", divs))
    org = re.search(r'(?s)/season/index\?orgId=\d+">(.*?)</a>', page)
    d["organizer_detail"] = clean(org.group(1)) if org else ""
    h2 = re.search(r"(?s)<h2>(.*?)</h2>", page)
    d["name_detail"] = clean(h2.group(1)) if h2 else ""
    return d


def city_from(loc):
    parts = [p.strip() for p in loc.split(",")]
    for i, p in enumerate(parts):
        if re.match(r"^(TX|Texas)\b", p):
            return parts[i - 1] if i else ""
    return ""


def category(e):
    """'7v7', 'flag', 'both' or '' based on sport/name/divisions text."""
    blob = " ".join([e.get("name") or "", e.get("organizer") or "", e.get("age_groups") or "", e.get("divisions") or ""])
    seven = "7v7" in (e.get("sport") or "") or bool(SEVEN.search(blob))
    flag = bool(FLAG.search(" ".join([e.get("sport") or "", e.get("name") or "", e.get("divisions") or ""])))
    return "both" if seven and flag else "7v7" if seven else "flag" if flag else ""


def row_from_event(e):
    start = e["start"]
    end = e["end"] or start
    return {
        "id": e["id"],
        "category": e["category"],
        "name": e["name"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "city": e["city"],
        "venue": e["location"],
        "sport": e["sport"],
        "age_groups": e["age_groups"],
        "divisions": e.get("divisions", ""),
        "entry_fee": e.get("entry_fee", ""),
        "registration_ends": e.get("registration_ends", ""),
        "organizer": e["organizer"],
        "contact_email": e.get("contact_email", ""),
        "contact_phone": e.get("contact_phone", ""),
        "event_url": e["event_url"],
        "clubhouse_url": e["clubhouse_url"],
        "source": e["source"],
    }


def fetch_events(*, months: int, no_find: bool, no_details: bool, max_pages: int, keywords: list[str], delay: float):
    today = dt.date.today()
    horizon = add_months(today, months)
    events = {}
    for sp in MAP_SPORTS:
        fb = parse_map(get(BASE + "/season/map", {"sport": sp}))
        print(f"map(sport={sp}): {len(fb)} events", file=sys.stderr)
        for k, v in fb.items():
            events.setdefault(k, v)
    allm = parse_map(get(BASE + "/season/map"))
    print(f"map(all sports): {len(allm)} events", file=sys.stderr)
    for k, v in allm.items():
        events.setdefault(k, v)
    if not no_find:
        for kw in keywords:
            n = 0
            last_page = 0
            for p in range(max_pages):
                last_page = p
                q = urllib.parse.urlencode({"types": "TOURNAMENT", "search": kw, "offset": p * 10, "max": 10})
                rows = parse_find(get(f"{BASE}/season/find?{q}"))
                if not rows:
                    break
                for k, v in rows.items():
                    if k not in events:
                        events[k] = v
                        n += 1
                time.sleep(delay)
            print(f"find(search={kw!r}): {last_page} pages, {n} extra events", file=sys.stderr)

    def is_match(e):
        if e["type"] != "Tournament":
            return False
        if not TEXAS.search(e["location"] or ""):
            return False
        if not category(e):
            return False
        return e["start"] is not None and today <= e["start"] <= horizon

    matches = [e for e in events.values() if is_match(e)]
    for e in matches:
        e["category_pre"] = category(e)
        e["event_url"] = f"{BASE}/join/tournament/{e['id']}"
        e["clubhouse_url"] = f"{BASE}/post/clubHouse/{e['id']}"
        e["city"] = city_from(e["location"])
        if not no_details:
            try:
                d = parse_detail(get(e["event_url"]))
                time.sleep(delay)
                e.update(
                    entry_fee=d["entry_fee"],
                    registration_ends=d["registration_ends"],
                    contact_email=d["contact_email"],
                    contact_phone=d["contact_phone"],
                    divisions=d["divisions"],
                )
                if d["venue"]:
                    e["location"] = d["venue"]
                    e["city"] = city_from(d["venue"]) or e["city"]
                if d["sport_detail"]:
                    e["sport"] = d["sport_detail"]
            except ZortsBlocked:
                raise
            except Exception as ex:
                print(f"detail {e['id']} failed: {ex}", file=sys.stderr)
    for e in matches:
        e["category"] = category(e) or e.get("category_pre", "")
    seen, out = set(), []
    for e in sorted(matches, key=lambda e: (e["start"], e["name"])):
        key = (e["name"].lower(), e["start"], (e["location"] or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    rows = [row_from_event(e) for e in out]
    payload = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "window": [today.isoformat(), horizon.isoformat()],
        "count": len(rows),
        "tournaments": rows,
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Public Zorts Texas 7v7/flag tournament scrape")
    ap.add_argument("--months", type=int, default=7)
    ap.add_argument("--outdir", default=str(ROOT / "data"))
    ap.add_argument("--no-find", action="store_true", help="skip paginated /season/find crawl")
    ap.add_argument("--no-details", action="store_true", help="skip per-event detail pages")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument(
        "--keywords",
        nargs="+",
        default=["7v7 TX", "7v7 Texas", "7on7", "7 on 7", "flag TX", "flag Texas", "5v5"],
        help="search terms for the /season/find crawl",
    )
    ap.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args()
    # Never accept credentials — this scrape is public pages only.
    if os.environ.get("ZORTS_EMAIL") or os.environ.get("ZORTS_PASSWORD"):
        print("ignoring ZORTS_EMAIL/ZORTS_PASSWORD (public pages only)", file=sys.stderr)
    try:
        payload = fetch_events(
            months=a.months,
            no_find=a.no_find,
            no_details=a.no_details,
            max_pages=a.max_pages,
            keywords=a.keywords,
            delay=a.delay,
        )
    except ZortsBlocked as e:
        print(f"zorts blocked ({e}); not writing (not invented)", file=sys.stderr)
        return 2
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / "tournaments.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    today, horizon = payload["window"]
    print(
        f"{payload['count']} Texas 7v7/flag tournaments {today}..{horizon} -> {dest}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
