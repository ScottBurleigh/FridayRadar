#!/usr/bin/env python3
"""Build a Scout+Matchup *seed* under data/import/ from known official scores
plus real recruits already on disk. Does not invent player names or re-fetch 247.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FR = json.loads((ROOT / "data/fridayradar.json").read_text())
OUT = ROOT / "data" / "import"
OUT.mkdir(parents=True, exist_ok=True)

OLD = {s["id"]: s for s in FR["schools"]}
PLAYERS_BY_HS: dict[str, list] = {}
for p in FR["players"]:
    PLAYERS_BY_HS.setdefault(p["high_school_id"], []).append(p)
RATINGS_BY_P: dict[str, list] = {}
for r in FR["ratings"]:
    RATINGS_BY_P.setdefault(r["player_id"], []).append(r)


def slug(state: str, city: str, name: str) -> str:
    def part(v: str) -> str:
        n = v.lower().replace("&", "and")
        n = re.sub(r"[^a-z0-9]+", "-", n)
        return n.strip("-")
    return f"{part(state)}-{part(city)}-{part(name)}"


def recruits_from(*old_ids: str, limit: int | None = None):
    rows = []
    seen = set()
    for oid in old_ids:
        for p in PLAYERS_BY_HS.get(oid, []):
            if p["id"] in seen:
                continue
            if p.get("class_year", 0) < 2027:
                continue
            seen.add(p["id"])
            hometown = None
            if p.get("hometown_city"):
                hometown = p["hometown_city"]
                if p.get("hometown_state"):
                    hometown += f", {p['hometown_state']}"
            ratings = []
            for r in RATINGS_BY_P.get(p["id"], []):
                ratings.append({
                    "source": r.get("source"),
                    "stars": r.get("stars"),
                    "rating": r.get("rating"),
                    "national_rank": r.get("national_rank"),
                    "position_rank": r.get("position_rank"),
                    "state_rank": r.get("state_rank"),
                    "position": r.get("position") or p.get("position"),
                    "profile_url": r.get("profile_url"),
                })
            rows.append({
                "id": p["id"],
                "full_name": p["full_name"],
                "class_year": p["class_year"],
                "position": p.get("position"),
                "height": p.get("height"),
                "weight": p.get("weight"),
                "college_commit": p.get("college_commit"),
                "hometown": hometown,
                "hometown_city": p.get("hometown_city"),
                "hometown_state": p.get("hometown_state"),
                "ratings": ratings,
                "source_ids": p.get("source_ids") or {},
            })
    rows.sort(key=lambda x: (-x["class_year"], x["full_name"]))
    if limit is not None:
        rows = rows[:limit]
    return rows


def school_from_old(oid: str, **over):
    s = OLD[oid]
    rec = {
        "name": s["name"],
        "city": s.get("city") or "",
        "state": s.get("state") or "",
        "zip": s.get("zip"),
        "zip5": s.get("zip"),
        "aliases": s.get("aliases") or [],
        "address": s.get("address"),
        "lat": s.get("lat"),
        "lng": s.get("lng"),
        "type": s.get("type"),
        "mapped": True,
        "ids_247": s.get("ids_247") or {"high_school_id": None},
        "maxpreps": None,
        "recruits": [],
    }
    if s.get("maxpreps"):
        rec["maxpreps"] = {
            "schoolId": s["maxpreps"].get("schoolId"),
            "canonicalUrl": s["maxpreps"].get("canonicalUrl"),
            "zip": s.get("zip"),
            "mascot": s.get("mascot"),
            "formattedName": s["maxpreps"].get("formattedName"),
            "footballUrl": None,
        }
    rec.update(over)
    return rec


schools = []

# Official Scout top 5 (talent_score / recruit_count from Builder)
schools.append({
    **school_from_old("08f6a8ea-242d-49c2-8282-71a7feb19407"),
    "id": "fl-bradenton-img-academy",
    "name": "IMG Academy",
    "city": "Bradenton",
    "state": "FL",
    "zip": "34210",
    "zip5": "34210",
    "recruit_count": 28,
    "talent_score": 2263.49,
    "lat": 27.443076,
    "lng": -82.597998,
    "address": "5500 34Th St W",
    "type": "Private",
    "maxpreps": {
        "schoolId": "7bdc339f-7cbf-4728-b0c8-ed898929cf68",
        "canonicalUrl": "https://www.maxpreps.com/fl/bradenton/img-academy-ascenders/",
        "zip": "34210",
        "mascot": "Ascenders",
        "formattedName": "IMG Academy (Bradenton, FL)",
        "footballUrl": "https://www.maxpreps.com/fl/bradenton/img-academy-ascenders/football/",
    },
    "recruits": recruits_from("08f6a8ea-242d-49c2-8282-71a7feb19407"),
})

schools.append({
    **school_from_old("c1783fb0-c965-42a0-abe3-41fbe7641303"),
    "id": "md-baltimore-st-frances-academy",
    "name": "St. Frances Academy",
    "recruit_count": 18,
    "talent_score": 1359.84,
    "recruits": recruits_from("c1783fb0-c965-42a0-abe3-41fbe7641303"),
})

schools.append({
    **school_from_old("229cf8e5-737c-418e-8f4e-f3ac3d566af4"),
    "id": "ca-bellflower-st-john-bosco",
    "name": "St. John Bosco",
    "recruit_count": 16,
    "talent_score": 1165,
    "recruits": recruits_from("229cf8e5-737c-418e-8f4e-f3ac3d566af4"),
})

schools.append({
    **school_from_old("2b6b45d3-4465-4750-ba48-a273b674e37c"),
    "id": "ca-santa-ana-mater-dei",
    "name": "Mater Dei",
    "recruit_count": 15,
    "talent_score": 1072.50,
    "recruits": recruits_from("2b6b45d3-4465-4750-ba48-a273b674e37c"),
})

thompson_old = next(s for s in FR["schools"] if s["id"] == "hs-al-thompson")
schools.append({
    **school_from_old("hs-al-thompson"),
    "id": "al-alabaster-thompson",
    "name": "Thompson",
    "city": thompson_old.get("city") or "Alabaster",
    "state": "AL",
    "zip": thompson_old.get("zip") or "35007",
    "zip5": thompson_old.get("zip") or "35007",
    "recruit_count": 13,
    "talent_score": 970,
    "maxpreps": {
        "schoolId": "fd85c43e-1a06-49c8-a805-b2c8fe9588ed",
        "canonicalUrl": "https://www.maxpreps.com/al/alabaster/thompson-warriors/",
        "zip": "35007",
        "mascot": thompson_old.get("mascot") or "Warriors",
        "formattedName": "Thompson (Alabaster, AL)",
        "footballUrl": "https://www.maxpreps.com/al/alabaster/thompson-warriors/football/",
    },
    "recruits": recruits_from("hs-al-thompson"),
})

# Buford — zip 30518 drill-down. Real recruits only; talentScore left unset so
# Scout top-5 order is preserved via explicit talent_score on the official five.
# Rankings prefer talent_score when present; Buford still ranks from imported rows.
schools.append({
    **school_from_old("6d00b044-607e-4dee-aa9b-e1fc2c6a87bc"),
    "id": "ga-buford-buford",
    "name": "Buford",
    "zip": "30518",
    "zip5": "30518",
    "recruits": recruits_from("6d00b044-607e-4dee-aa9b-e1fc2c6a87bc"),
})

# Game-side schools with talent derived from official combined scores
def side(old_id, site_id, name, talent, recruits_old=None, **extra):
    rec = school_from_old(old_id, **extra) if old_id in OLD else {
        "name": name, "city": extra.get("city", ""), "state": extra.get("state", ""),
        "zip": extra.get("zip"), "zip5": extra.get("zip"), "mapped": True,
        "maxpreps": extra.get("maxpreps"), "aliases": [], "recruits": [],
        "lat": extra.get("lat"), "lng": extra.get("lng"), "address": extra.get("address"),
        "type": extra.get("type"), "ids_247": {"high_school_id": None},
    }
    rec["id"] = site_id
    rec["name"] = name
    rec["talent_score"] = talent
    rec["recruit_count"] = extra.get("recruit_count")
    rec["mapped"] = True
    if recruits_old:
        rec["recruits"] = recruits_from(recruits_old)
    return rec

schools.append(side(
    "6e96854a-3ca4-44bb-a6b0-899cf84dfa3d",
    "ut-orem-orem", "Orem", 626.50,
))
schools[-1]["name"] = "Orem"

schools.append(side(
    "hs-al-clay-chalkville",
    "al-pinson-clay-chalkville", "Clay-Chalkville", 295,
    city="Pinson", state="AL", zip="35126",
))
schools[-1]["maxpreps"] = {
    "schoolId": "d10ba1be-e353-4009-bd7b-99311091eeb0",
    "canonicalUrl": "https://www.maxpreps.com/al/pinson/clay-chalkville-cougars/",
    "zip": "35126",
    "mascot": "Cougars",
    "formattedName": "Clay-Chalkville (Pinson, AL)",
}

schools.append(side(
    "cfedd35b-8252-4b69-948f-3a2318cdce69",
    "pa-philadelphia-roman-catholic", "Roman Catholic", 280,
))

schools.append(side(
    "0d4488fa-a03d-47c9-b874-f78523a2e76a",
    "tx-san-antonio-cornerstone-christian", "Cornerstone Christian", 155,
))

schools.append({
    **school_from_old("556cde7f-6469-4bd0-934c-fe78b5949f68"),
    "id": "tx-duncanville-duncanville",
    "name": "Duncanville",
    "mapped": True,
    "recruits": [],
})
schools.append({
    **school_from_old("0bad373d-33a2-45b6-b1d4-6c55e876344c"),
    "id": "tx-allen-allen",
    "name": "Allen",
    "mapped": True,
    "recruits": [],
})

# Five ambiguous zip-null schools (do not invent recruits)
schools.append({
    "id": "fl-fort-lauderdale-american-heritage",
    "name": "American Heritage",
    "city": "Fort Lauderdale",
    "state": "FL",
    "zip": None,
    "zip5": None,
    "mapped": True,
    "recruit_count": 0,
    "talent_score": 0,
    "recruits": [],
    "maxpreps": None,
    "aliases": [],
    "ids_247": {"high_school_id": None},
})
schools.append({
    "id": "az-queen-creek-ala",
    "name": "American Leadership Academy",
    "city": "Queen Creek",
    "state": "AZ",
    "zip": None,
    "zip5": None,
    "mapped": True,
    "recruit_count": 0,
    "talent_score": 0,
    "recruits": [],
    "maxpreps": None,
    "aliases": ["ALA Queen Creek"],
    "ids_247": {"high_school_id": None},
})
schools.append({
    "id": "ky-lexington-lexington-christian-academy",
    "name": "Lexington Christian Academy",
    "city": "Lexington",
    "state": "KY",
    "zip": None,
    "zip5": None,
    "mapped": True,
    "recruit_count": 0,
    "talent_score": 0,
    "recruits": [],
    "maxpreps": None,
    "aliases": [],
    "ids_247": {"high_school_id": None},
})
schools.append({
    "id": "ca-sherman-oaks-notre-dame",
    "name": "Notre Dame",
    "city": "Sherman Oaks",
    "state": "CA",
    "zip": None,
    "zip5": None,
    "mapped": True,
    "recruit_count": 0,
    "talent_score": 0,
    "recruits": [],
    "maxpreps": None,
    "aliases": [],
    "ids_247": {"high_school_id": None},
})
schools.append({
    "id": "tx-san-antonio-roosevelt",
    "name": "Roosevelt",
    "city": "San Antonio",
    "state": "TX",
    "zip": None,
    "zip5": None,
    "mapped": True,
    "recruit_count": 0,
    "talent_score": 0,
    "recruits": [],
    "maxpreps": None,
    "aliases": ["San Antonio Roosevelt"],
    "ids_247": {"high_school_id": None},
})

# Extra mapped sides for the 10-game slate (no invented recruits)
extra_ids = {
    "03c125d3-5255-4e5d-8991-5e543fe741d2": ("nv-las-vegas-bishop-gorman", "Bishop Gorman"),
}
# pull remaining from contest schools
for oid, (sid, name) in extra_ids.items():
    if oid in OLD:
        rec = school_from_old(oid)
        rec["id"] = sid
        rec["name"] = name
        rec["recruits"] = []
        rec["talent_score"] = 0
        rec["recruit_count"] = 0
        schools.append(rec)

# Columbus, DeSoto, STA, Mill Creek, Brookwood, Inglewood, Westlake from current by name
WANT = [
    ("Columbus", "FL", "fl-miami-columbus"),
    ("St. Thomas Aquinas", "FL", "fl-fort-lauderdale-st-thomas-aquinas"),
    ("DeSoto High School", "TX", "tx-desoto-desoto"),
    ("Mill Creek", "GA", "ga-hoschton-mill-creek"),
    ("Brookwood High School", "GA", "ga-snellville-brookwood"),
    ("Inglewood High School", "CA", "ca-inglewood-inglewood"),
    ("Westlake", "TX", "tx-austin-westlake"),
]
have_ids = {s["id"] for s in schools}
for name, st, sid in WANT:
    if sid in have_ids:
        continue
    hit = next((s for s in FR["schools"] if s["name"] == name and s["state"] == st), None)
    if not hit:
        hit = next((s for s in FR["schools"] if name.split()[0].lower() in s["name"].lower() and s["state"] == st), None)
    if hit:
        rec = school_from_old(hit["id"])
        rec["id"] = sid
        rec["name"] = hit["name"] if hit["name"] != "St. Thomas Aquinas" else "St. Thomas Aquinas"
        rec["recruits"] = []
        rec["talent_score"] = 0
        rec["recruit_count"] = 0
        schools.append(rec)
        have_ids.add(sid)

# Dedup by id
uniq = {}
for s in schools:
    uniq[s["id"]] = s
schools = list(uniq.values())

n_players = sum(len(s.get("recruits") or []) for s in schools)
n_2027 = sum(1 for s in schools for r in s.get("recruits") or [] if r["class_year"] == 2027)
n_2028 = sum(1 for s in schools for r in s.get("recruits") or [] if r["class_year"] == 2028)

summary = {
    "schools": len(schools),
    "players": n_players,
    "class_2027": n_2027,
    "class_2028": n_2028,
    "canonical_schools": 1554,
    "canonical_players": 2986,
    "note": "SEED: top Scout schools + Matchup week games until the full 1,554/2,986 dump is imported. Recruits are frozen ingest rows, not invented.",
}

games = {
    "week_start": "2026-08-26",
    "week_end": "2026-08-29",
    "games": [
        {
            "contest_id": "2c7f797f-6730-4bc5-a5a6-9e8a0f7578cb",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/cornerstone-christian-san-antonio-tx-vs-img-academy-bradenton-fl/8-29-2026/?c=2c7f797f-6730-4bc5-a5a6-9e8a0f7578cb",
            "kickoff_local": "2026-08-29T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "0d4488fa-a03d-47c9-b874-f78523a2e76a", "site_id": "tx-san-antonio-cornerstone-christian", "name": "Cornerstone Christian", "city": "San Antonio", "state": "TX", "zip": None, "talent_score": 155, "mapped": True},
            "home": {"maxpreps_id": "7bdc339f-7cbf-4728-b0c8-ed898929cf68", "site_id": "fl-bradenton-img-academy", "name": "IMG Academy", "city": "Bradenton", "state": "FL", "zip": "34210", "talent_score": 2263.49, "mapped": True},
            "combined_talent": 2418.49,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "0812d6d2-cfbd-4414-9acf-ef827a7dcce2",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/mater-dei-santa-ana-ca-vs-orem-ut/8-29-2026/?c=0812d6d2-cfbd-4414-9acf-ef827a7dcce2",
            "kickoff_local": "2026-08-29T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "2b6b45d3-4465-4750-ba48-a273b674e37c", "site_id": "ca-santa-ana-mater-dei", "name": "Mater Dei", "city": "Santa Ana", "state": "CA", "zip": "92707", "talent_score": 1072.50, "mapped": True},
            "home": {"maxpreps_id": "6e96854a-3ca4-44bb-a6b0-899cf84dfa3d", "site_id": "ut-orem-orem", "name": "Orem", "city": "Orem", "state": "UT", "zip": "84057", "talent_score": 626.50, "mapped": True},
            "combined_talent": 1699,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "63dc5024-3f38-4074-8dfb-69e4b76f0e6e",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/roman-catholic-philadelphia-pa-vs-st-john-bosco-bellflower-ca/8-28-2026/?c=63dc5024-3f38-4074-8dfb-69e4b76f0e6e",
            "kickoff_local": "2026-08-28T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "cfedd35b-8252-4b69-948f-3a2318cdce69", "site_id": "pa-philadelphia-roman-catholic", "name": "Roman Catholic", "city": "Philadelphia", "state": "PA", "zip": "19107", "talent_score": 280, "mapped": True},
            "home": {"maxpreps_id": "229cf8e5-737c-418e-8f4e-f3ac3d566af4", "site_id": "ca-bellflower-st-john-bosco", "name": "St. John Bosco", "city": "Bellflower", "state": "CA", "zip": "90706", "talent_score": 1165, "mapped": True},
            "combined_talent": 1445,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "6be37393-f001-47f2-8ece-2493d6449f51",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/deland-fl-vs-st-frances-academy-baltimore-md/8-28-2026/?c=6be37393-f001-47f2-8ece-2493d6449f51",
            "kickoff_local": "2026-08-28T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "c1783fb0-c965-42a0-abe3-41fbe7641303", "site_id": "md-baltimore-st-frances-academy", "name": "St. Frances Academy", "city": "Baltimore", "state": "MD", "zip": "21202", "talent_score": 1359.84, "mapped": True},
            "home": {"maxpreps_id": "a56cc5ad-8455-4ed9-8ecf-4eaa17076fe4", "site_id": None, "name": "DeLand", "city": "DeLand", "state": "FL", "zip": None, "talent_score": 0, "mapped": False},
            "combined_talent": 1359,
            "mapped_sides": 1,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "7a10d443-387c-4437-b97c-0b85afe2484a",
            "maxpreps_game_url": "https://www.maxpreps.com/al/football/game/clay-chalkville-pinson-vs-thompson-alabaster/8-27-2026/?c=7a10d443-387c-4437-b97c-0b85afe2484a",
            "kickoff_local": "2026-08-27T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "d10ba1be-e353-4009-bd7b-99311091eeb0", "site_id": "al-pinson-clay-chalkville", "name": "Clay-Chalkville", "city": "Pinson", "state": "AL", "zip": "35126", "talent_score": 295, "mapped": True},
            "home": {"maxpreps_id": "fd85c43e-1a06-49c8-a805-b2c8fe9588ed", "site_id": "al-alabaster-thompson", "name": "Thompson", "city": "Alabaster", "state": "AL", "zip": "35007", "talent_score": 970, "mapped": True},
            "combined_talent": 1265,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "d8398537-8e3f-41f6-91ef-caa6013687b6",
            "maxpreps_game_url": "https://www.maxpreps.com/tx/football/game/allen-vs-duncanville-panthers-and-pantherettes/8-28-2026/?c=d8398537-8e3f-41f6-91ef-caa6013687b6",
            "kickoff_local": "2026-08-28T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "556cde7f-6469-4bd0-934c-fe78b5949f68", "site_id": "tx-duncanville-duncanville", "name": "Duncanville", "city": "Duncanville", "state": "TX", "zip": "75116", "talent_score": 0, "mapped": True},
            "home": {"maxpreps_id": "0bad373d-33a2-45b6-b1d4-6c55e876344c", "site_id": "tx-allen-allen", "name": "Allen", "city": "Allen", "state": "TX", "zip": "75002", "talent_score": 0, "mapped": True},
            "combined_talent": 0,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "d5ff7e61-ff87-48ff-a6cd-98aa06558cf9",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/bishop-gorman-las-vegas-nv-vs-columbus-miami-fl/8-29-2026/?c=d5ff7e61-ff87-48ff-a6cd-98aa06558cf9",
            "kickoff_local": "2026-08-29T14:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": "03c125d3-5255-4e5d-8991-5e543fe741d2", "site_id": "nv-las-vegas-bishop-gorman", "name": "Bishop Gorman", "city": "Las Vegas", "state": "NV", "zip": "89148", "talent_score": 0, "mapped": True},
            "home": {"maxpreps_id": None, "site_id": "fl-miami-columbus", "name": "Columbus", "city": "Miami", "state": "FL", "zip": None, "talent_score": 0, "mapped": True},
            "combined_talent": 0,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "297a92d7-acdd-4f08-87a7-218b4bff4098",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/desoto-tx-vs-st-thomas-aquinas-fort-lauderdale-fl/8-29-2026/?c=297a92d7-acdd-4f08-87a7-218b4bff4098",
            "kickoff_local": "2026-08-29T18:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": None, "site_id": "tx-desoto-desoto", "name": "DeSoto", "city": "DeSoto", "state": "TX", "zip": None, "talent_score": 0, "mapped": True},
            "home": {"maxpreps_id": None, "site_id": "fl-fort-lauderdale-st-thomas-aquinas", "name": "St. Thomas Aquinas", "city": "Fort Lauderdale", "state": "FL", "zip": None, "talent_score": 0, "mapped": True},
            "combined_talent": 0,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "3c9521b0-574e-4ded-8952-34d8ce982012",
            "maxpreps_game_url": "https://www.maxpreps.com/ga/football/game/brookwood-snellville-vs-mill-creek-hoschton/8-28-2026/?c=3c9521b0-574e-4ded-8952-34d8ce982012",
            "kickoff_local": "2026-08-28T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": None, "site_id": "ga-hoschton-mill-creek", "name": "Mill Creek", "city": "Hoschton", "state": "GA", "zip": None, "talent_score": 0, "mapped": True},
            "home": {"maxpreps_id": None, "site_id": "ga-snellville-brookwood", "name": "Brookwood", "city": "Snellville", "state": "GA", "zip": None, "talent_score": 0, "mapped": True},
            "combined_talent": 0,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
        {
            "contest_id": "ea93fb09-e414-4b17-b942-53370b0cee26",
            "maxpreps_game_url": "https://www.maxpreps.com/inter-state/football/game/inglewood-ca-vs-westlake-austin-tx/8-28-2026/?c=ea93fb09-e414-4b17-b942-53370b0cee26",
            "kickoff_local": "2026-08-28T19:00:00",
            "is_neutral": False,
            "away": {"maxpreps_id": None, "site_id": "ca-inglewood-inglewood", "name": "Inglewood", "city": "Inglewood", "state": "CA", "zip": None, "talent_score": 0, "mapped": True},
            "home": {"maxpreps_id": None, "site_id": "tx-austin-westlake", "name": "Westlake", "city": "Austin", "state": "TX", "zip": None, "talent_score": 0, "mapped": True},
            "combined_talent": 0,
            "mapped_sides": 2,
            "home_score": None, "away_score": None,
        },
    ],
}

(OUT / "schools.json").write_text(json.dumps(schools, indent=2))
(OUT / "schools.summary.json").write_text(json.dumps(summary, indent=2))
(OUT / "games.json").write_text(json.dumps(games, indent=2))
print("wrote", OUT, "schools", len(schools), "players", n_players, "games", len(games["games"]))
