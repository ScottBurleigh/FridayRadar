#!/usr/bin/env python3
"""FridayRadar ingest: ESPN + 247Sports + On3/Rivals + MaxPreps → data/fridayradar.json."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"
TMP_RAW = Path("/tmp/ingest-raw")
AS_OF = datetime.now(timezone.utc).strftime("%Y-%m-%d")
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

STAR_POINTS = {5: 98, 4: 85, 3: 70, 2: 55, 1: 40, 0: 25}
MIN_CLASS = 2027

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


def http_get(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_text(url: str, timeout: int = 30) -> str:
    return http_get(url, timeout).decode("utf-8", "replace")


def http_get_json(url: str, timeout: int = 30):
    return json.loads(http_get_text(url, timeout))


def normalize_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"[.’']", "", n)
    n = n.replace(".", "")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def normalize_school_name(name: str) -> str:
    n = name.lower().replace("&amp;", "and")
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\b(high school|hs|high|school|collegiate|prep school)\b", " ", n)
    n = re.sub(r"[.’']", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def slugify(value: str) -> str:
    n = value.lower().replace("&", "and")
    n = re.sub(r"[^a-z0-9]+", "-", n)
    return n.strip("-")


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


def on3_state_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    m = re.search(r"-([a-z]{2})$", slug)
    if not m:
        return None
    st = m.group(1).upper()
    return st if len(st) == 2 else None


def apply_img_academy(name: str, city: str | None, state: str | None):
    if "img academy" in (name or "").lower() or (name or "").lower().startswith("img "):
        return "Bradenton", "FL"
    return city, state


def attr(item, *path, default=None):
    cur = item
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def player_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(json.loads(path.read_text()).get("players") or [])
    except Exception:
        return 0


def copy_raw():
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "espn").mkdir(exist_ok=True)
    (RAW / "247").mkdir(exist_ok=True)
    (RAW / "on3").mkdir(exist_ok=True)
    for year in (2027, 2028, 2029):
        src = TMP_RAW / "espn" / f"{year}.json"
        if src.exists():
            data = json.loads(src.read_text())
            slim = []
            for it in data.get("items") or []:
                a = it.get("athlete") or {}
                hs = a.get("highSchool") or {}
                addr = hs.get("address") or {}
                ranks = {x.get("name"): x for x in it.get("attributes") or []}
                verbal = None
                for s in it.get("schools") or []:
                    if (s.get("status") or {}).get("id") == 1:
                        verbal = (s.get("team") or {}).get("$ref")
                slim.append({
                    "espn_id": a.get("id"),
                    "full_name": a.get("fullName") or a.get("displayName"),
                    "class_year": it.get("recruitingClass"),
                    "position": attr(a, "position", "abbreviation"),
                    "height": a.get("height"),
                    "weight": a.get("weight"),
                    "hometown_city": attr(a, "hometown", "city"),
                    "hometown_state": attr(a, "hometown", "stateAbbreviation"),
                    "hs_id": hs.get("id"),
                    "hs_name": hs.get("properName") or hs.get("name"),
                    "hs_city": addr.get("city"),
                    "hs_state": addr.get("stateAbbreviation"),
                    "hs_zip": addr.get("zipCode"),
                    "hs_address": addr.get("address1"),
                    "grade": it.get("grade"),
                    "national_rank": attr(ranks.get("rank") or {}, "value"),
                    "position_rank": attr(ranks.get("positionRank") or {}, "value"),
                    "state_rank": attr(ranks.get("stateRank") or {}, "value"),
                    "profile": next((l.get("href") for l in a.get("links") or [] if l.get("href")), None),
                    "verbal_team_ref": verbal,
                })
            dest = RAW / "espn" / f"{year}.json"
            dest.write_text(json.dumps({"year": year, "count": len(slim), "players": slim}))
            print(f"slim espn {year}: {len(slim)}")
        for src_dir, dest_dir in (("247", "247"), ("on3", "on3")):
            s = TMP_RAW / src_dir / f"{year}.json"
            if not s.exists():
                continue
            dest = RAW / dest_dir / f"{year}.json"
            n_in, n_old = player_count(s), player_count(dest)
            if n_in >= n_old:
                dest.write_bytes(s.read_bytes())
                print(f"copy {src_dir} {year} ({n_in})")
            else:
                print(f"keep existing {src_dir} {year} ({n_old} > tmp {n_in})")


def load_year(kind: str, year: int):
    p = RAW / kind / f"{year}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("players") or []


PLACEHOLDER_SCHOOL = re.compile(
    r"^\s*(unknown|tba|tbd|n/?a|na|opponent|varsity\s*opponent)\s*$",
    re.I,
)


def real_school_name(name: str | None) -> str | None:
    n = re.sub(r"\s+", " ", (name or "").strip())
    if not n:
        return None
    if PLACEHOLDER_SCHOOL.match(n) or "varsity opponent" in n.lower():
        return None
    return n


def school_key(name: str, state: str | None) -> str:
    st = (state or "NA").upper()
    return f"{st}|{normalize_school_name(name)}"


def merge_all():
    schools: dict[str, dict] = {}
    players: dict[str, dict] = {}  # dedupe key → player
    ratings: list[dict] = []
    sources_status = []

    def ensure_school(name, state, city=None, zipc=None, address=None, mascot=None,
                      hs247=None, aliases=None, espn_hs_id=None):
        city, state = apply_img_academy(name, city, state)
        if not name or not state:
            return None
        key = school_key(name, state)
        rec = schools.get(key)
        if not rec:
            rec = {
                "key": key,
                "name": name if "high" in name.lower() or "prep" in name.lower() or "academy" in name.lower() else name,
                "name_normalized": normalize_school_name(name),
                "aliases": [],
                "mascot": mascot,
                "city": city or "",
                "state": state.upper(),
                "zip": pad_zip(zipc),
                "address": address,
                "lat": None,
                "lng": None,
                "type": None,
                "maxpreps": None,
                "ids_247": {"high_school_id": hs247},
                "espn_hs_id": espn_hs_id,
            }
            schools[key] = rec
        else:
            if city and not rec["city"]:
                rec["city"] = city
            if zipc and not rec["zip"]:
                rec["zip"] = pad_zip(zipc)
            if address and not rec["address"]:
                rec["address"] = address
            if mascot and not rec["mascot"]:
                rec["mascot"] = mascot
            if hs247 and not rec["ids_247"]["high_school_id"]:
                rec["ids_247"]["high_school_id"] = str(hs247)
            if espn_hs_id and not rec.get("espn_hs_id"):
                rec["espn_hs_id"] = espn_hs_id
        for al in aliases or []:
            if al and al not in rec["aliases"] and normalize_school_name(al) != rec["name_normalized"]:
                rec["aliases"].append(al)
        display = name
        # Prefer ESPN-style "X High School" when we have a short name
        if rec["name"] and "high school" in name.lower() and "high school" not in rec["name"].lower():
            rec["name"] = name
        elif not rec["name"]:
            rec["name"] = display
        return rec

    def upsert_player(full_name, class_year, position, school_rec, **extra):
        if not full_name or not class_year or int(class_year) < MIN_CLASS or not school_rec:
            return None
        class_year = int(class_year)
        dkey = f"{class_year}|{normalize_name(full_name)}|{pos_family(position)}"
        existing = players.get(dkey)
        if existing:
            # HS name/state is a tie-break, not a hard match requirement
            if extra.get("espn_id"):
                existing["source_ids"]["espn_id"] = str(extra["espn_id"])
            if extra.get("p247"):
                existing["source_ids"]["247sports_player_id"] = str(extra["p247"])
            if extra.get("on3"):
                existing["source_ids"]["on3_rivals_id"] = str(extra["on3"])
            if extra.get("height") and not existing["height"]:
                existing["height"] = extra["height"]
            if extra.get("weight") and not existing["weight"]:
                existing["weight"] = extra["weight"]
            if extra.get("hometown_city") and not existing["hometown_city"]:
                existing["hometown_city"] = extra["hometown_city"]
            if extra.get("hometown_state") and not existing["hometown_state"]:
                existing["hometown_state"] = extra["hometown_state"]
            if extra.get("college_commit") and not existing["college_commit"]:
                existing["college_commit"] = extra["college_commit"]
            if extra.get("position") and not existing["position"]:
                existing["position"] = extra["position"]
            existing["_school_keys"].add(school_rec["key"])
            return existing
        pid = None
        if extra.get("espn_id"):
            pid = f"espn-{extra['espn_id']}"
        elif extra.get("p247"):
            pid = f"247-{extra['p247']}"
        elif extra.get("on3"):
            pid = f"on3-{extra['on3']}"
        else:
            pid = f"p-{dkey.replace('|', '-')}"
        rec = {
            "id": pid,
            "full_name": full_name,
            "class_year": class_year,
            "position": position,
            "height": extra.get("height"),
            "weight": extra.get("weight"),
            "hometown_city": extra.get("hometown_city"),
            "hometown_state": extra.get("hometown_state"),
            "high_school_key": school_rec["key"],
            "_school_keys": {school_rec["key"]},
            "college_commit": extra.get("college_commit"),
            "source_ids": {},
        }
        if extra.get("espn_id"):
            rec["source_ids"]["espn_id"] = str(extra["espn_id"])
        if extra.get("p247"):
            rec["source_ids"]["247sports_player_id"] = str(extra["p247"])
        if extra.get("on3"):
            rec["source_ids"]["on3_rivals_id"] = str(extra["on3"])
        players[dkey] = rec
        return rec

    def add_rating(player, source, class_year, stars, rating, national_rank, position_rank,
                   state_rank, position, hs_raw, profile):
        if not player:
            return
        ratings.append({
            "player_id": player["id"],
            "source": source,
            "class_year": int(class_year) if class_year else player["class_year"],
            "as_of": AS_OF,
            "national_rank": int(national_rank) if national_rank not in (None, "") else None,
            "position_rank": int(position_rank) if position_rank not in (None, "") else None,
            "state_rank": int(state_rank) if state_rank not in (None, "") else None,
            "stars": stars,
            "rating": float(rating) if rating not in (None, "") else None,
            "position": position,
            "high_school_name_raw": hs_raw,
            "profile_url": profile,
        })

    espn_counts = {}
    for year in (2027, 2028):
        rows = load_year("espn", year)
        espn_counts[str(year)] = len(rows)
        for r in rows:
            city, st = apply_img_academy(r.get("hs_name") or "", r.get("hs_city"), r.get("hs_state"))
            sch = ensure_school(
                r.get("hs_name") or "Unknown",
                st,
                city=city,
                zipc=r.get("hs_zip"),
                address=r.get("hs_address"),
                espn_hs_id=r.get("hs_id"),
            )
            ht = r.get("height")
            height = ht if isinstance(ht, str) and "-" in str(ht) else inches_to_height(ht)
            p = upsert_player(
                r.get("full_name"), r.get("class_year"), r.get("position"), sch,
                espn_id=r.get("espn_id"), height=height, weight=r.get("weight"),
                hometown_city=r.get("hometown_city"), hometown_state=r.get("hometown_state"),
            )
            add_rating(
                p, "espn", r.get("class_year"), espn_stars(r.get("grade")), r.get("grade"),
                r.get("national_rank"), r.get("position_rank"), r.get("state_rank"),
                r.get("position"), r.get("hs_name"), r.get("profile"),
            )
    sources_status.append({
        "id": "espn",
        "label": "ESPN recruiting API",
        "status": "live",
        "detail": "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/recruiting/{year}/athletes",
        "counts": espn_counts,
    })

    c247 = {}
    for year in (2027, 2028):
        rows = load_year("247", year)
        c247[str(year)] = len(rows)
        for r in rows:
            hs_name, hs_city, hs_st = parse_247_meta(r.get("hs_meta"))
            city, st = apply_img_academy(hs_name or "", hs_city, hs_st)
            sch = ensure_school(hs_name or "Unknown", st, city=city, hs247=r.get("high_school_id"),
                                aliases=[r.get("hs_meta")] if r.get("hs_meta") else None)
            metrics = r.get("metrics") or ""
            height = metrics.split("/")[0].strip() if "/" in metrics else None
            weight = None
            if "/" in metrics:
                try:
                    weight = int(re.sub(r"\D", "", metrics.split("/")[1]))
                except ValueError:
                    weight = None
            p = upsert_player(
                r.get("name"), year, r.get("position"), sch,
                p247=r.get("player_id"), height=height, weight=weight,
                college_commit=r.get("college_commit") if r.get("college_commit") not in (None, "N/A") else None,
            )
            add_rating(
                p, "247sports_composite", year, r.get("stars"), r.get("rating"),
                r.get("national_rank"), r.get("position_rank"), r.get("state_rank"),
                r.get("position"), r.get("hs_meta"), r.get("url"),
            )
    sources_status.append({
        "id": "247sports",
        "label": "247Sports Composite",
        "status": "live-partial" if sum(c247.values()) < 200 else "live",
        "detail": "HTML composite ranking pages (CSS icon-starsolid yellow). Page=2+ XHR + gzip; Page=1 often 406. Never the gated JSON API.",
        "counts": c247,
    })

    on3c = {}
    for year in (2027, 2028):
        rows = load_year("on3", year)
        on3c[str(year)] = len(rows)
        for r in rows:
            st = r.get("state") or on3_state_from_slug(r.get("hs_slug"))
            hs_name = r.get("hs_name") or r.get("hs_full") or "Unknown"
            mascot = r.get("hs_mascot")
            if mascot and hs_name.lower().endswith(" " + mascot.lower()):
                hs_name = hs_name[: -(len(mascot) + 1)].strip()
            ht_city, ht_st = parse_hometown(r.get("hometown"))
            # HS from On3 token+slug state (hometown can lag after transfers)
            city_guess = None
            if r.get("hs_slug"):
                parts = r["hs_slug"].split("-")
                if len(parts) >= 2:
                    city_guess = " ".join(parts[:-1]).title()
            city, st = apply_img_academy(hs_name, city_guess, st)
            sch = ensure_school(
                hs_name, st, city=city, mascot=r.get("hs_mascot"),
                aliases=[r.get("hs_name"), r.get("hs_full"), r.get("hs_slug")],
            )
            p = upsert_player(
                r.get("name"), r.get("class_year") or year, r.get("position"), sch,
                on3=r.get("key"), height=r.get("height"), weight=r.get("weight"),
                hometown_city=ht_city, hometown_state=ht_st,
                college_commit=(r.get("college_slug") or "").replace("-", " ").title() if r.get("committed") else None,
            )
            type_map = {
                "On3": "on3_rivals",
                "Rivals": "on3_rivals",
                "Industry": "on3_industry",
                "247": "247sports",
                "Espn": "espn",
            }
            seen_src = set()
            for rt in r.get("ratings") or []:
                src = type_map.get(rt.get("type"))
                if not src or src in seen_src:
                    # Prefer On3 over Rivals when both map to on3_rivals — first On3 then skip Rivals if already set
                    continue
                if src == "espn" and p and p["source_ids"].get("espn_id"):
                    # keep ESPN API row as canonical espn rating
                    continue
                seen_src.add(src)
                profile = rt.get("link") or r.get("profile")
                add_rating(
                    p, src, rt.get("classYear") or year, rt.get("stars"), rt.get("rating"),
                    rt.get("overallRank"), rt.get("positionRank"), rt.get("stateRank"),
                    rt.get("positionAbbr") or r.get("position"),
                    r.get("hs_full") or r.get("hs_name"),
                    profile,
                )
    sources_status.append({
        "id": "on3",
        "label": "On3/Rivals own list",
        "status": "live",
        "detail": "https://www.on3.com/rivals/rankings/player/football/{year}/ — SSR payload (own + industry + 247/ESPN profile URLs).",
        "counts": on3c,
    })

    # Prefer ESPN HS when a player was merged across sources with conflicting HS keys
    for p in players.values():
        keys = list(p["_school_keys"])
        p["high_school_key"] = keys[0]
        # if any key has zip/address (ESPN), prefer it
        ranked = sorted(keys, key=lambda k: (
            0 if schools[k].get("zip") else 1,
            0 if "high school" in schools[k]["name"].lower() else 1,
        ))
        p["high_school_key"] = ranked[0]
        del p["_school_keys"]

    return schools, players, ratings, sources_status


def write_zip_centroids(needed_zips: set[str]):
    src = Path("/tmp/uszips-raw.json")
    if not src.exists():
        print("zip source missing")
        return
    rows = json.loads(src.read_text())
    out = {}
    for r in rows:
        z = pad_zip(r.get("zip_code"))
        if not z:
            continue
        lat, lng = r.get("latitude"), r.get("longitude")
        if lat in (None, "") or lng in (None, ""):
            continue
        try:
            out[z] = [round(float(lat), 5), round(float(lng), 5)]
        except (TypeError, ValueError):
            continue
    (OUT / "zip-centroids.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"zip centroids {len(out)}")


def read_build_id() -> str:
    html = http_get_text("https://www.maxpreps.com/ga/buford/buford-wolves/", timeout=40)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        data = json.loads(m.group(1))
        bid = str(data.get("buildId") or "").strip()
        if bid:
            return bid
    m = re.search(r'"buildId":"([^"]+)"', html)
    if not m:
        raise RuntimeError("MaxPreps buildId not found")
    return m.group(1).replace("\\n", "").strip()


def maxpreps_candidates(school: dict) -> list[str]:
    st = (school.get("state") or "").lower()
    city = slugify(school.get("city") or "")
    name = slugify(school.get("name") or "")
    name = (
        name.replace("-high-school", "")
        .replace("-high", "")
        .replace("saint-", "st-")
        .replace("-academy", "")
    )
    # keep academy for IMG
    if "img" in (school.get("name") or "").lower():
        name = "img-academy"
        city = "bradenton"
        st = "fl"
    mascot = slugify(school.get("mascot") or "")
    paths = []
    if st and city:
        if mascot:
            paths.append(f"/{st}/{city}/{city}-{mascot}/")
            paths.append(f"/{st}/{city}/{name}-{mascot}/")
        paths.append(f"/{st}/{city}/{name}/")
        paths.append(f"/{st}/{city}/{city}/")
        if "img" in name or st == "fl" and city == "bradenton":
            paths.append("/fl/bradenton/img-academy-ascenders/")
            paths.append("/fl/bradenton/img-academy/")
        if "frances" in name:
            paths.append("/md/baltimore/st-frances-academy-panthers/")
            paths.append("/md/baltimore/st-frances-panthers/")
        if "aquinas" in name:
            paths.append("/fl/fort-lauderdale/st-thomas-aquinas-raiders/")
        if "mater-dei" in name or "mater dei" in (school.get("name") or "").lower():
            paths.append("/ca/santa-ana/mater-dei-monarchs/")
        if "gorman" in name:
            paths.append("/nv/las-vegas/bishop-gorman-gaels/")
        if "buford" in name or city == "buford":
            paths.append("/ga/buford/buford-wolves/")
        if "grayson" in name:
            paths.append("/ga/loganville/grayson-rams/")
        if "gainesville" in name and st == "ga":
            paths.append("/ga/gainesville/gainesville-red-elephants/")
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:8]


def enrich_maxpreps(schools: dict, players: dict):
    # preliminary talent to pick which schools to match
    pts = defaultdict(float)
    by_id_ratings = defaultdict(list)
    # ratings not yet keyed — talent approx: count * 40 as fallback, better count espn grade later
    for p in players.values():
        pts[p["high_school_key"]] += 1
    ranked_keys = sorted(pts, key=lambda k: -pts[k])[:90]
    print(f"maxpreps matching {len(ranked_keys)} schools")

    try:
        build_id = read_build_id()
        print("maxpreps buildId", build_id)
    except Exception as e:
        print("maxpreps buildId fail", e)
        return {
            "id": "maxpreps",
            "label": "MaxPreps school home + football wall schedule",
            "status": "blocked",
            "detail": f"Could not read buildId: {e}",
            "counts": {"matched": 0, "games": 0},
        }, []

    matched = 0
    games = {}
    mp_by_id = {}

    def ingest_game(card, page_school_id, page_path):
        if not card:
            return
        if card.get("isDeleted"):
            return
        cid = card.get("contestId")
        if not cid:
            return
        teams = card.get("teams") or []
        if len(teams) < 2:
            return
        names = [real_school_name(t.get("schoolName")) for t in teams]
        if any(n is None for n in names):
            return
        hat = card.get("homeAwayType")
        page_team = teams[0]
        opp = teams[1]
        if page_team.get("isDeleted") or opp.get("isDeleted"):
            return
        # homeAwayType 0 home / 1 away / 2 neutral from page team's POV
        if hat == 1:
            home_t, away_t = opp, page_team
        else:
            home_t, away_t = page_team, opp
        kickoff = card.get("timestamp")
        if kickoff and str(kickoff)[:10] < "2026-08-01":
            return

        def school_from_team(t):
            name = real_school_name(t.get("schoolName"))
            if not name:
                return None
            url = t.get("teamCanonicalUrl") or ""
            tid = t.get("teamId")
            if tid and tid in mp_by_id:
                rec = mp_by_id[tid]
                if rec.get("name") and not real_school_name(rec.get("name")):
                    rec["name"] = name
                    rec["name_normalized"] = normalize_school_name(name)
                return rec
            m = re.search(r"maxpreps\.com/([a-z]{2})/([^/]+)/([^/]+)/", url)
            city = ""
            st = ""
            if m:
                st, city_slug, rest = m.group(1).upper(), m.group(2), m.group(3)
                city = city_slug.replace("-", " ").title()
            key = school_key(name, st or "NA")
            if key not in schools:
                schools[key] = {
                    "key": key,
                    "name": name,
                    "name_normalized": normalize_school_name(name),
                    "aliases": [],
                    "mascot": None,
                    "city": city,
                    "state": st or "NA",
                    "zip": None,
                    "address": None,
                    "lat": None,
                    "lng": None,
                    "type": None,
                    "maxpreps": {"schoolId": tid, "canonicalUrl": url, "formattedName": name} if tid else None,
                    "ids_247": {"high_school_id": None},
                }
            rec = schools[key]
            if tid:
                rec["maxpreps"] = rec.get("maxpreps") or {
                    "schoolId": tid,
                    "canonicalUrl": url,
                    "formattedName": name,
                }
                rec["id"] = tid
                mp_by_id[tid] = rec
            return rec

        home = school_from_team(home_t)
        away = school_from_team(away_t)
        if not home or not away:
            return
        if not real_school_name(home.get("name")) or not real_school_name(away.get("name")):
            return
        games[cid] = {
            "id": cid,
            "season": card.get("year") or "26-27",
            "kickoff": card.get("timestamp"),
            "home_school_id": home.get("id") or home["key"],
            "away_school_id": away.get("id") or away["key"],
            "home_score": home_t.get("score") if card.get("hasResult") else None,
            "away_score": away_t.get("score") if card.get("hasResult") else None,
            "is_gow": bool(card.get("isGow")),
            "game_url": card.get("canonicalUrl"),
            "city": None,
            "state": (home.get("state") if hat != 1 else away.get("state")),
            "is_time_tba": bool(card.get("isTimeTba")),
            "home_away_type": 2 if hat == 2 else (0 if hat != 1 else 0),
        }

    def path_from_url(url: str) -> str | None:
        m = re.search(r"maxpreps\.com(/[a-z]{2}/[^/?#]+/[^/?#]+)/?", url or "")
        if not m:
            return None
        p = m.group(1).rstrip("/")
        p = re.sub(r"/football$", "", p)
        return p + "/"

    def find_school(name: str, state: str | None):
        if not name or not state:
            return None
        key = school_key(name, state)
        if key in schools:
            return schools[key]
        norm = normalize_school_name(name)
        st = state.upper()
        for rec in schools.values():
            if rec["state"] == st and rec["name_normalized"] == norm:
                return rec
        # first-token overlap: Buford vs Buford High
        for rec in schools.values():
            if rec["state"] == st and (rec["name_normalized"].startswith(norm) or norm.startswith(rec["name_normalized"])):
                if rec["name_normalized"] and norm:
                    return rec
        return None

    def apply_info(rec, info, path):
        sid = info.get("schoolId")
        rec["id"] = sid
        rec["name"] = info.get("name") or rec["name"]
        rec["city"] = info.get("city") or rec["city"]
        rec["state"] = (info.get("stateCode") or info.get("state") or rec["state"] or "").upper()[:2]
        rec["zip"] = pad_zip(info.get("zip") or info.get("zipCode") or rec.get("zip"))
        rec["address"] = info.get("address") or rec.get("address")
        if info.get("latitude") is not None:
            rec["lat"] = info.get("latitude")
            rec["lng"] = info.get("longitude")
        rec["type"] = info.get("type") or rec.get("type")
        rec["mascot"] = info.get("mascot") or rec.get("mascot")
        rec["maxpreps"] = {
            "schoolId": sid,
            "canonicalUrl": info.get("canonicalUrl") or f"https://www.maxpreps.com{path}",
            "formattedName": info.get("formattedName"),
        }
        mp_by_id[sid] = rec

    def fetch_school_page(path: str):
        url = f"https://www.maxpreps.com/_next/data/{build_id}{path.rstrip('/')}.json"
        payload = http_get_json(url, timeout=10)
        return payload.get("pageProps") or payload

    seeds = [
        "/ga/buford/buford-wolves/",
        "/fl/bradenton/img-academy-ascenders/",
        "/nv/las-vegas/bishop-gorman-gaels/",
        "/ca/santa-ana/mater-dei-monarchs/",
        "/fl/fort-lauderdale/st-thomas-aquinas-raiders/",
        "/md/baltimore/st-frances-academy-panthers/",
        "/ga/loganville/grayson-rams/",
        "/ga/gainesville/gainesville-red-elephants/",
        "/ca/bellflower/st-john-bosco-braves/",
        "/tx/duncanville/duncanville-panthers/",
        "/pa/philadelphia/st-josephs-prep-hawks/",
        "/ca/long-beach/poly-jackrabbits/",
        "/la/new-orleans/brother-martin-crusaders/",
        "/in/indianapolis/lawrence-north-wildcats/",
        "/oh/columbus/st-edward-eagles/",
        "/tx/austin/westlake-chaparrals/",
        "/ga/roswell/blessed-trinity-titans/",
        "/pa/coatesville/coatesville-red-raiders/",
        "/nc/charlotte/mallard-creek-mavericks/",
        "/fl/miami/central-rockets/",
        "/al/hoover/hoover-buccaneers/",
        "/tn/chattanooga/baylor-red-raiders/",
        "/ne/omaha/millard-south-patriots/",
        "/ca/bellflower/st-john-bosco-braves/",
        "/ga/johns-creek/johns-creek-gladiators/",
    ]
    queue = list(dict.fromkeys(seeds))
    seen_paths = set()
    fetched = 0
    max_fetch = 70

    while queue and fetched < max_fetch:
        path = queue.pop(0)
        if path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            pp = fetch_school_page(path)
        except Exception as e:
            print(f"  seed miss {path} {e}", flush=True)
            continue
        fetched += 1
        ctx = pp.get("schoolContext") or {}
        info = ctx.get("schoolInfo") or {}
        if not info.get("schoolId"):
            tc = (pp.get("teamContext") or {}).get("data") or {}
            if tc.get("teamId"):
                info = {
                    "schoolId": tc.get("teamId"),
                    "name": tc.get("schoolName"),
                    "city": tc.get("schoolCity"),
                    "stateCode": tc.get("stateCode"),
                    "zip": tc.get("schoolZipCode"),
                    "address": tc.get("schoolAddress"),
                    "mascot": tc.get("schoolMascot"),
                    "canonicalUrl": tc.get("schoolCanonicalUrl"),
                    "formattedName": tc.get("schoolFormattedName"),
                    "latitude": None,
                    "longitude": None,
                    "type": None,
                }
        if not info.get("schoolId"):
            continue
        rec = find_school(info.get("name") or "", info.get("stateCode") or info.get("state"))
        if rec:
            apply_info(rec, info, path)
            matched += 1
        else:
            # still keep as a MaxPreps-only school so opponents appear in games
            st = (info.get("stateCode") or "")[:2].upper()
            mp_name = real_school_name(info.get("name"))
            if not mp_name:
                continue
            rec = ensure_mp_school = {
                "key": school_key(mp_name, st),
                "name": mp_name,
                "name_normalized": normalize_school_name(mp_name),
                "aliases": [],
                "mascot": info.get("mascot"),
                "city": info.get("city") or "",
                "state": st,
                "zip": pad_zip(info.get("zip") or info.get("zipCode")),
                "address": info.get("address"),
                "lat": info.get("latitude"),
                "lng": info.get("longitude"),
                "type": info.get("type"),
                "maxpreps": None,
                "ids_247": {"high_school_id": None},
            }
            if rec["key"] not in schools:
                schools[rec["key"]] = rec
            rec = schools[rec["key"]]
            apply_info(rec, info, path)

        for nb in pp.get("nearbySchools") or []:
            p2 = path_from_url(nb.get("canonicalUrl") or "")
            if p2 and p2 not in seen_paths:
                queue.append(p2)

        foot = path.rstrip("/") + "/football/"
        try:
            fpp = fetch_school_page(foot)
            sched = (((fpp.get("wallCards") or {}).get("schedule") or {}).get("data")) or []
            featured = fpp.get("featuredGameData")
            if featured:
                ingest_game(featured, info.get("schoolId"), path)
            for card in sched:
                ingest_game(card, info.get("schoolId"), path)
                for t in card.get("teams") or []:
                    p2 = path_from_url(t.get("teamCanonicalUrl") or "")
                    if p2 and p2 not in seen_paths:
                        queue.append(p2)
        except Exception as e:
            print(f"  football fail {path} {e}", flush=True)
        print(f"  maxpreps {fetched}/{max_fetch} matched {matched} games {len(games)} queue {len(queue)}", flush=True)
        time.sleep(0.08)

    print(f"maxpreps matched {matched} games {len(games)}", flush=True)
    status = {
        "id": "maxpreps",
        "label": "MaxPreps school home + football wall schedule",
        "status": "live" if matched else "blocked",
        "detail": "School-home JSON for lat/lng/zip; football page wallCards.schedule (full /schedule pages 504 in this environment). buildId read live.",
        "counts": {"matched": matched, "games": len(games)},
    }
    return status, list(games.values())


def assign_ids(schools: dict):
    for key, sch in schools.items():
        if sch.get("id"):
            continue
        if sch.get("maxpreps") and sch["maxpreps"].get("schoolId"):
            sch["id"] = sch["maxpreps"]["schoolId"]
        else:
            sch["id"] = f"hs-{sch['state'].lower()}-{slugify(sch['name_normalized'] or sch['name'])}"


def fallback_coords(schools: dict, zips: dict):
    for sch in schools.values():
        if sch.get("lat") is not None:
            continue
        z = sch.get("zip")
        if z and z in zips:
            sch["lat"], sch["lng"] = zips[z]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    copy_raw()
    schools, players, ratings, sources = merge_all()
    print(f"merged schools={len(schools)} players={len(players)} ratings={len(ratings)}")

    mp_status, games = enrich_maxpreps(schools, players)
    sources.append(mp_status)

    assign_ids(schools)
    id_by_key = {sch["key"]: sch["id"] for sch in schools.values()}
    for p in players.values():
        sch = schools[p.pop("high_school_key")]
        p["high_school_id"] = sch["id"]
    for g in games:
        g["home_school_id"] = id_by_key.get(g["home_school_id"], g["home_school_id"])
        g["away_school_id"] = id_by_key.get(g["away_school_id"], g["away_school_id"])

    write_zip_centroids(set())
    zips = json.loads((OUT / "zip-centroids.json").read_text())
    fallback_coords(schools, zips)

    school_list = []
    for sch in schools.values():
        school_list.append({
            "id": sch["id"],
            "name": sch["name"],
            "name_normalized": sch["name_normalized"],
            "aliases": sch.get("aliases") or [],
            "mascot": sch.get("mascot"),
            "city": sch.get("city") or "",
            "state": sch.get("state") or "",
            "zip": sch.get("zip"),
            "address": sch.get("address"),
            "lat": sch.get("lat"),
            "lng": sch.get("lng"),
            "type": sch.get("type"),
            "maxpreps": sch.get("maxpreps"),
            "ids_247": sch.get("ids_247") or {"high_school_id": None},
        })

    player_list = list(players.values())
    # drop empty names
    player_list = [p for p in player_list if p.get("full_name")]
    rating_list = [r for r in ratings if r.get("player_id")]

    by_id = {s["id"]: s for s in school_list}
    kept_games = []
    dropped_games = 0
    for g in games:
        home = by_id.get(g.get("home_school_id"))
        away = by_id.get(g.get("away_school_id"))
        if not home or not away:
            dropped_games += 1
            continue
        if not real_school_name(home.get("name")) or not real_school_name(away.get("name")):
            dropped_games += 1
            continue
        if home["id"] == away["id"]:
            dropped_games += 1
            continue
        kept_games.append(g)
    games = kept_games
    print(f"games kept {len(games)} dropped placeholders/unresolved {dropped_games}")
    for src in sources:
        if src.get("id") == "maxpreps" and isinstance(src.get("counts"), dict):
            src["counts"]["games"] = len(games)

    dataset = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "as_of": AS_OF,
            "min_class_year": MIN_CLASS,
            "sources": sources,
            "notes": [
                "High schools are ranked, not colleges. 247/ESPN Team/SCHOOL columns are college commits and are never used as the high school.",
                "Eligible recruits are class_year >= 2027 only.",
                "Player composite stars = average of available source star ratings. School talent = sum of player points.",
                "On3 hometown can lag after transfers; high school comes from the On3 HS token + slug state (e.g. Brewster → Buford GA, not Cedar Hill TX).",
                "Zip filter uses US zip centroids (25-mile haversine) against MaxPreps coords when matched, else the school's zip centroid.",
            ],
        },
        "schools": school_list,
        "players": player_list,
        "ratings": rating_list,
        "games": games,
    }
    dest = OUT / "fridayradar.json"
    dest.write_text(json.dumps(dataset))
    print("wrote", dest, "bytes", dest.stat().st_size)
    states = {s["state"] for s in school_list if s.get("state")}
    print("states", len(states), "schools", len(school_list), "players", len(player_list), "games", len(games))


if __name__ == "__main__":
    main()
