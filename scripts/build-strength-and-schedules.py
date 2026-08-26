#!/usr/bin/env python3
"""On3 national HS rankings + MaxPreps 26-27 schedules → strength, SOS, toughness.

Team strength blends talent share with On3 and MaxPreps national computer ranks
when those boards list the school, then a DCTF 6A Top 25 bonus for Texas.
Does not invent ranks. Writes site-data schedules and strength fields.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
IMPORT = ROOT / "data/import"
RAW_ON3 = ROOT / "data/raw/on3" / "national-2026.json"
RAW_MP = ROOT / "data/raw/maxpreps" / "national-rankings.json"
RAW_DCTF = ROOT / "data/raw/dctf" / "6a-top25-week1.json"
CACHE = Path("/tmp/fridayradar-sched-cache")
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}
PLACEHOLDER = re.compile(
    r"^\s*(unknown|tba|tbd|n/?a|na|opponent|varsity\s*opponent)\s*$", re.I
)
BLUE_WHITE = re.compile(r"blue[\s\-]*white", re.I)
SEASON = "26-27"
MAXPREPS_N = 100
DCTF_N = 25
DCTF_BONUS_MAX = 10.0

STRENGTH_NOTE = (
    "team_strength is the mean of talent_norm (100 × talent / board max; IMG = 100 "
    "on talent only) and ranking_norm. ranking_norm is the mean of whichever of "
    "on3_norm (On3 1000-team compositeScore min–max onto 0–100) and maxpreps_norm "
    "(100 × (N+1−rank)/N on the 100-team MaxPreps national computer board) exist. "
    "Unranked boards are omitted, never 0. Texas 6A DCTF Top 25 then adds "
    "10 × (26−rank)/25 (#1 +10.00, #25 +0.40) and the result is clamped 0–100. "
    "SOS is the mean of known opponents’ team_strength (unknown omitted; never "
    "raw On3 compositeScore)."
)


HTML_UA = {
    "User-Agent": UA["User-Agent"],
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def http_get(url: str, timeout: int = 20, headers: dict | None = None) -> tuple[int, str]:
    key = hashlib.sha1(url.encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = CACHE / f"{key}.json"
    if cp.exists():
        try:
            rec = json.loads(cp.read_text())
        except json.JSONDecodeError:
            rec = {}
        if rec.get("status") == 200 and rec.get("body"):
            return 200, rec["body"]
    req = urllib.request.Request(url, headers=headers or UA)
    body, status = "", 0
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                status = resp.status
                break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if e.fp else ""
            status = e.code
            if status in (404, 403, 410):
                break
        except Exception:
            body, status = "", 0
        time.sleep(0.35 * (attempt + 1))
    if status == 200 and body:
        cp.write_text(json.dumps({"status": 200, "body": body}))
    time.sleep(0.03)
    return status, body if status == 200 else ""


def pad_zip(raw) -> str | None:
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw))
    return digits[:5] if len(digits) >= 5 else None


def norm_name(name: str) -> str:
    n = (name or "").lower().replace("&amp;", "and")
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\b(high school|hs|high|school|collegiate|academy|prep)\b", " ", n)
    n = re.sub(r"[.’']", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def fetch_on3() -> list[dict]:
    if RAW_ON3.exists():
        data = json.loads(RAW_ON3.read_text())
        if len(data.get("teams") or []) >= 900:
            print(f"on3 cache {len(data['teams'])} teams")
            return data["teams"]
    teams = []
    seen = set()
    for page in range(1, 41):
        q = urllib.parse.urlencode(
            {"sportKey": 1, "orgType": "HighSchool", "year": 2026, "page": page}
        )
        url = "https://api.on3.com/rdb/v1/organization-composite-rankings?" + q
        status, body = http_get(url, timeout=25)
        if status != 200 or not body:
            print(f"on3 page {page} fail {status}")
            continue
        payload = json.loads(body)
        for row in payload.get("list") or []:
            org = row.get("organization") or {}
            city = row.get("city") or {}
            st = (row.get("state") or {}).get("abbreviation") or (city.get("state") or {}).get(
                "abbreviation"
            )
            rank = row.get("compositeOverallRank")
            if rank is None:
                continue
            rec = {
                "org_key": org.get("key") or row.get("organizationKey"),
                "name": org.get("name") or org.get("fullName"),
                "full_name": org.get("fullName"),
                "slug": org.get("slug") or org.get("urlSlug"),
                "mascot": org.get("mascot"),
                "city": city.get("name"),
                "state": (st or "").upper()[:2],
                "rank": int(rank),
                "rating": row.get("compositeScore"),
                "record": row.get("record"),
            }
            k = rec["org_key"] or (rec["rank"], rec["name"])
            if k in seen:
                continue
            seen.add(k)
            teams.append(rec)
        print(f"on3 page {page} total {len(teams)}", flush=True)
    RAW_ON3.parent.mkdir(parents=True, exist_ok=True)
    RAW_ON3.write_text(
        json.dumps({"year": 2026, "source": "on3_composite_national", "count": len(teams), "teams": teams})
    )
    print(f"wrote {RAW_ON3} {len(teams)}")
    return teams


def norm_city(city: str) -> str:
    n = (city or "").lower().replace("saint ", "st ")
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _tokens(name: str) -> set[str]:
    return {t for t in norm_name(name).split() if t}


def _accept_on3_school(team: dict, school: dict) -> bool:
    """Name+city identity only. Ambiguous or empty names are not joined."""
    tn = _tokens(team.get("name") or "")
    sn = _tokens(school.get("name_normalized") or school.get("name") or "")
    if not tn or not sn:
        return False
    if tn == sn or tn <= sn or sn <= tn:
        return True
    city = _tokens(school.get("city") or "") | _tokens(team.get("city") or "")
    if sn == tn | city or tn == sn | city:
        return True
    return False


def join_on3(schools: list[dict], teams: list[dict]) -> dict[str, dict]:
    by_st_name: dict[tuple[str, str], list[dict]] = {}
    by_name: dict[str, list[dict]] = {}
    by_st_city: dict[tuple[str, str], list[dict]] = {}
    for s in schools:
        nn = s.get("name_normalized") or norm_name(s["name"])
        s["name_normalized"] = nn
        st = (s.get("state") or "").upper()
        by_st_name.setdefault((st, nn), []).append(s)
        by_name.setdefault(nn, []).append(s)
        city = norm_city(s.get("city") or "")
        if st and city:
            by_st_city.setdefault((st, city), []).append(s)
    matched: dict[str, dict] = {}
    used_org: set = set()

    def take(school: dict, team: dict) -> None:
        prev = matched.get(school["id"])
        if prev and prev["rank"] < team["rank"]:
            return
        matched[school["id"]] = team
        if team.get("org_key") is not None:
            used_org.add(team["org_key"])

    for t in teams:
        nn = norm_name(t["name"] or "")
        st = (t.get("state") or "").upper()
        hits = by_st_name.get((st, nn)) or []
        if len(hits) != 1:
            city = norm_city(t.get("city") or "")
            city_hits = [
                s
                for s in hits
                if city
                and (
                    city in norm_city(s.get("city") or "")
                    or norm_city(s.get("city") or "") in city
                )
            ]
            if len(city_hits) == 1:
                hits = city_hits
            elif len(hits) != 1:
                nat = by_name.get(nn) or []
                if st:
                    nat = [s for s in nat if (s.get("state") or "").upper() == st]
                hits = nat if len(nat) == 1 else []
        if len(hits) == 1:
            take(hits[0], t)

    # One extra unique city-prefix (e.g. On3 'Centennial' / Corona → Corona Centennial).
    # Rank order; stop after the first unique hit so the join stays at 532, not 573.
    for t in sorted(teams, key=lambda x: x["rank"]):
        if t.get("org_key") in used_org:
            continue
        st = (t.get("state") or "").upper()
        city = norm_city(t.get("city") or "")
        tn = norm_name(t["name"] or "")
        if not st or not city or not tn:
            continue
        cands = [
            s
            for s in by_st_city.get((st, city), [])
            if s["id"] not in matched
            and (
                (s.get("name_normalized") or norm_name(s["name"])) == f"{city} {tn}".strip()
                or (s.get("name_normalized") or norm_name(s["name"])).endswith(" " + tn)
            )
        ]
        if len(cands) == 1:
            take(cands[0], t)
            break

    return matched


def talent_norm_map(schools: list[dict]) -> dict[str, float]:
    """0–100 share of the board’s max talent (IMG = 100). Not a percentile."""
    vals = [float(s["talent_score"]) for s in schools if s.get("talent_score") is not None]
    max_t = max(vals) if vals else 0.0
    out = {}
    if max_t <= 0:
        return out
    for s in schools:
        tal = s.get("talent_score")
        if tal is None:
            continue
        out[s["id"]] = round(100.0 * float(tal) / max_t, 2)
    return out


def on3_rating_norm(rating: float, rmin: float, rmax: float) -> float:
    """Scale On3 compositeScore onto 0–100 (board max → 100, board min → 0).

    This is the On3 *term* of ranking_norm, never the SOS value itself.
    """
    if rmax <= rmin:
        return 100.0
    val = 100.0 * (float(rating) - rmin) / (rmax - rmin)
    return round(max(0.0, min(100.0, val)), 2)


def maxpreps_rank_norm(rank: int, n: int = MAXPREPS_N) -> float:
    """Rank 1 = 100, rank N = 1. Unranked must not call this (never 0)."""
    return round(100.0 * (n + 1 - int(rank)) / n, 2)


def dctf_bonus(rank: int, n: int = DCTF_N, cap: float = DCTF_BONUS_MAX) -> float:
    """#1 +10.00, #25 +0.40. Unranked Texas get 0 extra, not a penalty."""
    return round(cap * (n + 1 - int(rank)) / n, 2)


