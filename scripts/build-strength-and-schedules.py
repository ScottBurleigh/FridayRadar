#!/usr/bin/env python3
"""On3 national HS rankings + MaxPreps 26-27 schedules → strength, SOS, toughness.

Does not invent On3 ranks. Unranked schools use talent share only.
Writes data/raw/on3/national-2026.json, site-data/schedules.json, and
team_strength / on3 / sos fields on site-data + data/import schools.json.
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
SEASON = "26-27"


def http_get(url: str, timeout: int = 20) -> tuple[int, str]:
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
    req = urllib.request.Request(url, headers=UA)
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


def on3_norm(rank: int, n: int) -> float:
    """Rank 1 = 100, log decay so mid-board is ~30 not ~50. Never uses compositeScore."""
    if n <= 1 or rank <= 1:
        return 100.0
    val = 100.0 * (1.0 - math.log(rank) / math.log(n))
    return round(max(0.0, min(100.0, val)), 2)


def toughness_icon(us: float | None, them: float | None) -> str:
    """THIS team's view. Missing opponent strength is a cupcake (0), not unknown.

    SOS still omits unknown opponents so they do not count as zeros there.
    A superteam vs an unmapped nobody is much_easier for the superteam.
    """
    if us is None:
        return "unknown"
    opp = 0.0 if them is None else them
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
    status, html = http_get("https://www.maxpreps.com/ga/buford/buford-wolves/", timeout=30)
    m = re.search(r'"buildId":"([^"]+)"', html)
    if not m:
        raise RuntimeError("MaxPreps buildId missing")
    return m.group(1).replace("\\n", "").strip()


STOP_SLUG = {"high", "school", "hs", "catholic", "academy", "prep", "collegiate"}
TEAM_PATHS: dict[str, str] = {}


def slugify(value: str) -> str:
    v = (value or "").lower().replace("&", " and ").replace("saint ", "st ")
    v = re.sub(r"[^a-z0-9]+", "-", v).strip("-")
    return v


def remember_team_path(mp_id: str | None, url: str | None) -> None:
    if not mp_id or not url:
        return
    path = urllib.parse.urlparse(url).path if "://" in url else url
    path = path.split("?")[0].rstrip("/")
    path = re.sub(r"/football(/.*)?$", "", path)
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3:
        TEAM_PATHS[mp_id.lower()] = "/" + "/".join(parts[:3])


def school_path_guesses(school: dict) -> list[str]:
    """MaxPreps pages are /st/city/name-mascot/. Stored canonicalUrl often omits mascot."""
    mp = school.get("maxpreps") or {}
    st = (school.get("state") or "").lower()
    city = slugify(school.get("city") or "")
    raw_name = slugify(school.get("name") or "")
    raw_name = raw_name.replace("-high-school", "").replace("-high", "")
    mascot = slugify(mp.get("mascot") or "")
    parts = [p for p in raw_name.split("-") if p]
    names: list[str] = []

    def add_name(n: str) -> None:
        n = re.sub(r"-+", "-", (n or "")).strip("-")
        if n and n not in names:
            names.append(n)

    add_name(raw_name)
    if city and raw_name.startswith(city) and len(raw_name) > len(city) + 1:
        add_name(raw_name[len(city) :].strip("-"))
    add_name("-".join(p for p in parts if p not in STOP_SLUG))
    if parts:
        add_name(parts[-1])
    if len(parts) >= 2:
        add_name("-".join(parts[-2:]))
    add_name(city)

    paths: list[str] = []

    def add_path(p: str) -> None:
        p = re.sub(r"-+", "-", p)
        if p not in paths and p.count("/") >= 3:
            paths.append(p)

    sid = (mp.get("schoolId") or "").lower()
    if sid and sid in TEAM_PATHS:
        add_path(TEAM_PATHS[sid])
    for base in (mp.get("footballUrl"), mp.get("canonicalUrl"), mp.get("scheduleUrl")):
        if not base or not str(base).startswith("http"):
            continue
        path = urllib.parse.urlparse(base).path.rstrip("/")
        path = re.sub(r"/football(/.*)?$", "", path)
        add_path(path)
    for n in names:
        if mascot:
            add_path(f"/{st}/{city}/{n}-{mascot}")
            add_path(f"/{st}/{city}/{city}-{mascot}")
        add_path(f"/{st}/{city}/{n}")
    return paths[:14]


def schedule_json_urls(school: dict, build_id: str) -> list[str]:
    out = []
    for path in school_path_guesses(school):
        sched = path.rstrip("/") + f"/football/{SEASON}/schedule"
        out.append(f"https://www.maxpreps.com/_next/data/{build_id}{sched}.json")
    seen = set()
    uniq = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def search_school_path(school: dict) -> str | None:
    st = (school.get("state") or "").lower()
    city = slugify(school.get("city") or "")
    if not st or not city:
        return None
    q = urllib.parse.urlencode({"q": f"{school.get('name')} {school.get('state')}"})
    status, html = http_get(f"https://www.maxpreps.com/search/?{q}", timeout=18)
    if status != 200 or not html:
        return None
    prefix = f"/{st}/{city}/"
    found = []
    for raw in re.findall(r"(?:https://www\.maxpreps\.com)?(/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+)/?", html, re.I):
        path = raw.rstrip("/").lower()
        if not path.startswith(prefix) or path.count("/") != 3:
            continue
        slug = path.rsplit("/", 1)[-1]
        name_toks = set(slugify(school.get("name") or "").split("-")) - STOP_SLUG
        if name_toks and not (name_toks & set(slug.split("-"))):
            continue
        if path not in found:
            found.append(path)
    return found[0] if len(found) == 1 else None


def parse_team(arr: list) -> dict | None:
    if not isinstance(arr, list) or len(arr) < 17:
        return None
    name = arr[14] if isinstance(arr[14], str) else None
    if not name or PLACEHOLDER.match(name) or "varsity opponent" in name.lower():
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


def parse_contests(payload: dict, page_mp: str | None) -> tuple[list[dict], str | None]:
    contests = (payload.get("pageProps") or payload).get("contests") or []
    html_url = None
    tc = ((payload.get("pageProps") or payload).get("teamContext") or {})
    data = tc.get("data") if isinstance(tc, dict) else None
    if isinstance(data, dict):
        html_url = data.get("canonicalUrl")
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
        if page_mp:
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


def _schedule_from_url(
    url: str, build_id: str, page_mp: str | None
) -> tuple[list[dict], str | None] | None:
    status, body = http_get(url, timeout=18)
    if status != 200 or not body:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    games, page_url = parse_contests(payload, page_mp)
    if not games:
        return None
    html = page_url
    if "/_next/data/" in url:
        rebuilt = "https://www.maxpreps.com" + urllib.parse.urlparse(url).path.replace(
            f"/_next/data/{build_id}", ""
        ).replace(".json", "/")
        if not rebuilt.endswith("/"):
            rebuilt += "/"
        html = rebuilt
    return games, html


def fetch_schedule(school: dict, build_id: str, *, search: bool = False) -> tuple[list[dict], str | None]:
    mp = ((school.get("maxpreps") or {}).get("schoolId") or "").lower() or None
    urls = schedule_json_urls(school, build_id)
    mp_info = school.get("maxpreps") or {}
    tried: set[str] = set()

    def consider(url: str) -> tuple[list[dict], str | None] | None:
        if url in tried:
            return None
        tried.add(url)
        return _schedule_from_url(url, build_id, mp)

    for url in urls:
        hit = consider(url)
        if hit:
            return hit

    if search and not (mp_info.get("mascot") or "").strip():
        st = (school.get("state") or "").lower()
        city = slugify(school.get("city") or "")
        full = slugify(school.get("name") or "")
        last = full.split("-")[-1] if full else ""
        for mascot in (
            "eagles", "tigers", "panthers", "wildcats", "lions", "knights",
            "warriors", "saints", "explorers", "raiders", "wolves", "bears",
            "hawks", "falcons", "cardinals", "cougars", "mustangs", "rams",
            "bulldogs", "spartans", "huskies", "trojans", "chargers", "stags",
        ):
            for n in dict.fromkeys([last, full]):
                if not n:
                    continue
                path = f"/{st}/{city}/{n}-{mascot}/football/{SEASON}/schedule"
                hit = consider(f"https://www.maxpreps.com/_next/data/{build_id}{path}.json")
                if hit:
                    return hit

    if search:
        extra = search_school_path(school)
        if extra:
            hit = consider(
                f"https://www.maxpreps.com/_next/data/{build_id}{extra}/football/{SEASON}/schedule.json"
            )
            if hit:
                return hit
    return [], None


def opp_norm_name(name: str) -> str:
    """Strip parentheticals and known extra suffixes, then the usual HS tokens.

    'The St. James Performance Academy' → 'the st james' (equals The St. James).
    'Legacy School of Sport Sciences' → 'legacy' (does not equal Legacy Christian).
    """
    n = name or ""
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\b(performance academy|school of sport sciences)\b", " ", n, flags=re.I)
    return norm_name(n)


def opponent_indexes(schools: list[dict]) -> tuple[dict, dict]:
    by_mp: dict[str, dict] = {}
    by_st_nn: dict[tuple[str, str], list[dict]] = {}
    for s in schools:
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


def apply_strength(schools: list[dict], joined: dict[str, dict], n_on3: int) -> None:
    tnorm = talent_norm_map(schools)
    for s in schools:
        sid = s["id"]
        tn = tnorm.get(sid)
        on3 = joined.get(sid)
        if on3 and tn is not None:
            st = round((tn + on3_norm(on3["rank"], n_on3)) / 2.0, 2)
        elif tn is not None:
            st = tn
        elif on3:
            st = on3_norm(on3["rank"], n_on3)
        else:
            st = None
        s["team_strength"] = st
        if on3:
            s["on3"] = {
                "rank": on3["rank"],
                "rating": round(on3["rating"], 3) if on3.get("rating") is not None else None,
                "org_key": on3.get("org_key"),
            }
        else:
            s.pop("on3", None)


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
        for g in row.get("games") or []:
            opp = g.get("opponent") or {}
            hit = match_opponent(by_mp, by_st_nn, opp)
            if hit:
                opp["site_id"] = hit["id"]
                opp["team_strength"] = hit.get("team_strength")
            else:
                opp["site_id"] = None
                opp["team_strength"] = None
            g["opponent"] = opp
            g["toughness_icon"] = toughness_icon(school.get("team_strength"), opp.get("team_strength"))
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
    for s in schools:
        if s.get("sos") is None:
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


def write_board(schools: list[dict], schedules: dict[str, dict], n_on3: int, joined: int) -> None:
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
            "schedules": len(schedules),
            "with_zip": sum(1 for s in schools if s.get("zip")),
            "v1_games": n_games,
            "v1_both_sides": n_games,
            "v1_partial": 0,
            "rank_by": "two_sided_talent",
            "team_strength_note": (
                "team_strength is the mean of talent share (100 × talent / board max; IMG = 100) "
                "and an On3 national rank log-curve (rank 1 = 100, decaying). "
                "Unranked schools omit the On3 term. SOS is the mean of known opponents’ "
                "team_strength on that 0–100 scale (unknown omitted, never On3 compositeScore)."
            ),
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


def restamp_from_disk() -> int:
    """Recompute 0–100 strength + SOS from on-disk schedules. Does not scrape."""
    schools = json.loads((SITE / "schools.json").read_text())
    schedules = json.loads((SITE / "schedules.json").read_text())
    fill_published_week_zips(schools)
    on3_teams = fetch_on3()
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    apply_strength(schools, joined, n_on3)
    restamp_schedules(schools, schedules)
    n_games = slice_v1_games(schools, 196)
    write_board(schools, schedules, n_on3, len(joined))
    img = next((s for s in schools if s["id"] == "fl-bradenton-img-academy"), {})
    print(
        "restamp IMG strength",
        img.get("team_strength"),
        "on3",
        img.get("on3"),
        "sos",
        img.get("sos"),
        "schedules",
        len(schedules),
        "on3_joined",
        len(joined),
        "games",
        n_games,
    )
    return 0


def main() -> int:
    schools = json.loads((SITE / "schools.json").read_text())
    on3_teams = fetch_on3()
    n_on3 = len(on3_teams)
    joined = join_on3(schools, on3_teams)
    print(f"on3 joined {len(joined)} / {n_on3} onto {len(schools)} schools")
    tnorm = talent_norm_map(schools)
    strength: dict[str, float] = {}
    for s in schools:
        sid = s["id"]
        tn = tnorm.get(sid)
        on3 = joined.get(sid)
        if on3 and tn is not None:
            on = on3_norm(on3["rank"], n_on3)
            st = round((tn + on) / 2.0, 2)
        elif tn is not None:
            st = tn
        elif on3:
            st = on3_norm(on3["rank"], n_on3)
        else:
            st = None
        s["team_strength"] = st
        if st is not None:
            strength[sid] = st
        if on3:
            s["on3"] = {
                "rank": on3["rank"],
                "rating": round(on3["rating"], 3) if on3.get("rating") is not None else None,
                "org_key": on3.get("org_key"),
            }
        else:
            s.pop("on3", None)

    by_mp = {}
    by_id = {s["id"]: s for s in schools}
    for s in schools:
        mp = (s.get("maxpreps") or {}).get("schoolId")
        if mp:
            by_mp[mp.lower()] = s

    try:
        build_id = read_build_id()
        print("maxpreps buildId", build_id)
    except Exception as e:
        print("buildId fail", e)
        build_id = "30052b80-31ab3f27"

    def run_fetch(batch: list[dict], search: bool) -> None:
        if not batch:
            return
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(fetch_schedule, s, build_id, search=search): s["id"] for s in batch}
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
                if done % 50 == 0:
                    ok = sum(1 for g, _ in fetched.values() if g)
                    print(f"  {done}/{len(batch)} fetched {ok} paths {len(TEAM_PATHS)}", flush=True)

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
    print(f"pass1 {sum(1 for g,_ in fetched.values() if g)} miss {len(miss)} harvested_paths {len(TEAM_PATHS)}", flush=True)
    run_fetch(miss, search=False)
    miss = [s for s in want if not fetched.get(s["id"], ([], None))[0]]
    print(f"pass2 harvest miss {len(miss)}", flush=True)
    run_fetch(miss, search=True)
    print(f"pass3 search done {sum(1 for g,_ in fetched.values() if g)}", flush=True)

    for s in want:
        games, page_url = fetched.get(s["id"], ([], None))
        if not games:
            continue
        mp = s.get("maxpreps") or {}
        sched_url = mp.get("scheduleUrl") or page_url
        if page_url and not mp.get("scheduleUrl"):
            mp["scheduleUrl"] = page_url
            s["maxpreps"] = mp
        for g in games:
            opp = g["opponent"]
            hit = by_mp.get((opp.get("maxpreps_id") or "").lower()) if opp.get("maxpreps_id") else None
            if not hit:
                nn = norm_name(opp["name"])
                st = (opp.get("state") or "").upper()
                cands = [
                    x
                    for x in schools
                    if (x.get("name_normalized") or norm_name(x["name"])) == nn
                    and (not st or x.get("state") == st)
                ]
                if len(cands) == 1:
                    hit = cands[0]
            if hit:
                opp["site_id"] = hit["id"]
                opp["team_strength"] = hit.get("team_strength")
            g["toughness_icon"] = toughness_icon(s.get("team_strength"), opp.get("team_strength"))
        known = [g["opponent"]["team_strength"] for g in games if g["opponent"].get("team_strength") is not None]
        sos = round(sum(known) / len(known), 2) if known else None
        s["sos"] = sos
        s["sos_games"] = len(known)
        s["schedule_games"] = len(games)
        schedules[s["id"]] = {
            "school_id": s["id"],
            "season": SEASON,
            "team_strength": s.get("team_strength"),
            "schedule_url": sched_url,
            "sos": sos,
            "sos_games": len(known),
            "games": games,
        }

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
            "team_strength_note": (
                "team_strength is the mean of talent share (100 × talent / board max; IMG = 100) "
                "and an On3 national rank log-curve (rank 1 = 100, decaying). "
                "Unranked schools omit the On3 term. SOS is the mean of known opponents’ "
                "team_strength on that 0–100 scale (unknown omitted, never On3 compositeScore)."
            ),
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
    if "--restamp" in sys.argv:
        raise SystemExit(restamp_from_disk())
    raise SystemExit(main())
