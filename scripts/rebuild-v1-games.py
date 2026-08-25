#!/usr/bin/env python3
"""Rebuild v1 games-top213.json from MaxPreps scoreboard cache + existing Scout board.

Does not rebuild schools.json (keeps the 1,554-school board). Writes two-sided
games only, ranked by geometric mean of home/away talent_score, with a venue
object (home school unless is_neutral). Never writes games.json.
"""
from __future__ import annotations

import html as htmlmod
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
IMPORT = ROOT / "data/import"
CACHE = Path("/tmp/fridayradar-mp-cache")
ZIP_PATH = ROOT / "data/zip-centroids.json"
WEEK_DATES = ("2026-08-26", "2026-08-27", "2026-08-28", "2026-08-29")
HOLLYWOOD_MP = "128d50e8-0ae6-4b71-8506-85fdac103bf3"
# Matchup treated DeLand as unmapped; do not promote it to two-sided.
FORCE_UNMAPPED = {("6be37393-f001-47f2-8ece-2493d6449f51", "home")}


def load_csm():
    spec = importlib.util.spec_from_file_location("csm", ROOT / "scripts/compile-scout-matchup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_contests(html: str, csm) -> list[dict]:
    out = []
    chunks = re.split(r'(?=<li\b[^>]*\bclass="c")', html)
    for chunk in chunks:
        m = re.search(r'data-contest-id(?:-x)?=["\']([0-9a-f-]{36})', chunk, re.I)
        if not m:
            continue
        cid = m.group(1).lower()
        href_m = re.search(r'href="(https://www\.maxpreps\.com/[^"]+/football/game/[^"]+)"', chunk)
        if not href_m:
            continue
        url = htmlmod.unescape(href_m.group(1))
        names = []
        for nm in re.findall(r'<div class="name"[^>]*>(.*?)</div>', chunk, re.S):
            names.append(csm.real_school_name(csm.inner_text(nm)))
        names = [n for n in names if n]
        if len(names) < 2:
            continue
        mp_ids = re.findall(r"school-mascot/./././([0-9a-f-]{36})", chunk, re.I)
        det_m = re.search(r'<div class="details"[^>]*>(.*?)</div>', chunk, re.S)
        details = csm.inner_text(det_m.group(1)) if det_m else ""
        meta = csm.parse_url_sides(url) or {}
        date_iso = meta.get("date")
        if not date_iso or date_iso not in WEEK_DATES:
            continue
        away_name, home_name = names[0], names[1]
        kickoff, tba = csm.parse_kickoff(date_iso, details)
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
            "location": None,
        })
    return out


def contest_tokens_ok(contest: str, school_name: str, csm) -> bool:
    c = set(csm.normalize_school_name(contest).split())
    s = set(csm.normalize_school_name(school_name).split())
    return bool(c) and c.issubset(s)


def zip_for_coords(lat, lng, centroids: dict) -> str | None:
    if lat is None or lng is None:
        return None
    for z, pair in centroids.items():
        if abs(pair[0] - lat) < 1e-5 and abs(pair[1] - lng) < 1e-5:
            return z
    return None


def two_sided_talent(home: float, away: float) -> float:
    if home <= 0 or away <= 0:
        return 0.0
    return round(math.sqrt(home * away), 2)


