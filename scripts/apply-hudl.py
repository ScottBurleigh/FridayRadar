#!/usr/bin/env python3
"""Join site-data/hudl-map.tsv + hudl-teams.tsv onto schools.json.

Sidecar only. Payload `id` is a Scout UUID (same as hudl.json players[].id),
not the FridayRadar `247-*` recruit id. Unmatched rows are omitted. Do not
invent athlete URLs or scrape Hudl.
"""
from __future__ import annotations

import csv
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
IMPORT = ROOT / "data" / "import"

CANON_SCHOOL = {
    "md-baltimore-saint-frances-academy": "md-baltimore-st-frances-academy",
    "va-springfield-saint-james": "va-springfield-the-st-james",
    "nj-jersey-city-saint-peters-prep": "nj-jersey-city-st-peter-s-prep",
    "il-east-saint-louis-east-saint-louis": "il-east-st-louis-east-st-louis",
    "ca-bellflower-saint-john-bosco": "ca-bellflower-st-john-bosco",
    "fl-jacksonville-bolles-school": "fl-jacksonville-the-bolles-school",
    "dc-washington-saint-johns-college": "dc-washington-st-john-s-college",
    "nj-montvale-saint-joseph-regional": "nj-montvale-st-joseph-regional",
}

FIRST_ALIASES = {
    "jake": {"jacob"},
    "jacob": {"jake"},
    "chuck": {"charles", "charlie"},
    "charles": {"chuck", "charlie"},
    "charlie": {"charles", "chuck"},
    "cam": {"cameron", "camden"},
    "cameron": {"cam"},
    "camden": {"cam"},
    "greg": {"gregory"},
    "gregory": {"greg"},
    "dj": {"dailon"},
    "dailon": {"dj"},
    "mike": {"michael"},
    "michael": {"mike"},
    "coop": {"cooper"},
    "cooper": {"coop"},
    "reno": {"moreno"},
    "moreno": {"reno"},
    "rocco": {"aloalii"},
    "aloalii": {"rocco"},
}

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v|vi|lll|ll|i)\b")
PARENS = re.compile(r"\([^)]*\)")


def canon_school(sid: str) -> str:
    return CANON_SCHOOL.get(sid, sid)


def norm(name: str) -> str:
    name = html.unescape(name or "")
    name = PARENS.sub(" ", name)
    name = name.lower().replace("'", "").replace("’", "")
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = SUFFIX.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


def first_ok(hudl_first: str, rec_bits: list[str]) -> bool:
    if not hudl_first:
        return False
    aliases = {hudl_first, *FIRST_ALIASES.get(hudl_first, set())}
    for bit in rec_bits:
        if bit in aliases:
            return True
        if any(
            bit.startswith(a) or a.startswith(bit)
            for a in aliases
            if len(min(bit, a, key=len)) >= 3
        ):
            return True
    return False


def rating_profile_urls(rec: dict) -> dict[str, str]:
    by = {r.get("source"): r for r in rec.get("ratings") or [] if r.get("source")}
    urls: dict[str, str] = {}
    u247 = (by.get("247sports_composite") or by.get("247sports") or {}).get("profile_url")
    on3 = (by.get("on3_rivals") or by.get("on3_industry") or {}).get("profile_url")
    espn = (by.get("espn") or {}).get("profile_url")
    if u247:
        urls["247sports_composite"] = u247
    if on3:
        urls["on3_rivals"] = on3
    if espn:
        urls["espn"] = espn
    return urls