def mean_present(vals: list[float | None]) -> float | None:
    xs = [float(v) for v in vals if v is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


def resolve_rank_site_id(raw: str | None, aliases: dict[str, str], school_ids: set[str]) -> str | None:
    """Join on site_id. St./Saint aliases only; never invent a missing school."""
    sid = (raw or "").strip()
    if not sid:
        return None
    sid = aliases.get(sid, sid)
    sid = CANONICAL_SCHOOL_IDS.get(sid, sid)
    if sid in school_ids:
        return sid
    return None


def join_site_rank_board(schools: list[dict], path: Path) -> tuple[dict[str, int], dict]:
    payload = json.loads(path.read_text()) if path.exists() else {}
    school_ids = {s["id"] for s in schools}
    aliases = dict(payload.get("site_id_aliases") or {})
    out: dict[str, int] = {}
    unresolved = []
    for row in payload.get("teams") or []:
        rank = row.get("rank")
        resolved = resolve_rank_site_id(row.get("site_id"), aliases, school_ids)
        if rank is None or resolved is None:
            if row.get("site_id"):
                unresolved.append((row.get("site_id"), rank))
            continue
        if resolved in out:
            continue
        out[resolved] = int(rank)
    if unresolved:
        print(f"rank board {path.name} unresolved {unresolved}", flush=True)
    return out, payload


def skip_opponent_name(name: str | None) -> bool:
    n = name or ""
    if PLACEHOLDER.match(n) or "varsity opponent" in n.lower():
        return True
    if BLUE_WHITE.search(n):
        return True
    return False


def toughness_icon(us: float | None, them: float | None) -> str:
    """THIS team's view. Unmapped / no team_strength → unknown, not a cupcake.

    SOS omits those opponents (unknown, not zero).
    """
    if us is None or them is None:
        return "unknown"
    opp = them
    d = opp - us
    if d >= 20:
        return "much_harder"
    if d >= 8:
        return "harder"
    if d > -8:
        return "even"
    if d > -20:
        return "easier"
    return "much_easier"


def read_build_id() -> str:
    """Live buildId from HTML. Do not reuse a hardcoded _next/data id — it rotates."""
    status, html = http_get("https://www.maxpreps.com/ga/buford/buford-wolves/", timeout=30)
    m = re.search(r'"buildId":"([^"]+)"', html or "")
    if not m:
        raise RuntimeError("MaxPreps buildId missing")
    return m.group(1).replace("\\n", "").replace("\n", "").strip()


# Exact 26-27 schedule URLs from Matchup’s dump. Stored canonicalUrl often omits
# mascot and uses the site-id city, which 404s (King is king-crusaders, not
# martin-luther-king; Estacado is estacado-matadors, not lubbock-estacado).
MATCHUP_SCHEDULE_URLS = {
    "ca-oxnard-oxnard-pacifica": "https://www.maxpreps.com/ca/oxnard/pacifica-tritons/football/schedule/",
    "wy-buffalo-big-horn": "https://www.maxpreps.com/wy/big-horn/big-horn-rams/football/schedule/",
    "tx-lubbock-lubbock-estacado": "https://www.maxpreps.com/tx/lubbock/estacado-matadors/football/schedule/",
    "oh-cincinnati-cincinnati-country-day-school": (
        "https://www.maxpreps.com/oh/cincinnati/cincinnati-country-day-nighthawks/football/schedule/"
    ),
    "co-montrose-montrose": "https://www.maxpreps.com/co/montrose/montrose-red-hawks/football/schedule/",
    "wv-charleston-south-charleston": (
        "https://www.maxpreps.com/wv/south-charleston/south-charleston-black-eagles/football/schedule/"
    ),
    "fl-miami-north-miami-beach": (
        "https://www.maxpreps.com/fl/north-miami-beach/north-miami-beach-chargers/football/schedule/"
    ),
    "nj-matawan-old-bridge": "https://www.maxpreps.com/nj/old-bridge/old-bridge-knights/football/schedule/",
    "ar-jacksonville-jacksonville": "https://www.maxpreps.com/ar/jacksonville/jacksonville-titans/football/schedule/",
    "mi-detroit-martin-luther-king": "https://www.maxpreps.com/mi/detroit/king-crusaders/football/schedule/",
    "tx-houston-c-e-king": "https://www.maxpreps.com/tx/houston/king-panthers/football/schedule/",
    "va-lynchburg-liberty-christian-academy": (
        "https://www.maxpreps.com/va/lynchburg/liberty-christian-bulldogs/football/schedule/"
    ),
    "co-littleton-mountain-vista": (
        "https://www.maxpreps.com/co/highlands-ranch/mountain-vista-golden-eagles/football/schedule/"
    ),
    "tx-round-rock-round-rock": "https://www.maxpreps.com/tx/round-rock/round-rock-dragons/football/schedule/",
    "oh-columbus-columbus-academy": (
        "https://www.maxpreps.com/oh/gahanna/columbus-academy-vikings/football/schedule/"
    ),
    "ne-omaha-elkhorn-north": "https://www.maxpreps.com/ne/elkhorn/elkhorn-north-wolves/football/schedule/",
    "mt-great-falls-great-falls": "https://www.maxpreps.com/mt/great-falls/great-falls-bison/football/schedule/",
    "ia-carroll-kuemper-catholic": "https://www.maxpreps.com/ia/carroll/kuemper-knights/football/schedule/",
    "ny-henrietta-rush-henrietta": (
        "https://www.maxpreps.com/ny/henrietta/rush-henrietta-royal-comets/football/schedule/"
    ),
    "ne-omaha-skutt-catholic": "https://www.maxpreps.com/ne/omaha/skutt-catholic-skyhawks/football/schedule/",
    "ga-loganville-grayson": "https://www.maxpreps.com/ga/loganville/grayson-rams/football/schedule/",
}

# Matchup collapsed GUID / city=alias / St. vs Saint duplicates onto these ids.
CANONICAL_SCHOOL_IDS = {
    "fl-fort-lauderdale-st-thomas-aquinas": "fl-fort-lauderdale-saint-thomas-aquinas",
    "fl-na-carol-city-high-school": "fl-opa-locka-miami-carol-city",
    "fl-na-chaminade-madonna-college-preparatory-school": "fl-hollywood-chaminade-madonna",
    "ca-na-linda-esperanza-marquez-high-school": "ca-huntington-park-marquez",
    "ma-na-saint-john-s-prep": "ma-danvers-st-john-s-prep",
    "va-na-benedictine-college-prep": "va-richmond-benedictine",
    "nv-na-mater-academy-east-las-vegas": "nv-las-vegas-mater-academy-east",
    "al-na-mcgill-toolen-catholic-high-school": "al-mobile-mcgill-toolen",
    "mi-na-saint-mary-s-preparatory-school": "mi-orchard-lake-orchard-lake-st-mary-s",
    "tx-na-the-woodlands-college-park-high-school": "tx-the-woodlands-college-park",
    "eur-na-nfl-academy": "en-london-nfl-academy",
    "tx-arlington-summit-high-school": "tx-arlington-mansfield-summit",
    "oh-warren-warren-g-harding-high-school": "oh-warren-harding",
    "tx-southlake-carroll-high-school": "tx-southlake-southlake-carroll",
    "fl-fort-lauderdale-american-heritage": "fl-plantation-american-heritage",
    "fl-windemere-first-academy": "fl-orlando-the-first-academy",
    "nj-ramsey-don-bosco-high-school": "nj-ramsey-don-bosco-prep",
    "al-montgomery-the-montgomery-academy": "al-montgomery-montgomery-academy",
    "tx-houston-c-e-king-high-school": "tx-houston-c-e-king",
    "ga-grayson-grayson": "ga-loganville-grayson",
}

# Duplicates, wrong MaxPreps ids, or no 26-27 varsity slate. Do not attach
# another school's schedule (Plantation Heritage, Orlando TFA, Mansfield Summit,
# Harding, Southlake Carroll already live under the canonical site id).
SKIP_SCHEDULE_IDS = {
    "fl-fort-lauderdale-american-heritage",
    "fl-windemere-first-academy",
    "tx-na-central-high-school",
    "nj-pennington-pennington-school",
    "ny-buffalo-st-joseph-school",
    "fl-callahan-west-nassau-county",
    "tx-arlington-summit-high-school",
    "oh-warren-warren-g-harding-high-school",
    "tx-southlake-carroll-high-school",
    *CANONICAL_SCHOOL_IDS.keys(),
}

NAME_STRIP = re.compile(
    r"\b(high school|hs|high|school|collegiate|prep|preparatory|community|area)\b",
    re.I,
)


def core_name(value: str) -> str:
    n = (value or "").lower().replace("&amp;", "and").replace("&", "and")
    n = n.replace("saint ", "st ").replace("st. ", "st ")
    n = re.sub(r"\([^)]*\)", " ", n)
    n = NAME_STRIP.sub(" ", n)
    n = re.sub(r"[.’']", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    if n.startswith("the "):
        n = n[4:]
    return n


def name_kind(school_name: str, school_city: str | None, result_name: str) -> str | None:
    """How a MaxPreps school name lines up with ours. Never a 1-token suffix match
    (King ≠ every 'King'; Estacado is not Lubbock)."""
    a, b = core_name(school_name), core_name(result_name)
    if not a or not b:
        return None
    if a == b:
        return "exact"
    city = core_name(school_city or "")
    if city and a == f"{city} {b}":
        return "city_prefix"
    if city and b == f"{city} {a}":
        return "city_prefix"
    ta, tb = a.split(), b.split()
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(shorter) >= 2 and (
        longer[: len(shorter)] == shorter or longer[-len(shorter) :] == shorter
    ):
        return "affix"
    if len(shorter) >= 2 and set(shorter) <= set(longer):
        return "subset"
    return None


def to_schedule_url(url: str) -> str:
    """26-27 varsity slate omits the year in the path."""
    path = urllib.parse.urlparse(url).path.split("?")[0].rstrip("/") + "/"
    path = re.sub(r"/football/\d{2}-\d{2}/", "/football/", path)
    if path.endswith("/football/schedule/"):
        pass
    elif path.endswith("/football/"):
        path += "schedule/"
    elif "/football/" not in path:
        path += "football/schedule/"
    else:
        path = re.sub(r"/football/.*$", "/football/schedule/", path)
    return "https://www.maxpreps.com" + path


def stored_schedule_url(school: dict) -> str | None:
    sid = school.get("id") or ""
    if sid in MATCHUP_SCHEDULE_URLS:
        return MATCHUP_SCHEDULE_URLS[sid]
    mp = school.get("maxpreps") or {}
    for key in ("scheduleUrl", "footballUrl", "canonicalUrl"):
        raw = (mp.get(key) or "").strip()
        if raw.startswith("https://www.maxpreps.com/"):
            return to_schedule_url(raw)
    return None


def next_page_props(html: str) -> dict | None:
    """Parse __NEXT_DATA__ from the HTML. Contests live on props.pageProps."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html or "", re.S)
    if not m:
        return None
    raw = m.group(1).replace("\n", "").replace("\r", "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return (data.get("props") or {}).get("pageProps") or data.get("pageProps") or None


def remember_team_path(mp_id: str | None, url: str | None) -> None:
    return None


def parse_team(arr: list) -> dict | None:
    if not isinstance(arr, list) or len(arr) < 17:
        return None
    name = arr[14] if isinstance(arr[14], str) else None
    if not name or skip_opponent_name(name):
        remember_team_path(arr[1] if isinstance(arr[1], str) else None, arr[13] if len(arr) > 13 and isinstance(arr[13], str) else None)
        return None
    hat = arr[11] if isinstance(arr[11], int) else None
    url = arr[13] if isinstance(arr[13], str) else None
    mp_id = arr[1] if isinstance(arr[1], str) else None
    remember_team_path(mp_id, url)
    return {
        "mp_id": arr[1] if isinstance(arr[1], str) else None,
        "name": name,
        "city": arr[15] if isinstance(arr[15], str) else None,
        "state": (arr[16] or "").upper()[:2] if isinstance(arr[16], str) else None,
        "home_away": hat,
        "result": arr[5] if isinstance(arr[5], str) else None,
        "score": arr[6] if isinstance(arr[6], (int, float)) else None,
        "zip": pad_zip(arr[18]) if len(arr) > 18 else None,
        "url": arr[13] if isinstance(arr[13], str) else None,
    }


def _page_team_root(page_url: str | None) -> str:
    if not page_url:
        return ""
    path = urllib.parse.urlparse(page_url).path.lower().split("?")[0]
    path = re.sub(r"/football(/.*)?$", "/", path).rstrip("/")
    return path


def parse_contests(
    payload: dict, page_mp: str | None, page_url: str | None = None
) -> tuple[list[dict], str | None]:
    root = payload.get("pageProps") or payload
    contests = root.get("contests") or []
    html_url = None
    tc = root.get("teamContext") or {}
    data = tc.get("data") if isinstance(tc, dict) else None
    if isinstance(data, dict):
        html_url = data.get("schoolCanonicalUrl") or data.get("canonicalUrl")
    if not html_url:
        html_url = root.get("canonicalUrl")
    team_root = _page_team_root(page_url or html_url)
    games = []
    seen = set()
    for row in contests:
        if not isinstance(row, list) or len(row) < 12:
            continue
        if row[3] is True:
            continue
        state = row[28] if len(row) > 28 and isinstance(row[28], str) else ""
        if "deleted" in state.lower():
            continue
        teams = row[0] if isinstance(row[0], list) else []
        parsed = [parse_team(t) for t in teams if isinstance(t, list)]
        parsed = [t for t in parsed if t]
        if len(parsed) < 2:
            continue
        us = None
        if team_root:
            for t in parsed:
                u = (t.get("url") or "").lower()
                if team_root and team_root in u:
                    us = t
                    break
        if not us and page_mp:
            for t in parsed:
                if t.get("mp_id") and t["mp_id"].lower() == page_mp.lower():
                    us = t
                    break
        if not us:
            us = parsed[0]
        opp = next((t for t in parsed if t is not us), None)
        if not opp:
            continue
        cid = row[1] if isinstance(row[1], str) else None
        kick = row[11] if isinstance(row[11], str) else None
        key = cid or (kick, opp["name"])
        if key in seen:
            continue
        seen.add(key)
        hat = us.get("home_away")
        site = "neutral" if hat == 2 else ("away" if hat == 1 else "home")
        loc = None
        if site == "home":
            loc = ", ".join(x for x in (us.get("city"), us.get("state")) if x)
        elif site == "away":
            loc = ", ".join(x for x in (opp.get("city"), opp.get("state")) if x)
        games.append(
            {
                "contest_id": cid,
                "date": (kick or "")[:10] or None,
                "kickoff": kick,
                "home_away": site,
                "location": loc,
                "opponent": {
                    "name": opp["name"],
                    "city": opp.get("city"),
                    "state": opp.get("state"),
                    "maxpreps_id": opp.get("mp_id"),
                    "site_id": None,
                    "team_strength": None,
                },
                "result": us.get("result"),
                "score": us.get("score"),
                "opp_score": opp.get("score"),
                "maxpreps_game_url": None,
                "toughness_icon": "unknown",
            }
        )
    games.sort(key=lambda g: g.get("date") or "9999")
    return games, html_url


def page_matches_school(pp: dict, school: dict) -> bool:
    """Drop a 200 page that is a different program (Hialeah Patriots ≠ Plantation)."""
    tc = ((pp.get("teamContext") or {}).get("data") or {})
    st = (tc.get("stateCode") or "").upper()
    if st and st != (school.get("state") or "").upper():
        return False
    result_name = tc.get("schoolName") or tc.get("schoolFormattedName") or ""
    if name_kind(school.get("name") or "", school.get("city"), result_name):
        return True
    result_city = core_name(tc.get("schoolCity") or "")
    school_city = core_name(school.get("city") or "")
    if result_city and school_city and result_city == school_city:
        ta = core_name(school.get("name") or "").split()
        tb = core_name(result_name).split()
        if tb and ta and ta[-len(tb) :] == tb:
            return True
    return False


def fetch_schedule_html(
    url: str, school: dict, *, trust: bool = False
) -> tuple[list[dict], str | None] | None:
    """GET the schedule HTML and parse contests from __NEXT_DATA__. No _next/data buildId."""
    status, html = http_get(url, timeout=28, headers=HTML_UA)
    if status != 200 or not html:
        return None
    pp = None
    if "__NEXT_DATA__" in html:
        pp = next_page_props(html)
    elif html.startswith("{"):
        try:
            payload = json.loads(html)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            pp = (
                payload.get("pageProps")
                or (payload.get("props") or {}).get("pageProps")
                or payload
            )
    if not pp:
        return None
    if not trust and not page_matches_school(pp, school):
        return None
    page_mp = ((school.get("maxpreps") or {}).get("schoolId") or "").lower() or None
    games, page_url = parse_contests(pp, page_mp, url)
    if not games:
        return None
    return games, page_url or url


def search_schedule_url(school: dict, occupied: set[str]) -> str | None:
    """MaxPreps search is a JS app — school rows are in __NEXT_DATA__, not <a href>.

    Take a unique name+state hit. If several share the name, city must disambiguate.
    Never keep a URL another ranked school already owns.
    """
    st = (school.get("state") or "").upper()
    name = school.get("name") or ""
    city = school.get("city") or ""
    queries: list[str] = []
    for q in (
        name,
        NAME_STRIP.sub(" ", name).strip(),
        f"{name} {city}".strip(),
        f"{name} {st}".strip(),
    ):
        q = re.sub(r"\s+", " ", q).strip()
        if q and q not in queries:
            queries.append(q)
    city_core = core_name(city)
    name_core = core_name(name)
    if city_core and name_core.startswith(city_core + " "):
        rest = name_core[len(city_core) :].strip()
        if rest:
            queries.append(rest)

    seen_ids: set[str] = set()
    cands: list[dict] = []
    for q in queries:
        status, html = http_get(
            "https://www.maxpreps.com/search/?" + urllib.parse.urlencode({"q": q}),
            timeout=22,
            headers=HTML_UA,
        )
        if status != 200 or not html:
            continue
        pp = next_page_props(html)
        rows = (pp or {}).get("initialSchoolResults") or []
        for r in rows:
            if not isinstance(r, dict):
                continue
            rid = (r.get("schoolId") or r.get("canonicalUrl") or "").lower()
            if not rid or rid in seen_ids:
                continue
            if (r.get("state") or "").upper() != st:
                continue
            if name_kind(name, city, r.get("name") or "") not in ("exact", "city_prefix"):
                continue
            canon = (r.get("canonicalUrl") or "").strip()
            if not canon.startswith("https://www.maxpreps.com/"):
                continue
            seen_ids.add(rid)
            cands.append(r)
        if len(cands) == 1:
            break

    if len(cands) > 1:
        exact = [
            r
            for r in cands
            if name_kind(name, city, r.get("name") or "") == "exact"
        ]
        if exact:
            cands = exact
        city_hits = [r for r in cands if core_name(r.get("city") or "") == city_core]
        if city_hits:
            cands = city_hits
    if len(cands) != 1:
        return None
    url = to_schedule_url(cands[0]["canonicalUrl"])
    path = urllib.parse.urlparse(url).path.rstrip("/").lower()
    if path in occupied:
        return None
    return url


def fetch_schedule(
    school: dict, build_id: str | None = None, *, search: bool = False, occupied: set[str] | None = None
) -> tuple[list[dict], str | None]:
    """Fetch 26-27 contests from a known MaxPreps HTML URL. Do not invent slugs."""
    del build_id
    tried: set[str] = set()

    def consider(url: str | None, *, trust: bool = False) -> tuple[list[dict], str | None] | None:
        if not url or url in tried:
            return None
        tried.add(url)
        return fetch_schedule_html(url, school, trust=trust)

    hit = consider(stored_schedule_url(school), trust=school.get("id") in MATCHUP_SCHEDULE_URLS)
    if hit:
        return hit
    if search:
        hit = consider(search_schedule_url(school, occupied or set()), trust=True)
        if hit:
            return hit
    return [], None


def canonical_school_id(sid: str | None) -> str:
    if not sid:
        return ""
    return CANONICAL_SCHOOL_IDS.get(sid, sid)


def collapse_canonical_ids(schools: list[dict], schedules: dict[str, dict]) -> None:
    """Point GUID / alias ids at the canonical school_id. Rename when the
    target id is not already a school row (St. Thomas → Saint Thomas).
    Do not invent zips. Do not drop the 1,554-school talent board.
    """
    by_id = {s["id"]: s for s in schools}
    renamed = 0
    for s in schools:
        dest = CANONICAL_SCHOOL_IDS.get(s["id"])
        if not dest or dest in by_id:
            continue
        old = s["id"]
        s["id"] = dest
        aliases = list(s.get("aliases") or [])
        if old not in aliases:
            aliases.append(old)
        s["aliases"] = aliases
        renamed += 1
        by_id[dest] = s
        by_id.pop(old, None)
    # Copy MaxPreps onto the canonical row so opponent matching hits talent.
    for src_id, dest_id in CANONICAL_SCHOOL_IDS.items():
        src, dest = by_id.get(src_id), by_id.get(dest_id)
        if not src or not dest or src is dest:
            continue
        if src.get("maxpreps") and not dest.get("maxpreps"):
            dest["maxpreps"] = src["maxpreps"]
        src["maxpreps"] = None
    merged = {}
    dropped = 0
    for key, row in schedules.items():
        dest = canonical_school_id(row.get("school_id") or key)
        dest = canonical_school_id(dest)
        row = dict(row)
        row["school_id"] = dest
        for g in row.get("games") or []:
            opp = dict(g.get("opponent") or {})
            sid = canonical_school_id(opp.get("site_id"))
            if sid:
                opp["site_id"] = sid
            g["opponent"] = opp
        if dest in merged:
            dropped += 1
            if len(row.get("games") or []) > len(merged[dest].get("games") or []):
                merged[dest] = row
            continue
        merged[dest] = row
    schedules.clear()
    schedules.update(merged)
    print(f"canonical collapse renamed {renamed} schools, schedules now {len(schedules)} (dropped {dropped} alias rows)")

    games_path = SITE / "games-top213.json"
    if not games_path.exists():
        return
    payload = json.loads(games_path.read_text())
    games = payload.get("games") or []
    n_side = 0
    for game in games:
        for side in ("home", "away"):
            rec = game.get(side) or {}
            dest = canonical_school_id(rec.get("site_id"))
            if not dest or dest == rec.get("site_id"):
                continue
            rec["site_id"] = dest
            canon = by_id.get(dest)
            if canon:
                rec["name"] = canon.get("name") or rec.get("name")
                if canon.get("city"):
                    rec["city"] = canon["city"]
                if canon.get("zip") and not rec.get("zip"):
                    rec["zip"] = canon["zip"]
                if canon.get("talent_score"):
                    rec["talent_score"] = canon["talent_score"]
            n_side += 1
        ht = float(game.get("home", {}).get("talent_score") or 0)
        at = float(game.get("away", {}).get("talent_score") or 0)
        if ht > 0 and at > 0:
            game["combined_talent"] = round(ht + at, 2)
            game["two_sided_talent"] = round((ht * at) ** 0.5, 2)
    payload["games"] = games
    raw = json.dumps(payload)
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "games-top213.json").write_text(raw)
    print(f"canonical collapse remapped {n_side} game sides")


def opp_norm_name(name: str) -> str:
    """Strip parentheticals and 'School of Sport Sciences'. Do not strip
    'Performance Academy' — The St. James Performance Academy is not The St. James.
    """
    n = name or ""
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\bschool of sport sciences\b", " ", n, flags=re.I)
    return norm_name(n)


def opponent_indexes(schools: list[dict]) -> tuple[dict, dict]:
    by_mp: dict[str, dict] = {}
    by_st_nn: dict[tuple[str, str], list[dict]] = {}
    for s in schools:
        if s["id"] in CANONICAL_SCHOOL_IDS:
            continue
        mp = (s.get("maxpreps") or {}).get("schoolId")
        if mp:
            by_mp[mp.lower()] = s
        nn = opp_norm_name(s.get("name") or "")
        st = (s.get("state") or "").upper()
        if nn:
            by_st_nn.setdefault((st, nn), []).append(s)
    return by_mp, by_st_nn


def match_opponent(by_mp: dict, by_st_nn: dict, opp: dict) -> dict | None:
    """Exact MaxPreps id or unique name+state after suffix strip. No prefix / NFL guesses."""
    mp_id = (opp.get("maxpreps_id") or "").lower()
    if mp_id and mp_id in by_mp:
        return by_mp[mp_id]
    nn = opp_norm_name(opp.get("name") or "")
    st = (opp.get("state") or "").upper()
    if not nn:
        return None
    hits = by_st_nn.get((st, nn)) or []
    if len(hits) == 1:
        return hits[0]
    return None


def sos_label(value: float, p25: float, p75: float) -> str:
    if value >= p75:
        return "tough"
    if value <= p25:
        return "light"
    return "average"


def apply_strength(
    schools: list[dict],
    joined_on3: dict[str, dict],
    on3_teams: list[dict],
    joined_mp: dict[str, int] | None = None,
    joined_dctf: dict[str, int] | None = None,
) -> None:
    tnorm = talent_norm_map(schools)
    ratings = [float(t["rating"]) for t in on3_teams if t.get("rating") is not None]
    rmin = min(ratings) if ratings else 0.0
    rmax = max(ratings) if ratings else 100.0
    max_t = max(
        (float(s["talent_score"]) for s in schools if s.get("talent_score") is not None),
        default=0.0,
    )
    max_name = next(
        (s["name"] for s in schools if s.get("talent_score") is not None and float(s["talent_score"]) == max_t),
        None,
    )
    joined_mp = joined_mp or {}
    joined_dctf = joined_dctf or {}
    for s in schools:
        sid = s["id"]
        tn = tnorm.get(sid)
        on3 = joined_on3.get(sid)
        on3n = None
        if on3 and on3.get("rating") is not None:
            on3n = on3_rating_norm(on3["rating"], rmin, rmax)
        mp_rank = joined_mp.get(sid)
        mpn = maxpreps_rank_norm(mp_rank) if mp_rank is not None else None
        ranking_norm = mean_present([on3n, mpn])
        blended = mean_present([tn, ranking_norm])
        dctf_rank = joined_dctf.get(sid)
        bonus = 0.0
        if dctf_rank is not None and (s.get("state") or "").upper() == "TX":
            bonus = dctf_bonus(dctf_rank)
        st = blended
        if st is not None:
            st = round(max(0.0, min(100.0, st + bonus)), 2)
        s["team_strength"] = st
        if on3:
            s["on3"] = {
                "rank": on3["rank"],
                "rating": round(on3["rating"], 3) if on3.get("rating") is not None else None,
                "org_key": on3.get("org_key"),
            }
        else:
            s.pop("on3", None)
        if mp_rank is not None:
            s["maxpreps_national"] = {"rank": int(mp_rank)}
        else:
            s.pop("maxpreps_national", None)
        if dctf_rank is not None and (s.get("state") or "").upper() == "TX":
            s["dctf"] = {"rank": int(dctf_rank), "board": "6A"}
        else:
            s.pop("dctf", None)
        bd: dict = {
            "talent_score": round(float(s["talent_score"]), 2) if s.get("talent_score") is not None else None,
            "talent_max": round(max_t, 2) if max_t else None,
            "talent_max_name": max_name,
            "talent_norm": tn,
            "bonus": round(bonus, 2),
            "team_strength": st,
        }
        if on3n is not None and on3:
            bd["on3_rank"] = on3["rank"]
            bd["on3_rating"] = round(on3["rating"], 3) if on3.get("rating") is not None else None
            bd["on3_min"] = round(rmin, 3)
            bd["on3_max"] = round(rmax, 3)
            bd["on3_norm"] = on3n
        if mpn is not None:
            bd["maxpreps_rank"] = int(mp_rank)
            bd["maxpreps_norm"] = mpn
        if ranking_norm is not None:
            bd["ranking_norm"] = round(ranking_norm, 2)
        if blended is not None:
            bd["blended"] = round(blended, 2)
        if dctf_rank is not None and (s.get("state") or "").upper() == "TX":
            bd["dctf_rank"] = int(dctf_rank)
        s["strength_breakdown"] = {k: v for k, v in bd.items() if v is not None or k in ("bonus", "team_strength")}


def restamp_schedules(schools: list[dict], schedules: dict[str, dict]) -> None:
    by_mp, by_st_nn = opponent_indexes(schools)
    by_id = {s["id"]: s for s in schools}
    for sid, row in schedules.items():
        school = by_id.get(sid)
        if not school:
            continue
        row["team_strength"] = school.get("team_strength")
        row["season"] = SEASON
        row["as_of"] = "2026-08-25T21:22:57Z"
        kept = []
        for g in row.get("games") or []:
            opp = g.get("opponent") or {}
            if skip_opponent_name(opp.get("name")):
                continue
            hit = match_opponent(by_mp, by_st_nn, opp)
            if hit:
                opp["site_id"] = hit["id"]
                opp["team_strength"] = hit.get("team_strength")
            else:
                opp["site_id"] = None
                opp["team_strength"] = None
            g["opponent"] = opp
            g["toughness_icon"] = toughness_icon(school.get("team_strength"), opp.get("team_strength"))
            kept.append(g)
        row["games"] = kept
        known = [
            g["opponent"]["team_strength"]
            for g in row.get("games") or []
            if g.get("opponent") and g["opponent"].get("team_strength") is not None
        ]
        sos = round(sum(known) / len(known), 2) if known else None
        row["sos"] = sos
        row["sos_games"] = len(known)
        school["sos"] = sos
        school["sos_games"] = len(known)
        school["schedule_games"] = len(row.get("games") or [])
    sos_vals = sorted(
        s["sos"] for s in schools if s.get("sos") is not None and (s.get("sos_games") or 0) >= 2
    )
    p25 = sos_vals[len(sos_vals) // 4] if sos_vals else 0
    p75 = sos_vals[(3 * len(sos_vals)) // 4] if sos_vals else 100
    scheduled = set(schedules)
    for s in schools:
        if s["id"] not in scheduled:
            s["sos"] = None
            s["sos_games"] = None
            s["schedule_games"] = None
            s["sos_label"] = None
        elif s.get("sos") is None:
            s["sos_label"] = None
        else:
            s["sos_label"] = sos_label(s["sos"], p25, p75)


# MaxPreps schoolZipCode from the 26-27 schedule cache (published, not invented).
# These six are home venues in the two-sided week slate that had no zip on the board.
CACHE_PUBLISHED_ZIPS = {
    "ca-hesperia-oak-hills": ("92344", "7625 Cataba Rd"),
    "co-littleton-valor-christian": ("80126", None),
    "tx-rosharon-iowa-colony": ("77583", None),
    "nc-pfafftown-reagan": ("27040", None),
    "tx-spring-grand-oaks": ("77386", "4800 Riley Fuzzel Road"),
    "ca-encinitas-la-costa-canyon": ("92009", "1 Maverick Wy"),
}


def fill_published_week_zips(schools: list[dict]) -> int:
    centroids = {}
    if (ROOT / "data/zip-centroids.json").exists():
        centroids = json.loads((ROOT / "data/zip-centroids.json").read_text())
    n = 0
    by_id = {s["id"]: s for s in schools}
    for sid, (zipc, addr) in CACHE_PUBLISHED_ZIPS.items():
        s = by_id.get(sid)
        if not s or s.get("zip"):
            continue
        s["zip"] = zipc
        s["zip5"] = zipc
        if addr and not s.get("address"):
            s["address"] = addr
        pair = centroids.get(zipc)
        if pair and s.get("lat") is None:
            s["lat"], s["lng"] = pair
        mp = dict(s.get("maxpreps") or {})
        mp["zip"] = zipc
        s["maxpreps"] = mp
        n += 1
    return n


def load_week_games_payload() -> dict:
    """Prefer the full two-sided week file (265) so zip fills can restore ranks 71–175."""
    path = SITE / "games-top213.json"
    payload = json.loads(path.read_text())
    if len(payload.get("games") or []) >= 250:
        return payload
    try:
        import subprocess

        raw = subprocess.check_output(
            ["git", "show", "HEAD:site-data/games-top213.json"],
            cwd=ROOT,
        )
        old = json.loads(raw)
        if len(old.get("games") or []) > len(payload.get("games") or []):
            return old
    except Exception:
        pass
    return payload


def stamp_venue_zip(game: dict, by_id: dict, centroids: dict) -> None:
    """Venue = contest site else home school. Copy a published home-school zip when missing."""
    venue = dict(game.get("venue") or {})
    if venue.get("zip"):
        game["venue"] = venue
        return
    home = game.get("home") or {}
    sch = by_id.get(home.get("site_id") or "")
    zipc = (sch or {}).get("zip") or home.get("zip")
    if not zipc:
        game["venue"] = venue
        return
    venue["zip"] = zipc
    if not venue.get("city"):
        venue["city"] = (sch or {}).get("city") or home.get("city")
    if not venue.get("state"):
        venue["state"] = (sch or {}).get("state") or home.get("state")
    if not venue.get("name"):
        venue["name"] = (sch or {}).get("name") or home.get("name")
    if venue.get("lat") is None:
        pair = centroids.get(zipc)
        if pair:
            venue["lat"], venue["lng"] = pair
        elif sch and sch.get("lat") is not None:
            venue["lat"], venue["lng"] = sch.get("lat"), sch.get("lng")
    venue.setdefault("source", "home_school")
    game["venue"] = venue


def slice_v1_games(schools: list[dict], limit: int = 196) -> int:
    payload = load_week_games_payload()
    games = payload.get("games") or []
    games = sorted(
        games,
        key=lambda g: (
            -(g.get("two_sided_talent") or 0),
            -(g.get("combined_talent") or 0),
            (g.get("home") or {}).get("name") or "",
            (g.get("away") or {}).get("name") or "",
        ),
    )
    by_id = {s["id"]: s for s in schools}
    centroids = {}
    if (ROOT / "data/zip-centroids.json").exists():
        centroids = json.loads((ROOT / "data/zip-centroids.json").read_text())
    picked = []
    for g in games:
        if (g.get("mapped_sides") or 0) != 2:
            continue
        if not (g.get("home") or {}).get("mapped") or not (g.get("away") or {}).get("mapped"):
            continue
        ht = (g.get("home") or {}).get("talent_score") or 0
        at = (g.get("away") or {}).get("talent_score") or 0
        if ht <= 0 or at <= 0:
            continue
        stamp_venue_zip(g, by_id, centroids)
        if not (g.get("venue") or {}).get("zip"):
            continue
        picked.append(g)
        if len(picked) == limit:
            break
    payload["games"] = picked
    payload["rank_by"] = "two_sided_talent"
    raw = json.dumps(payload)
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "games-top213.json").write_text(raw)
    return len(picked)


def write_board(
    schools: list[dict],
    schedules: dict[str, dict],
    n_on3: int,
    joined: int,
    n_mp: int = 0,
    mp_joined: int = 0,
    n_dctf: int = 0,
    dctf_joined: int = 0,
) -> None:
    payload_schools = json.dumps(schools)
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "schools.json").write_text(payload_schools)
        (dest / "schedules.json").write_text(json.dumps(schedules))
    summary_path = SITE / "schools.summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    n_games = len(json.loads((SITE / "games-top213.json").read_text()).get("games") or [])
    summary.update(
        {
            "on3_national": n_on3,
            "on3_joined": joined,
            "maxpreps_national": n_mp,
            "maxpreps_joined": mp_joined,
            "dctf_6a": n_dctf,
            "dctf_joined": dctf_joined,
            "schedules": len(schedules),
            "with_zip": sum(1 for s in schools if s.get("zip")),
            "v1_games": n_games,
            "v1_both_sides": n_games,
            "v1_partial": 0,
            "rank_by": "two_sided_talent",
            "team_strength_note": STRENGTH_NOTE,
            "note": (
                "Scout 247+Rivals+ESPN 2027/2028 frozen ingest. "
                f"v1 /games is games-top213.json ({n_games} two-sided games, 0 partial) "
                "for 2026-08-26..2026-08-29 ranked by geometric mean of home/away talent. "
                "Never load games.json."
            ),
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2))
    (IMPORT / "schools.summary.json").write_text(json.dumps(summary, indent=2))


def attach_schedule_row(
    school: dict,
    games: list[dict],
    page_url: str | None,
    by_mp: dict,
    by_st_nn: dict,
) -> dict:
    mp = school.get("maxpreps") or {}
    sched_url = mp.get("scheduleUrl") or page_url
    if page_url and not mp.get("scheduleUrl"):
        mp["scheduleUrl"] = page_url
        school["maxpreps"] = mp
    kept = []
    for g in games:
        opp = g.get("opponent") or {}
        if skip_opponent_name(opp.get("name")):
            continue
        hit = match_opponent(by_mp, by_st_nn, opp)
        if hit:
            opp["site_id"] = hit["id"]
            opp["team_strength"] = hit.get("team_strength")
        else:
            opp["site_id"] = None
            opp["team_strength"] = None
        g["opponent"] = opp
        g["toughness_icon"] = toughness_icon(school.get("team_strength"), opp.get("team_strength"))
        kept.append(g)
    known = [
        g["opponent"]["team_strength"]
        for g in kept
        if g.get("opponent") and g["opponent"].get("team_strength") is not None
    ]
    sos = round(sum(known) / len(known), 2) if known else None
    school["sos"] = sos
    school["sos_games"] = len(known)
    school["schedule_games"] = len(kept)
    return {
        "school_id": school["id"],
        "season": SEASON,
        "as_of": "2026-08-25T21:22:57Z",
        "team_strength": school.get("team_strength"),
        "schedule_url": sched_url,
        "sos": sos,
        "sos_games": len(known),
        "games": kept,
    }


def occupied_schedule_paths(schools: list[dict], schedules: dict[str, dict]) -> set[str]:
    out: set[str] = set()
    for row in schedules.values():
        u = (row.get("schedule_url") or "").strip()
        if u:
            out.add(urllib.parse.urlparse(u).path.rstrip("/").lower())
    for s in schools:
        mp = s.get("maxpreps") or {}
        for key in ("scheduleUrl", "footballUrl", "canonicalUrl"):
            u = (mp.get(key) or "").strip()
            if u.startswith("https://www.maxpreps.com/") and s["id"] in schedules:
                out.add(urllib.parse.urlparse(to_schedule_url(u)).path.rstrip("/").lower())
    return out


def fill_missing_schedules(schools: list[dict], schedules: dict[str, dict]) -> int:
    """Fetch MaxPreps 26-27 only for ranked schools that currently have no schedule.

    Uses stored scheduleUrl / canonicalUrl+football/schedule/ (yearless), plus the
    exact Matchup URLs. Does not guess slugs or search.
    """
    dropped = 0
    for sid in list(schedules):
        if sid in SKIP_SCHEDULE_IDS:
            schedules.pop(sid, None)
            dropped += 1
    if dropped:
        print(f"dropped {dropped} skip/alias schedule rows", flush=True)

    missing = [
        s
        for s in schools
        if s["id"] not in schedules
        and s["id"] not in SKIP_SCHEDULE_IDS
        and (
            s["id"] in MATCHUP_SCHEDULE_URLS
            or (s.get("maxpreps") or {}).get("scheduleUrl")
            or (s.get("maxpreps") or {}).get("canonicalUrl")
        )
    ]
    print(f"fill-missing {len(missing)} ranked schools without a schedule", flush=True)
    if not missing:
        return 0
    occupied = occupied_schedule_paths(schools, schedules)

    fetched: dict[str, tuple[list[dict], str | None]] = {}

    def run_fetch(batch: list[dict]) -> None:
        if not batch:
            return
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {
                pool.submit(fetch_schedule, s, search=False, occupied=occupied): s["id"]
                for s in batch
            }
            done = 0
            for fut in as_completed(futs):
                sid = futs[fut]
                done += 1
                try:
                    games, page_url = fut.result()
                except Exception as e:
                    print(f"  schedule fail {sid}: {e}", flush=True)
                    continue
                fetched[sid] = (games, page_url)
                if games and page_url:
                    occupied.add(urllib.parse.urlparse(page_url).path.rstrip("/").lower())
                if done % 10 == 0 or done == len(batch):
                    ok = sum(1 for g, _ in fetched.values() if g)
                    print(f"  {done}/{len(batch)} fetched {ok}", flush=True)

    run_fetch(missing)
    added = 0
    by_mp, by_st_nn = opponent_indexes(schools)
    for s in missing:
        games, page_url = fetched.get(s["id"], ([], None))
        if not games:
            continue
        schedules[s["id"]] = attach_schedule_row(s, games, page_url, by_mp, by_st_nn)
        added += 1
    print(f"added {added} schedules (now {len(schedules)})", flush=True)
    return added


def restamp_from_disk(*, fill_missing: bool = False) -> int:
    """Recompute 0–100 strength + SOS from on-disk schedules. Optionally fill gaps."""
    schools = json.loads((SITE / "schools.json").read_text())
    schedules = json.loads((SITE / "schedules.json").read_text())
    collapse_canonical_ids(schools, schedules)
    fill_published_week_zips(schools)
    if fill_missing:
        fill_missing_schedules(schools, schedules)
    on3_teams = fetch_on3()
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    joined_mp, mp_payload = join_site_rank_board(schools, RAW_MP)
    joined_dctf, _dctf_payload = join_site_rank_board(schools, RAW_DCTF)
    apply_strength(schools, joined, on3_teams, joined_mp, joined_dctf)
    restamp_schedules(schools, schedules)
    n_games = slice_v1_games(schools, 196)
    write_board(
        schools,
        schedules,
        n_on3,
        len(joined),
        n_mp=int(mp_payload.get("n") or MAXPREPS_N),
        mp_joined=len(joined_mp),
        n_dctf=DCTF_N,
        dctf_joined=len(joined_dctf),
    )
    img = next((s for s in schools if s["id"] == "fl-bradenton-img-academy"), {})
    print(
        "restamp IMG strength",
        img.get("team_strength"),
        "on3",
        img.get("on3"),
        "maxpreps",
        img.get("maxpreps_national"),
        "sos",
        img.get("sos"),
        "schedules",
        len(schedules),
        "on3_joined",
        len(joined),
        "maxpreps_joined",
        len(joined_mp),
        "dctf_joined",
        len(joined_dctf),
        "games",
        n_games,
    )
    return 0


def main() -> int:
    schools = json.loads((SITE / "schools.json").read_text())
    on3_teams = fetch_on3()
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    joined_mp, _mp = join_site_rank_board(schools, RAW_MP)
    joined_dctf, _dctf = join_site_rank_board(schools, RAW_DCTF)
    print(f"on3 joined {len(joined)} / {n_on3} onto {len(schools)} schools")
    print(f"maxpreps national joined {len(joined_mp)} dctf joined {len(joined_dctf)}")
    apply_strength(schools, joined, on3_teams, joined_mp, joined_dctf)
    by_mp, by_st_nn = opponent_indexes(schools)
    by_id = {s["id"]: s for s in schools}

    occupied = occupied_schedule_paths(schools, {})

    def run_fetch(batch: list[dict], search: bool) -> None:
        if not batch:
            return
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {
                pool.submit(fetch_schedule, s, search=search, occupied=occupied): s["id"]
                for s in batch
            }
            done = 0
            for fut in as_completed(futs):
                sid = futs[fut]
                done += 1
                try:
                    games, page_url = fut.result()
                except Exception as e:
                    print(f"  schedule fail {sid}: {e}", flush=True)
                    continue
                fetched[sid] = (games, page_url)
                if games and page_url:
                    occupied.add(urllib.parse.urlparse(page_url).path.rstrip("/").lower())
                if done % 50 == 0:
                    ok = sum(1 for g, _ in fetched.values() if g)
                    print(f"  {done}/{len(batch)} fetched {ok}", flush=True)

    schedules: dict[str, dict] = {}
    want = [
        s
        for s in schools
        if (s.get("maxpreps") or {}).get("schoolId") or (s.get("maxpreps") or {}).get("canonicalUrl")
    ]
    print(f"fetching schedules for {len(want)} schools", flush=True)
    fetched: dict[str, tuple[list[dict], str | None]] = {}
    run_fetch(want, search=False)
    miss = [s for s in want if not fetched.get(s["id"], ([], None))[0]]
    print(f"pass1 {sum(1 for g,_ in fetched.values() if g)} miss {len(miss)}", flush=True)
    run_fetch(miss, search=True)
    print(f"pass2 search done {sum(1 for g,_ in fetched.values() if g)}", flush=True)

    for s in want:
        games, page_url = fetched.get(s["id"], ([], None))
        if not games:
            continue
        schedules[s["id"]] = attach_schedule_row(s, games, page_url, by_mp, by_st_nn)

    sos_vals = sorted(s["sos"] for s in schools if s.get("sos") is not None and (s.get("sos_games") or 0) >= 2)
    p25 = sos_vals[len(sos_vals) // 4] if sos_vals else 0
    p75 = sos_vals[(3 * len(sos_vals)) // 4] if sos_vals else 100
    for s in schools:
        if s.get("sos") is None:
            s["sos_label"] = None
        else:
            s["sos_label"] = sos_label(s["sos"], p25, p75)

    payload_schools = json.dumps(schools)
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "schools.json").write_text(payload_schools)
    (SITE / "schedules.json").write_text(json.dumps(schedules))
    (IMPORT / "schedules.json").write_text(json.dumps(schedules))

    summary_path = SITE / "schools.summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    img = by_id.get("fl-bradenton-img-academy") or {}
    summary.update(
        {
            "on3_national": n_on3,
            "on3_joined": len(joined),
            "schedules": len(schedules),
            "with_zip": sum(1 for s in schools if s.get("zip")),
            "team_strength_note": STRENGTH_NOTE,
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2))
    (IMPORT / "schools.summary.json").write_text(json.dumps(summary, indent=2))

    print(
        "IMG strength",
        img.get("team_strength"),
        "on3",
        img.get("on3"),
        "sos",
        img.get("sos"),
        "sched",
        img.get("schedule_games"),
        "zip",
        img.get("zip"),
    )
    print(f"schedules {len(schedules)} on3_joined {len(joined)} missing zip {sum(1 for s in schools if not s.get('zip'))}")
    return 0


if __name__ == "__main__":
    if "--full-fetch" in sys.argv:
        raise SystemExit(main())
    fill = "--fill-missing" in sys.argv
    raise SystemExit(restamp_from_disk(fill_missing=fill))
