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
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
IMPORT = ROOT / "data/import"
RAW_ON3 = ROOT / "data/raw/on3" / "national-2026.json"
RAW_MP = ROOT / "data/raw/maxpreps" / "national-rankings.json"
RAW_DCTF = ROOT / "data/raw/dctf" / "6a-top25-week1.json"
CACHE = Path("/tmp/fridayradar-sched-cache")
# Live restamp must not replay Aug 25 HTML. --full-fetch sets this False.
USE_HTTP_CACHE = True
AS_OF = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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

RAW_HISTORY = ROOT / "data/raw/maxpreps" / "season-history.json"
SEASON_RE = re.compile(r"^\d\d-\d\d$")
RECORD_RE = re.compile(r"^(\d+)-(\d+)(?:-(\d+))?$")
# Recency weights, newest completed season first.
SEASON_DECAY = [1.0, 0.75, 0.55, 0.4, 0.3]
# Full-swing adjustment needs roughly two full seasons of games on file.
SUCCESS_FULL_CONFIDENCE_GAMES = 22
# Max points recent form may move team_strength, in either direction.
SUCCESS_ADJ_MAX = 8.0

STRENGTH_NOTE = (
    "team_strength is the mean of talent_norm (100 × talent / board max; IMG = 100 "
    "on talent only) and ranking_norm. ranking_norm is the mean of whichever of "
    "on3_norm (100 × (N+1−rank)/N on the 1000-team On3 national board) and "
    "maxpreps_norm (100 × (N+1−rank)/N on the 100-team MaxPreps national computer "
    "board) exist — both rank-based; On3's raw compositeScore only spans ~79–91 "
    "across all 1000 teams, so min–max on the raw score wildly overweighted tiny "
    "rating gaps near the top and is not used. Unranked boards are omitted, never "
    "0. Texas 6A DCTF Top 25 then adds 10 × (26−rank)/25 (#1 +10.00, #25 +0.40). "
    "Recent form then adjusts by up to ±8: a recency-weighted win rate over the "
    "last five MaxPreps seasons, centred on .500 and shrunk toward 0 when few "
    "games are on file. It is an adjustment rather than a blend term because raw "
    "win rate ignores schedule quality; schools with no history on file are not "
    "adjusted at all. The result is clamped 0–100. SOS is the mean of known "
    "opponents’ team_strength (unknown omitted; never raw On3 compositeScore)."
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
    if USE_HTTP_CACHE and cp.exists():
        try:
            rec = json.loads(cp.read_text())
        except json.JSONDecodeError:
            rec = {}
        if rec.get("status") == 200 and rec.get("body"):
            return 200, rec["body"]
    req = urllib.request.Request(url, headers=headers or UA)
    body, status = "", 0
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                status = resp.status
                break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if e.fp else ""
            status = e.code
            if status == 429:
                ra = e.headers.get("Retry-After")
                try:
                    wait = float(ra) if ra else min(32.0, 2 ** (attempt + 1))
                except ValueError:
                    wait = min(32.0, 2 ** (attempt + 1))
                time.sleep(wait)
                continue
            if status in (404, 403, 410):
                break
        except Exception:
            body, status = "", 0
        time.sleep(0.35 * (attempt + 1))
    if status == 200 and body:
        cp.write_text(json.dumps({"status": 200, "body": body}))
    time.sleep(0.12 if (headers or {}) == HTML_UA else 0.03)
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


def fetch_on3(*, force: bool = False) -> list[dict]:
    if not force and RAW_ON3.exists():
        data = json.loads(RAW_ON3.read_text())
        if len(data.get("teams") or []) >= 900:
            print(f"on3 cache {len(data['teams'])} teams")
            return data["teams"]
    teams = []
    seen = set()
    for page in range(1, 41):
        q = urllib.parse.urlencode(
            {
                "sportKey": 1,
                "orgType": "HighSchool",
                "year": 2026,
                "page": page,
                "pageSize": 25,
            }
        )
        url = "https://api.on3.com/rdb/v1/organization-composite-rankings?" + q
        status, body = http_get(url, timeout=25)
        if status != 200 or not body:
            print(f"on3 page {page} fail {status}")
            continue
        payload = json.loads(body)
        page_rows = payload.get("list") or []
        if not page_rows:
            print(f"on3 page {page} empty, stopping")
            break
        for row in page_rows:
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
        if len(teams) >= 1000:
            break
    RAW_ON3.parent.mkdir(parents=True, exist_ok=True)
    RAW_ON3.write_text(
        json.dumps({"year": 2026, "source": "on3_composite_national", "count": len(teams), "teams": teams})
    )
    print(f"wrote {RAW_ON3} {len(teams)}")
    return teams


def norm_city(city: str) -> str:
    n = (city or "").lower().replace("saint ", "st ").replace("st. ", "st ")
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def on3_norm_name(name: str) -> str:
    """St./Saint, C.E./CE, High School/HS — never a unique identity by itself."""
    n = norm_name(name)
    n = n.replace("saint ", "st ")
    n = re.sub(r"\bc e\b", "ce", n)
    if n == "king panthers":
        n = "ce king"
    return n


# City pairs that are the same program on On3 vs FridayRadar. Name must still match.
ON3_CITY_ALIASES: dict[tuple[str, str], set[str]] = {
    ("GA", "milton"): {"alpharetta", "milton"},
    ("GA", "alpharetta"): {"alpharetta", "milton"},
    ("GA", "norman park"): {"moultrie", "norman park"},
    ("GA", "moultrie"): {"moultrie", "norman park"},
    ("MI", "west bloomfield"): {"orchard lake", "west bloomfield"},
    ("MI", "orchard lake"): {"orchard lake", "west bloomfield"},
}


def cities_compatible(team_city: str, school_city: str, state: str) -> bool:
    tc, sc = norm_city(team_city), norm_city(school_city)
    if not tc or not sc:
        return False
    if tc == sc or tc in sc or sc in tc:
        return True
    allowed = ON3_CITY_ALIASES.get(((state or "").upper(), tc), set())
    return sc in allowed


def names_compatible(team_name: str, school_name: str) -> bool:
    tn = set(on3_norm_name(team_name).split())
    sn = set(on3_norm_name(school_name).split())
    if not tn or not sn:
        return False
    if tn == sn:
        return True
    shorter, longer = (tn, sn) if len(tn) <= len(sn) else (sn, tn)
    # One-token subset is too loose (King ≠ every King). Need 2+ shared tokens.
    if len(shorter) >= 2 and shorter <= longer:
        return True
    return False


def _tokens(name: str) -> set[str]:
    return {t for t in on3_norm_name(name).split() if t}


def _accept_on3_school(team: dict, school: dict) -> bool:
    """Name + city + ST. Ambiguous or empty names are not joined.

    Gardena Serra must not inherit San Mateo Serra's On3 rank: same name, different city.
    """
    st_t = (team.get("state") or "").upper()
    st_s = (school.get("state") or "").upper()
    if not st_t or st_t != st_s:
        return False
    school_name = school.get("name") or school.get("name_normalized") or ""
    if not names_compatible(team.get("name") or "", school_name) and not names_compatible(
        team.get("full_name") or "", school.get("name") or ""
    ):
        return False
    if not cities_compatible(team.get("city") or "", school.get("city") or "", st_t):
        return False
    return True


# join_on3 writes school ids skipped because several FR rows matched one On3 team.
ON3_AMBIGUOUS_IDS: set[str] = set()


def join_on3(schools: list[dict], teams: list[dict]) -> dict[str, dict]:
    """Org_key first (only when city+ST still line up), then conservative name+city+ST."""
    ON3_AMBIGUOUS_IDS.clear()
    by_org: dict = {}
    for t in teams:
        ok = t.get("org_key")
        if ok is not None:
            by_org[ok] = t
    matched: dict[str, dict] = {}
    used_org: set = set()
    used_school: set[str] = set()

    def take(school: dict, team: dict) -> None:
        prev = matched.get(school["id"])
        if prev and prev["rank"] < team["rank"]:
            return
        matched[school["id"]] = team
        used_school.add(school["id"])
        if team.get("org_key") is not None:
            used_org.add(team["org_key"])

    # 1) Stored On3 org_key, trusted only when the live team is still this campus.
    #    Name can differ (On3 'Centennial' vs 'Corona Centennial'); city+ST cannot
    #    (Gardena Serra must not keep San Mateo Serra's org_key).
    for s in schools:
        ok = (s.get("on3") or {}).get("org_key")
        if ok is None:
            continue
        team = by_org.get(ok)
        if not team:
            continue
        st_t = (team.get("state") or "").upper()
        st_s = (s.get("state") or "").upper()
        if st_t and st_t == st_s and cities_compatible(team.get("city") or "", s.get("city") or "", st_t):
            take(s, team)

    # 2) Conservative name + city + ST. Skip when several schools or several teams hit.
    unmatched_teams = [t for t in teams if t.get("org_key") not in used_org]
    unmatched_schools = [s for s in schools if s["id"] not in used_school]
    for t in unmatched_teams:
        hits = [s for s in unmatched_schools if _accept_on3_school(t, s)]
        if len(hits) > 1:
            for s in hits:
                ON3_AMBIGUOUS_IDS.add(s["id"])
            continue
        if len(hits) != 1:
            continue
        school = hits[0]
        reverse = [
            other
            for other in unmatched_teams
            if other is not t and _accept_on3_school(other, school)
        ]
        if reverse:
            ON3_AMBIGUOUS_IDS.add(school["id"])
            continue
        take(school, t)
        unmatched_schools = [s for s in unmatched_schools if s["id"] not in used_school]

    print(
        f"on3 join {len(matched)} schools, skipped ambiguous {len(ON3_AMBIGUOUS_IDS)}",
        flush=True,
    )
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


def on3_rank_norm(rank: int, n: int) -> float:
    """Rank 1 = 100, rank N = ~0. Mirrors maxpreps_rank_norm.

    On3's raw compositeScore only spans ~79–91 across the full 1000-team
    board, so min–max normalizing the raw rating (the old approach) turned a
    handful of raw points near the top into a 0–100-scale swing — e.g. rank
    #8 vs #32 (both top 3.2% nationally) came out ~98 vs ~59. Rank position
    is the honest signal On3 itself is publishing; use it directly, the same
    way the MaxPreps board term already does.

    This is the On3 *term* of ranking_norm, never the SOS value itself.
    """
    return round(max(0.0, min(100.0, 100.0 * (n + 1 - int(rank)) / n)), 2)


def maxpreps_rank_norm(rank: int, n: int = MAXPREPS_N) -> float:
    """Rank 1 = 100, rank N = 1. Unranked must not call this (never 0)."""
    return round(100.0 * (n + 1 - int(rank)) / n, 2)


def dctf_bonus(rank: int, n: int = DCTF_N, cap: float = DCTF_BONUS_MAX) -> float:
    """#1 +10.00, #25 +0.40. Unranked Texas get 0 extra, not a penalty."""
    return round(cap * (n + 1 - int(rank)) / n, 2)


def load_season_history() -> dict[str, dict[str, str]]:
    """school_id -> {season: 'W-L' | 'W-L-T'} from fetch-season-history.py."""
    if not RAW_HISTORY.exists():
        return {}
    try:
        return json.loads(RAW_HISTORY.read_text()).get("records", {}) or {}
    except Exception:
        return {}


def recent_success(history: dict[str, str] | None) -> dict | None:
    """Recency-weighted win rate over recent seasons, as a bounded adjustment.

    Deliberately an *adjustment*, not a co-equal blend term. Raw win rate is
    not comparable across programs: a 12-0 record against weak opposition is
    not evidence of an elite roster, and letting win% carry a third of the
    score would vault small unbeaten schools past loaded ones. On3 and
    MaxPreps national ranks already fold in results *with* strength-of-
    schedule adjustment, and they stay the primary results signal; this term
    exists mainly for the ~1,000 schools on neither board, where it is the
    only on-field signal available.

    Each game is weighted by how recent its season is, so a 14-1 season
    outweighs a 1-0 in-progress one without special-casing. `confidence`
    shrinks the adjustment toward 0 when few games are on file, so one
    partial season never swings the full range. Missing history returns
    None and the term is omitted — never treated as 0-0 or as a penalty.
    """
    if not history:
        return None
    seasons = sorted(
        (s for s in history if SEASON_RE.match(s)),
        key=lambda s: int(s.split("-")[0]),
        reverse=True,
    )
    num = 0.0  # weighted wins
    den = 0.0  # weighted games
    games_total = 0
    used: list[str] = []
    for i, season in enumerate(seasons):
        m = RECORD_RE.match((history.get(season) or "").strip())
        if not m:
            continue
        wins, losses = int(m.group(1)), int(m.group(2))
        ties = int(m.group(3)) if m.group(3) else 0
        games = wins + losses + ties
        if games <= 0:
            continue  # 0-0 = season not started; not a loss
        w = SEASON_DECAY[i] if i < len(SEASON_DECAY) else SEASON_DECAY[-1]
        num += w * (wins + 0.5 * ties)
        den += w * games
        games_total += games
        used.append(season)
    if den <= 0:
        return None
    pct = num / den
    confidence = min(1.0, games_total / SUCCESS_FULL_CONFIDENCE_GAMES)
    adj = SUCCESS_ADJ_MAX * (2.0 * pct - 1.0) * confidence
    return {
        "win_pct": round(pct, 4),
        "games": games_total,
        "seasons": used,
        "confidence": round(confidence, 3),
        "adj": round(adj, 2),
    }


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
    "md-baltimore-saint-frances-academy": "md-baltimore-st-frances-academy",
    "va-springfield-saint-james": "va-springfield-the-st-james",
    "nj-jersey-city-saint-peters-prep": "nj-jersey-city-st-peter-s-prep",
    "il-east-saint-louis-east-saint-louis": "il-east-st-louis-east-st-louis",
    "ca-bellflower-saint-john-bosco": "ca-bellflower-st-john-bosco",
    "fl-jacksonville-bolles-school": "fl-jacksonville-the-bolles-school",
    "dc-washington-saint-johns-college": "dc-washington-st-john-s-college",
    "nj-montvale-saint-joseph-regional": "nj-montvale-st-joseph-regional",
    "pa-haverford-haverford-school": "pa-haverford-the-haverford-school",
    "fl-miami-carol-city": "fl-opa-locka-miami-carol-city",
    "oh-warren-warren-g-harding": "oh-warren-harding",
    "al-hoover-spain-park": "al-birmingham-spain-park",
    "al-birmingham-a-h-parker": "al-birmingham-parker",
    "nc-haw-river-southeast-alamance": "nc-graham-southeast-alamance",
    "tx-arlington-mansfield-timberview": "tx-mansfield-mansfield-timberview",
    "md-forestville-bishop-mcnamara": "md-district-heights-bishop-mcnamara",
    "ca-fresno-clovis-west": "ca-hanford-clovis-west",
    "tx-iowa-colony-iowa-colony": "tx-rosharon-iowa-colony",
    "tx-woodlands-woodlands-college-park": "tx-the-woodlands-college-park",
    "nj-lawrenceville-lawrenceville-school": "nj-lawrenceville-the-lawrenceville-school",
    "hi-kapaa-kapaa": "hi-kapa-a-kapa-a",
    "ny-melville-saint-anthonys": "ny-long-island-city-st-anthony-s",
    "az-glendale-sandra-day-oconnor": "az-glendale-sandra-day-o-connor",
    "ca-mountain-view-saint-francis": "ca-mountain-view-st-francis",
    "il-chicago-saint-rita-of-cascia": "il-chicago-st-rita-of-cascia",
    "la-covington-saint-pauls": "la-covington-st-paul-s",
    "la-new-orleans-john-curtis": "la-river-ridge-john-curtis",
    "ma-danvers-saint-johns-prep": "ma-danvers-st-john-s-prep",
    "mo-saint-louis-christian-brothers-college": "mo-st-louis-christian-brothers-college",
    "mo-saint-louis-de-smet-jesuit": "mo-st-louis-de-smet-jesuit",
    "al-fairhope-saint-michael-catholic": "al-fairhope-st-michael-catholic",
    "al-odenville-saint-clair-county": "al-odenville-st-clair-county",
    "al-prichard-vigor": "al-mobile-vigor",
    "tx-colony-colony": "tx-the-colony-the-colony",
    "tx-waco-robinson": "tx-robinson-robinson",
    "tx-woodlands-college-park": "tx-the-woodlands-college-park",
    "tx-arlington-martin": "tx-arlington-arlington-martin",
    "tx-houston-cypress-falls": "tx-houston-cy-falls",
    "ca-bellflower-crean-lutheran": "ca-irvine-crean-lutheran",
    "ca-downey-saint-pius-x-saint-matthias-academy": "ca-downey-st-pius-x-st-matthias-academy",
    "ca-inglewood-inglewood": "ca-los-angeles-inglewood",
    "ca-long-beach-long-beach-polytechnic": "ca-long-beach-long-beach-poly",
    "ca-oneals-minarets": "ca-o-neals-minarets",
    "ca-san-diego-saint-augustine": "ca-san-diego-st-augustine",
    "ca-santa-monica-saint-monica-catholic": "ca-santa-monica-st-monica-catholic",
    "ca-stockton-saint-marys": "ca-stockton-st-mary-s",
    "ca-ventura-saint-bonaventure": "ca-ventura-st-bonaventure",
    "ct-oakdale-saint-thomas-more": "ct-oakdale-st-thomas-more",
    "ct-trumbull-saint-joseph": "ct-trumbull-st-joseph",
    "fl-boca-raton-saint-andrews": "fl-boca-raton-saint-andrew-s",
    "fl-fort-pierce-vero-beach": "fl-vero-beach-vero-beach",
    "fl-lake-minneola-first-academy": "fl-orlando-the-first-academy",
    "fl-miami-columbus": "fl-miami-miami-columbus",
    "fl-miami-miami-carol-city": "fl-opa-locka-miami-carol-city",
    "fl-miramar-saint-thomas-aquinas": "fl-fort-lauderdale-saint-thomas-aquinas",
    "fl-orlando-first-academy": "fl-orlando-the-first-academy",
    "fl-pembroke-pines-chaminade-madonna": "fl-hollywood-chaminade-madonna",
    "fl-saint-petersburg-gibbs": "fl-st-petersburg-gibbs",
    "fl-saint-petersburg-northside-christian": "fl-st-petersburg-northside-christian",
    "fl-tampa-armwood": "fl-seffner-armwood",
    "fl-villages-villages-charter": "fl-the-villages-the-villages-charter",
    "ga-atlanta-creekside": "ga-fairburn-creekside",
    "ga-atlanta-douglas-county": "ga-douglasville-douglas-county",
    "ga-college-park-woodward-academy": "ga-atlanta-woodward-academy",
    "ga-roswell-blessed-trinity": "ga-roswell-blessed-trinity-catholic",
    "ga-warner-robins-houston-county": "ga-macon-houston-county",
    "hi-honolulu-saint-louis": "hi-honolulu-st-louis-school",
    "hi-honolulu-saint-louis-school": "hi-honolulu-st-louis-school",
    "il-chicago-saint-patrick": "il-chicago-st-patrick",
    "il-evergreen-park-saint-laurence": "il-evergreen-park-st-laurence",
    "il-lombard-montini-catholic": "il-arlington-heights-montini-catholic",
    "il-oak-lawn-brother-rice": "il-chicago-brother-rice",
    "il-saint-joseph-saint-joseph-ogden": "il-st-joseph-st-joseph-ogden",
    "la-cecilia-cecilia": "la-carencro-cecilia",
    "la-new-orleans-saint-augustine": "la-new-orleans-st-augustine",
    "la-saint-francisville-west-feliciana": "la-st-francisville-west-feliciana",
    "ma-reading-tabor-academy": "ma-marion-tabor-academy",
    "md-baltimore-saint-pauls-school": "md-baltimore-st-paul-s-school",
    "mo-kansas-city-saint-pius-x": "mo-kansas-city-st-pius-x",
    "mo-lees-summit-lees-summit-north": "mo-lee-s-summit-lee-s-summit-north",
    "mo-lees-summit-lees-summit-west": "mo-lee-s-summit-lee-s-summit-west",
    "mo-saint-louis-cardinal-ritter-college-prep": "mo-st-louis-cardinal-ritter-college-prep",
    "mo-saint-louis-ladue-horton-watkins": "mo-st-louis-ladue-horton-watkins",
    "mo-saint-louis-lindbergh": "mo-st-louis-lindbergh",
    "mo-saint-louis-ritenour": "mo-st-louis-ritenour",
    "ms-diberville-diberville": "ms-d-iberville-d-iberville",
    "ms-tigers-winona-winona": "ms-winona-winona",
    "nc-saint-pauls-saint-pauls": "nc-st-pauls-st-pauls",
    "ne-hastings-saint-cecilia": "ne-hastings-st-cecilia",
    "nj-richland-saint-augustine-prep": "nj-richland-st-augustine-prep",
    "ny-hamburg-saint-francis": "ny-hamburg-st-francis",
    "ny-long-island-city-saint-anthonys": "ny-long-island-city-st-anthony-s",
    "oh-cincinnati-saint-xavier": "oh-cincinnati-st-xavier",
    "oh-cleveland-saint-ignatius": "oh-cleveland-st-ignatius",
    "oh-cleveland-villa-angela-saint-joseph": "oh-cleveland-villa-angela-st-joseph",
    "oh-columbus-saint-francis-de-sales": "oh-columbus-st-francis-de-sales",
    "oh-lakewood-saint-edward": "oh-lakewood-st-edward",
    "oh-massillon-washington": "oh-massillon-massillon-washington",
    "oh-saint-clairsville-saint-clairsville": "oh-st-clairsville-st-clairsville",
    "pa-philadelphia-la-salle-college": "pa-wyndmoor-la-salle-college",
    "pa-philadelphia-saint-josephs-prep": "pa-philadelphia-st-joseph-s-prep",
    "pa-springfield-cardinal-ohara": "pa-springfield-cardinal-o-hara",
    "pa-upper-saint-clair-upper-saint-clair": "pa-upper-st-clair-upper-st-clair",
    "sc-saint-stephen-timberland": "sc-st-stephen-timberland",
    "va-suffolk-kings-fork": "va-suffolk-king-s-fork",
    "wa-seattle-odea": "wa-seattle-o-dea",
    # Do not alias The Woodlands HS onto College Park — different campuses.
    # Do not alias ca-san-mateo-junipero-serra onto Gardena Serra.
    # Do not alias ga-conyers-heritage onto ga-ringgold-heritage — different cities.
    # Do not alias ca-stockton-edison onto Huntington Beach Edison.
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
    live_id = page_maxpreps_school_id(pp, page_url or url)
    if live_id:
        school["_page_maxpreps_id"] = live_id
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
    n_on3 = len(on3_teams) or 1
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
    history = load_season_history()
    for s in schools:
        sid = s["id"]
        tn = tnorm.get(sid)
        on3 = joined_on3.get(sid)
        on3n = None
        if on3 and on3.get("rank") is not None:
            on3n = on3_rank_norm(on3["rank"], n_on3)
        mp_rank = joined_mp.get(sid)
        mpn = maxpreps_rank_norm(mp_rank) if mp_rank is not None else None
        ranking_norm = mean_present([on3n, mpn])
        blended = mean_present([tn, ranking_norm])
        dctf_rank = joined_dctf.get(sid)
        bonus = 0.0
        if dctf_rank is not None and (s.get("state") or "").upper() == "TX":
            bonus = dctf_bonus(dctf_rank)
        success = recent_success(history.get(sid))
        success_adj = success["adj"] if success else 0.0
        st = blended
        if st is not None:
            st = round(max(0.0, min(100.0, st + bonus + success_adj)), 2)
        s["team_strength"] = st
        if on3:
            s["on3"] = {
                "rank": on3["rank"],
                "rating": round(on3["rating"], 3) if on3.get("rating") is not None else None,
                "org_key": on3.get("org_key"),
                # On3 team URLs are /high-school/{slug}-{org_key}/ — stored, never guessed.
                "slug": on3.get("slug"),
            }
        else:
            stored = s.get("on3") or {}
            if stored.get("org_key") is not None and stored.get("slug"):
                rating = stored.get("rating")
                s["on3"] = {
                    "rank": stored.get("rank"),
                    "rating": round(rating, 3) if isinstance(rating, (int, float)) else None,
                    "org_key": stored.get("org_key"),
                    "slug": stored.get("slug"),
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
            bd["on3_n"] = n_on3
            bd["on3_norm"] = on3n
        if mpn is not None:
            bd["maxpreps_rank"] = int(mp_rank)
            bd["maxpreps_norm"] = mpn
        if ranking_norm is not None:
            bd["ranking_norm"] = round(ranking_norm, 2)
        if blended is not None:
            bd["blended"] = round(blended, 2)
        if success is not None:
            bd["success_win_pct"] = success["win_pct"]
            bd["success_games"] = success["games"]
            bd["success_seasons"] = len(success["seasons"])
            bd["success_confidence"] = success["confidence"]
            bd["success_adj"] = success["adj"]
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
        row["as_of"] = AS_OF
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
        if not row.get("schedule_source"):
            url = (row.get("schedule_url") or "")
            row["schedule_source"] = "on3" if "on3.com" in url else "maxpreps"
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


def load_schedules() -> dict[str, dict]:
    raw = json.loads((SITE / "schedules.json").read_text())
    if (
        isinstance(raw, dict)
        and isinstance(raw.get("schools"), dict)
        and ("as_of" in raw or "season" in raw)
    ):
        return raw["schools"]
    return raw


HUDL_ORG_RE = re.compile(r"/organization/(\d+)/")


def load_hudl_team_ids() -> dict[str, str]:
    """school_id → Hudl organization id from hudl-teams.tsv. Never invents URLs."""
    path = SITE / "hudl-teams.tsv"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    lines = path.read_text().splitlines()
    if not lines:
        return out
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sid, url = parts[0].strip(), parts[1].strip()
        if not sid or not url.startswith("https://fan.hudl.com/"):
            continue
        cid = canonical_school_id(sid)
        m = HUDL_ORG_RE.search(url)
        if not m:
            continue
        out[cid] = m.group(1)
        if cid != sid:
            out[sid] = m.group(1)
    return out


def write_crosswalk(schools: list[dict], joined_on3: dict[str, dict]) -> None:
    """One record per FridayRadar school. IDs only when actually held — no invented GUIDs."""
    hudl_ids = load_hudl_team_ids()
    school_ids = {s["id"] for s in schools}
    rows: dict[str, dict] = {}
    for s in schools:
        sid = s["id"]
        names: list[str] = []
        for n in (
            s.get("name"),
            *(s.get("aliases") or []),
            (s.get("maxpreps") or {}).get("formattedName"),
        ):
            if n and n not in names:
                names.append(n)
        mp_id = (s.get("maxpreps") or {}).get("schoolId") or None
        on3 = joined_on3.get(sid) or s.get("on3") or {}
        on3_key = on3.get("org_key")
        hs_247 = (s.get("ids_247") or {}).get("high_school_id") or None
        hudl = hudl_ids.get(sid) if sid in school_ids else None
        sources = {
            "fridayradar": sid,
            "maxpreps": mp_id,
            "on3": on3_key,
            "hudl": hudl,
            "247": hs_247,
            "espn": None,
        }
        n_ext = sum(1 for k, v in sources.items() if k != "fridayradar" and v is not None)
        if sid in ON3_AMBIGUOUS_IDS and sid not in joined_on3:
            status = "ambiguous"
        elif n_ext >= 2:
            status = "linked"
        elif n_ext == 1:
            status = "partial"
        else:
            status = "unmatched"
        rows[sid] = {
            "names": names,
            "city": s.get("city") or "",
            "state": (s.get("state") or "").upper(),
            "zip": s.get("zip") or s.get("zip5") or None,
            "sources": sources,
            "match_status": status,
        }
    payload = {
        "as_of": AS_OF,
        "count": len(rows),
        "schools": rows,
    }
    raw = json.dumps(payload)
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "schools-crosswalk.json").write_text(raw)
    linked = sum(1 for r in rows.values() if r["match_status"] == "linked")
    partial = sum(1 for r in rows.values() if r["match_status"] == "partial")
    unmatched = sum(1 for r in rows.values() if r["match_status"] == "unmatched")
    amb = sum(1 for r in rows.values() if r["match_status"] == "ambiguous")
    print(
        f"crosswalk {len(rows)} linked={linked} partial={partial} unmatched={unmatched} ambiguous={amb}",
        flush=True,
    )


def write_board(
    schools: list[dict],
    schedules: dict[str, dict],
    n_on3: int,
    joined: int,
    n_mp: int = 0,
    mp_joined: int = 0,
    n_dctf: int = 0,
    dctf_joined: int = 0,
    joined_on3: dict[str, dict] | None = None,
) -> None:
    for s in schools:
        s.pop("_page_maxpreps_id", None)
    payload_schools = json.dumps(schools)
    wrapped = {"as_of": AS_OF, "season": SEASON, "schools": schedules}
    payload_sched = json.dumps(wrapped)
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "schools.json").write_text(payload_schools)
        (dest / "schedules.json").write_text(payload_sched)
    summary_path = SITE / "schools.summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    n_games = len(json.loads((SITE / "games-top213.json").read_text()).get("games") or [])
    n_played = 0
    for row in schedules.values():
        for g in row.get("games") or []:
            if g.get("result") in ("W", "L", "T") or g.get("score") is not None:
                n_played += 1
    summary.update(
        {
            "as_of": AS_OF,
            "season": SEASON,
            "on3_national": n_on3,
            "on3_joined": joined,
            "maxpreps_national": n_mp,
            "maxpreps_joined": mp_joined,
            "dctf_6a": n_dctf,
            "dctf_joined": dctf_joined,
            "schedules": len(schedules),
            "schedule_games": sum(len(r.get("games") or []) for r in schedules.values()),
            "schedule_played": n_played,
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
                "Never load games.json. "
                f"MaxPreps 26-27 schedules restamped {AS_OF}."
            ),
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2))
    (IMPORT / "schools.summary.json").write_text(json.dumps(summary, indent=2))
    write_crosswalk(schools, joined_on3 or {})


