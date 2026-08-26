#!/usr/bin/env python3
"""Merge verified Hudl athlete + team URLs onto site-data/schools.json.

Payload UUID ids are not FridayRadar recruit ids (`247-{247sports_player_id}`).
Each athlete is joined to a 2027+ roster by the public Hudl profile name,
scoped to the 41 schools with public team pages. Unmatched / ambiguous skipped.
Do not invent athlete URLs.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data"
IMPORT = ROOT / "data" / "import"

# UUIDs with a known school when the Hudl display name is otherwise ambiguous.
SCHOOL_HINT = {
    "46cfe0d8-10e2-4f73-ae02-2f2c8e93ec20": "fl-bradenton-img-academy",  # Chuck/Charles Roberts
    "56b97201-0193-4538-bebe-74a10b913e44": "fl-fort-lauderdale-saint-thomas-aquinas",
    "8577c0cc-bc5f-464a-ac0b-bea87e117111": "ca-chatsworth-sierra-canyon",
    "7b3dfb16-88d2-45b9-99d5-ef7b591d301b": "ca-chatsworth-sierra-canyon",
    "a7b24ffa-dd52-47c0-9def-f1d66703c5c1": "nc-charlotte-providence-day-school",
    "dda4fd89-be2a-40c7-82cc-645d240ab201": "nc-cornelius-hough",
    "a42a36dc-2e70-4d8a-8a48-8799c432e0a0": "hi-mililani-mililani",
    "2dd20ded-7715-422f-911f-6f4d4865e243": "al-alabaster-thompson",
    "b8863072-8ee4-45fb-baba-fec76671d7e9": "az-chandler-basha",
    "73146578-4e68-47c8-b3f7-c60fb89d77ba": "pa-pittsburgh-central-catholic",
    "fc50dba4-d2ab-4911-bf62-454c4ab4c8d5": "ut-orem-orem",  # Hudl title Jag Iaone
    "59897798-ad62-407c-92c2-977db7dd2be0": "ca-temecula-chaparral",
    "c97d4a8a-bf32-42b1-bc68-5f2244c0a99f": "tn-chattanooga-baylor-school",
    "a4e2f1a6-117a-4d01-b1a3-2762595be60d": "fl-miami-miami-central",
    "3937b2fd-7dc6-4ddd-9993-c03ff570c74c": "va-springfield-the-st-james",
    "25441e14-5d2a-4138-9b90-68bd4af07e07": "ut-orem-orem",
    "5100140b-f69d-4528-b51c-035ce4a0acce": "nc-cornelius-hough",  # Reno/Moreno Fisher
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
}

TEAM_URLS = {
    "fl-bradenton-img-academy": "https://fan.hudl.com/usa/fl/bradenton/organization/29038/img-academy/team/81606/boys-varsity-football",
    "md-baltimore-st-frances-academy": "https://fan.hudl.com/usa/md/baltimore/organization/11813/st-frances-academy/team/27609/boys-varsity-football",
    "ca-santa-ana-mater-dei": "https://fan.hudl.com/usa/ca/santa-ana/organization/6380/mater-dei-high-school/team/19620/boys-varsity-football",
    "fl-fort-lauderdale-saint-thomas-aquinas": "https://fan.hudl.com/usa/fl/fort-lauderdale/organization/9478/st-thomas-aquinas-high-school/team/22383/boys-varsity-football",
    "ga-loganville-grayson": "https://fan.hudl.com/usa/ga/loganville/organization/1486/grayson-high-school/team/3632/boys-varsity-football",
    "ga-buford-buford": "https://fan.hudl.com/usa/ga/buford/organization/8640/buford-high-school/team/20910/boys-varsity-football",
    "ca-chatsworth-sierra-canyon": "https://fan.hudl.com/usa/ca/chatsworth/organization/749/sierra-canyon-high-school/team/2112/boys-varsity-football",
    "az-goodyear-desert-edge": "https://fan.hudl.com/usa/az/goodyear/organization/4041/desert-edge-high-school/team/10684/boys-varsity-football",
    "nv-las-vegas-bishop-gorman": "https://fan.hudl.com/usa/nv/las-vegas/organization/561/bishop-gorman-high-school/team/1492/boys-varsity-football",
    "ca-temecula-chaparral": "https://fan.hudl.com/usa/ca/temecula/organization/5544/chaparral-high-school/team/14757/boys-varsity-football",
    "az-chandler-basha": "https://fan.hudl.com/usa/az/chandler/organization/23047/basha-high-school/team/47714/boys-varsity-football",
    "ma-marion-tabor-academy": "https://fan.hudl.com/usa/ma/marion/organization/4340/tabor-academy-high/team/11592/boys-varsity-football",
    "tn-chattanooga-baylor-school": "https://fan.hudl.com/usa/tn/chattanooga/organization/12981/baylor-school-high-school/team/29587/boys-varsity-football",
    "ca-corona-corona-centennial": "https://fan.hudl.com/usa/ca/corona/organization/9599/centennial-high-school/team/22512/boys-varsity-football",
    "va-springfield-the-st-james": "https://fan.hudl.com/usa/va/springfield/organization/185835/the-st-james-academ-high-school/team/862466/boys-varsity-football",
    "nj-glassboro-glassboro": "https://fan.hudl.com/usa/nj/glassboro/organization/19970/glassboro-high-school/team/36577/boys-varsity-football",
    "ca-tustin-tustin": "https://fan.hudl.com/usa/ca/tustin/organization/1674/tustin-high-school/team/4021/boys-varsity-football",
    "nc-cornelius-hough": "https://fan.hudl.com/usa/nc/cornelius/organization/4521/william-a-hough-high-school/team/12090/boys-varsity-football",
    "la-ruston-ruston": "https://fan.hudl.com/usa/la/ruston/organization/11970/ruston-high-school/team/28217/boys-varsity-football",
    "ga-gainesville-gainesville": "https://fan.hudl.com/usa/ga/gainesville/organization/11888/gainesville-high-school/team/27871/boys-varsity-football",
    "hi-mililani-mililani": "https://fan.hudl.com/usa/hi/mililani/organization/6631/mililani-high-school/team/17068/boys-varsity-football",
    "nj-jersey-city-st-peter-s-prep": "https://fan.hudl.com/usa/nj/jersey-city/organization/1517/st-peters-prep/team/3700/boys-varsity-football",
    "ga-powder-springs-mceachern": "https://fan.hudl.com/usa/ga/powder-springs/organization/4080/mceachern-high-school/team/10852/boys-varsity-football",
    "ga-leesburg-lee-county": "https://fan.hudl.com/usa/ga/leesburg/organization/7589/lee-county-high-school/team/18738/boys-varsity-football",
    "tn-brentwood-brentwood-academy": "https://fan.hudl.com/usa/tn/brentwood/organization/4890/brentwood-academy/team/12991/boys-varsity-football",
    "fl-orlando-jones": "https://fan.hudl.com/usa/fl/orlando/organization/27240/jones-high-school/team/66291/boys-varsity-football",
    "pa-pittsburgh-central-catholic": "https://fan.hudl.com/usa/pa/pittsburgh/organization/20159/central-catholic-high-school/team/36766/boys-varsity-football",
    "ga-fairburn-creekside": "https://fan.hudl.com/usa/ga/fairburn/organization/18726/creekside-high-school/team/35333/boys-varsity-football",
    "il-chicago-mount-carmel": "https://fan.hudl.com/usa/il/chicago/organization/1942/mount-carmel-high-school/team/4640/boys-varsity-football",
    "il-east-st-louis-east-st-louis": "https://fan.hudl.com/usa/il/east-st-louis/organization/13361/east-st-louis-high-school/team/29967/boys-varsity-football",
    "ca-bellflower-st-john-bosco": "https://fan.hudl.com/usa/ca/bellflower/organization/6603/st-john-bosco-high-school/team/17022/boys-varsity-football",
    "al-alabaster-thompson": "https://fan.hudl.com/usa/al/alabaster/organization/21421/thompson-high-school/team/38907/boys-varsity-football",
    "fl-hollywood-chaminade-madonna": "https://fan.hudl.com/usa/fl/hollywood/organization/28574/chaminade-madonna-high-school/team/77940/boys-varsity-football",
    "nc-charlotte-providence-day-school": "https://fan.hudl.com/usa/nc/charlotte/organization/6076/providence-day-high-school/team/16213/boys-varsity-football",
    "ca-orange-orange-lutheran": "https://fan.hudl.com/usa/ca/orange/organization/4062/orange-lutheran-high-school/team/16475/boys-varsity-football",
    "ca-irvine-crean-lutheran": "https://fan.hudl.com/usa/ca/irvine/organization/10639/crean-lutheran-high-school/team/24407/boys-varsity-football",
    "fl-miami-miami-central": "https://fan.hudl.com/usa/fl/miami/organization/13686/central-high-school/team/30292/boys-varsity-football",
    "ut-orem-orem": "https://fan.hudl.com/usa/ut/orem/organization/16696/orem-high-school/team/33303/boys-varsity-football",
    "ga-douglasville-douglas-county": "https://fan.hudl.com/usa/ga/douglasville/organization/4699/douglas-county-high-school/team/12538/boys-varsity-football",
    "fl-jacksonville-the-bolles-school": "https://fan.hudl.com/usa/fl/jacksonville/organization/10209/the-bolles-school-high-school/team/23286/boys-varsity-football",
    "tx-houston-c-e-king": "https://fan.hudl.com/usa/tx/houston/organization/11065/ce-king-high-school/team/25478/boys-varsity-football",
}

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v|vi|lll|ll|i)\b")
PARENS = re.compile(r"\([^)]*\)")


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


def main() -> None:
    schools = json.loads((SITE / "schools.json").read_text())
    by_id = {s["id"]: s for s in schools}
    names = json.loads((SITE / "hudl-athlete-names.json").read_text())
    pairs = [
        line.split()
        for line in (SITE / "hudl-pairs.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if len(pairs) != 343:
        raise SystemExit(f"expected 343 payload pairs, got {len(pairs)}")
    if any(uid == "4721f539-8749-450a-b15a-466b4616fc0d" for uid, _ in pairs):
        raise SystemExit("Davion Jones UUID must stay unlinked")
    if len(TEAM_URLS) != 41:
        raise SystemExit(f"expected 41 team URLs, got {len(TEAM_URLS)}")

    hudl_rosters: list[tuple[str, dict]] = []
    for sid in TEAM_URLS:
        school = by_id.get(sid)
        if not school:
            raise SystemExit(f"team URL school missing on board: {sid}")
        if "boys-varsity-football" not in TEAM_URLS[sid]:
            raise SystemExit(f"not a boys-varsity-football URL: {sid}")
        for rec in school.get("recruits") or []:
            hudl_rosters.append((sid, rec))

    players_out = []
    recruit_hudl: dict[str, dict] = {}
    athlete_hit: dict[str, tuple[str, dict]] = {}
    unmatched = []
    for uid, hid in pairs:
        hudl_name = names.get(hid)
        if not hudl_name:
            raise SystemExit(f"missing Hudl display name for athlete {hid}")
        url = f"https://www.hudl.com/profile/{hid}"
        rec = None
        school_id = None
        if hid in athlete_hit:
            school_id, rec = athlete_hit[hid]
        else:
            hint = SCHOOL_HINT.get(uid)
            if hint:
                rec = match_recruit(
                    by_id[hint].get("recruits") or [], hudl_name, allow_unique_last=True
                )
                school_id = hint if rec else None
            if rec is None:
                hits: dict[str, tuple[str, dict]] = {}
                for sid, candidate in hudl_rosters:
                    m = match_recruit([candidate], hudl_name, allow_unique_last=False)
                    if m:
                        hits[m["id"]] = (sid, m)
                if len(hits) == 1:
                    school_id, rec = next(iter(hits.values()))
                elif not hits:
                    last = norm(hudl_name).split()[-1] if norm(hudl_name) else ""
                    last_hits = [
                        (sid, r)
                        for sid, r in hudl_rosters
                        if last and last in norm(r.get("full_name") or "").split()
                    ]
                    uniq = {r["id"]: (sid, r) for sid, r in last_hits}
                    if len(uniq) == 1:
                        school_id, rec = next(iter(uniq.values()))
        if rec is None:
            unmatched.append((uid, hid, hudl_name))
            continue
        athlete_hit[hid] = (school_id, rec)
        row = {
            "id": uid,
            "recruit_id": rec["id"],
            "school_id": school_id,
            "full_name": rec["full_name"],
            "hudl_name": hudl_name,
            "hudl_url": url,
            "hudl_athlete_id": hid,
        }
        players_out.append(row)
        prev = recruit_hudl.get(rec["id"])
        if prev and prev["hudl_athlete_id"] != hid:
            raise SystemExit(f"conflicting Hudl ids for {rec['id']}")
        recruit_hudl[rec["id"]] = row

    if unmatched:
        raise SystemExit("unmatched Hudl payload rows:\n" + "\n".join(map(str, unmatched)))
    if len(players_out) != 343:
        raise SystemExit(f"expected 343 payload players, got {len(players_out)}")
    charles = next(p for p in players_out if p["id"] == "46cfe0d8-10e2-4f73-ae02-2f2c8e93ec20")
    if charles["hudl_athlete_id"] != "20157149" or charles["recruit_id"] != "247-46143570":
        raise SystemExit(f"Charles Roberts mapping wrong: {charles}")
    royal = next(p for p in players_out if p["id"] == "dda4fd89-be2a-40c7-82cc-645d240ab201")
    if royal["recruit_id"] != "247-46148009" or royal["hudl_athlete_id"] != "19525270":
        raise SystemExit(f"Ethan Royal mapping wrong: {royal}")
    ioane = next(p for p in players_out if p["id"] == "fc50dba4-d2ab-4911-bf62-454c4ab4c8d5")
    if ioane["recruit_id"] != "247-46152618":
        raise SystemExit(f"Jag Ioane mapping wrong: {ioane}")
    fisher = next(p for p in players_out if p["id"] == "5100140b-f69d-4528-b51c-035ce4a0acce")
    if fisher["recruit_id"] != "247-46165206" or fisher["hudl_athlete_id"] != "19658142":
        raise SystemExit(f"Moreno Fisher mapping wrong: {fisher}")

    hudl_doc = {
        "as_of": "2026-08-26",
        "notes": [
            "Verified public Hudl batch (On3 embed → hudl.com/profile/{id}).",
            "343 payload rows: 327-set minus Hough Davion Jones plus later verified first-batch crumbs. Davion Jones stays unlinked (athlete 19494412 is West Charlotte).",
            "Duplicate payload UUIDs that share a Hudl id map to one FridayRadar recruit.",
            "Payload UUID is not the FridayRadar recruit id; join is payload id → public Hudl name → school roster recruit id.",
            "Unmatched recruits are omitted on purpose. Do not invent athlete URLs.",
            "41/41 top-school public team pages. C.E. King is fully matched.",
        ],
        "players": players_out,
        "schools": [
            {"school_id": sid, "hudl_team_url": url} for sid, url in TEAM_URLS.items()
        ],
    }
    (SITE / "hudl.json").write_text(json.dumps(hudl_doc, indent=2) + "\n")

    hudl_by_recruit = {row["recruit_id"]: row for row in players_out}
    for school in schools:
        url = TEAM_URLS.get(school["id"])
        if url:
            school["hudl_team_url"] = url
        elif "hudl_team_url" in school:
            del school["hudl_team_url"]
        for rec in school.get("recruits") or []:
            strip_hudl(rec)
            hit = hudl_by_recruit.get(rec["id"])
            if not hit:
                continue
            source_ids = dict(rec.get("source_ids") or {})
            source_ids["hudl"] = hit["hudl_athlete_id"]
            rec["source_ids"] = source_ids
            urls = rating_profile_urls(rec)
            urls["hudl"] = hit["hudl_url"]
            rec["profile_urls"] = urls

    king = by_id["tx-houston-c-e-king"]
    if king.get("hudl_team_url") != TEAM_URLS["tx-houston-c-e-king"]:
        raise SystemExit("C.E. King team URL missing")
    king_hudl = [r for r in king.get("recruits") or [] if (r.get("profile_urls") or {}).get("hudl")]
    if len(king_hudl) != len(king.get("recruits") or []):
        raise SystemExit(f"C.E. King expected all recruits to have Hudl, got {len(king_hudl)}")
    willis = next(r for r in king["recruits"] if r["id"] == "247-46153677")
    if willis["profile_urls"]["hudl"] != "https://www.hudl.com/profile/30031086":
        raise SystemExit("Triston Willis Hudl mismatch")

    img = by_id["fl-bradenton-img-academy"]
    mcf = next(r for r in img["recruits"] if r["id"] == "247-46148083")
    if mcf["profile_urls"]["hudl"] != "https://www.hudl.com/profile/22055854":
        raise SystemExit("McFarland Hudl mismatch")
    roberts = next(r for r in img["recruits"] if r["id"] == "247-46143570")
    if roberts["profile_urls"]["hudl"] != "https://www.hudl.com/profile/20157149":
        raise SystemExit("Charles Roberts Hudl mismatch")
    buf = by_id["ga-buford-buford"]
    brew = next(r for r in buf["recruits"] if r["id"] == "247-46145095")
    if brew["profile_urls"]["hudl"] != "https://www.hudl.com/profile/19965528":
        raise SystemExit("Brewster Hudl mismatch")
    hough = by_id["nc-cornelius-hough"]
    davion = next(r for r in hough["recruits"] if r["id"] == "247-46153290")
    if (davion.get("profile_urls") or {}).get("hudl") or (davion.get("source_ids") or {}).get("hudl"):
        raise SystemExit("Davion Jones must not have a Hudl chip")

    (SITE / "schools.json").write_text(json.dumps(schools, ensure_ascii=False))
    shutil.copyfile(SITE / "schools.json", IMPORT / "schools.json")
    shutil.copyfile(SITE / "hudl.json", IMPORT / "hudl.json")
    print(
        "hudl players",
        len(players_out),
        "unique recruits",
        len(hudl_by_recruit),
        "team pages",
        len(TEAM_URLS),
    )


if __name__ == "__main__":
    main()