def side_payload(sch, name, city, state, mp_id) -> dict:
    if sch:
        return {
            "maxpreps_id": ((sch.get("maxpreps") or {}).get("schoolId") or mp_id),
            "site_id": sch["id"],
            "name": sch["name"],
            "city": sch.get("city") or city or "",
            "state": sch.get("state") or state or "",
            "zip": sch.get("zip"),
            "talent_score": sch.get("talent_score") or 0,
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


def home_venue(home_side: dict, home_sch, centroids) -> dict:
    zipc = None
    lat = lng = None
    if home_sch:
        lat = home_sch.get("lat")
        lng = home_sch.get("lng")
        zipc = zip_for_coords(lat, lng, centroids) or home_sch.get("zip")
    zipc = zipc or home_side.get("zip")
    return {
        "city": (home_sch or {}).get("city") or home_side.get("city") or None,
        "state": ((home_sch or {}).get("state") or home_side.get("state") or "").upper() or None,
        "zip": zipc,
        "lat": lat,
        "lng": lng,
        "name": (home_sch or {}).get("name") or home_side.get("name") or None,
        "source": "home_school",
    }


def venue_for(home_side: dict, home_sch, is_neutral: bool, location, centroids) -> dict:
    """Contest/play-at location when MaxPreps has one; otherwise the HOME school only."""
    loc = location or {}
    has_site = bool(loc.get("city") or loc.get("state") or loc.get("zip") or loc.get("name"))
    if is_neutral and has_site:
        return {
            "city": loc.get("city") or None,
            "state": (loc.get("state") or "").upper() or None,
            "zip": loc.get("zip") or None,
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "name": loc.get("name") or None,
            "source": "contest_location",
        }
    return home_venue(home_side, home_sch, centroids)


def rebuild() -> list[dict]:
    csm = load_csm()
    schools = json.loads((SITE / "schools.json").read_text())
    centroids = json.loads(ZIP_PATH.read_text()) if ZIP_PATH.exists() else {}
    for s in schools:
        s["name_normalized"] = s.get("name_normalized") or csm.normalize_school_name(s["name"])
    by_id = {s["id"]: s for s in schools}
    by_mp: dict[str, dict] = {}
    by_norm: dict[str, list] = {}
    by_norm_st: dict[tuple, list] = {}
    for s in schools:
        mp = (s.get("maxpreps") or {}).get("schoolId")
        if mp:
            by_mp[mp.lower()] = s
        by_norm.setdefault(s["name_normalized"], []).append(s)
        by_norm_st.setdefault(((s.get("state") or "").upper(), s["name_normalized"]), []).append(s)

    hollywood = by_id.get("fl-hollywood-chaminade-madonna")
    west = by_id.get("ca-west-hills-chaminade")
    if west and (west.get("maxpreps") or {}).get("schoolId") == HOLLYWOOD_MP:
        west["maxpreps"]["schoolId"] = None
        by_mp.pop(HOLLYWOOD_MP, None)
    if hollywood:
        hollywood["maxpreps"] = hollywood.get("maxpreps") or {}
        hollywood["maxpreps"]["schoolId"] = HOLLYWOOD_MP
        by_mp[HOLLYWOOD_MP] = hollywood

    def match(name, state, mp_id):
        if mp_id and mp_id.lower() in by_mp:
            sch = by_mp[mp_id.lower()]
            if contest_tokens_ok(name, sch["name"], csm):
                return sch
        if csm.is_img(name):
            return by_id.get("fl-bradenton-img-academy")
        st = (state or "").upper()
        norm = csm.normalize_school_name(name)
        if st:
            hits = by_norm_st.get((st, norm)) or []
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                return sorted(hits, key=lambda x: -(x.get("talent_score") or 0))[0]
        hits = by_norm.get(norm) or []
        if len(hits) == 1:
            return hits[0]
        cand = [s for s in schools if s["name_normalized"] == norm]
        if len(cand) == 1:
            return cand[0]
        return None

    games_by_id = {}
    if CACHE.exists():
        for p in CACHE.glob("*.html"):
            for g in parse_contests(p.read_text("utf-8", "replace"), csm):
                games_by_id[g["contest_id"]] = g

    # Keep previously imported two-sided contests if the cache missed them.
    old_path = SITE / "games-top213.json"
    if old_path.exists():
        old = json.loads(old_path.read_text())
        for og in old.get("games") or []:
            cid = og.get("contest_id")
            if not cid or cid in games_by_id:
                continue
            games_by_id[cid] = {
                "contest_id": cid,
                "maxpreps_game_url": og.get("maxpreps_game_url"),
                "kickoff_local": og.get("kickoff_local"),
                "is_time_tba": og.get("is_time_tba") or False,
                "is_neutral": og.get("is_neutral") or False,
                "away_name": og.get("away", {}).get("name"),
                "home_name": og.get("home", {}).get("name"),
                "away_mp": og.get("away", {}).get("maxpreps_id"),
                "home_mp": og.get("home", {}).get("maxpreps_id"),
                "away_state": og.get("away", {}).get("state"),
                "home_state": og.get("home", {}).get("state"),
                "location": og.get("location"),
                "seed_sides": og,
            }

    rows = []
    for g in games_by_id.values():
        if g.get("seed_sides"):
            sg = g["seed_sides"]
            home_s = by_id.get(sg.get("home", {}).get("site_id") or "") if sg.get("home", {}).get("mapped") else None
            away_s = by_id.get(sg.get("away", {}).get("site_id") or "") if sg.get("away", {}).get("mapped") else None
            if not home_s:
                home_s = match(g["home_name"], g.get("home_state"), g.get("home_mp"))
            if not away_s:
                away_s = match(g["away_name"], g.get("away_state"), g.get("away_mp"))
        else:
            away_s = match(g["away_name"], g.get("away_state"), g.get("away_mp")) or match(g["away_name"], None, g.get("away_mp"))
            home_s = match(g["home_name"], g.get("home_state"), g.get("home_mp")) or match(g["home_name"], None, g.get("home_mp"))
        cid = g["contest_id"]
        if (cid, "home") in FORCE_UNMAPPED:
            home_s = None
        if (cid, "away") in FORCE_UNMAPPED:
            away_s = None
        home = side_payload(home_s, g["home_name"], (home_s or {}).get("city"), g.get("home_state"), g.get("home_mp"))
        away = side_payload(away_s, g["away_name"], (away_s or {}).get("city"), g.get("away_state"), g.get("away_mp"))
        ht = home.get("talent_score") or 0
        at = away.get("talent_score") or 0
        if not home["mapped"] or not away["mapped"] or ht <= 0 or at <= 0:
            continue
        if not csm.real_school_name(home["name"]) or not csm.real_school_name(away["name"]):
            continue
        ts = two_sided_talent(ht, at)
        combined = round(ht + at, 2)
        is_neutral = bool(g.get("is_neutral"))
        venue = venue_for(home, home_s, is_neutral, g.get("location"), centroids)
        rows.append({
            "contest_id": cid,
            "maxpreps_game_url": g.get("maxpreps_game_url"),
            "kickoff_local": g.get("kickoff_local"),
            "is_neutral": is_neutral,
            "home": home,
            "away": away,
            "combined_talent": combined,
            "two_sided_talent": ts,
            "mapped_sides": 2,
            "home_score": None,
            "away_score": None,
            "is_time_tba": bool(g.get("is_time_tba")),
            "venue": venue,
            "location": g.get("location"),
        })

    rows.sort(key=lambda r: (-(r["two_sided_talent"] or 0), -(r["combined_talent"] or 0), r["home"]["name"], r["away"]["name"]))
    return rows


def main():
    rows = rebuild()
    payload = json.dumps({
        "week_start": "2026-08-26",
        "week_end": "2026-08-29",
        "rank_by": "two_sided_talent",
        "games": rows,
    })
    for dest in (SITE, IMPORT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "games-top213.json").write_text(payload)
        leftover = dest / "games.json"
        if leftover.exists():
            leftover.unlink()
        summary_path = dest / "schools.summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            summary["v1_games"] = len(rows)
            summary["v1_both_sides"] = len(rows)
            summary["v1_partial"] = 0
            summary["rank_by"] = "two_sided_talent"
            summary["note"] = (
                "Scout 247+Rivals+ESPN 2027/2028 frozen ingest. "
                f"v1 /games is games-top213.json ({len(rows)} two-sided games, 0 partial) "
                "for 2026-08-26..2026-08-29 ranked by geometric mean of home/away talent. "
                "Never load games.json."
            )
            summary_path.write_text(json.dumps(summary, indent=2))
    print(f"wrote {len(rows)} two-sided games")
    for i, r in enumerate(rows[:3], 1):
        print(i, r["away"]["name"], "@", r["home"]["name"], r["two_sided_talent"], r["combined_talent"], r["venue"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
