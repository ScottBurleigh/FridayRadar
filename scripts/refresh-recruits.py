#!/usr/bin/env python3
"""Refresh 2027+ recruits onto the existing FridayRadar school list.

Reads data/raw/{247,espn,on3}/{2027,2028,2029}.json, maps each listed player
onto the current 1554 schools, and recomputes talent_score from player points.
Does not add schools, rewrite GOTW, or apply OFFICIAL_TALENT.

Matching order (first unique hit wins; 2+ hits → unmapped, never guessed):
  247 high_school_id, On3 crosswalk hs_key, school_key, unique name+state,
  unique prefix, unique word-start containment, unique district-prefix strip.
"""
from __future__ import annotations

import importlib.util
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
IMPORT = ROOT / "data" / "import"
RAW = ROOT / "data" / "raw"
YEARS = (2027, 2028, 2029)

DISTRICT_PREFIXES = (
    "fort bend",
    "katy",
    "klein",
    "conroe",
    "humble",
    "alvin",
    "galena park",
    "sheldon",
    "northside",
    "north east",
    "spring branch",
    "round rock",
    "lewisville",
    "mansfield",
    "arlington",
)

# ESPN extra rows that are the same campus as the 247-id FridayRadar school.
EXTRA_CANONICAL = {
    "tx-denton-john-h-guyer-high-school": "tx-denton-denton-guyer",
    "oh-massillon-washington-high-school": "oh-massillon-massillon-washington",
    "wi-green-bay-notre-dame-de-la-baie-academy": "wi-green-bay-notre-dame-academy",
    "ne-omaha-westside-high-school": "ne-omaha-omaha-westside",
    "tx-killeen-shoemaker-high-school": "tx-killeen-killeen-shoemaker",
    "oh-columbus-saint-francis-de-sales-high-school": "oh-columbus-st-francis-de-sales",
    "la-baton-rouge-catholic-high-school": "la-baton-rouge-baton-rouge-catholic",
    "il-park-ridge-maine-township-south-high-school": "il-park-ridge-maine-south",
    "fl-tallahassee-james-s-rickards-high-school": "fl-tallahassee-rickards",
    "la-metairie-archbishop-rummel-school-for-boys": "la-metairie-archbishop-rummel",
    "tx-conroe-oak-ridge-high-school": "tx-conroe-conroe-oak-ridge",
    "sd-pierre-theodore-f-riggs-high-school": "sd-pierre-t-f-riggs",
    "md-indian-head-lackey-high-school": "md-indian-head-henry-e-lackey",
}


def load_canonical_ids() -> dict[str, str]:
    out = dict(EXTRA_CANONICAL)
    text = (ROOT / "src" / "lib" / "school-ids.ts").read_text()
    for m in re.finditer(r'"([^"]+)": "([^"]+)"', text):
        src, dest = m.group(1), m.group(2)
        if src.startswith("http") or dest.startswith("http"):
            continue
        out[src] = dest
    return out

spec = importlib.util.spec_from_file_location(
    "csm", ROOT / "scripts" / "compile-scout-matchup.py"
)
csm = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(csm)