def match_recruit(roster: list[dict], hudl_name: str, *, allow_unique_last: bool = False) -> dict | None:
    hn = norm(hudl_name)
    tokens = hn.split()
    first, last = (tokens[0] if tokens else ""), (tokens[-1] if tokens else "")
    exact = [r for r in roster if norm(r.get("full_name") or "") == hn]
    if len(exact) == 1:
        return exact[0]
    first_last = []
    for rec in roster:
        bits = norm(rec.get("full_name") or "").split()
        if not (first and last and last in bits):
            continue
        if first_ok(first, bits):
            first_last.append(rec)
    uniq = {r["id"]: r for r in first_last}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    nick_m = re.search(r'"([^"]+)"', html.unescape(hudl_name))
    if nick_m and last:
        nick = norm(nick_m.group(1))
        nick_hits = [
            r
            for r in roster
            if nick in norm(r.get("full_name") or "").split()
            and last in norm(r.get("full_name") or "").split()
        ]
        uniq = {r["id"]: r for r in nick_hits}
        if len(uniq) == 1:
            return next(iter(uniq.values()))
    if last and len(first) >= 4:
        last_hits = [r for r in roster if last in norm(r.get("full_name") or "").split()]
        if len(last_hits) == 1:
            rec_first = (norm(last_hits[0].get("full_name") or "").split() or [""])[0]
            if rec_first[:4] == first[:4] or first_ok(first, [rec_first]):
                return last_hits[0]
    if allow_unique_last and last:
        last_hits = [r for r in roster if last in norm(r.get("full_name") or "").split()]
        uniq = {r["id"]: r for r in last_hits}
        if len(uniq) == 1:
            return next(iter(uniq.values()))
    if allow_unique_last and first:
        first_hits = []
        for rec in roster:
            bits = norm(rec.get("full_name") or "").split()
            if first in bits or first_ok(first, bits):
                first_hits.append(rec)
        uniq = {r["id"]: r for r in first_hits}
        if len(uniq) == 1:
            return next(iter(uniq.values()))
    return None


def strip_hudl(rec: dict) -> None:
    urls = dict(rec.get("profile_urls") or {})
    urls.pop("hudl", None)
    if urls:
        rec["profile_urls"] = urls
    elif "profile_urls" in rec:
        del rec["profile_urls"]
    source_ids = dict(rec.get("source_ids") or {})
    source_ids.pop("hudl", None)
    if source_ids:
        rec["source_ids"] = source_ids
    elif "source_ids" in rec:
        del rec["source_ids"]


def read_tsv(path: Path, expected: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"missing sidecar {path}")
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames != expected:
            raise SystemExit(f"{path.name} header must be {expected!r}, got {reader.fieldnames!r}")
        rows = []
        for row in reader:
            if not row:
                continue
            if not any((v or "").strip() for v in row.values()):
                continue
            rows.append({k: (v or "").strip() for k, v in row.items()})
        return rows


def previous_uuid_index(by_id: dict) -> dict[str, list[str]]:
    """Scout payload UUID → FridayRadar recruit ids from the last hudl.json join."""
    path = SITE / "hudl.json"
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    index: dict[str, list[str]] = {}
    for row in doc.get("players") or []:
        uid = (row.get("id") or "").strip()
        rid = (row.get("recruit_id") or "").strip()
        if not uid or not rid:
            continue
        school = by_id.get(row.get("school_id") or "")
        recs = school.get("recruits") or [] if school else []
        if not any(r.get("id") == rid for r in recs) and rid not in {
            r.get("id") for s in by_id.values() for r in (s.get("recruits") or [])
        }:
            continue
        index.setdefault(uid, [])
        if rid not in index[uid]:
            index[uid].append(rid)
    return index


def resolve_recruits(
    payload_id: str,
    school_id: str,
    hid: str,
    by_id: dict,
    names: dict[str, str],
    uuid_index: dict[str, list[str]],
) -> list[dict]:
    """Return 0+ roster recruits. Duplicate payload rows can hit two recruits."""
    found: list[dict] = []
    seen: set[str] = set()

    def add(rec: dict | None) -> None:
        if rec and rec.get("id") and rec["id"] not in seen:
            seen.add(rec["id"])
            found.append(rec)

    # Direct FridayRadar recruit id (rare) or nested roster id.
    for school in by_id.values():
        for rec in school.get("recruits") or []:
            if rec.get("id") == payload_id:
                add(rec)
    for rid in uuid_index.get(payload_id) or []:
        for school in by_id.values():
            rec = next((r for r in (school.get("recruits") or []) if r.get("id") == rid), None)
            add(rec)
    school = by_id.get(school_id)
    if school:
        hudl_name = names.get(hid)
        if hudl_name:
            add(match_recruit(school.get("recruits") or [], hudl_name, allow_unique_last=True))
    return found


