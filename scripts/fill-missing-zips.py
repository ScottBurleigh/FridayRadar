#!/usr/bin/env python3
"""Fill missing school zips/coords from MaxPreps schoolInfo or public geocoders.

Does not invent zips: only writes a zip that a lookup returned. Updates
site-data/schools.json and data/import/schools.json in place.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-data" / "schools.json"
IMPORT = ROOT / "data" / "import" / "schools.json"
CENTROIDS = ROOT / "data" / "zip-centroids.json"
CACHE = Path("/tmp/fridayradar-zip-cache")
UA = {
    "User-Agent": "FridayRadar/1.0 (high-school zip lookup; local dataset rebuild)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
BUILD_ID = "30052b80-31ab3f27"
COMMON_NAMES = {
    "central", "north", "south", "east", "west", "union", "city", "county",
    "memorial", "christian", "catholic", "academy", "roosevelt", "washington",
    "lincoln", "jefferson", "madison", "franklin", "kennedy", "edison", "wilson",
    "high", "school", "prep", "collegiate",
}
NAME_STOP = {
    "high", "school", "hs", "academy", "prep", "college", "preparatory",
    "the", "of", "and",
}
US_STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "DC": "district of columbia", "FL": "florida", "GA": "georgia", "HI": "hawaii",
    "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming",
}
ALLOWED_OSM = {
    "school", "college", "university", "kindergarten", "building",
    "educational_institution", "yes",
}
PATH_OVERRIDES = {
    "fl-hollywood-chaminade-madonna": "/fl/hollywood/chaminade-madonna-lions/",
    "ga-alpharetta-milton": "/ga/milton/milton-eagles/",
    "ca-west-hills-chaminade": "/ca/west-hills/chaminade-eagles/",
    "ca-sherman-oaks-notre-dame": "/ca/sherman-oaks/notre-dame-so-knights/",
    "fl-fort-lauderdale-american-heritage": "/fl/plantation/american-heritage-patriots/",
}


def slugify(text: str) -> str:
    t = (text or "").lower().replace("&", " and ")
    t = re.sub(r"['’]", "", t)
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-")


def pad_zip(raw) -> str | None:
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 5:
        return None
    return digits[:5]


def norm(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("saint ", "st ").replace("mt.", "mount").replace(".", "")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def cities_close(a: str, b: str) -> bool:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    ta, tb = na.split(), nb.split()
    if ta and tb and ta[0] == tb[0] and len(ta[0]) >= 6:
        return True
    return False


def names_close(a: str, b: str) -> bool:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    sa, sb = set(na.split()) - NAME_STOP, set(nb.split()) - NAME_STOP
    return bool(sa and sb and (sa <= sb or sb <= sa))


def state_match(feat_state: str, want: str) -> bool:
    want = (want or "").upper()
    fs = (feat_state or "").strip()
    if not want or not fs:
        return False
    if fs.upper() == want:
        return True
    return norm(fs) == US_STATE_NAMES.get(want, "")


def needs_city_match(name: str) -> bool:
    tokens = [t for t in norm(name).split() if t not in {"high", "school", "hs"}]
    if len(tokens) <= 1:
        return True
    return any(t in COMMON_NAMES for t in tokens)


def mp_matches(info: dict, school: dict) -> bool:
    st = (info.get("stateCode") or info.get("state") or "").upper()
    if st and st != (school.get("state") or "").upper():
        return False
    name_ok = names_close(info.get("name") or "", school.get("name") or "")
    if not name_ok:
        return False
    mp_city = info.get("city") or ""
    our_city = school.get("city") or ""
    if mp_city and our_city and not cities_close(mp_city, our_city):
        tokens = [
            t
            for t in norm(school.get("name") or "").split()
            if t not in {"high", "school", "hs", "the", "of"}
        ]
        # Short/generic names must share a city so Riverside Notre Dame cannot
        # fill Sherman Oaks (and similar collisions).
        if len(tokens) < 3:
            return False
    return True


def cache_path(key: str) -> Path:
    h = hashlib.sha1(key.encode()).hexdigest()
    return CACHE / f"{h}.json"


def http_get(url: str, timeout: int = 20) -> tuple[int, str]:
    cp = cache_path(url)
    if cp.exists():
        rec = json.loads(cp.read_text())
        return rec["status"], rec.get("body") or ""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        status = e.code
    except Exception as e:
        body = str(e)
        status = 0
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"status": status, "body": body if status == 200 else ""}))
    time.sleep(0.08)
    return status, body if status == 200 else ""


def school_info_from_html(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    pp = (data.get("props") or {}).get("pageProps") or {}
    ctx = pp.get("schoolContext") or {}
    info = ctx.get("schoolInfo") or {}
    if info.get("schoolId") or info.get("zip") or info.get("address"):
        return info
    tc = ((pp.get("teamContext") or {}).get("data") or {})
    if tc.get("teamId") or tc.get("schoolZipCode"):
        return {
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
        }
    return None


def candidate_paths(school: dict) -> list[str]:
    paths: list[str] = []
    sid = school.get("id") or ""
    if sid in PATH_OVERRIDES:
        paths.append(PATH_OVERRIDES[sid])
    mp = school.get("maxpreps") or {}
    url = (mp.get("canonicalUrl") or "").strip()
    if url.startswith("https://www.maxpreps.com/"):
        path = urllib.parse.urlparse(url).path
        if path.endswith(".json"):
            path = path[: -len(".json")]
        if not path.endswith("/"):
            path += "/"
        paths.append(path)
    st = (school.get("state") or "").lower()
    city = slugify(school.get("city") or "")
    name = slugify(school.get("name") or "")
    name = (
        name.replace("-high-school", "")
        .replace("-high", "")
        .replace("saint-", "st-")
    )
    mascot = slugify(mp.get("mascot") or "")
    city_opts = [c for c in (city, name) if c]
    name_opts = [n for n in (name, city) if n]
    for c in city_opts:
        for n in name_opts:
            if mascot:
                paths.append(f"/{st}/{c}/{n}-{mascot}/")
                paths.append(f"/{st}/{c}/{c}-{mascot}/")
                paths.append(f"/{st}/{c}/{n}-so-{mascot}/")
            paths.append(f"/{st}/{c}/{n}/")
    # Unique, keep order, cap attempts.
    seen = set()
    out = []
    for p in paths:
        if not p or p in seen or p.count("/") < 4:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= 8:
            break
    return out


def fetch_maxpreps(school: dict) -> dict | None:
    for path in candidate_paths(school):
        for url in (
            f"https://www.maxpreps.com{path}",
            f"https://www.maxpreps.com/_next/data/{BUILD_ID}{path.rstrip('/')}.json",
        ):
            status, body = http_get(url)
            if status != 200 or not body:
                continue
            info = None
            if url.endswith(".json"):
                try:
                    payload = json.loads(body)
                    pp = payload.get("pageProps") or payload
                    info = (pp.get("schoolContext") or {}).get("schoolInfo")
                    if not info:
                        tc = ((pp.get("teamContext") or {}).get("data") or {})
                        if tc.get("schoolZipCode") or tc.get("teamId"):
                            info = {
                                "schoolId": tc.get("teamId"),
                                "name": tc.get("schoolName"),
                                "city": tc.get("schoolCity"),
                                "stateCode": tc.get("stateCode"),
                                "zip": tc.get("schoolZipCode"),
                                "address": tc.get("schoolAddress"),
                                "mascot": tc.get("schoolMascot"),
                                "canonicalUrl": tc.get("schoolCanonicalUrl"),
                                "latitude": None,
                                "longitude": None,
                            }
                except json.JSONDecodeError:
                    info = None
            else:
                info = school_info_from_html(body)
            if info and mp_matches(info, school):
                z = pad_zip(info.get("zip") or info.get("zipCode"))
                if z or info.get("address") or (info.get("latitude") is not None):
                    return info
    return None


def census_address(street: str, city: str, state: str) -> dict | None:
    if not street or not city or not state or len(street) < 5:
        return None
    q = urllib.parse.urlencode(
        {
            "street": street,
            "city": city,
            "state": state,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
    )
    url = "https://geocoding.geo.census.gov/geocoder/locations/address?" + q
    status, body = http_get(url, timeout=25)
    if status != 200 or not body:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    matches = (data.get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    hit = matches[0]
    comp = hit.get("addressComponents") or {}
    coords = hit.get("coordinates") or {}
    zipc = pad_zip(comp.get("zip"))
    if not zipc:
        return None
    lat = coords.get("y")
    lng = coords.get("x")
    return {
        "zip": zipc,
        "lat": float(lat) if lat is not None else None,
        "lng": float(lng) if lng is not None else None,
        "source": "census_address",
        "matched": hit.get("matchedAddress"),
    }


def photon_search(school: dict) -> dict | None:
    city = school.get("city") or ""
    state = school.get("state") or ""
    name = school.get("name") or ""
    if not city or not state or not name:
        return None
    q = f"{name} High School, {city}, {state}, USA"
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": q, "limit": 8})
    status, body = http_get(url, timeout=20)
    if status != 200 or not body:
        return None
    try:
        feats = json.loads(body).get("features") or []
    except json.JSONDecodeError:
        return None
    for feat in feats:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None]
        postcode = pad_zip(props.get("postcode"))
        if not postcode:
            continue
        country = (props.get("countrycode") or "").upper()
        if country and country not in {"US", "USA"}:
            continue
        if not state_match(props.get("statecode") or props.get("state") or "", state):
            continue
        feat_city = props.get("city") or props.get("town") or ""
        if not cities_close(feat_city, city):
            continue
        osm_value = (props.get("osm_value") or "").lower()
        if osm_value and osm_value not in ALLOWED_OSM:
            continue
        if not names_close(props.get("name") or "", name):
            continue
        lng, lat = coords[0], coords[1]
        return {
            "zip": postcode,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "source": "photon",
            "matched": props.get("name"),
        }
    return None


def nominatim_search(school: dict) -> dict | None:
    city = school.get("city") or ""
    state = school.get("state") or ""
    name = school.get("name") or ""
    if not city or not state or not name:
        return None
    q = f"{name} High School, {city}, {state}, United States"
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "addressdetails": 1, "limit": 5, "countrycodes": "us"}
    )
    status, body = http_get(url, timeout=25)
    time.sleep(0.9)
    if status != 200 or not body:
        return None
    try:
        hits = json.loads(body)
    except json.JSONDecodeError:
        return None
    for h in hits:
        addr = h.get("address") or {}
        postcode = pad_zip(addr.get("postcode"))
        if not postcode:
            continue
        if not state_match(addr.get("state") or addr.get("ISO3166-2-lvl4") or "", state):
            # ISO3166-2-lvl4 is like US-GA
            iso = (addr.get("ISO3166-2-lvl4") or "")
            if iso.upper() != f"US-{state.upper()}":
                continue
        feat_city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
        if not cities_close(feat_city, city):
            continue
        if not names_close(h.get("name") or h.get("display_name") or "", name):
            continue
        return {
            "zip": postcode,
            "lat": float(h["lat"]) if h.get("lat") else None,
            "lng": float(h["lon"]) if h.get("lon") else None,
            "source": "nominatim",
            "matched": h.get("display_name"),
        }
    return None


def apply_lookup(school: dict, zipc: str, lat, lng, address=None, mp_info=None, source=""):
    school["zip"] = zipc
    school["zip5"] = zipc
    if lat is not None and lng is not None:
        school["lat"] = round(float(lat), 6)
        school["lng"] = round(float(lng), 6)
    if address and not school.get("address"):
        school["address"] = address
    if mp_info:
        mp = dict(school.get("maxpreps") or {})
        if mp_info.get("schoolId"):
            mp["schoolId"] = mp_info["schoolId"]
        if mp_info.get("canonicalUrl"):
            mp["canonicalUrl"] = mp_info["canonicalUrl"]
        if mp_info.get("mascot"):
            mp["mascot"] = mp_info["mascot"]
        if mp_info.get("formattedName"):
            mp["formattedName"] = mp_info["formattedName"]
        mp["zip"] = zipc
        if mp.get("canonicalUrl"):
            base = mp["canonicalUrl"].rstrip("/") + "/"
            mp.setdefault("footballUrl", base + "football/")
            mp.setdefault("scheduleUrl", base + "football/26-27/schedule/")
        school["maxpreps"] = mp
    school["_zip_source"] = source  # stripped before write


def fill_one(school: dict, centroids: dict) -> str | None:
    if pad_zip(school.get("zip") or school.get("zip5")):
        return None
    # 1) street address already on the row
    if school.get("address") and school.get("city") and school.get("state"):
        hit = census_address(school["address"], school["city"], school["state"])
        if hit:
            apply_lookup(school, hit["zip"], hit["lat"], hit["lng"], source="census_address")
            return "census_address"
    # 2) MaxPreps schoolInfo
    info = fetch_maxpreps(school)
    if info:
        zipc = pad_zip(info.get("zip") or info.get("zipCode"))
        addr = info.get("address")
        lat, lng = info.get("latitude"), info.get("longitude")
        if not zipc and addr and (info.get("city") or school.get("city")):
            geo = census_address(
                addr,
                info.get("city") or school.get("city"),
                info.get("stateCode") or school.get("state"),
            )
            if geo:
                zipc, lat, lng = geo["zip"], geo["lat"], geo["lng"]
        if zipc:
            if lat is None or lng is None:
                pair = centroids.get(zipc)
                if pair:
                    lat, lng = pair
            apply_lookup(
                school,
                zipc,
                lat,
                lng,
                address=addr,
                mp_info=info,
                source="maxpreps",
            )
            return "maxpreps"
    # 3) public name + city + state search
    for fn, label in ((photon_search, "photon"), (nominatim_search, "nominatim")):
        hit = fn(school)
        if hit:
            apply_lookup(school, hit["zip"], hit["lat"], hit["lng"], source=label)
            return label
    return None


def main() -> int:
    schools = json.loads(SITE.read_text())
    centroids = json.loads(CENTROIDS.read_text()) if CENTROIDS.exists() else {}
    missing = [s for s in schools if not pad_zip(s.get("zip") or s.get("zip5"))]
    print(f"missing zip: {len(missing)} / {len(schools)}", flush=True)
    counts: dict[str, int] = {}
    for i, sch in enumerate(missing, 1):
        src = fill_one(sch, centroids)
        if src:
            counts[src] = counts.get(src, 0) + 1
            print(
                f"  [{i}/{len(missing)}] {sch['id']} -> {sch.get('zip')} ({src})",
                flush=True,
            )
        elif i % 25 == 0:
            print(f"  [{i}/{len(missing)}] still missing {sch['id']}", flush=True)
    still = sum(1 for s in schools if not pad_zip(s.get("zip") or s.get("zip5")))
    for s in schools:
        s.pop("_zip_source", None)
    payload = json.dumps(schools)
    SITE.write_text(payload)
    IMPORT.write_text(payload)
    print(f"filled {sum(counts.values())} {counts}; still missing {still}")
    # sanity: IMG zip unchanged
    img = next(s for s in schools if s["id"] == "fl-bradenton-img-academy")
    print("IMG zip", img.get("zip"), "talent", img.get("talent_score"), "recruits", img.get("recruit_count"))
    cham = next((s for s in schools if s["id"] == "fl-hollywood-chaminade-madonna"), None)
    if cham:
        print("Chaminade-Madonna", cham.get("zip"), cham.get("address"), cham.get("lat"), cham.get("lng"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