def contains_at_word_start(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return haystack == needle or haystack.startswith(needle + " ") or f" {needle}" in f" {haystack} "


def strip_district_prefix(norm: str) -> str:
    for prefix in DISTRICT_PREFIXES:
        if norm.startswith(prefix + " ") and len(norm) > len(prefix) + 3:
            return norm[len(prefix) :].strip()
    return norm


class SchoolIndex:
    def __init__(self, schools: list[dict], crosswalk: dict | None):
        self.schools = schools
        self.by_id = {s["id"]: s for s in schools}
        self.by_247: dict[str, dict] = {}
        self.by_on3: dict[str, dict] = {}
        self.by_key: dict[str, list[dict]] = defaultdict(list)
        self.by_norm_state: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.by_state: dict[str, list[dict]] = defaultdict(list)
        self.canonical = load_canonical_ids()
        for s in schools:
            hid = str((s.get("ids_247") or {}).get("high_school_id") or "").strip()
            if hid:
                self.by_247[hid] = s
            key = csm.school_key(s.get("name") or "", s.get("state"), s.get("city"))
            s["_match_key"] = key
            self.by_key[key].append(s)
            st = (s.get("state") or "").upper()
            nn = s.get("name_normalized") or csm.normalize_school_name(s.get("name") or "")
            self.by_norm_state[(st, nn)].append(s)
            self.by_state[st].append(s)
            for alias in s.get("aliases") or []:
                if isinstance(alias, str) and alias in self.by_id:
                    continue
                if isinstance(alias, str) and alias.strip():
                    an = csm.normalize_school_name(alias)
                    if an and an != nn:
                        self.by_norm_state[(st, an)].append(s)
        cw_schools = ((crosswalk or {}).get("schools") or {}) if crosswalk else {}
        for sid, row in cw_schools.items():
            sch = self.by_id.get(sid)
            if not sch:
                continue
            on3 = ((row.get("sources") or {}).get("on3"))
            if on3 not in (None, "", 0):
                self.by_on3[str(on3)] = sch

    def unique(self, hits: list[dict]) -> dict | None:
        ids = {h["id"] for h in hits if h}
        if len(ids) == 1:
            return self.canonical_school(self.by_id[next(iter(ids))])
        return None

    def map_school(
        self,
        hs_name: str | None,
        city: str | None,
        state: str | None,
        hs247: str | None = None,
        on3_key=None,
    ) -> dict | None:
        hs_name, city, state = csm.apply_img(hs_name, city, state)
        if csm.is_img(hs_name):
            return self.by_id.get("fl-bradenton-img-academy")
        # Name/city/state first so a stale 247 campus id cannot pin a transfer
        # to the old school when the listing already shows the new campus.
        if hs_name and csm.real_school_name(hs_name) and (state or "").upper():
            st = (state or "").upper()
            key = csm.school_key(hs_name, st, city)
            uniq = self.unique(self.by_key.get(key) or [])
            if uniq:
                return uniq
            key_nocity = csm.school_key(hs_name, st, None)
            if key_nocity != key:
                uniq = self.unique(self.by_key.get(key_nocity) or [])
                if uniq:
                    return uniq
            norm = csm.normalize_school_name(hs_name)
            if norm:
                uniq = self.unique(self.by_norm_state.get((st, norm)) or [])
                if uniq:
                    return uniq
                state_schools = self.by_state.get(st) or []
                prefix = [
                    s
                    for s in state_schools
                    if s.get("name_normalized")
                    and (
                        s["name_normalized"].startswith(norm)
                        or norm.startswith(s["name_normalized"])
                    )
                ]
                uniq = self.unique(prefix)
                if uniq:
                    return uniq
                if len(norm) >= 5:
                    contain = [
                        s
                        for s in state_schools
                        if contains_at_word_start(s.get("name_normalized") or "", norm)
                        or contains_at_word_start(norm, s.get("name_normalized") or "")
                    ]
                    uniq = self.unique(contain)
                    if uniq:
                        return uniq
                    stripped_src = strip_district_prefix(norm)
                    district = [
                        s
                        for s in state_schools
                        if strip_district_prefix(s.get("name_normalized") or "") == stripped_src
                        or (s.get("name_normalized") or "") == stripped_src
                    ]
                    uniq = self.unique(district)
                    if uniq:
                        return uniq
                if city:
                    city_n = csm.normalize_school_name(city)
                    city_hits = [
                        s
                        for s in state_schools
                        if csm.normalize_school_name(s.get("city") or "") == city_n
                        and (
                            contains_at_word_start(s.get("name_normalized") or "", norm)
                            or contains_at_word_start(norm, s.get("name_normalized") or "")
                            or strip_district_prefix(s.get("name_normalized") or "")
                            == strip_district_prefix(norm)
                        )
                    ]
                    uniq = self.unique(city_hits)
                    if uniq:
                        return uniq
        if hs247:
            hit = self.by_247.get(str(hs247))
            if hit:
                return self.canonical_school(hit)
        if on3_key not in (None, "", 0):
            hit = self.by_on3.get(str(on3_key))
            if hit:
                return self.canonical_school(hit)
        return None

    def canonical_school(self, sch: dict | None) -> dict | None:
        if not sch:
            return None
        dest = self.canonical.get(sch["id"])
        if dest and dest in self.by_id:
            return self.by_id[dest]
        return sch


def load_crosswalk() -> dict:
    for p in (SITE / "schools-crosswalk.json", IMPORT / "schools-crosswalk.json"):
        if p.exists():
            try:
                return json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
    return {}


def attach_on3_ratings(player: dict, row: dict, year: int) -> None:
    type_map = {
        "On3": "on3_rivals",
        "Rivals": "on3_rivals",
        "Industry": "on3_industry",
        "247": "247sports",
        "Espn": "espn",
    }
    seen = set()
    for rt in row.get("ratings") or []:
        src = type_map.get(rt.get("type"))
        if not src or src in seen:
            continue
        if src == "espn" and player["source_ids"].get("espn_id"):
            continue
        if src == "247sports":
            continue
        seen.add(src)
        csm.add_rating(
            player,
            csm.rating_row(
                src,
                rt.get("classYear") or year,
                rt.get("stars"),
                rt.get("rating"),
                rt.get("overallRank"),
                rt.get("positionRank"),
                rt.get("stateRank"),
                rt.get("positionAbbr") or row.get("position"),
                row.get("hs_full") or row.get("hs_name"),
                rt.get("link") or row.get("profile"),
            ),
        )


class PlayerBoard:
    def __init__(self):
        self.players: dict[str, dict] = {}
        self.by_name_year: dict[tuple[int, str], list[str]] = defaultdict(list)
        self.merges = 0
        self.transfers = 0
        self.transfer_rows: list[dict] = []

    def _index(self, dkey: str, player: dict) -> None:
        ny = (int(player["class_year"]), csm.normalize_name(player["full_name"]))
        if dkey not in self.by_name_year[ny]:
            self.by_name_year[ny].append(dkey)

    def lookup(self, year, name, position, school_key_val: str | None):
        year = int(year)
        nn = csm.normalize_name(name or "")
        fam = csm.pos_family(position)
        # Same name + HS + class (user merge rule).
        if school_key_val:
            for dkey in self.by_name_year.get((year, nn), []):
                p = self.players[dkey]
                if p.get("_school_key") == school_key_val:
                    return dkey, p
        keys = self.by_name_year.get((year, nn), [])
        fam_hits = [
            k
            for k in keys
            if csm.pos_family(self.players[k].get("position")) == fam
        ]
        # Same person transferring campuses: unique name+class+position family.
        # Different position family at another HS is a different person (Jamir Lee).
        if len(fam_hits) == 1:
            return fam_hits[0], self.players[fam_hits[0]]
        if len(keys) == 1:
            p = self.players[keys[0]]
            if fam == "UNK" or csm.pos_family(p.get("position")) in (fam, "UNK"):
                return keys[0], p
        dkey = csm.dedupe_key(year, name, position)
        if school_key_val:
            dkey = f"{dkey}|{school_key_val}"
        return dkey, self.players.get(dkey)

    def put(self, dkey: str, player: dict, school: dict, *, is_new: bool) -> dict:
        old_key = player.get("_school_key")
        school_key_val = school.get("key") or school.get("_match_key")
        player["_school_key"] = school_key_val
        player["_site_id"] = school["id"]
        if not is_new and old_key and old_key != school_key_val:
            self.transfers += 1
            self.transfer_rows.append(
                {
                    "name": player["full_name"],
                    "class_year": player["class_year"],
                    "from_key": old_key,
                    "to_school": school["id"],
                    "to_name": school["name"],
                }
            )
        if is_new:
            self.players[dkey] = player
            self._index(dkey, player)
        else:
            self.merges += 1
        return player


def build_players(index: SchoolIndex):
    board = PlayerBoard()
    unmapped: list[dict] = []

    def record_unmapped(source, year, name, hs_name, city, state, extra=None):
        unmapped.append(
            {
                "source": source,
                "class_year": year,
                "name": name,
                "hs_name": hs_name,
                "city": city,
                "state": state,
                **(extra or {}),
            }
        )

    for year in YEARS:
        for r in csm.load_year("247", year):
            hs_name, hs_city, hs_st = csm.parse_247_meta(r.get("hs_meta"))
            hs_name, hs_city, hs_st = csm.apply_img(hs_name, hs_city, hs_st)
            sch = index.map_school(
                hs_name, hs_city, hs_st, hs247=r.get("high_school_id")
            )
            if not sch:
                record_unmapped(
                    "247sports_composite",
                    year,
                    r.get("name"),
                    hs_name,
                    hs_city,
                    hs_st,
                    {"stars": r.get("stars"), "rating": r.get("rating")},
                )
                continue
            metrics = r.get("metrics") or ""
            height = metrics.split("/")[0].strip() if "/" in metrics else None
            weight = None
            if "/" in metrics:
                try:
                    weight = int(re.sub(r"\D", "", metrics.split("/")[1]))
                except ValueError:
                    weight = None
            extra = dict(
                p247=r.get("player_id"),
                height=height,
                weight=weight,
                college_commit=r.get("college_commit")
                if r.get("college_commit") not in (None, "N/A")
                else None,
            )
            dkey, p = board.lookup(year, r.get("name") or "", r.get("position"), sch["_match_key"])
            if p:
                csm.merge_player_extra(p, position=r.get("position"), **extra)
                board.put(dkey, p, sch, is_new=False)
            else:
                p = csm.new_player(r.get("name"), year, r.get("position"), {"key": sch["_match_key"]}, **extra)
                board.put(dkey, p, sch, is_new=True)
            csm.add_rating(
                p,
                csm.rating_row(
                    "247sports_composite",
                    year,
                    r.get("stars"),
                    r.get("rating"),
                    r.get("national_rank"),
                    r.get("position_rank"),
                    r.get("state_rank"),
                    r.get("position"),
                    r.get("hs_meta"),
                    r.get("url"),
                ),
            )

    print(f"after 247 players={len(board.players)} unmapped={len(unmapped)}")

    for year in YEARS:
        for r in csm.load_year("espn", year):
            hs_name, hs_city, hs_st = csm.apply_img(
                r.get("hs_name"), r.get("hs_city"), r.get("hs_state")
            )
            sch = index.map_school(hs_name, hs_city, hs_st)
            extra = dict(
                espn_id=r.get("espn_id"),
                height=r.get("height")
                if isinstance(r.get("height"), str) and "-" in str(r.get("height"))
                else csm.inches_to_height(r.get("height")),
                weight=r.get("weight"),
                hometown_city=r.get("hometown_city"),
                hometown_state=r.get("hometown_state"),
                hometown=", ".join(
                    x for x in (r.get("hometown_city"), r.get("hometown_state")) if x
                )
                or None,
            )
            dkey, p = board.lookup(
                r.get("class_year") or year,
                r.get("full_name") or "",
                r.get("position"),
                sch["_match_key"] if sch else None,
            )
            if p and sch:
                csm.merge_player_extra(p, **extra)
                board.put(dkey, p, sch, is_new=False)
            elif sch:
                p = csm.new_player(
                    r.get("full_name"),
                    r.get("class_year") or year,
                    r.get("position"),
                    {"key": sch["_match_key"]},
                    **extra,
                )
                board.put(dkey, p, sch, is_new=True)
            else:
                record_unmapped(
                    "espn",
                    r.get("class_year") or year,
                    r.get("full_name"),
                    hs_name,
                    hs_city,
                    hs_st,
                    {"grade": r.get("grade")},
                )
                continue
            csm.add_rating(
                p,
                csm.rating_row(
                    "espn",
                    year,
                    csm.espn_stars(r.get("grade")),
                    r.get("grade"),
                    r.get("national_rank"),
                    r.get("position_rank"),
                    r.get("state_rank"),
                    r.get("position"),
                    r.get("hs_name"),
                    r.get("profile"),
                ),
            )

    print(f"after espn players={len(board.players)} unmapped={len(unmapped)}")

    for year in YEARS:
        for r in csm.load_year("on3", year):
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
            hs_name, city_guess, st = csm.apply_img(hs_name, city_guess, st)
            ht_city, ht_st = csm.parse_hometown(r.get("hometown"))
            sch = index.map_school(hs_name, city_guess, st, on3_key=r.get("hs_key"))
            extra = dict(
                on3=r.get("key"),
                height=r.get("height"),
                weight=r.get("weight"),
                hometown_city=ht_city,
                hometown_state=ht_st,
                hometown=r.get("hometown"),
                college_commit=(r.get("college_slug") or "").replace("-", " ").title()
                if r.get("committed")
                else None,
            )
            dkey, p = board.lookup(
                r.get("class_year") or year,
                r.get("name") or "",
                r.get("position"),
                sch["_match_key"] if sch else None,
            )
            if p and sch:
                csm.merge_player_extra(p, **extra)
                board.put(dkey, p, sch, is_new=False)
            elif sch:
                p = csm.new_player(
                    r.get("name"),
                    r.get("class_year") or year,
                    r.get("position"),
                    {"key": sch["_match_key"]},
                    **extra,
                )
                board.put(dkey, p, sch, is_new=True)
            else:
                record_unmapped(
                    "on3_rivals",
                    r.get("class_year") or year,
                    r.get("name"),
                    hs_name,
                    city_guess,
                    st,
                )
                continue
            attach_on3_ratings(p, r, year)

    print(
        f"board players={len(board.players)} merges={board.merges} "
        f"transfers={board.transfers} unmapped={len(unmapped)}"
    )
    return board, unmapped


def score_player(p: dict) -> dict:
    p = dict(p)
    site_id = p.pop("_site_id", None)
    p.pop("_school_key", None)
    if not p.get("hometown") and p.get("hometown_city"):
        ht = p["hometown_city"]
        if p.get("hometown_state"):
            ht += f", {p['hometown_state']}"
        p["hometown"] = ht
    stars = csm.official_stars(p.get("ratings") or [])
    p["talent_points"] = round(csm.player_points(stars), 4)
    p["sources"] = [r["source"] for r in p.get("ratings") or []]
    p["ratings"] = [
        {k: v for k, v in r.items() if k != "high_school_name_raw"}
        for r in p.get("ratings") or []
    ]
    return p, site_id


def apply_to_schools(schools: list[dict], board: PlayerBoard) -> dict[str, int]:
    by_site: dict[str, list[dict]] = defaultdict(list)
    for p in board.players.values():
        rec, site_id = score_player(p)
        if site_id:
            by_site[site_id].append(rec)
    before_counts = {s["id"]: len(s.get("recruits") or []) for s in schools}
    gained = 0
    for sch in schools:
        recs = by_site.get(sch["id"], [])
        recs.sort(key=lambda x: (-int(x.get("class_year") or 0), x.get("full_name") or ""))
        sch["recruits"] = recs
        talent = sum(r.get("talent_points") or 0 for r in recs)
        s5 = s4 = s3 = 0
        for r in recs:
            b = csm.badge_stars(csm.official_stars(r.get("ratings") or []))
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
        if len(recs) > before_counts.get(sch["id"], 0):
            gained += 1
        sch.pop("_match_key", None)
    return {
        "teams_gained_recruits": gained,
        "schools": len(schools),
        "players": sum(len(s.get("recruits") or []) for s in schools),
    }


def raw_counts() -> dict:
    out = {}
    for src in ("247", "espn", "on3"):
        out[src] = {}
        for year in YEARS:
            p = RAW / src / f"{year}.json"
            if not p.exists():
                out[src][year] = {"count": 0, "as_of": None}
                continue
            d = json.loads(p.read_text())
            out[src][year] = {
                "count": len(d.get("players") or []),
                "listed": d.get("listed"),
                "as_of": d.get("as_of"),
            }
    return out


def notable_additions(old_schools: list[dict], new_schools: list[dict]) -> list[dict]:
    old_names = set()
    for s in old_schools:
        for r in s.get("recruits") or []:
            old_names.add(
                (
                    csm.normalize_name(r.get("full_name") or ""),
                    int(r.get("class_year") or 0),
                    s["id"],
                )
            )
    added = []
    for s in new_schools:
        for r in s.get("recruits") or []:
            key = (
                csm.normalize_name(r.get("full_name") or ""),
                int(r.get("class_year") or 0),
                s["id"],
            )
            if key in old_names:
                continue
            stars = csm.official_stars(r.get("ratings") or [])
            ratings = [
                {
                    "source": x.get("source"),
                    "stars": x.get("stars"),
                    "rating": x.get("rating"),
                }
                for x in r.get("ratings") or []
            ]
            added.append(
                {
                    "name": r.get("full_name"),
                    "school": s.get("name"),
                    "school_id": s["id"],
                    "class_year": r.get("class_year"),
                    "stars": stars,
                    "sources": r.get("sources") or [x["source"] for x in ratings],
                    "ratings": ratings,
                    "talent_points": r.get("talent_points"),
                }
            )
    added.sort(
        key=lambda x: (
            -(x.get("stars") or 0),
            -(x.get("talent_points") or 0),
            x.get("name") or "",
        )
    )
    return added


def main():
    schools = json.loads((SITE / "schools.json").read_text())
    old_schools = json.loads(json.dumps(schools))
    index = SchoolIndex(schools, load_crosswalk())
    board, unmapped = build_players(index)
    stats = apply_to_schools(schools, board)
    added = notable_additions(old_schools, schools)
    payload = json.dumps(schools)
    (SITE / "schools.json").write_text(payload)
    IMPORT.mkdir(parents=True, exist_ok=True)
    (IMPORT / "schools.json").write_text(payload)

    n2027 = sum(
        1
        for s in schools
        for r in s.get("recruits") or []
        if r.get("class_year") == 2027
    )
    n2028 = sum(
        1
        for s in schools
        for r in s.get("recruits") or []
        if r.get("class_year") == 2028
    )
    n2029 = sum(
        1
        for s in schools
        for r in s.get("recruits") or []
        if r.get("class_year") == 2029
    )
    summary_path = SITE / "schools.summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    summary["players"] = stats["players"]
    summary["class_2027"] = n2027
    summary["class_2028"] = n2028
    summary["class_2029"] = n2029
    summary["canonical_players"] = stats["players"]
    summary["recruit_refresh_as_of"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    summary_path.write_text(json.dumps(summary, indent=2))
    (IMPORT / "schools.summary.json").write_text(json.dumps(summary, indent=2))

    watch = [
        "tx-missouri-city-fort-bend-ridge-point",
        "fl-bradenton-img-academy",
        "tx-allen-allen",
    ]
    watch_after = {}
    by_id = {s["id"]: s for s in schools}
    old_by = {s["id"]: s for s in old_schools}
    for sid in watch:
        s = by_id[sid]
        o = old_by[sid]
        watch_after[sid] = {
            "name": s["name"],
            "before": {
                "talent_score": o.get("talent_score"),
                "team_strength": o.get("team_strength"),
                "sos": o.get("sos"),
                "recruit_count": o.get("recruit_count"),
            },
            "after_talent": {
                "talent_score": s.get("talent_score"),
                "recruit_count": s.get("recruit_count"),
                "recruits": [
                    {
                        "name": r["full_name"],
                        "class_year": r["class_year"],
                        "position": r.get("position"),
                        "sources": r.get("sources"),
                        "stars": csm.official_stars(r.get("ratings") or []),
                    }
                    for r in s.get("recruits") or []
                ],
            },
        }

    report = {
        "raw": raw_counts(),
        "board": {
            "players": stats["players"],
            "class_2027": n2027,
            "class_2028": n2028,
            "class_2029": n2029,
            "merges": board.merges,
            "transfers": board.transfers,
            "teams_gained_recruits": stats["teams_gained_recruits"],
            "unmapped": len(unmapped),
        },
        "watch": watch_after,
        "transfers": board.transfer_rows[:80],
        "notable_additions": added[:40],
        "unmapped": unmapped,
    }
    report_path = RAW / "recruit-refresh-report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("raw", "board")}, indent=2))
    print("watch", json.dumps(watch_after, indent=2)[:4000])
    print("wrote", report_path, "unmapped", len(unmapped), "added", len(added))
    needles = ("bartee", "ramseur")
    for s in schools:
        for r in s.get("recruits") or []:
            n = (r.get("full_name") or "").lower()
            if any(x in n for x in needles):
                print("FOUND", r["full_name"], s["name"], r["class_year"], r.get("sources"))


if __name__ == "__main__":
    main()