def attach_schedule_row(
    school: dict,
    games: list[dict],
    page_url: str | None,
    by_mp: dict,
    by_st_nn: dict,
    *,
    source: str = "maxpreps",
) -> dict:
    mp = school.get("maxpreps") or {}
    sched_url = page_url or mp.get("scheduleUrl")
    if source == "maxpreps" and sched_url and str(sched_url).startswith("https://www.maxpreps.com/"):
        sched_url = to_schedule_url(sched_url)
        mp["scheduleUrl"] = sched_url
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
        "as_of": AS_OF,
        "team_strength": school.get("team_strength"),
        "schedule_url": sched_url,
        "schedule_source": source,
        "sos": sos,
        "sos_games": len(known),
        "games": kept,
    }


GAP_TSV = SITE / "maxpreps-gap-resolutions.tsv"
MISSING_TSV = SITE / "maxpreps-missing-schedules.tsv"
ON3_SCHED_HEADERS = {
    "User-Agent": UA["User-Agent"],
    "Accept": "application/json",
    "Origin": "https://www.on3.com",
    "Referer": "https://www.on3.com/",
}


def _parse_maxpreps_gap_tsv(path: Path) -> list[dict]:
    """Verified MaxPreps schedule URLs only. Never invent a path.

    Accepts the 5-column gap-resolutions header (school_id, method) and the
    3-column missing-schedules header (fr_school_id, maxpreps_url, games_count).
    """
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split("\t")]
    try:
        i_id = header.index("fr_school_id")
        i_url = header.index("maxpreps_url")
    except ValueError:
        print(f"gap TSV bad header {path.name} {header[:5]}", flush=True)
        return []
    i_sid = header.index("school_id") if "school_id" in header else None
    i_method = header.index("method") if "method" in header else None
    rows = []
    seen = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if max(i_id, i_url) >= len(cols):
            continue
        sid = (cols[i_id] or "").strip()
        url = (cols[i_url] or "").strip()
        mp_id = (cols[i_sid] or "").strip() if i_sid is not None and i_sid < len(cols) else ""
        method = (cols[i_method] or "").strip() if i_method is not None and i_method < len(cols) else ""
        if not sid or not url:
            continue
        if not url.startswith("https://www.maxpreps.com/") or "/football/schedule" not in url:
            print(f"  skip non-maxpreps URL {sid}", flush=True)
            continue
        url = to_schedule_url(url)
        key = (canonical_school_id(sid), url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "fr_school_id": sid,
                "maxpreps_url": url,
                "school_id": mp_id,
                "method": method,
            }
        )
    return rows


