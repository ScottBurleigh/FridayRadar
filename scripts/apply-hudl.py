#!/usr/bin/env python3
"""Merge verified Hudl athlete + team URLs onto site-data/schools.json.

Payload UUID ids are not FridayRadar recruit ids (`247-{247sports_player_id}`).
Each athlete is joined to that school's 2027+ roster by the public Hudl profile
name. Unmatched 359 skipped. Do not invent athlete URLs.
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

CANON_SCHOOL = {
    "md-baltimore-saint-frances-academy": "md-baltimore-st-frances-academy",
    "va-springfield-saint-james": "va-springfield-the-st-james",
    "nj-jersey-city-saint-peters-prep": "nj-jersey-city-st-peter-s-prep",
    "il-east-saint-louis-east-saint-louis": "il-east-st-louis-east-st-louis",
}

# Payload rows: uuid, payload_school_id, hudl_url, hudl_athlete_id
PAYLOAD = """
3761cbf2-6555-46d9-a8ac-bbf8f1fd9e6b fl-bradenton-img-academy https://www.hudl.com/profile/22055854 22055854
f91ff5f0-d5bd-4d8e-b4c7-4a2a9364d1b8 fl-bradenton-img-academy https://www.hudl.com/profile/19304058 19304058
907ea573-1ff9-4133-b101-1605c1036a2a fl-bradenton-img-academy https://www.hudl.com/profile/22432094 22432094
a6f951e1-5311-4021-84dd-4746f5a3dea0 fl-bradenton-img-academy https://www.hudl.com/profile/18008781 18008781
41c6ba4d-1f24-4496-8345-7ffe79fa3f25 md-baltimore-saint-frances-academy https://www.hudl.com/profile/16860665 16860665
c8f07adf-460b-4ddc-bc3e-2b4d1925f53e md-baltimore-saint-frances-academy https://www.hudl.com/profile/19341597 19341597
eb32030a-af36-46a9-bae7-2d098ac3e690 ca-santa-ana-mater-dei https://www.hudl.com/profile/19576984 19576984
1d5125cc-e660-4c82-a804-e7a37af3a9a1 fl-fort-lauderdale-saint-thomas-aquinas https://www.hudl.com/profile/19972142 19972142
98ddcd17-0385-484c-adbd-7f78c9cffeb1 fl-fort-lauderdale-saint-thomas-aquinas https://www.hudl.com/profile/20767020 20767020
90d48419-ca6e-41a3-a790-3686eee36afd fl-fort-lauderdale-saint-thomas-aquinas https://www.hudl.com/profile/20133523 20133523
7d13ff78-840a-48a6-889e-988293c98b49 fl-fort-lauderdale-saint-thomas-aquinas https://www.hudl.com/profile/19530451 19530451
d6669fbb-5e03-4888-9515-8267268cad51 ga-loganville-grayson https://www.hudl.com/profile/24297059 24297059
ae2cc99d-2dcc-4f9f-9a01-190d55b649f2 ga-buford-buford https://www.hudl.com/profile/19965528 19965528
24978ef8-546f-4ca0-8615-acf9779d9e1b ca-chatsworth-sierra-canyon https://www.hudl.com/profile/22567319 22567319
8959a7f9-04e8-4b92-b96d-42936ec9a0d2 ca-chatsworth-sierra-canyon https://www.hudl.com/profile/19474303 19474303
8b329194-bff6-4f2a-a0cd-e40b1f154056 ca-chatsworth-sierra-canyon https://www.hudl.com/profile/19495559 19495559
0e703375-d7d9-4584-bcc4-7a6750ba5abd az-goodyear-desert-edge https://www.hudl.com/profile/18174937 18174937
4ed560dd-6c52-486e-a3cd-b593a286de02 nv-las-vegas-bishop-gorman https://www.hudl.com/profile/19444261 19444261
caecfea7-ef21-4079-bfd6-0673dbf80941 ca-temecula-chaparral https://www.hudl.com/profile/19603450 19603450
4b3aad70-8593-429d-ae45-b154c11da0df az-chandler-basha https://www.hudl.com/profile/19470635 19470635
e893dbfd-80dd-4f7d-bb4a-d68e2b4d28ea ma-marion-tabor-academy https://www.hudl.com/profile/15927844 15927844
0d0a9bbd-bff3-4338-a1d9-2b110f2e2030 tn-chattanooga-baylor-school https://www.hudl.com/profile/15480201 15480201
27789f63-3647-418c-8c34-34cf6bd3399a tn-chattanooga-baylor-school https://www.hudl.com/profile/18094089 18094089
5ad68265-8f35-4622-b247-cb77e174a769 ca-corona-corona-centennial https://www.hudl.com/profile/18196284 18196284
1340414a-f86f-4008-96d7-6c95106b24ff ca-corona-corona-centennial https://www.hudl.com/profile/20129253 20129253
49797109-a3e2-4574-b78e-610af7112973 va-springfield-saint-james https://www.hudl.com/profile/19688611 19688611
df20e770-9033-4462-ba50-3e5444e27959 nj-glassboro-glassboro https://www.hudl.com/profile/19055410 19055410
050f1a88-b495-467e-a80d-de9feeffcbe0 nj-glassboro-glassboro https://www.hudl.com/profile/19055410 19055410
3fc59d5e-9080-49be-92f2-29af0502185c ca-tustin-tustin https://www.hudl.com/profile/16240673 16240673
764eaca7-fcab-4731-a5f8-ee8d5439fbb3 ca-tustin-tustin https://www.hudl.com/profile/19520967 19520967
37904ca5-6ff5-44d4-b950-e10896a1d952 nc-cornelius-hough https://www.hudl.com/profile/9823173 9823173
4721f539-8749-450a-b15a-466b4616fc0d nc-cornelius-hough https://www.hudl.com/profile/19494412 19494412
97fc3776-92ba-4cfa-9110-1eebfe77f22b la-ruston-ruston https://www.hudl.com/profile/16751692 16751692
acee3e06-220d-44c8-b924-acf03d868b32 la-ruston-ruston https://www.hudl.com/profile/23629919 23629919
881161e9-5056-40a3-ae0c-e82dac3bcbb9 ga-gainesville-gainesville https://www.hudl.com/profile/16833240 16833240
60f2ba82-2609-47a4-9637-6ae553a6d188 ga-gainesville-gainesville https://www.hudl.com/profile/19384713 19384713
d91c0ebc-5ec1-48d0-8366-c4277ffb46ca hi-mililani-mililani https://www.hudl.com/profile/17953752 17953752
68714512-ff29-481c-8dbf-bd60129fd2ff nj-jersey-city-saint-peters-prep https://www.hudl.com/profile/19739500 19739500
97fd826f-1e02-46e5-acbe-ab6deb456077 ga-powder-springs-mceachern https://www.hudl.com/profile/19308460 19308460
30cd2ff8-9a6b-4bc1-94ac-2528b1620557 ga-leesburg-lee-county https://www.hudl.com/profile/19321690 19321690
8c098bc1-8ca9-42d6-9673-12105197ee9f tn-brentwood-brentwood-academy https://www.hudl.com/profile/21922659 21922659
03f54899-e6f6-4fb9-b2c0-a8feee231741 tn-brentwood-brentwood-academy https://www.hudl.com/profile/19544745 19544745
d11e1c07-d731-463b-922b-05851cdc7834 fl-orlando-jones https://www.hudl.com/profile/19746113 19746113
045811c5-f54b-4961-bdd1-436b06f4af48 fl-orlando-jones https://www.hudl.com/profile/19746113 19746113
61578221-1ef2-44c7-86fa-3278d91d6168 pa-pittsburgh-central-catholic https://www.hudl.com/profile/22637312 22637312
ba29b1bb-e829-4b92-8274-d535cf047ba1 ga-fairburn-creekside https://www.hudl.com/profile/19403692 19403692
0aaf6b71-85ad-4934-b344-7635909169af il-chicago-mount-carmel https://www.hudl.com/profile/20228458 20228458
0c936d91-8246-442a-9c67-8e4ab5fe9cab il-chicago-mount-carmel https://www.hudl.com/profile/19379885 19379885
f6330c42-28fe-4995-90b5-a11b9fcab628 il-chicago-mount-carmel https://www.hudl.com/profile/20228529 20228529
ffebebbd-0afc-4b31-8e0c-e361b6e7e096 il-east-saint-louis-east-saint-louis https://www.hudl.com/profile/22185816 22185816
ba9ca33f-3bcf-4b71-9bda-c324f801ad53 il-east-saint-louis-east-saint-louis https://www.hudl.com/profile/22185816 22185816
73ad61cf-08b4-4a55-b990-d1c98e36c84f il-east-saint-louis-east-saint-louis https://www.hudl.com/profile/20080624 20080624
""".strip().splitlines()

HUDL_NAMES = {
    "22055854": "Eric Mcfarland lll",
    "19304058": "Zyron Forstall",
    "22432094": "Aaryn Washington",
    "18008781": "Jackson Vaughn",
    "16860665": "Anthony Sweeney",
    "19341597": "Raylaun Henry",
    "19576984": "Danny Lang",
    "19972142": "Mark Matthews",
    "20767020": "Julius Jones",
    "20133523": "Wyatt Smith",
    "19530451": "Zayden Gamble",
    "24297059": "Jordan Agbanoma",
    "19965528": "Jalen Brewster",
    "22567319": "Marcus Fakatou",
    "19474303": "Kasi Currie",
    "19495559": "Myles Baker",
    "18174937": "Blake Roskopf",
    "19444261": "Hayden Stepp",
    "19603450": "Eli Woodard",
    "19470635": "Jake Hildebrand",
    "15927844": "Peter Bourque",
    "15480201": "David Gabriel Georges",
    "18094089": "Keegan Croucher",
    "18196284": "Jaden Walk-Green",
    "20129253": "Quentin Hale",
    "19688611": "Kenaz Sullivan",
    "19055410": "Xavier Sabb",
    "16240673": "Khalil Terry",
    "19520967": "Taven Epps",
    "9823173": "Joshua Dobson",
    "19494412": "Davion Jones",
    "16751692": "Ahmad Hudson",
    "23629919": "Jayden Anding",
    "16833240": "Kharim Hughley",
    "19384713": "Nigel Newkirk",
    "17953752": 'Samson "Toa" Satele',
    "19739500": "Oluwasemilore Olubobola",
    "19308460": "Joakim Gouda",
    "19321690": "Jaden Upshaw",
    "21922659": "Kenneth Simon II",
    "19544745": "Kesean Bowman",
    "19746113": "Fred Ards",
    "22637312": "James Halter",
    "19403692": "Gary Walker",
    "20228458": "Quentin Burrell",
    "19379885": "Roman Igwebuike",
    "20228529": "Tavares Harrington",
    "22185816": "Myson Johnson-Cook",
    "20080624": "Raheem Floyd",
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


def norm(name: str) -> str:
    name = html.unescape(name or "")
    name = name.lower().replace("'", "").replace("’", "")
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = SUFFIX.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


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


def match_recruit(school: dict, hudl_name: str) -> dict:
    hn = norm(hudl_name)
    tokens = hn.split()
    first, last = (tokens[0] if tokens else ""), (tokens[-1] if tokens else "")
    roster = school.get("recruits") or []
    exact = [r for r in roster if norm(r.get("full_name") or "") == hn]
    if len(exact) == 1:
        return exact[0]
    first_last = []
    for rec in roster:
        rn = norm(rec.get("full_name") or "")
        bits = rn.split()
        if not (first and last and last in bits):
            continue
        if first in bits or any(b.startswith(first) or first.startswith(b) for b in bits if len(min(b, first, key=len)) >= 3):
            first_last.append(rec)
    uniq = {r["id"]: r for r in first_last}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    # Nickname in quotes, e.g. Samson "Toa" Satele → Toa Satele
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
    raise SystemExit(f"no unique roster match for {hudl_name!r} at {school['id']}")


def main() -> None:
    schools = json.loads((SITE / "schools.json").read_text())
    by_id = {s["id"]: s for s in schools}

    players_out = []
    recruit_hudl: dict[str, dict] = {}
    for line in PAYLOAD:
        pid, payload_school, url, hid = line.split()
        school_id = CANON_SCHOOL.get(payload_school, payload_school)
        school = by_id.get(school_id)
        if not school:
            raise SystemExit(f"missing school {school_id} (payload {payload_school})")
        hudl_name = HUDL_NAMES[hid]
        rec = match_recruit(school, hudl_name)
        row = {
            "id": pid,
            "recruit_id": rec["id"],
            "school_id": school_id,
            "payload_school_id": payload_school,
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

    if len(players_out) != 52:
        raise SystemExit(f"expected 52 payload players, got {len(players_out)}")
    if len(TEAM_URLS) != 41:
        raise SystemExit(f"expected 41 team URLs, got {len(TEAM_URLS)}")
    for sid in TEAM_URLS:
        if sid not in by_id:
            raise SystemExit(f"team URL school missing on board: {sid}")
        if "boys-varsity-football" not in TEAM_URLS[sid]:
            raise SystemExit(f"not a boys-varsity-football URL: {sid}")

    hudl_doc = {
        "as_of": "2026-08-26",
        "notes": [
            "First verified public Hudl batch (On3 embed → hudl.com/profile/{id}).",
            "52 payload rows / 49 unique athlete ids. Duplicate payload UUIDs share one Hudl id (Glassboro, Jones, East St. Louis).",
            "Payload UUID is not the FridayRadar recruit id; join is payload id → public Hudl name → school roster recruit id.",
            "359 unmatched recruits are omitted on purpose. Do not invent athlete URLs.",
            "41/41 top-school public team pages. C.E. King has a team page and 0 recruit Hudl profiles.",
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
            hit = hudl_by_recruit.get(rec["id"])
            if not hit:
                continue
            source_ids = dict(rec.get("source_ids") or {})
            source_ids["hudl"] = hit["hudl_athlete_id"]
            rec["source_ids"] = source_ids
            urls = rating_profile_urls(rec)
            urls["hudl"] = hit["hudl_url"]
            rec["profile_urls"] = urls

    # King recruits must not get Hudl
    king = by_id["tx-houston-c-e-king"]
    if king.get("hudl_team_url") != TEAM_URLS["tx-houston-c-e-king"]:
        raise SystemExit("C.E. King team URL missing")
    for rec in king.get("recruits") or []:
        if rec.get("profile_urls", {}).get("hudl") or (rec.get("source_ids") or {}).get("hudl"):
            raise SystemExit(f"invented King Hudl on {rec['id']}")

    img = by_id["fl-bradenton-img-academy"]
    mcf = next(r for r in img["recruits"] if r["id"] == "247-46148083")
    if mcf["profile_urls"]["hudl"] != "https://www.hudl.com/profile/22055854":
        raise SystemExit("McFarland Hudl mismatch")
    buf = by_id["ga-buford-buford"]
    brew = next(r for r in buf["recruits"] if r["id"] == "247-46145095")
    if brew["profile_urls"]["hudl"] != "https://www.hudl.com/profile/19965528":
        raise SystemExit("Brewster Hudl mismatch")

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