def main() -> None:
    schools = json.loads((SITE / "schools.json").read_text())
    by_id = {s["id"]: s for s in schools}
    names_path = SITE / "hudl-athlete-names.json"
    names = json.loads(names_path.read_text()) if names_path.exists() else {}
    uuid_index = previous_uuid_index(by_id)

    map_rows = read_tsv(SITE / "hudl-map.tsv", ["id", "school_id", "hudl_athlete_id"])
    team_rows = read_tsv(SITE / "hudl-teams.tsv", ["school_id", "hudl_team_url"])

    team_urls: dict[str, str] = {}
    for row in team_rows:
        sid = canon_school(row.get("school_id") or "")
        url = (row.get("hudl_team_url") or "").strip()
        if not sid or sid not in by_id or "boys-varsity-football" not in url:
            continue
        if not url.startswith("https://fan.hudl.com/"):
            continue
        team_urls[sid] = url

    players_out = []
    recruit_hudl: dict[str, dict] = {}
    skipped = 0
    for row in map_rows:
        uid = row.get("id") or ""
        hid = row.get("hudl_athlete_id") or ""
        school_id = canon_school(row.get("school_id") or "")
        if not uid or not hid or not hid.isdigit():
            skipped += 1
            continue
        url = f"https://www.hudl.com/profile/{hid}"
        recs = resolve_recruits(uid, school_id, hid, by_id, names, uuid_index)
        if not recs:
            skipped += 1
            continue
        for rec in recs:
            sid = school_id if school_id in by_id else next(
                (s["id"] for s in schools if any(r.get("id") == rec["id"] for r in (s.get("recruits") or []))),
                school_id,
            )
            out = {
                "id": uid,
                "recruit_id": rec["id"],
                "school_id": sid,
                "full_name": rec.get("full_name"),
                "hudl_url": url,
                "hudl_athlete_id": hid,
            }
            players_out.append(out)
            prev = recruit_hudl.get(rec["id"])
            if prev and prev["hudl_athlete_id"] != hid:
                skipped += 1
                continue
            recruit_hudl[rec["id"]] = out

    hudl_doc = {
        "as_of": "2026-08-27",
        "notes": [
            "Hudl sidecar join from site-data/hudl-map.tsv + hudl-teams.tsv only.",
            "Strip then overlay. Payload id is a Scout UUID; join onto FridayRadar 247-* recruit ids.",
            "Duplicate payload rows that share an athlete id both receive the chip.",
            "Unmatched ids are omitted. Do not invent athlete URLs. Do not scrape Hudl.",
        ],
        "players": players_out,
        "schools": [{"school_id": sid, "hudl_team_url": url} for sid, url in team_urls.items()],
    }
    (SITE / "hudl.json").write_text(json.dumps(hudl_doc, indent=2) + "\n")

    for school in schools:
        url = team_urls.get(school["id"])
        if url:
            school["hudl_team_url"] = url
        elif "hudl_team_url" in school:
            del school["hudl_team_url"]
        for rec in school.get("recruits") or []:
            strip_hudl(rec)
            hit = recruit_hudl.get(rec["id"])
            if not hit:
                continue
            source_ids = dict(rec.get("source_ids") or {})
            source_ids["hudl"] = hit["hudl_athlete_id"]
            rec["source_ids"] = source_ids
            urls = rating_profile_urls(rec)
            urls["hudl"] = hit["hudl_url"]
            rec["profile_urls"] = urls

    (SITE / "schools.json").write_text(json.dumps(schools, ensure_ascii=False))
    IMPORT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SITE / "schools.json", IMPORT / "schools.json")
    shutil.copyfile(SITE / "hudl.json", IMPORT / "hudl.json")
    shutil.copyfile(SITE / "hudl-map.tsv", IMPORT / "hudl-map.tsv")
    shutil.copyfile(SITE / "hudl-teams.tsv", IMPORT / "hudl-teams.tsv")
    print(
        "hudl map rows",
        len(map_rows),
        "joined payload",
        len(players_out),
        "unique recruits",
        len(recruit_hudl),
        "team pages",
        len(team_urls),
        "skipped",
        skipped,
    )


if __name__ == "__main__":
    main()
