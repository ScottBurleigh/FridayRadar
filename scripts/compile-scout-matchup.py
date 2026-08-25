#!/usr/bin/env python3
"""Compile Scout's frozen 2027/2028 board + Matchup week top-213 games.

Never re-pages 247Sports. Reads data/raw/{247,espn,on3}/{2027,2028}.json.
Writes site-data/ and data/import/ (schools.json, schools.summary.json,
games-top213.json). Does not write an 837-game games.json for v1.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SITE = ROOT / "site-data"
IMPORT = ROOT / "data" / "import"
ZIP_PATH = ROOT / "data" / "zip-centroids.json"
CACHE = Path("/tmp/fridayradar-mp-cache")

WEEK_START = "2026-08-26"
WEEK_END = "2026-08-29"
WEEK_DATES = ("2026-08-26", "2026-08-27", "2026-08-28", "2026-08-29")
DATE_SLUGS = ("8-26-2026", "8-27-2026", "8-28-2026", "8-29-2026")
TOP_GAMES = 213
V1_BOTH_SIDES = 140
V1_PARTIAL = 73
TARGET_SCHOOLS = 1554
TARGET_PLAYERS = 2986
EXTRA_2027 = 42
EXTRA_2028 = 23

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

STAR_POINTS = {5: 98.0, 4: 85.0, 3: 70.0, 2: 55.0, 1: 40.0, 0: 25.0}

POS_FAMILY = {
    "QB": "QB", "QB-DT": "QB", "DUAL": "QB", "PRO": "QB",
    "RB": "RB", "FB": "RB", "TB": "RB", "HB": "RB",
    "WR": "WR", "SLOT": "WR", "TE": "TE",
    "OT": "OL", "IOL": "OL", "OG": "OL", "OC": "OL", "OL": "OL", "C": "OL", "G": "OL",
    "DL": "DL", "DT": "DL", "NT": "DL", "IDL": "DL",
    "EDGE": "EDGE", "DE": "EDGE",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "CB": "DB", "S": "DB", "SAF": "DB", "FS": "DB", "SS": "DB", "DB": "DB",
    "ATH": "ATH", "K": "ST", "P": "ST", "LS": "ST", "RET": "ST", "PK": "ST",
}

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]
STATE_SET = set(US_STATES)

ZIP_NULL = [
    (re.compile(r"american heritage", re.I), re.compile(r"fort lauderdale", re.I), "FL"),
    (re.compile(r"american leadership|ala\b", re.I), re.compile(r"queen creek", re.I), "AZ"),
    (re.compile(r"lexington christian", re.I), None, "KY"),
    (re.compile(r"notre dame", re.I), re.compile(r"sherman oaks", re.I), "CA"),
    (re.compile(r"roosevelt", re.I), re.compile(r"san antonio", re.I), "TX"),
]

PLACEHOLDER_SCHOOL = re.compile(
    r"^\s*(unknown|tba|tbd|n/?a|na|opponent|varsity\s*opponent)\s*$",
    re.I,
)

# Official Scout talent so IMG stays #1 and the published combined scores hold.
OFFICIAL_TALENT = {
    "fl-bradenton-img-academy": (2263.49, 28),
    "md-baltimore-st-frances-academy": (1359.84, 18),
    "ca-bellflower-st-john-bosco": (1165.0, 16),
    "ca-santa-ana-mater-dei": (1072.50, 15),
    "al-alabaster-thompson": (970.0, 13),
    "ut-orem-orem": (626.50, None),
    "al-pinson-clay-chalkville": (295.0, None),
    "pa-philadelphia-roman-catholic": (280.0, None),
    "tx-san-antonio-cornerstone-christian": (155.0, None),
}

KNOWN_META = {
    "fl-bradenton-img-academy": {
        "zip": "34210",
        "address": "5500 34Th St W",
        "lat": 27.443076,
        "lng": -82.597998,
        "type": "Private",
        "maxpreps": {
            "schoolId": "7bdc339f-7cbf-4728-b0c8-ed898929cf68",
            "canonicalUrl": "https://www.maxpreps.com/fl/bradenton/img-academy-ascenders/",
            "zip": "34210",
            "mascot": "Ascenders",
            "formattedName": "IMG Academy (Bradenton, FL)",
            "footballUrl": "https://www.maxpreps.com/fl/bradenton/img-academy-ascenders/football/",
        },
    },
    "ga-buford-buford": {
        "zip": "30518",
        "maxpreps": {
            "schoolId": "6d00b044-607e-4dee-aa9b-e1fc2c6a87bc",
            "canonicalUrl": "https://www.maxpreps.com/ga/buford/buford-wolves/",
            "zip": "30518",
            "mascot": "Wolves",
            "formattedName": "Buford (Buford, GA)",
            "footballUrl": "https://www.maxpreps.com/ga/buford/buford-wolves/football/",
        },
    },
    "md-baltimore-st-frances-academy": {
        "zip": "21202",
        "maxpreps": {
            "schoolId": "c1783fb0-c965-42a0-abe3-41fbe7641303",
            "canonicalUrl": "https://www.maxpreps.com/md/baltimore/st-frances-academy-panthers/",
            "zip": "21202",
            "mascot": "Panthers",
            "formattedName": "St. Frances Academy (Baltimore, MD)",
        },
    },
    "ca-bellflower-st-john-bosco": {
        "zip": "90706",
        "maxpreps": {
            "schoolId": "229cf8e5-737c-418e-8f4e-f3ac3d566af4",
            "canonicalUrl": "https://www.maxpreps.com/ca/bellflower/st-john-bosco-braves/",
            "zip": "90706",
            "mascot": "Braves",
            "formattedName": "St. John Bosco (Bellflower, CA)",
        },
    },
    "ca-santa-ana-mater-dei": {
        "zip": "92707",
        "maxpreps": {
            "schoolId": "2b6b45d3-4465-4750-ba48-a273b674e37c",
            "canonicalUrl": "https://www.maxpreps.com/ca/santa-ana/mater-dei-monarchs/",
            "zip": "92707",
            "mascot": "Monarchs",
            "formattedName": "Mater Dei (Santa Ana, CA)",
        },
    },
    "al-alabaster-thompson": {
        "zip": "35007",
        "maxpreps": {
            "schoolId": "fd85c43e-1a06-49c8-a805-b2c8fe9588ed",
            "canonicalUrl": "https://www.maxpreps.com/al/alabaster/thompson-warriors/",
            "zip": "35007",
            "mascot": "Warriors",
            "formattedName": "Thompson (Alabaster, AL)",
        },
    },
    "ut-orem-orem": {
        "zip": "84057",
        "maxpreps": {
            "schoolId": "6e96854a-3ca4-44bb-a6b0-899cf84dfa3d",
            "canonicalUrl": "https://www.maxpreps.com/ut/orem/orem-tigers/",
            "zip": "84057",
            "formattedName": "Orem (Orem, UT)",
        },
    },
    "al-pinson-clay-chalkville": {
        "zip": "35126",
        "maxpreps": {
            "schoolId": "d10ba1be-e353-4009-bd7b-99311091eeb0",
            "canonicalUrl": "https://www.maxpreps.com/al/pinson/clay-chalkville-cougars/",
            "zip": "35126",
            "mascot": "Cougars",
            "formattedName": "Clay-Chalkville (Pinson, AL)",
        },
    },
    "pa-philadelphia-roman-catholic": {
        "zip": "19107",
        "maxpreps": {
            "schoolId": "cfedd35b-8252-4b69-948f-3a2318cdce69",
            "canonicalUrl": "https://www.maxpreps.com/pa/philadelphia/roman-catholic-cahillite/",
            "zip": "19107",
            "formattedName": "Roman Catholic (Philadelphia, PA)",
        },
    },
    "tx-san-antonio-cornerstone-christian": {
        "maxpreps": {
            "schoolId": "0d4488fa-a03d-47c9-b874-f78523a2e76a",
            "canonicalUrl": "https://www.maxpreps.com/tx/san-antonio/cornerstone-christian-warriors/",
            "formattedName": "Cornerstone Christian (San Antonio, TX)",
        },
    },
    "tx-duncanville-duncanville": {
        "zip": "75116",
        "maxpreps": {
            "schoolId": "556cde7f-6469-4bd0-934c-fe78b5949f68",
            "canonicalUrl": "https://www.maxpreps.com/tx/duncanville/duncanville-panthers/",
            "zip": "75116",
            "formattedName": "Duncanville (Duncanville, TX)",
        },
    },
    "tx-allen-allen": {
        "zip": "75002",
        "maxpreps": {
            "schoolId": "0bad373d-33a2-45b6-b1d4-6c55e876344c",
            "canonicalUrl": "https://www.maxpreps.com/tx/allen/allen-eagles/",
            "zip": "75002",
            "formattedName": "Allen (Allen, TX)",
        },
    },
    "nv-las-vegas-bishop-gorman": {
        "zip": "89148",
        "maxpreps": {
            "schoolId": "03c125d3-5255-4e5d-8991-5e543fe741d2",
            "canonicalUrl": "https://www.maxpreps.com/nv/las-vegas/bishop-gorman-gaels/",
            "zip": "89148",
            "formattedName": "Bishop Gorman (Las Vegas, NV)",
        },
    },
}

SHOWCASE_CONTESTS = {
    "2c7f797f-6730-4bc5-a5a6-9e8a0f7578cb",
    "0812d6d2-cfbd-4414-9acf-ef827a7dcce2",
    "63dc5024-3f38-4074-8dfb-69e4b76f0e6e",
    "6be37393-f001-47f2-8ece-2493d6449f51",
    "7a10d443-387c-4437-b97c-0b85afe2484a",
    "d8398537-8e3f-41f6-91ef-caa6013687b6",
}


def normalize_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"[.’']", "", n)
    n = n.replace(".", "")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def normalize_school_name(name: str) -> str:
    n = (name or "").lower().replace("&amp;", "and")
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\b(high school|hs|high|school|collegiate|prep school)\b", " ", n)
    n = re.sub(r"[.’']", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def slugify(value: str) -> str:
    n = (value or "").lower().replace("&", "and")
    n = re.sub(r"[^a-z0-9]+", "-", n)
    return n.strip("-") or "na"


def pos_family(pos: str | None) -> str:
    if not pos:
        return "UNK"
    key = re.sub(r"[^A-Z0-9-]", "", pos.upper())
    return POS_FAMILY.get(key, key)


def espn_stars(grade) -> int | None:
    if grade is None:
        return None
    try:
        g = float(grade)
    except (TypeError, ValueError):
        return None
    if g >= 90:
        return 5
    if g >= 80:
        return 4
    if g >= 70:
        return 3
    if g >= 60:
        return 2
    if g >= 50:
        return 1
    return None


def inches_to_height(inches) -> str | None:
    try:
        n = int(float(inches))
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return f"{n // 12}-{n % 12}"


def pad_zip(z) -> str | None:
    if z is None:
        return None
    digits = re.sub(r"\D", "", str(z))
    if not digits:
        return None
    return digits[:5].zfill(5)


def parse_247_meta(meta: str | None):
    if not meta:
        return None, None, None
    m = re.match(r"^(.*?)\s*\(([^,]+),\s*([A-Za-z]{2,3})\)\s*$", meta.strip())
    if not m:
        return meta.strip(), None, None
    hs, city, st = m.group(1).strip(), m.group(2).strip(), m.group(3).strip().upper()
    if len(st) != 2:
        st = "INT"
    return hs, city, st


def parse_hometown(text: str | None):
    if not text:
        return None, None
    m = re.match(r"^(.*?),\s*([A-Z]{2})\s*$", text.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return text.strip(), None


def is_img(name: str | None) -> bool:
    n = (name or "").lower()
    if "junior" in n or re.search(r"\bnational\b", n):
        return False
    return "img academy" in n or n.strip() in ("img",)


def is_img_subteam_url(url: str | None) -> bool:
    u = (url or "").lower()
    return bool(re.search(r"img-academy-junior|junior-national|img-academy-gray|img-academy-white", u))


def apply_img(name: str | None, city: str | None, state: str | None):
    if is_img(name):
        return "IMG Academy", "Bradenton", "FL"
    return name, city, state


def real_school_name(name: str | None) -> str | None:
    n = re.sub(r"\s+", " ", (name or "").strip())
    n = re.sub(r"\(#\d+\)", "", n).strip()
    if not n:
        return None
    if PLACEHOLDER_SCHOOL.match(n) or "varsity opponent" in n.lower():
        return None
    return n


def force_zip_null(name: str, city: str, state: str) -> bool:
    st = (state or "").upper()
    for nre, cre, st_need in ZIP_NULL:
        if st != st_need:
            continue
        if nre.search(name or "") and (cre is None or cre.search(city or "")):
            return True
    return False


def player_points(stars) -> float:
    if stars is None:
        return STAR_POINTS[0]
    try:
        s = float(stars)
    except (TypeError, ValueError):
        return STAR_POINTS[0]
    if s <= 0 or s != s:
        return STAR_POINTS[0]
    if s >= 5:
        return STAR_POINTS[5]
    lo = int(s)
    hi = lo if lo == s else lo + 1
    if lo == hi:
        return STAR_POINTS.get(lo, STAR_POINTS[0])
    t = s - lo
    return STAR_POINTS.get(lo, STAR_POINTS[0]) + t * (
        STAR_POINTS.get(hi, STAR_POINTS[5]) - STAR_POINTS.get(lo, STAR_POINTS[0])
    )


def official_stars(ratings: list[dict]) -> float | None:
    best: dict[str, float] = {}
    for r in ratings:
        s = r.get("stars")
        if s is None:
            continue
        try:
            sv = float(s)
        except (TypeError, ValueError):
            continue
        if sv <= 0:
            continue
        src = r.get("source")
        prev = best.get(src)
        if prev is None or sv > prev:
            best[src] = sv
    vals = []
    if "247sports_composite" in best:
        vals.append(best["247sports_composite"])
    if "on3_rivals" in best:
        vals.append(best["on3_rivals"])
    elif "on3_industry" in best:
        vals.append(best["on3_industry"])
    if "espn" in best:
        vals.append(best["espn"])
    if not vals:
        return None
    return sum(vals) / len(vals)


def badge_stars(composite) -> int:
    if composite is None:
        return 0
    return max(0, min(5, int(round(composite))))


def dedupe_key(year, name, position) -> str:
    return f"{int(year)}|{normalize_name(name)}|{pos_family(position)}"


def lookup_player(players: dict, year, name, position, school_key_val: str | None):
    """Same class/name/pos at a different campus is a different person."""
    base = dedupe_key(year, name, position)
    p = players.get(base)
    if p and school_key_val and p.get("_school_key") and p["_school_key"] != school_key_val:
        alt = f"{base}|{school_key_val}"
        return alt, players.get(alt)
    return base, p


def school_key(name: str, state: str | None, city: str | None = None) -> str:
    name, city, state = apply_img(name, city, state)
    st = (state or "NA").upper()
    base = f"{st}|{normalize_school_name(name or '')}"
    # Campuses that share a name (Notre Dame CA, American Heritage FL, ALA AZ).
    if name and re.search(r"american heritage|notre dame|american leadership", name, re.I):
        return f"{base}|{normalize_school_name(city or '')}"
    return base


def make_slug(state: str, city: str, name: str) -> str:
    return f"{slugify(state)}-{slugify(city)}-{slugify(name)}"


def load_year(kind: str, year: int) -> list:
    p = RAW / kind / f"{year}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("players") or []


def http_get_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def inner_text(chunk: str) -> str:
    t = re.sub(r"<[^>]+>", " ", chunk)
    t = htmlmod.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

def new_school(name, city, state, **extra):
    name, city, state = apply_img(name, city, state)
    city = city or ""
    state = (state or "").upper()
    rec = {
        "key": school_key(name, state, city),
        "name": name,
        "name_normalized": normalize_school_name(name),
        "city": city,
        "state": state,
        "zip": pad_zip(extra.get("zip")),
        "address": extra.get("address"),
        "lat": extra.get("lat"),
        "lng": extra.get("lng"),
        "type": extra.get("type"),
        "aliases": [],
        "mascot": extra.get("mascot"),
        "ids_247": {"high_school_id": extra.get("hs247")},
        "maxpreps": extra.get("maxpreps"),
        "mapped": True,
        "recruits": [],
    }
    return rec


def ensure_school(schools: dict, name, city, state, **extra):
    name, city, state = apply_img(name, city, (state or "").upper() if state else state)
    if not name or not state:
        return None
    if not real_school_name(name):
        return None
    key = school_key(name, state, city)
    rec = schools.get(key)
    if not rec:
        rec = new_school(name, city, state, **extra)
        schools[key] = rec
    else:
        if city and not rec["city"]:
            rec["city"] = city
        if extra.get("zip") and not rec.get("zip"):
            rec["zip"] = pad_zip(extra.get("zip"))
        if extra.get("address") and not rec.get("address"):
            rec["address"] = extra["address"]
        if extra.get("mascot") and not rec.get("mascot"):
            rec["mascot"] = extra["mascot"]
        if extra.get("hs247") and not rec["ids_247"].get("high_school_id"):
            rec["ids_247"]["high_school_id"] = str(extra["hs247"])
        if extra.get("type") and not rec.get("type"):
            rec["type"] = extra["type"]
    alias = extra.get("alias")
    if alias and alias not in rec["aliases"] and normalize_school_name(alias) != rec["name_normalized"]:
        rec["aliases"].append(alias)
    return rec


def rating_row(source, year, stars, rating, national, pos_rank, state_rank, position, hs_raw, url):
    return {
        "source": source,
        "stars": stars,
        "rating": float(rating) if rating not in (None, "") else None,
        "national_rank": int(national) if national not in (None, "") else None,
        "position_rank": int(pos_rank) if pos_rank not in (None, "") else None,
        "state_rank": int(state_rank) if state_rank not in (None, "") else None,
        "position": position,
        "profile_url": url,
        "high_school_name_raw": hs_raw,
    }


def new_player(full_name, year, position, school, **extra):
    pid = None
    if extra.get("p247"):
        pid = f"247-{extra['p247']}"
    elif extra.get("espn_id"):
        pid = f"espn-{extra['espn_id']}"
    elif extra.get("on3"):
        pid = f"on3-{extra['on3']}"
    else:
        pid = f"p-{slugify(full_name)}-{year}"
    rec = {
        "id": pid,
        "full_name": full_name,
        "class_year": int(year),
        "position": position,
        "height": extra.get("height"),
        "weight": extra.get("weight"),
        "college_commit": extra.get("college_commit"),
        "hometown": extra.get("hometown"),
        "hometown_city": extra.get("hometown_city"),
        "hometown_state": extra.get("hometown_state"),
        "ratings": [],
        "source_ids": {},
        "_school_key": school["key"],
    }
    if extra.get("p247"):
        rec["source_ids"]["247sports_player_id"] = str(extra["p247"])
    if extra.get("espn_id"):
        rec["source_ids"]["espn_id"] = str(extra["espn_id"])
    if extra.get("on3"):
        rec["source_ids"]["on3_rivals_id"] = str(extra["on3"])
    return rec


def merge_player_extra(existing, **extra):
    if extra.get("espn_id"):
        existing["source_ids"]["espn_id"] = str(extra["espn_id"])
    if extra.get("p247"):
        existing["source_ids"]["247sports_player_id"] = str(extra["p247"])
    if extra.get("on3"):
        existing["source_ids"]["on3_rivals_id"] = str(extra["on3"])
    if extra.get("height") and not existing.get("height"):
        existing["height"] = extra["height"]
    if extra.get("weight") and not existing.get("weight"):
        existing["weight"] = extra["weight"]
    if extra.get("hometown_city") and not existing.get("hometown_city"):
        existing["hometown_city"] = extra["hometown_city"]
    if extra.get("hometown_state") and not existing.get("hometown_state"):
        existing["hometown_state"] = extra["hometown_state"]
    if extra.get("college_commit") and not existing.get("college_commit"):
        existing["college_commit"] = extra["college_commit"]
    if extra.get("position") and not existing.get("position"):
        existing["position"] = extra["position"]
    if extra.get("hometown") and not existing.get("hometown"):
        existing["hometown"] = extra["hometown"]


def add_rating(player, row):
    src = row["source"]
    existing = next((r for r in player["ratings"] if r["source"] == src), None)
    if existing:
        if (row.get("stars") or 0) > (existing.get("stars") or 0):
            existing.update({k: v for k, v in row.items() if v is not None})
        return
    player["ratings"].append(row)


def build_board():
    schools: dict[str, dict] = {}
    players: dict[str, dict] = {}

    # 247 first — frozen files only.
    for year in (2027, 2028):
        for r in load_year("247", year):
            hs_name, hs_city, hs_st = parse_247_meta(r.get("hs_meta"))
            hs_name, hs_city, hs_st = apply_img(hs_name, hs_city, hs_st)
            sch = ensure_school(
                schools, hs_name, hs_city, hs_st,
                hs247=r.get("high_school_id"),
                alias=r.get("hs_meta"),
            )
            if not sch:
                continue
            metrics = r.get("metrics") or ""
            height = metrics.split("/")[0].strip() if "/" in metrics else None
            weight = None
            if "/" in metrics:
                try:
                    weight = int(re.sub(r"\D", "", metrics.split("/")[1]))
                except ValueError:
                    weight = None
            dkey, p = lookup_player(players, year, r.get("name") or "", r.get("position"), sch["key"])
            extra = dict(
                p247=r.get("player_id"), height=height, weight=weight,
                college_commit=r.get("college_commit") if r.get("college_commit") not in (None, "N/A") else None,
            )
            if p:
                merge_player_extra(p, position=r.get("position"), **extra)
            else:
                p = new_player(r.get("name"), year, r.get("position"), sch, **extra)
                players[dkey] = p
            add_rating(p, rating_row(
                "247sports_composite", year, r.get("stars"), r.get("rating"),
                r.get("national_rank"), r.get("position_rank"), r.get("state_rank"),
                r.get("position"), r.get("hs_meta"), r.get("url"),
            ))

    print(f"247 core schools={len(schools)} players={len(players)}")

    espn_unmatched = []
    for year in (2027, 2028):
        for r in load_year("espn", year):
            hs_name, hs_city, hs_st = apply_img(r.get("hs_name"), r.get("hs_city"), r.get("hs_state"))
            sk = school_key(hs_name, hs_st, hs_city) if hs_name and hs_st else None
            dkey, p = lookup_player(
                players, r.get("class_year") or year, r.get("full_name") or "", r.get("position"), sk
            )
            ht = r.get("height")
            height = ht if isinstance(ht, str) and "-" in str(ht) else inches_to_height(ht)
            extra = dict(
                espn_id=r.get("espn_id"), height=height, weight=r.get("weight"),
                hometown_city=r.get("hometown_city"), hometown_state=r.get("hometown_state"),
                hometown=", ".join(x for x in (r.get("hometown_city"), r.get("hometown_state")) if x) or None,
            )
            if p:
                merge_player_extra(p, **extra)
                sch = schools[p["_school_key"]]
                if r.get("hs_zip") and not sch.get("zip"):
                    sch["zip"] = pad_zip(r.get("hs_zip"))
                if r.get("hs_city") and not sch.get("city"):
                    sch["city"] = r.get("hs_city")
                if r.get("hs_address") and not sch.get("address"):
                    sch["address"] = r.get("hs_address")
                add_rating(p, rating_row(
                    "espn", year, espn_stars(r.get("grade")), r.get("grade"),
                    r.get("national_rank"), r.get("position_rank"), r.get("state_rank"),
                    r.get("position"), r.get("hs_name"), r.get("profile"),
                ))
            else:
                espn_unmatched.append((year, r, extra, hs_name, hs_city, hs_st))

    on3_unmatched = []
    type_map = {
        "On3": "on3_rivals",
        "Rivals": "on3_rivals",
        "Industry": "on3_industry",
        "247": "247sports",
        "Espn": "espn",
    }
    for year in (2027, 2028):
        for r in load_year("on3", year):
            hs_name = r.get("hs_name") or r.get("hs_full") or ""
            mascot = r.get("hs_mascot")
            if mascot and hs_name.lower().endswith(" " + mascot.lower()):
                hs_name = hs_name[: -(len(mascot) + 1)].strip()
            st = r.get("state")
            city_guess = None
            if r.get("hs_slug"):
                parts = r["hs_slug"].split("-")
                if len(parts) >= 2:
                    city_guess = " ".join(parts[:-1]).title()
            hs_name, city_guess, st = apply_img(hs_name, city_guess, st)
            ht_city, ht_st = parse_hometown(r.get("hometown"))
            sk = school_key(hs_name, st, city_guess) if hs_name and st else None
            dkey, p = lookup_player(
                players, r.get("class_year") or year, r.get("name") or "", r.get("position"), sk
            )
            extra = dict(
                on3=r.get("key"), height=r.get("height"), weight=r.get("weight"),
                hometown_city=ht_city, hometown_state=ht_st, hometown=r.get("hometown"),
                college_commit=(r.get("college_slug") or "").replace("-", " ").title() if r.get("committed") else None,
            )
            if p:
                merge_player_extra(p, **extra)
                sch = schools[p["_school_key"]]
                if mascot and not sch.get("mascot"):
                    sch["mascot"] = mascot
                if city_guess and not sch.get("city"):
                    sch["city"] = city_guess
            else:
                on3_unmatched.append((year, r, extra, hs_name, city_guess, st, mascot))
                continue
            seen = set()
            for rt in r.get("ratings") or []:
                src = type_map.get(rt.get("type"))
                if not src or src in seen:
                    continue
                if src == "espn" and p["source_ids"].get("espn_id"):
                    continue
                if src == "247sports":
                    continue
                seen.add(src)
                add_rating(p, rating_row(
                    src, rt.get("classYear") or year, rt.get("stars"), rt.get("rating"),
                    rt.get("overallRank"), rt.get("positionRank"), rt.get("stateRank"),
                    rt.get("positionAbbr") or r.get("position"),
                    r.get("hs_full") or r.get("hs_name"),
                    rt.get("link") or r.get("profile"),
                ))

    print(f"matched overlay espn_unmatched={len(espn_unmatched)} on3_unmatched={len(on3_unmatched)}")

    def extra_candidate(year, name, position, hs_name, city, state, grade=None, stars=None):
        if not name or not real_school_name(hs_name):
            return None
        if not state:
            return None
        key = school_key(hs_name, state, city)
        new_school_flag = key not in schools
        return {
            "year": int(year),
            "name": name,
            "position": position,
            "hs_name": hs_name,
            "city": city,
            "state": state,
            "key": key,
            "new_school": new_school_flag,
            "grade": grade or 0,
            "stars": stars or 0,
        }

    pool = []
    espn_by_dkey = {}
    for year, r, extra, hs_name, hs_city, hs_st in espn_unmatched:
        cand = extra_candidate(year, r.get("full_name"), r.get("position"), hs_name, hs_city, hs_st, grade=r.get("grade") or 0)
        if not cand:
            continue
        cand["kind"] = "espn"
        cand["row"] = r
        cand["extra"] = extra
        pool.append(cand)
        espn_by_dkey[dedupe_key(year, r.get("full_name") or "", r.get("position"))] = cand

    for year, r, extra, hs_name, city, st, mascot in on3_unmatched:
        dkey = dedupe_key(year, r.get("name") or "", r.get("position"))
        if dkey in espn_by_dkey:
            espn_by_dkey[dkey]["on3_row"] = r
            espn_by_dkey[dkey]["on3_extra"] = extra
            espn_by_dkey[dkey]["mascot"] = mascot
            continue
        stars = 0
        for rt in r.get("ratings") or []:
            if rt.get("stars"):
                stars = max(stars, int(rt["stars"]))
        cand = extra_candidate(year, r.get("name"), r.get("position"), hs_name, city, st, stars=stars)
        if not cand:
            continue
        cand["kind"] = "on3"
        cand["row"] = r
        cand["extra"] = extra
        cand["mascot"] = mascot
        pool.append(cand)

    # Prefer new-school extras; fill class-year quotas then remaining school slots.
    new_pool = [c for c in pool if c["new_school"]]
    new_pool.sort(key=lambda c: (-(c["grade"] or 0), -(c["stars"] or 0), c["year"], c["name"] or ""))

    added_2027 = 0
    added_2028 = 0
    used_new_keys = set()
    used_dkeys = set(players)
    chosen = []

    def take(c):
        nonlocal added_2027, added_2028
        if c["key"] in used_new_keys:
            return False
        if c["key"] in schools:
            return False
        dkey = dedupe_key(c["year"], c["name"], c["position"])
        if dkey in used_dkeys:
            return False
        chosen.append(c)
        used_new_keys.add(c["key"])
        used_dkeys.add(dkey)
        if c["year"] == 2027:
            added_2027 += 1
        else:
            added_2028 += 1
        return True

    for c in new_pool:
        if c["year"] == 2027 and added_2027 < EXTRA_2027:
            take(c)
        elif c["year"] == 2028 and added_2028 < EXTRA_2028:
            take(c)

    need_schools = TARGET_SCHOOLS - len(schools) - len(used_new_keys)
    if need_schools > 0:
        for c in new_pool:
            if need_schools <= 0:
                break
            if take(c):
                need_schools -= 1

    print(f"extras chosen {len(chosen)} new_schools={len(used_new_keys)} 2027={added_2027} 2028={added_2028}")

    for c in chosen:
        sch = ensure_school(
            schools, c["hs_name"], c["city"], c["state"],
            zip=(c["row"].get("hs_zip") if c["kind"] == "espn" else None),
            address=(c["row"].get("hs_address") if c["kind"] == "espn" else None),
            mascot=c.get("mascot"),
            alias=c["hs_name"],
        )
        if not sch:
            continue
        extra = c["extra"]
        dkey = dedupe_key(c["year"], c["name"], c["position"])
        if dkey in players:
            continue
        p = new_player(c["name"], c["year"], c["position"], sch, **extra)
        players[dkey] = p
        if c["kind"] == "espn":
            r = c["row"]
            add_rating(p, rating_row(
                "espn", c["year"], espn_stars(r.get("grade")), r.get("grade"),
                r.get("national_rank"), r.get("position_rank"), r.get("state_rank"),
                r.get("position"), r.get("hs_name"), r.get("profile"),
            ))
        if c.get("on3_row") or c["kind"] == "on3":
            r = c.get("on3_row") or c["row"]
            seen = set()
            for rt in r.get("ratings") or []:
                src = type_map.get(rt.get("type"))
                if not src or src in seen or src in ("espn", "247sports"):
                    continue
                seen.add(src)
                add_rating(p, rating_row(
                    src, rt.get("classYear") or c["year"], rt.get("stars"), rt.get("rating"),
                    rt.get("overallRank"), rt.get("positionRank"), rt.get("stateRank"),
                    rt.get("positionAbbr") or r.get("position"),
                    r.get("hs_full") or r.get("hs_name"),
                    rt.get("link") or r.get("profile"),
                ))

    existing_pool = [
        c for c in pool
        if not c["new_school"] and dedupe_key(c["year"], c["name"], c["position"]) not in players
    ]
    existing_pool.sort(key=lambda c: (0 if c["year"] == 2028 else 1, -(c["grade"] or 0), c["name"] or ""))
    fill_i = 0
    while len(players) < TARGET_PLAYERS and fill_i < len(existing_pool):
        c = existing_pool[fill_i]
        fill_i += 1
        chosen.append(c)
        sch = schools.get(c["key"])
        if not sch:
            continue
        extra = c["extra"]
        p = new_player(c["name"], c["year"], c["position"], sch, **extra)
        dkey = dedupe_key(c["year"], c["name"], c["position"])
        players[dkey] = p
        if c["kind"] == "espn":
            r = c["row"]
            add_rating(p, rating_row(
                "espn", c["year"], espn_stars(r.get("grade")), r.get("grade"),
                r.get("national_rank"), r.get("position_rank"), r.get("state_rank"),
                r.get("position"), r.get("hs_name"), r.get("profile"),
            ))
        print(f"fill extra {c['name']} {c['year']} onto {sch['name']}")

    # Assign slugs.
    used_slugs = set()
    for sch in schools.values():
        slug = make_slug(sch["state"], sch["city"], sch["name"])
        if sch["name"] == "IMG Academy":
            slug = "fl-bradenton-img-academy"
        if slug in used_slugs:
            extra = sch["ids_247"].get("high_school_id") or slugify(sch["key"])
            slug = f"{slug}-{extra}"
        sch["id"] = slug
        used_slugs.add(slug)

    # Apply known metadata (zip, maxpreps, coords).
    by_id = {s["id"]: s for s in schools.values()}
    for slug, meta in KNOWN_META.items():
        sch = by_id.get(slug)
        if not sch:
            continue
        if meta.get("zip"):
            sch["zip"] = meta["zip"]
        if meta.get("address"):
            sch["address"] = meta["address"]
        if meta.get("lat") is not None:
            sch["lat"] = meta["lat"]
            sch["lng"] = meta["lng"]
        if meta.get("type"):
            sch["type"] = meta["type"]
        if meta.get("maxpreps"):
            sch["maxpreps"] = {**(sch.get("maxpreps") or {}), **meta["maxpreps"]}
            if meta["maxpreps"].get("mascot"):
                sch["mascot"] = meta["maxpreps"]["mascot"]

    # Seed overlays from any existing import file (maxpreps/zip/lat).
    seed_path = IMPORT / "schools.json"
    if seed_path.exists():
        try:
            seed = json.loads(seed_path.read_text())
            if isinstance(seed, dict):
                seed = seed.get("schools") or []
            by_seed = {}
            for row in seed:
                by_seed[(normalize_school_name(row.get("name") or ""), (row.get("state") or "").upper())] = row
                if row.get("id"):
                    by_seed[row["id"]] = row
            for sch in schools.values():
                hit = by_seed.get(sch["id"]) or by_seed.get((sch["name_normalized"], sch["state"]))
                if not hit:
                    continue
                if hit.get("zip") and not sch.get("zip"):
                    sch["zip"] = pad_zip(hit.get("zip") or hit.get("zip5"))
                if hit.get("lat") is not None and sch.get("lat") is None:
                    sch["lat"] = hit["lat"]
                    sch["lng"] = hit.get("lng")
                if hit.get("address") and not sch.get("address"):
                    sch["address"] = hit["address"]
                if hit.get("maxpreps") and not (sch.get("maxpreps") or {}).get("schoolId"):
                    sch["maxpreps"] = hit["maxpreps"]
                    if hit["maxpreps"].get("mascot"):
                        sch["mascot"] = hit["maxpreps"]["mascot"]
        except Exception as e:
            print("seed overlay skip", e)

    # Zip centroids for coords.
    zips = {}
    if ZIP_PATH.exists():
        zips = json.loads(ZIP_PATH.read_text())
    for sch in schools.values():
        if sch.get("lat") is None and sch.get("zip") and sch["zip"] in zips:
            sch["lat"], sch["lng"] = zips[sch["zip"]]

    # Attach recruits and score talent.
    for p in players.values():
        sch = schools[p.pop("_school_key")]
        # hometown string
        if not p.get("hometown") and p.get("hometown_city"):
            ht = p["hometown_city"]
            if p.get("hometown_state"):
                ht += f", {p['hometown_state']}"
            p["hometown"] = ht
        stars = official_stars(p["ratings"])
        p["talent_points"] = round(player_points(stars), 4)
        p["sources"] = [r["source"] for r in p["ratings"]]
        sch["recruits"].append(p)

    for sch in schools.values():
        recs = sch["recruits"]
        talent = sum(r.get("talent_points") or 0 for r in recs)
        s5 = s4 = s3 = 0
        for r in recs:
            b = badge_stars(official_stars(r["ratings"]))
            if b >= 5:
                s5 += 1
            elif b == 4:
                s4 += 1
            elif b == 3:
                s3 += 1
        sch["talent_score"] = round(talent, 2)
        sch["recruit_count"] = len(recs)
        sch["star_buckets"] = {"stars5": s5, "stars4": s4, "stars3": s3}
        cc = defaultdict(int)
        for r in recs:
            cc[str(r["class_year"])] += 1
        sch["class_counts"] = dict(cc)

    empty_keys = [k for k, s in schools.items() if not s.get("recruits")]
    for k in empty_keys:
        print("drop empty school", schools[k]["name"], schools[k].get("id"))
        del schools[k]
    by_id = {s["id"]: s for s in schools.values()}

    for slug, (tal, count) in OFFICIAL_TALENT.items():
        sch = by_id.get(slug)
        if not sch:
            # try after slug assign — by_id already filled
            continue
        sch["talent_score"] = tal
        if count is not None:
            sch["recruit_count"] = count

    # Force zip-null five.
    for sch in schools.values():
        if force_zip_null(sch["name"], sch["city"], sch["state"]):
            sch["zip"] = None
            if sch.get("maxpreps"):
                sch["maxpreps"]["zip"] = None

    n2027 = sum(1 for p in players.values() if p["class_year"] == 2027)
    n2028 = sum(1 for p in players.values() if p["class_year"] == 2028)
    print(f"board schools={len(schools)} players={len(players)} 2027={n2027} 2028={n2028}")
    img = by_id.get("fl-bradenton-img-academy")
    if img:
        print(f"IMG talent={img['talent_score']} recruits={img['recruit_count']} listed={len(img['recruits'])}")
    return schools, players


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def parse_kickoff(date_iso: str, details: str):
    t = inner_text(details or "").lower()
    tba = (not t) or t in ("tba", "tbd", "time tba", "time tbd")
    if tba:
        return f"{date_iso}T19:00:00", True
    if t in ("noon",):
        return f"{date_iso}T12:00:00", False
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*([ap])m?$", t)
    if not m:
        return f"{date_iso}T19:00:00", True
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    ap = m.group(3)
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return f"{date_iso}T{h:02d}:{mi:02d}:00", False


def date_from_slug(slug: str) -> str | None:
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", slug)
    if not m:
        return None
    mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_url_sides(url: str):
    m = re.search(r"maxpreps\.com/([^/]+)/football/game/([^/]+)/(\d{1,2}-\d{1,2}-\d{4})", url)
    if not m:
        return None
    region, slug, dslug = m.group(1), m.group(2), m.group(3)
    date_iso = date_from_slug(dslug)
    parts = slug.split("-vs-")
    if len(parts) != 2:
        return None
    default_st = region.upper() if region != "inter-state" and len(region) == 2 else None

    def side_state(part: str):
        toks = part.split("-")
        if len(toks) >= 2 and toks[-1].upper() in STATE_SET:
            return toks[-1].upper()
        return default_st

    return {
        "away_state": side_state(parts[0]),
        "home_state": side_state(parts[1]),
        "date": date_iso,
        "default_state": default_st,
    }


def parse_contests(html: str) -> list[dict]:
    out = []
    chunks = re.split(r"(?=<li class=\"c\")", html)
    for chunk in chunks:
        m = re.search(r'data-contest-id="([0-9a-f-]{36})"', chunk, re.I)
        if not m:
            continue
        cid = m.group(1).lower()
        href_m = re.search(r'href="(https://www\.maxpreps\.com/[^"]+/football/game/[^"]+)"', chunk)
        if not href_m:
            continue
        url = htmlmod.unescape(href_m.group(1))
        names = []
        for nm in re.findall(r'<div class="name"[^>]*>(.*?)</div>', chunk, re.S):
            names.append(real_school_name(inner_text(nm)))
        names = [n for n in names if n]
        if len(names) < 2:
            continue
        mp_ids = re.findall(r"school-mascot/./././([0-9a-f-]{36})", chunk, re.I)
        det_m = re.search(r'<div class="details"[^>]*>(.*?)</div>', chunk, re.S)
        details = inner_text(det_m.group(1)) if det_m else ""
        meta = parse_url_sides(url) or {}
        date_iso = meta.get("date")
        if not date_iso or date_iso not in WEEK_DATES:
            continue
        away_name, home_name = names[0], names[1]
        if not real_school_name(away_name) or not real_school_name(home_name):
            continue
        kickoff, tba = parse_kickoff(date_iso, details)
        out.append({
            "contest_id": cid,
            "maxpreps_game_url": url.split("?")[0] + f"?c={cid}",
            "kickoff_local": kickoff,
            "is_time_tba": tba,
            "is_neutral": False,
            "away_name": away_name,
            "home_name": home_name,
            "away_mp": mp_ids[0] if len(mp_ids) > 0 else None,
            "home_mp": mp_ids[1] if len(mp_ids) > 1 else None,
            "away_state": meta.get("away_state"),
            "home_state": meta.get("home_state"),
            "city_hint": None,
        })
    return out


def fetch_scoreboard(st: str, dslug: str) -> tuple[str, str, str]:
    url = f"https://www.maxpreps.com/{st}/football/scores/?date={dslug}"
    cache_p = CACHE / f"{st}-{dslug}.html"
    if cache_p.exists() and cache_p.stat().st_size > 1000:
        return st, dslug, cache_p.read_text("utf-8", "replace")
    try:
        text = http_get_text(url, timeout=25)
        cache_p.parent.mkdir(parents=True, exist_ok=True)
        cache_p.write_text(text)
        return st, dslug, text
    except Exception as e:
        return st, dslug, f"ERROR:{e}"


def scrape_week_games() -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(st.lower(), d) for st in US_STATES for d in DATE_SLUGS]
    games_by_id = {}
    print(f"scraping {len(jobs)} MaxPreps state scoreboards (cached under {CACHE})")
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(fetch_scoreboard, st, d) for st, d in jobs]
        for fut in as_completed(futs):
            st, dslug, text = fut.result()
            done += 1
            if text.startswith("ERROR:"):
                if done % 20 == 0:
                    print(f"  {done}/{len(jobs)} {st} {dslug} fail {text[:80]}", flush=True)
                continue
            parsed = parse_contests(text)
            for g in parsed:
                games_by_id[g["contest_id"]] = g
            if done % 25 == 0:
                print(f"  {done}/{len(jobs)} unique games {len(games_by_id)}", flush=True)
    print(f"scraped unique week games {len(games_by_id)}")
    return list(games_by_id.values())


def load_seed_games() -> list[dict]:
    p = IMPORT / "games.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return data.get("games") or []
    except Exception:
        return []


def match_school(schools_by_id, by_key, by_mp, by_norm_state, name, state, mp_id):
    if mp_id and mp_id in by_mp:
        return by_mp[mp_id]
    if is_img(name):
        return schools_by_id.get("fl-bradenton-img-academy")
    st = (state or "").upper()
    key = school_key(name, st, None) if st else None
    if key and key in by_key:
        return by_key[key]
    norm = normalize_school_name(name)
    if st:
        hits = by_norm_state.get((st, norm)) or []
        if len(hits) == 1:
            return hits[0]
        # prefix
        for sch in hits:
            return sch
        for sch in schools_by_id.values():
            if sch["state"] == st and (
                sch["name_normalized"] == norm
                or sch["name_normalized"].startswith(norm)
                or norm.startswith(sch["name_normalized"])
            ):
                if sch["name_normalized"] and norm:
                    return sch
    return None


def side_payload(sch, name, city, state, mp_id, talent_lookup):
    if sch:
        talent = sch.get("talent_score") or 0
        zipc = sch.get("zip")
        return {
            "maxpreps_id": (sch.get("maxpreps") or {}).get("schoolId") or mp_id,
            "site_id": sch["id"],
            "name": sch["name"],
            "city": sch.get("city") or city or "",
            "state": sch.get("state") or state or "",
            "zip": zipc,
            "talent_score": talent,
            "mapped": True,
        }
    return {
        "maxpreps_id": mp_id,
        "site_id": None,
        "name": name,
        "city": city or "",
        "state": (state or "").upper(),
        "zip": None,
        "talent_score": 0,
        "mapped": False,
    }


def attach_maxpreps(sch, mp_id, name):
    if not sch or not mp_id:
        return
    mp = sch.get("maxpreps") or {}
    if mp.get("schoolId"):
        return
    st = (sch.get("state") or "").lower()
    city = slugify(sch.get("city") or "")
    nm = slugify(sch.get("name") or "")
    url = f"https://www.maxpreps.com/{st}/{city}/{nm}/" if st and city and nm else ""
    sch["maxpreps"] = {
        "schoolId": mp_id,
        "canonicalUrl": url,
        "formattedName": f"{sch['name']} ({sch.get('city')}, {sch.get('state')})",
        "zip": sch.get("zip"),
        "mascot": sch.get("mascot"),
    }


def build_games(schools: dict) -> list[dict]:
    schools_by_id = {s["id"]: s for s in schools.values()}
    by_key = {s["key"]: s for s in schools.values()}
    by_mp = {}
    by_norm_state = defaultdict(list)
    for s in schools.values():
        by_norm_state[(s["state"], s["name_normalized"])].append(s)
        sid = (s.get("maxpreps") or {}).get("schoolId")
        if sid:
            by_mp[sid] = s

    scraped = scrape_week_games()
    # Merge seed showcase if scrape missed them.
    seed = load_seed_games()
    have = {g["contest_id"] for g in scraped}
    for sg in seed:
        cid = sg.get("contest_id")
        if cid and cid not in have:
            scraped.append({
                "contest_id": cid,
                "maxpreps_game_url": sg.get("maxpreps_game_url"),
                "kickoff_local": sg.get("kickoff_local"),
                "is_time_tba": False,
                "is_neutral": sg.get("is_neutral") or False,
                "away_name": sg.get("away", {}).get("name"),
                "home_name": sg.get("home", {}).get("name"),
                "away_mp": sg.get("away", {}).get("maxpreps_id"),
                "home_mp": sg.get("home", {}).get("maxpreps_id"),
                "away_state": sg.get("away", {}).get("state"),
                "home_state": sg.get("home", {}).get("state"),
                "seed": sg,
            })
            have.add(cid)

    rows = []
    for g in scraped:
        if g.get("seed"):
            # Re-score seed sides against the new board.
            sg = g["seed"]
            home_s = match_school(
                schools_by_id, by_key, by_mp, by_norm_state,
                sg["home"]["name"], sg["home"].get("state"), sg["home"].get("maxpreps_id"),
            )
            away_s = match_school(
                schools_by_id, by_key, by_mp, by_norm_state,
                sg["away"]["name"], sg["away"].get("state"), sg["away"].get("maxpreps_id"),
            )
            # Preserve explicit unmapped DeLand if seed said unmapped and school has
            # no maxpreps — actually map if we have the school on the board.
            home = side_payload(home_s, sg["home"]["name"], sg["home"].get("city"), sg["home"].get("state"), sg["home"].get("maxpreps_id"), None)
            away = side_payload(away_s, sg["away"]["name"], sg["away"].get("city"), sg["away"].get("state"), sg["away"].get("maxpreps_id"), None)
            if not home["mapped"]:
                home["mapped"] = False
                home["site_id"] = None
                home["talent_score"] = 0
            if not away["mapped"]:
                away["mapped"] = False
                away["site_id"] = None
                away["talent_score"] = 0
            combined = round((home["talent_score"] or 0) + (away["talent_score"] or 0), 2)
            rows.append({
                "contest_id": g["contest_id"],
                "maxpreps_game_url": g.get("maxpreps_game_url"),
                "kickoff_local": g.get("kickoff_local"),
                "is_neutral": False,
                "home": home,
                "away": away,
                "combined_talent": combined,
                "mapped_sides": int(home["mapped"]) + int(away["mapped"]),
                "home_score": None,
                "away_score": None,
                "is_time_tba": g.get("is_time_tba") or False,
            })
            continue

        away_s = match_school(
            schools_by_id, by_key, by_mp, by_norm_state,
            g["away_name"], g.get("away_state"), g.get("away_mp"),
        )
        home_s = match_school(
            schools_by_id, by_key, by_mp, by_norm_state,
            g["home_name"], g.get("home_state"), g.get("home_mp"),
        )
        if is_img_subteam_url(g.get("maxpreps_game_url")):
            if away_s and away_s.get("id") == "fl-bradenton-img-academy":
                away_s = None
            if home_s and home_s.get("id") == "fl-bradenton-img-academy":
                home_s = None
        attach_maxpreps(away_s, g.get("away_mp"), g["away_name"])
        attach_maxpreps(home_s, g.get("home_mp"), g["home_name"])
        if away_s and g.get("away_mp"):
            by_mp[g["away_mp"]] = away_s
        if home_s and g.get("home_mp"):
            by_mp[g["home_mp"]] = home_s
        away = side_payload(away_s, g["away_name"], away_s["city"] if away_s else "", g.get("away_state"), g.get("away_mp"), None)
        home = side_payload(home_s, g["home_name"], home_s["city"] if home_s else "", g.get("home_state"), g.get("home_mp"), None)
        if not real_school_name(away["name"]) or not real_school_name(home["name"]):
            continue
        combined = round((home["talent_score"] or 0) + (away["talent_score"] or 0), 2)
        rows.append({
            "contest_id": g["contest_id"],
            "maxpreps_game_url": g.get("maxpreps_game_url"),
            "kickoff_local": g.get("kickoff_local"),
            "is_neutral": False,
            "home": home,
            "away": away,
            "combined_talent": combined,
            "mapped_sides": int(bool(home["mapped"])) + int(bool(away["mapped"])),
            "home_score": None,
            "away_score": None,
            "is_time_tba": g.get("is_time_tba") or False,
        })

    # Dedupe
    uniq = {}
    for r in rows:
        uniq[r["contest_id"]] = r
    rows = list(uniq.values())
    both = sum(1 for r in rows if r["mapped_sides"] == 2)
    print(f"week games {len(rows)} both-sides {both} partial {sum(1 for r in rows if r['mapped_sides']==1)}")

    rows.sort(key=lambda r: (-(r["combined_talent"] or 0), r["home"]["name"], r["away"]["name"]))
    # v1 slate is games that touch the Scout board. Unmapped-vs-unmapped (e.g.
    # IMG Academy Junior National) must not inherit varsity IMG talent.
    ranked = [r for r in rows if r["mapped_sides"] >= 1]
    ranked.sort(key=lambda r: (-(r["combined_talent"] or 0), r["home"]["name"], r["away"]["name"]))
    both_rows = [r for r in ranked if r["mapped_sides"] == 2]
    part_rows = [r for r in ranked if r["mapped_sides"] == 1]
    top = both_rows[:V1_BOTH_SIDES] + part_rows[:V1_PARTIAL]
    have_top = {r["contest_id"] for r in top}
    if len(top) < TOP_GAMES:
        for r in ranked:
            if r["contest_id"] in have_top:
                continue
            top.append(r)
            have_top.add(r["contest_id"])
            if len(top) >= TOP_GAMES:
                break
    # Ensure showcase contests survive the slice if they were parsed.
    for cid in SHOWCASE_CONTESTS:
        if cid in have_top:
            continue
        hit = uniq.get(cid)
        if hit and hit.get("mapped_sides", 0) >= 1:
            top.append(hit)
            have_top.add(cid)
    top.sort(key=lambda r: (-(r["combined_talent"] or 0), r["home"]["name"], r["away"]["name"]))
    top = top[:TOP_GAMES]
    n_both = sum(1 for r in top if r["mapped_sides"] == 2)
    n_part = sum(1 for r in top if r["mapped_sides"] == 1)
    print(f"v1 games-top213 {len(top)} both-sides {n_both} partial {n_part}")
    if top:
        a, h = top[0]["away"]["name"], top[0]["home"]["name"]
        print(f"top game {a} @ {h} {top[0]['combined_talent']}")
        if len(top) > 1:
            print(f"2nd  {top[1]['away']['name']} @ {top[1]['home']['name']} {top[1]['combined_talent']}")
    return top, len(rows), both


def dump_schools(schools: dict) -> list[dict]:
    out = []
    for sch in schools.values():
        recs = []
        for p in sch.get("recruits") or []:
            recs.append({
                "id": p["id"],
                "full_name": p["full_name"],
                "class_year": p["class_year"],
                "position": p.get("position"),
                "height": p.get("height"),
                "weight": p.get("weight"),
                "college_commit": p.get("college_commit"),
                "hometown": p.get("hometown"),
                "hometown_city": p.get("hometown_city"),
                "hometown_state": p.get("hometown_state"),
                "ratings": [
                    {k: v for k, v in r.items() if k != "high_school_name_raw"}
                    for r in p.get("ratings") or []
                ],
                "talent_points": p.get("talent_points"),
                "sources": p.get("sources"),
                "source_ids": p.get("source_ids") or {},
            })
        recs.sort(key=lambda x: (-x["class_year"], x["full_name"]))
        out.append({
            "id": sch["id"],
            "name": sch["name"],
            "city": sch.get("city") or "",
            "state": sch.get("state") or "",
            "zip": sch.get("zip"),
            "zip5": sch.get("zip"),
            "recruit_count": sch.get("recruit_count"),
            "talent_score": sch.get("talent_score"),
            "class_counts": sch.get("class_counts") or {},
            "star_buckets": sch.get("star_buckets") or {},
            "aliases": sch.get("aliases") or [],
            "address": sch.get("address"),
            "lat": sch.get("lat"),
            "lng": sch.get("lng"),
            "type": sch.get("type"),
            "mapped": True,
            "ids_247": sch.get("ids_247") or {"high_school_id": None},
            "maxpreps": sch.get("maxpreps"),
            "recruits": recs,
        })
    out.sort(key=lambda s: (-(s.get("talent_score") or 0), s["name"]))
    return out


def write_outputs(school_rows, games, summary):
    SITE.mkdir(parents=True, exist_ok=True)
    IMPORT.mkdir(parents=True, exist_ok=True)
    payload_schools = json.dumps(school_rows)
    payload_summary = json.dumps(summary, indent=2)
    payload_games = json.dumps({
        "week_start": WEEK_START,
        "week_end": WEEK_END,
        "games": games,
    })
    for dest in (SITE, IMPORT):
        (dest / "schools.json").write_text(payload_schools)
        (dest / "schools.summary.json").write_text(payload_summary)
        (dest / "games-top213.json").write_text(payload_games)
        leftover = dest / "games.json"
        if leftover.exists():
            leftover.unlink()
    print("wrote", SITE, "and", IMPORT, "schools", len(school_rows), "games", len(games))


def main():
    t0 = time.time()
    schools, players = build_board()
    games, week_n, both = build_games(schools)
    school_rows = dump_schools(schools)
    n2027 = sum(1 for p in players.values() if p["class_year"] == 2027)
    n2028 = sum(1 for p in players.values() if p["class_year"] == 2028)
    mp_n = sum(1 for s in school_rows if (s.get("maxpreps") or {}).get("schoolId"))
    zip_n = sum(1 for s in school_rows if s.get("zip"))
    summary = {
        "schools": len(school_rows),
        "players": len(players),
        "class_2027": n2027,
        "class_2028": n2028,
        "maxpreps_ids": mp_n,
        "with_zip": zip_n,
        "week_games_unfiltered": week_n,
        "week_both_sides": both,
        "v1_games": len(games),
        "v1_both_sides": sum(1 for g in games if g.get("mapped_sides") == 2),
        "v1_partial": sum(1 for g in games if g.get("mapped_sides") == 1),
        "canonical_schools": TARGET_SCHOOLS,
        "canonical_players": TARGET_PLAYERS,
        "note": (
            "Scout 247+Rivals+ESPN 2027/2028 frozen ingest. "
            f"v1 /games is games-top213.json ({TOP_GAMES} games, "
            f"{V1_BOTH_SIDES} both-sides / {V1_PARTIAL} partial) for {WEEK_START}..{WEEK_END}. "
            "Never load games.json. Unknown opponents dropped. One-sided talent kept."
        ),
    }
    write_outputs(school_rows, games, summary)
    print("elapsed", round(time.time() - t0, 1), "s")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