def load_gap_resolutions() -> list[dict]:
    """Verified MaxPreps schedule URLs only. Never invent a path."""
    rows = []
    seen = set()
    seen_names: set[str] = set()
    for path in (
        GAP_TSV,
        MISSING_TSV,
        IMPORT / "maxpreps-gap-resolutions.tsv",
        IMPORT / "maxpreps-missing-schedules.tsv",
    ):
        if not path.exists() or path.name in seen_names:
            continue
        seen_names.add(path.name)
        for rec in _parse_maxpreps_gap_tsv(path):
            key = (canonical_school_id(rec["fr_school_id"]), rec["maxpreps_url"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(rec)
    return rows


def page_maxpreps_school_id(pp: dict, page_url: str | None) -> str | None:
    """MaxPreps UUID for the team on this schedule page. Never guessed."""
    team_root = _page_team_root(page_url)
    if not team_root:
        return None
    root = pp.get("pageProps") or pp
    for row in root.get("contests") or []:
        if not isinstance(row, list) or not row:
            continue
        teams = row[0] if isinstance(row[0], list) else []
        for t in teams:
            if not isinstance(t, list):
                continue
            parsed = parse_team(t)
            if not parsed:
                continue
            u = (parsed.get("url") or "").lower()
            if team_root in u and parsed.get("mp_id"):
                return parsed["mp_id"]
    return None


def fill_on3_from_crosswalk(schools: list[dict], on3_teams: list[dict]) -> int:
    """If school.on3 is null, copy org_key from the crosswalk and slug from the
    On3 national payload for that key. Never invent a slug.
    """
    cw_path = SITE / "schools-crosswalk.json"
    if not cw_path.exists():
        cw_path = IMPORT / "schools-crosswalk.json"
    cw = {}
    if cw_path.exists():
        cw = json.loads(cw_path.read_text()).get("schools") or {}
    by_org = {t.get("org_key"): t for t in on3_teams if t.get("org_key") is not None}
    n = 0
    for s in schools:
        stored = s.get("on3") or {}
        if stored.get("org_key") is not None and stored.get("slug"):
            continue
        sid = s["id"]
        org = stored.get("org_key")
        if org is None:
            org = ((cw.get(sid) or {}).get("sources") or {}).get("on3")
        if org is None:
            continue
        team = by_org.get(org)
        slug = stored.get("slug") or ((team or {}).get("slug") if team else None)
        if not slug:
            continue
        s["on3"] = {
            "org_key": org,
            "slug": slug,
            "rank": (team or {}).get("rank") if team else stored.get("rank"),
            "rating": (team or {}).get("rating") if team else stored.get("rating"),
        }
        n += 1
    print(f"on3 crosswalk-link fill {n} schools", flush=True)
    return n


def stamp_maxpreps_from_gap(school: dict, url: str, mp_id: str) -> None:
    """Write verified MaxPreps ids/URLs onto the school. Do not invent slugs."""
    mp = dict(school.get("maxpreps") or {})
    if mp_id:
        mp["schoolId"] = mp_id
    mp["scheduleUrl"] = url
    path = urllib.parse.urlparse(url).path.rstrip("/")
    path = re.sub(r"/football/schedule$", "", path)
    if path and not mp.get("canonicalUrl"):
        mp["canonicalUrl"] = "https://www.maxpreps.com" + path + "/"
    if path and not mp.get("footballUrl"):
        mp["footballUrl"] = "https://www.maxpreps.com" + path + "/football/"
    school["maxpreps"] = mp


def apply_maxpreps_gapfill(schools: list[dict], schedules: dict[str, dict]) -> int:
    """Fetch TSV MaxPreps URLs live. Existing MaxPreps stays unless this TSV row hits that school.

    Overwrites an On3 fallback for the same school. Skips TSV ids with no board row
    (never invent a school). Does not steal another school's MaxPreps UUID.
    """
    rows = load_gap_resolutions()
    by_id = {s["id"]: s for s in schools}
    uuid_owner: dict[str, str] = {}
    for s in schools:
        uid = ((s.get("maxpreps") or {}).get("schoolId") or "").lower()
        if uid:
            uuid_owner.setdefault(uid, s["id"])
    print(f"gapfill TSV {len(rows)} verified MaxPreps URLs", flush=True)
    if not rows:
        return 0
    priority = "tx-missouri-city-fort-bend-ridge-point"
    rows.sort(key=lambda r: 0 if canonical_school_id(r["fr_school_id"]) == priority else 1)
    by_mp, by_st_nn = opponent_indexes(schools)
    added = 0
    skipped = 0
    kept = 0
    work: list[tuple[dict, dict, str, str, str | None]] = []
    seen_sid: set[str] = set()
    for rec in rows:
        raw_id = rec["fr_school_id"]
        sid = canonical_school_id(raw_id)
        school = by_id.get(sid)
        if not school:
            print(f"  skip unknown school {raw_id}", flush=True)
            skipped += 1
            continue
        if sid in SKIP_SCHEDULE_IDS:
            print(f"  skip alias/skip-list {sid}", flush=True)
            skipped += 1
            continue
        if sid in seen_sid:
            continue
        seen_sid.add(sid)
        existing = schedules.get(sid)
        existing_src = (existing or {}).get("schedule_source") or (
            "maxpreps" if existing else None
        )
        if has_maxpreps_slate(existing):
            kept += 1
            continue
        mp_id = rec["school_id"]
        owner = uuid_owner.get(mp_id.lower()) if mp_id else None
        if owner and owner != sid:
            print(f"  omit uuid owned by {owner} not {sid}", flush=True)
            mp_id = ""
        url = rec["maxpreps_url"]
        work.append((school, rec, url, mp_id, existing_src))

    def attach_hit(school: dict, url: str, mp_id: str, hit, existing_src: str | None) -> bool:
        nonlocal added, skipped
        sid = school["id"]
        if not hit:
            print(f"  fetch miss {sid} {url}", flush=True)
            skipped += 1
            return False
        games, page_url = hit
        if not games:
            print(f"  empty contests {sid}", flush=True)
            skipped += 1
            return False
        live_id = school.pop("_page_maxpreps_id", None)
        if not mp_id and live_id:
            owner = uuid_owner.get(live_id.lower())
            if owner and owner != sid:
                print(f"  omit live uuid owned by {owner} not {sid}", flush=True)
            else:
                mp_id = live_id
                stamp_maxpreps_from_gap(school, page_url or url, mp_id)
        else:
            school.pop("_page_maxpreps_id", None)
        if mp_id:
            uuid_owner[mp_id.lower()] = sid
        schedules[sid] = attach_schedule_row(
            school, games, page_url or url, by_mp, by_st_nn, source="maxpreps"
        )
        added += 1
        print(f"  maxpreps {sid} {len(games)} games (was {existing_src})", flush=True)
        return True

    # Ridge Point first so the school page table can be verified before the rest.
    rest = []
    for item in work:
        school, rec, url, mp_id, existing_src = item
        stamp_maxpreps_from_gap(school, url, mp_id)
        if school["id"] == priority:
            attach_hit(school, url, mp_id, fetch_schedule_html(url, school, trust=True), existing_src)
        else:
            rest.append(item)

    def one(item: tuple[dict, dict, str, str, str | None]):
        school, rec, url, mp_id, existing_src = item
        return school["id"], fetch_schedule_html(url, school, trust=True)

    fetched: dict[str, tuple] = {}
    if rest:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(one, item): item[0]["id"] for item in rest}
            done = 0
            for fut in as_completed(futs):
                done += 1
                try:
                    sid, hit = fut.result()
                except Exception as e:
                    print(f"  fetch fail {futs[fut]}: {e}", flush=True)
                    continue
                fetched[sid] = hit
                if done % 25 == 0 or done == len(rest):
                    print(f"  fetched {done}/{len(rest)}", flush=True)
        by_work = {item[0]["id"]: item for item in rest}
        for sid, item in by_work.items():
            school, rec, url, mp_id, existing_src = item
            attach_hit(school, url, mp_id, fetched.get(sid), existing_src)
    print(
        f"gapfill attached {added} MaxPreps slates, kept {kept} existing, skipped {skipped}",
        flush=True,
    )
    return added


def _on3_org_name(org: dict | None) -> str:
    if not isinstance(org, dict):
        return ""
    return (org.get("name") or org.get("fullName") or "").strip()


def parse_on3_schedule(payload: dict, org_key) -> list[dict]:
    """Map On3 v2 organization schedule rows. Scores only when final. Never invent opponents."""
    games = []
    seen = set()
    for it in payload.get("list") or []:
        if not isinstance(it, dict):
            continue
        home = bool(it.get("currentOrgIsHome"))
        opp_org = it.get("opponentOrganization") or (
            it.get("awayTeamOrganization") if home else it.get("homeTeamOrganization")
        )
        opp_name = _on3_org_name(opp_org)
        if not opp_name or skip_opponent_name(opp_name):
            continue
        cid = it.get("key")
        key = f"on3-{cid}" if cid is not None else None
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        ts = it.get("startDateUtc")
        date = None
        kickoff = None
        if isinstance(ts, (int, float)) and ts > 0:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            date = dt.strftime("%Y-%m-%d")
            if it.get("startTime") and str(it.get("startTime")).upper() != "TBD":
                kickoff = dt.strftime("%Y-%m-%dT%H:%M:%S")
        elif isinstance(it.get("startDate"), str) and it["startDate"].strip():
            # On3 lists M/D without year; the request year is 2026.
            try:
                md = datetime.strptime(it["startDate"].strip(), "%m/%d")
                date = f"2026-{md.month:02d}-{md.day:02d}"
            except ValueError:
                date = None
        site = "home" if home else "away"
        loc = ", ".join(x for x in (it.get("city"), (it.get("state") or "").upper()[:2]) if x) or None
        is_final = bool(it.get("isFinal")) or str(it.get("status") or "").upper() == "COMPLETED"
        us_score = it.get("homeTeamScore") if home else it.get("awayTeamScore")
        opp_score = it.get("awayTeamScore") if home else it.get("homeTeamScore")
        if not isinstance(us_score, (int, float)):
            us_score = None
        if not isinstance(opp_score, (int, float)):
            opp_score = None
        result = None
        if is_final and us_score is not None and opp_score is not None:
            if it.get("currentOrgIsWinner") is True or us_score > opp_score:
                result = "W"
            elif it.get("currentOrgIsWinner") is False or us_score < opp_score:
                result = "L"
            else:
                result = "T"
        elif not is_final:
            us_score = None
            opp_score = None
        wp = it.get("homeTeamWinProbability") if home else it.get("awayTeamWinProbability")
        if not isinstance(wp, (int, float)):
            wp = None
        slug = (opp_org or {}).get("slug") if isinstance(opp_org, dict) else None
        games.append(
            {
                "contest_id": key,
                "date": date,
                "kickoff": kickoff,
                "home_away": site,
                "location": loc,
                "opponent": {
                    "name": opp_name,
                    "city": None,
                    "state": None,
                    "maxpreps_id": None,
                    "site_id": None,
                    "team_strength": None,
                    "on3_org_key": (opp_org or {}).get("key") if isinstance(opp_org, dict) else None,
                    "on3_slug": slug,
                },
                "result": result,
                "score": us_score if is_final else None,
                "opp_score": opp_score if is_final else None,
                "maxpreps_game_url": None,
                "toughness_icon": "unknown",
                "win_prob": round(float(wp), 6) if wp is not None else None,
            }
        )
    games.sort(key=lambda g: g.get("date") or "9999")
    return games


def fetch_on3_schedule(org_key) -> list[dict]:
    """GET On3 org schedule for 2026. Never invent a URL or opponent."""
    if org_key is None or org_key == "":
        return []
    games: list[dict] = []
    page = 1
    while page <= 8:
        q = urllib.parse.urlencode({"sportKey": 1, "year": 2026, "page": page})
        url = f"https://api.on3.com/rdb/v2/organizations/{org_key}/schedule?{q}"
        status, body = http_get(url, timeout=25, headers=ON3_SCHED_HEADERS)
        if status != 200 or not body:
            print(f"  on3 schedule fail {org_key} page {page} {status}", flush=True)
            break
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            break
        chunk = parse_on3_schedule(payload, org_key)
        games.extend(chunk)
        pag = payload.get("pagination") or {}
        count = pag.get("pageCount") or 1
        if page >= count or not (payload.get("list") or []):
            break
        page += 1
    return games


def load_on3_gap() -> list[dict]:
    """Verified On3 schedule pages only. Never invent a URL."""
    path = SITE / "on3-gap-schedules.tsv"
    if not path.exists():
        path = IMPORT / "on3-gap-schedules.tsv"
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    if header[:4] != ["fr_school_id", "org_key", "slug", "url"]:
        print(f"on3 gap TSV bad header {header[:4]}", flush=True)
        return []
    rows = []
    seen = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        sid = (cols[0] or "").strip()
        org = (cols[1] or "").strip()
        slug = (cols[2] or "").strip()
        url = (cols[3] or "").strip()
        if not sid or not org or not url:
            continue
        if not url.startswith("https://www.on3.com/high-school/"):
            print(f"  skip non-on3 URL {sid}", flush=True)
            continue
        key = canonical_school_id(sid)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"fr_school_id": sid, "org_key": org, "slug": slug, "url": url})
    return rows


def has_maxpreps_slate(row: dict | None) -> bool:
    if not row:
        return False
    src = row.get("schedule_source")
    if src == "maxpreps":
        return True
    if src == "on3":
        return False
    url = (row.get("schedule_url") or "")
    return "maxpreps.com" in url


def apply_on3_fallback(schools: list[dict], schedules: dict[str, dict]) -> int:
    """On3 2026 slate from the TSV, only when that school still has no MaxPreps."""
    rows = load_on3_gap()
    by_id = {s["id"]: s for s in schools}
    print(f"on3-fallback TSV {len(rows)} verified org schedules", flush=True)
    work: list[tuple[dict, dict]] = []
    skipped = 0
    for rec in rows:
        sid = canonical_school_id(rec["fr_school_id"])
        school = by_id.get(sid)
        if not school:
            print(f"  skip unknown school {rec['fr_school_id']}", flush=True)
            skipped += 1
            continue
        if sid in SKIP_SCHEDULE_IDS:
            print(f"  skip alias/skip-list {sid}", flush=True)
            skipped += 1
            continue
        if has_maxpreps_slate(schedules.get(sid)):
            skipped += 1
            continue
        work.append((school, rec))
    print(f"on3-fallback fetching {len(work)} (skipped {skipped} unknown/maxpreps)", flush=True)
    if not work:
        return 0
    by_mp, by_st_nn = opponent_indexes(schools)
    added = 0
    fetched: dict[str, list[dict]] = {}

    def one(item: tuple[dict, dict]) -> tuple[str, list[dict]]:
        school, rec = item
        return school["id"], fetch_on3_schedule(rec["org_key"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(one, item): item[0]["id"] for item in work}
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                sid, games = fut.result()
            except Exception as e:
                print(f"  on3 fail {futs[fut]}: {e}", flush=True)
                continue
            fetched[sid] = games
            if done % 10 == 0 or done == len(work):
                ok = sum(1 for g in fetched.values() if g)
                print(f"  on3 {done}/{len(work)} fetched {ok}", flush=True)
    for school, rec in work:
        sid = school["id"]
        if has_maxpreps_slate(schedules.get(sid)):
            continue
        games = fetched.get(sid) or []
        if not games:
            print(f"  on3 empty {sid}", flush=True)
            continue
        schedules[sid] = attach_schedule_row(
            school, games, rec["url"], by_mp, by_st_nn, source="on3"
        )
        added += 1
    print(f"on3-fallback attached {added} slates (schedules now {len(schedules)})", flush=True)
    return added


def gapfill_from_tsv(*, on3_fallback: bool = False) -> int:
    """Merge verified MaxPreps TSV (and optional On3 fallback) onto on-disk schedules."""
    global USE_HTTP_CACHE, AS_OF
    USE_HTTP_CACHE = False
    AS_OF = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"gapfill as_of {AS_OF} on3_fallback={on3_fallback}", flush=True)
    schools = json.loads((SITE / "schools.json").read_text())
    schedules = load_schedules()
    collapse_canonical_ids(schools, schedules)
    fill_published_week_zips(schools)
    apply_maxpreps_gapfill(schools, schedules)
    if on3_fallback:
        apply_on3_fallback(schools, schedules)
    on3_teams = fetch_on3(force=False)
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    fill_on3_from_crosswalk(schools, on3_teams)
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
        joined_on3=joined,
    )
    dest = IMPORT / "maxpreps-gap-resolutions.tsv"
    if GAP_TSV.exists():
        dest.write_text(GAP_TSV.read_text())
    if MISSING_TSV.exists():
        (IMPORT / "maxpreps-missing-schedules.tsv").write_text(MISSING_TSV.read_text())
    on3_tsv = SITE / "on3-gap-schedules.tsv"
    if on3_tsv.exists():
        (IMPORT / "on3-gap-schedules.tsv").write_text(on3_tsv.read_text())
    print(
        f"gapfill done schedules {len(schedules)} games "
        f"{sum(len(r.get('games') or []) for r in schedules.values())} gow {n_games}",
        flush=True,
    )
    return 0


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
    global AS_OF
    AS_OF = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schools = json.loads((SITE / "schools.json").read_text())
    schedules = load_schedules()
    collapse_canonical_ids(schools, schedules)
    fill_published_week_zips(schools)
    if fill_missing:
        fill_missing_schedules(schools, schedules)
    on3_teams = fetch_on3(force=not USE_HTTP_CACHE)
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    fill_on3_from_crosswalk(schools, on3_teams)
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
        joined_on3=joined,
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
    """Live MaxPreps 26-27 + On3 national restamp. Does not read the Aug 25 HTML cache."""
    global USE_HTTP_CACHE, AS_OF
    USE_HTTP_CACHE = False
    AS_OF = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"full-fetch as_of {AS_OF} cache={USE_HTTP_CACHE}", flush=True)

    schools = json.loads((SITE / "schools.json").read_text())
    schedules: dict[str, dict] = {}
    collapse_canonical_ids(schools, schedules)
    fill_published_week_zips(schools)

    on3_teams = fetch_on3(force=True)
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    joined_mp, mp_payload = join_site_rank_board(schools, RAW_MP)
    joined_dctf, _dctf = join_site_rank_board(schools, RAW_DCTF)
    print(f"on3 joined {len(joined)} / {n_on3} onto {len(schools)} schools")
    print(f"maxpreps national joined {len(joined_mp)} dctf joined {len(joined_dctf)}")
    apply_strength(schools, joined, on3_teams, joined_mp, joined_dctf)
    by_mp, by_st_nn = opponent_indexes(schools)
    by_id = {s["id"]: s for s in schools}

    occupied = occupied_schedule_paths(schools, {})
    fetched: dict[str, tuple[list[dict], str | None]] = {}

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
                if done % 50 == 0 or done == len(batch):
                    ok = sum(1 for g, _ in fetched.values() if g)
                    print(f"  {done}/{len(batch)} fetched {ok}", flush=True)

    want = [
        s
        for s in schools
        if s["id"] not in SKIP_SCHEDULE_IDS
        and (
            stored_schedule_url(s)
            or (s.get("maxpreps") or {}).get("scheduleUrl")
            or (s.get("maxpreps") or {}).get("footballUrl")
        )
    ]
    print(f"fetching schedules for {len(want)} schools", flush=True)
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
        joined_on3=joined,
    )
    img = by_id.get("fl-bradenton-img-academy") or {}
    n_games_sched = sum(len(r.get("games") or []) for r in schedules.values())
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
    print(
        f"schedules {len(schedules)} games {n_games_sched} on3_joined {len(joined)} "
        f"gow {n_games} missing zip {sum(1 for s in schools if not s.get('zip'))}"
    )
    return 0


if __name__ == "__main__":
    if "--gapfill" in sys.argv:
        raise SystemExit(gapfill_from_tsv(on3_fallback="--on3-fallback" in sys.argv))
    if "--full-fetch" in sys.argv:
        raise SystemExit(main())
    fill = "--fill-missing" in sys.argv
    raise SystemExit(restamp_from_disk(fill_missing=fill))
