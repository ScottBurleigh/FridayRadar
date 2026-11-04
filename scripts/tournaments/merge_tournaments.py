#!/usr/bin/env python3
"""
Merge Zorts + Flag50 tournament lists into one deduplicated dataset (FridayRadar /tournaments schema).

Inputs : data/zorts/tournaments.json (fetch_zorts.py), data/flag50.json (fetch_flag50.py)
Outputs: tournaments.json, tournaments.csv, dedupe_report.md (+ tournaments.html via make_html.py)

Matching (union-find over all records):
  A. Hard link: a Flag50 record whose id is 'zs<tid>' or whose registration URL is a Zorts event
     -> same event as Zorts tid. Two Flag50 records linking the same Zorts tid are also merged.
  B. Fuzzy: same state, start dates within +/-1 day, compatible city (equal, one contains the other,
     or one blank), and similar normalized names (years, punctuation, city/state words and filler
     words like 'presents', 'tournament', 'clone' removed): token containment == 1.0 (with >= 2 shared tokens) or
     SequenceMatcher ratio >= 0.85, AND the names do not differ by a discriminating token
     (girls/boys/coed, high/middle school, numbers, pt/part, roman numerals, day names, indoor...).
     Near misses (ratio >= 0.6 on the same dates/city) are listed in the report as NOT merged.
Merged row: primary = Zorts record with the lowest tid (else Flag50), id 'zorts-<tid>' or 'flag50-<id>'.
"""
import csv, datetime as dt, difflib, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import girls_filter  # noqa: E402

STOP = {"the", "a", "an", "of", "and", "at", "in", "by", "to", "for", "presents", "presented", "powered",
        "brought", "you", "tournament", "tournaments", "tourney", "event", "annual", "clone", "copy", "series",
        "football", "usa", "us", "tx", "texas", "st", "nd", "rd", "th", "with", "vs", "edition"}
DISCRIM = {"girls", "girl", "boys", "boy", "coed", "high", "middle", "elementary", "school", "hs", "ms",
           "youth", "adult", "varsity", "jv", "pt", "part", "i", "ii", "iii", "iv", "v", "vi", "indoor",
           "outdoor", "friday", "saturday", "sunday", "day", "1", "2", "3", "4", "5", "6"}
NUMWORDS = re.compile(r"^(19|20)\d\d$|^\d{1,2}$")

def norm_tokens(name, city="", state_name="texas"):
    s = (name or "").lower().replace("’", "'").replace("&", " and ")
    s = re.sub(r"\b(19|20)\d{2}\b|\b\d{2}'", " ", s)            # years: 2026, 27'
    s = re.sub(r"\b\d{1,2}[./]\d{1,2}(?:[./-]\d{1,4})*\b", " ", s)  # dates like 1.23-1.24
    s = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    city_toks = set(re.sub(r"[^a-z0-9]+", " ", (city or "").lower()).split())
    toks = [t for t in s.split() if t not in STOP and t != state_name]
    stripped = [t for t in toks if t not in city_toks]
    return stripped or toks

def ncity(c):
    c = re.sub(r"[^a-z ]+", " ", (c or "").lower())
    c = re.sub(r"\b(metropolitan area|metro|area|tx|texas|usa)\b", " ", c)
    return re.sub(r"\s+", " ", c).strip()

def city_ok(a, b):
    x, y = ncity(a), ncity(b)
    return (not x or not y) or x == y or x in y or y in x

def fee_num(s):
    m = re.search(r"\$([\d,]+(?:\.\d+)?)", s or "")
    return float(m.group(1).replace(",", "")) if m else None

def d(s): return dt.date.fromisoformat(s)

def name_match(r1, r2):
    t1, t2 = r1["_toks"], r2["_toks"]
    if not t1 or not t2: return 0.0, "empty name", False
    s1, s2 = set(t1), set(t2)
    diff = (s1 ^ s2)
    bad = sorted(t for t in diff if t in DISCRIM or t.isdigit())
    ratio = difflib.SequenceMatcher(None, " ".join(t1), " ".join(t2)).ratio()
    contain = len(s1 & s2) / min(len(s1), len(s2))
    shared = len(s1 & s2)
    ok = ((contain == 1.0 and shared >= 2) or ratio >= 0.85) and not bad
    why = f"ratio={ratio:.2f}, containment={contain:.2f}" + (f", differs by {bad}" if bad else "")
    if contain == 1.0 and shared < 2 and ratio < 0.85: why += f", only {shared} shared token"
    return max(ratio, contain if not bad else ratio), why, ok

def check_zorts(tid):
    """Open the public Zorts event page for a tid and read its header (sport, type, dates)."""
    import urllib.request, time, html as H
    url = f"https://www.zortssports.com/join/tournament/{tid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FridayRadarBot/1.0 (+tournament listing cross-check)"})
        page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"); time.sleep(0.5)
    except Exception as ex:
        print(f"zorts link check {tid} failed: {ex}", file=sys.stderr); return None
    m = re.search(r'(?s)<h4 style="margin:0">(.*?)</h4>', page)
    if not m: return None
    header = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).replace("\xa0", " ").strip()
    from fetch_zorts import parse_long
    dm = re.search(r"-\s*([A-Z][a-z]+ \d{1,2})(?: to ([A-Z][a-z]+ \d{1,2}))?, (\d{4})", header)
    start = None
    if dm:
        st = parse_long(dm.group(1) + ", " + dm.group(3)); start = st.isoformat() if st else None
    return {"url": url, "header": header, "start": start}

class UF:
    def __init__(s, n): s.p = list(range(n))
    def f(s, i):
        while s.p[i] != i: s.p[i] = s.p[s.p[i]]; i = s.p[i]
        return i
    def u(s, a, b): s.p[s.f(a)] = s.f(b)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zorts", default=os.path.join(HERE, "data", "zorts", "tournaments.json"))
    ap.add_argument("--flag50", default=os.path.join(HERE, "data", "flag50.json"))
    ap.add_argument("--outdir", default=HERE)
    ap.add_argument("--no-link-check", action="store_true",
                    help="don't open Zorts event pages for Flag50 rows whose linked Zorts event is missing from the Zorts feed")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    from states import NAMES
    Z = json.load(open(a.zorts)); F = json.load(open(a.flag50))
    recs = []
    for r in Z["tournaments"]:
        r = dict(r); r["source"] = "zorts"; r["_tid"] = r["id"]; r.setdefault("state", "TX"); recs.append(r)
    for r in F["tournaments"]:
        r = dict(r); r["_tid"] = r.get("zorts_tid") or ""; recs.append(r)
    for r in recs:
        r["_toks"] = norm_tokens(r["name"], r.get("city"), NAMES.get(r.get("state"), "").lower())
    n = len(recs); uf = UF(n); merges, near = [], []
    by_tid = {}
    for i, r in enumerate(recs):
        if r["_tid"]: by_tid.setdefault(r["_tid"], []).append(i)
    for tid, idx in by_tid.items():
        for j in idx[1:]:
            uf.u(idx[0], j)
            merges.append(("link", idx[0], j, f"same Zorts event id {tid} (Flag50 id/registration URL)"))
    for i in range(n):
        for j in range(i + 1, n):
            r1, r2 = recs[i], recs[j]
            if r1.get("state") != r2.get("state"): continue
            if abs((d(r1["start_date"]) - d(r2["start_date"])).days) > 1: continue
            if not city_ok(r1.get("city"), r2.get("city")): continue
            score, why, ok = name_match(r1, r2)
            same = uf.f(i) == uf.f(j)
            if ok and not same:
                # never fuzzy-merge two different Zorts events of different sources' hard links unless names match
                uf.u(i, j); merges.append(("fuzzy", i, j, why + f"; dates {r1['start_date']}/{r2['start_date']}; city '{r1.get('city')}'/'{r2.get('city')}'"))
            elif not ok and not same and score >= 0.6:
                near.append((i, j, why))
    clusters = {}
    for i in range(n): clusters.setdefault(uf.f(i), []).append(i)

    out, report_rows, dropped, link_checks = [], [], [], []
    girls_dropped, recats = [], []
    for root, idx in clusters.items():
        group = [recs[i] for i in idx]
        zs = sorted([g for g in group if g["source"] == "zorts"], key=lambda g: int(g["_tid"]))
        fs = [g for g in group if g["source"] == "flag50"]
        if not zs and fs and all(g.get("flag50_is_adult") for g in fs):
            dropped.append((fs, "Flag50-only adult event (isAdult=true); not a youth tournament")); continue
        prim = dict(zs[0] if zs else fs[0])
        row = {k: v for k, v in prim.items() if not k.startswith("_")}
        row["id"] = f"zorts-{prim['_tid']}" if zs else prim["id"]
        for g in group[1:] if False else group:
            for k in ("venue", "divisions", "entry_fee", "registration_ends", "organizer", "contact_email",
                      "contact_phone", "age_groups", "city", "sport", "clubhouse_url"):
                if not row.get(k) and g.get(k): row[k] = g[k]
        cats = {g["category"] for g in group}
        seven = any(c in ("7v7", "both") for c in cats); flag = any(c in ("flag", "both") for c in cats)
        row["category"] = "both" if seven and flag else "7v7" if seven else "flag"
        row["sources"] = sorted({g["source"] for g in group})
        row["verified"] = len(row["sources"]) > 1
        row["zorts_url"] = f"https://www.zortssports.com/join/tournament/{zs[0]['_tid']}" if zs else ""
        row["flag50_url"] = fs[0]["event_url"] if fs else ""
        row["event_url"] = row["zorts_url"] or row["flag50_url"]
        row["source"] = "+".join(row["sources"])
        others = [g["event_url"] for g in zs[1:]] + [g["event_url"] for g in fs[1:]]
        row["also_listed_as"] = others
        conf = []
        starts = sorted({g["start_date"] for g in group}); ends = sorted({g["end_date"] for g in group})
        if len(starts) > 1: conf.append("start date differs: " + "; ".join(f"{g['source']} {g['id']}={g['start_date']}" for g in group))
        if len(ends) > 1: conf.append("end date differs: " + "; ".join(f"{g['source']} {g['id']}={g['end_date']}" for g in group))
        cities = {ncity(g.get("city")) for g in group if g.get("city")}
        if len(cities) > 1 and not all(city_ok(x, y) for x in cities for y in cities):
            conf.append("city differs: " + "; ".join(f"{g['source']} {g['id']}={g.get('city')}" for g in group))
        fees = {fee_num(g.get("entry_fee")) for g in group if fee_num(g.get("entry_fee")) is not None}
        if len(fees) > 1: conf.append("fee differs: " + "; ".join(f"{g['source']} {g['id']}={g.get('entry_fee')}" for g in group if g.get("entry_fee")))
        if any(g.get("flag50_is_adult") for g in fs): conf.append("Flag50 marks a listing as adult (isAdult)")
        if any(g.get("flag50_event_type") == "review" for g in fs): conf.append("Flag50 eventType='review'")
        if not zs and not a.no_link_check:
            tids = sorted({g["_tid"] for g in fs if g["_tid"]})
            if tids:
                chk = check_zorts(tids[0])
                if chk:
                    row["zorts_url"] = chk["url"]; row["sources"] = sorted(set(row["sources"]) | {"zorts"})
                    row["verified"] = True; row["source"] = "+".join(row["sources"])
                    conf.append(f"linked Zorts event {tids[0]} is not in the Zorts feed; its page says: {chk['header']}")
                    if chk["start"] and chk["start"] != row["start_date"]:
                        conf.append(f"start date differs: flag50={row['start_date']}; zorts page={chk['start']}")
                    link_checks.append((row["id"], tids[0], chk))
        row["conflicts"] = " | ".join(conf)
        row["start_date"] = prim["start_date"]; row["end_date"] = prim["end_date"]
        for k in ("zorts_tid", "flag50_id", "flag50_event_type", "registration_platform", "flag50_is_adult"):
            row.pop(k, None)
        gc = girls_filter.classify(row)
        if gc["girls_only"]:
            girls_dropped.append((row, gc["reason"])); continue
        if gc["category"] != row["category"]:
            recats.append((row["id"], row["name"], row["category"], gc["category"])); row["category"] = gc["category"]
        row["has_girls_divisions"] = gc["has_girls_divisions"]
        row["girls_divisions"] = gc["girls_divisions"]
        row["open_divisions"] = gc["open_divisions"]
        out.append(row)
        if len(group) > 1:
            report_rows.append((row, group))

    out.sort(key=lambda r: (r["start_date"], r["name"].lower()))
    # integrity checks
    ids = [r["id"] for r in out]
    assert len(ids) == len(set(ids)), "duplicate ids"
    keys = [(" ".join(norm_tokens(r["name"], r.get("city"))), r["start_date"], ncity(r.get("city"))) for r in out]
    dupk = [k for k in set(keys) if keys.count(k) > 1]
    assert not dupk, f"duplicate name+date+city keys: {dupk}"

    today = Z.get("window", [None])[0] or F.get("window", [None])[0]
    window = Z.get("window") or F.get("window")
    gen = dt.datetime.now().isoformat(timespec="seconds")
    os.makedirs(a.outdir, exist_ok=True)
    json.dump({"generated": gen, "window": window, "count": len(out), "tournaments": out},
              open(os.path.join(a.outdir, "tournaments.json"), "w"), indent=2)
    fields = ["id", "category", "state", "name", "start_date", "end_date", "city", "venue", "sport", "age_groups",
              "divisions", "entry_fee", "registration_ends", "organizer", "contact_email", "contact_phone",
              "event_url", "clubhouse_url", "source", "sources", "verified", "conflicts", "zorts_url", "flag50_url", "also_listed_as", "has_girls_divisions", "girls_divisions"]
    with open(os.path.join(a.outdir, "tournaments.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader()
        for r in out: w.writerow({**r, "sources": ";".join(r["sources"]), "also_listed_as": ";".join(r["also_listed_as"]), "girls_divisions": "; ".join(r["girls_divisions"])})

    # report
    L = [f"# Dedupe report ({gen})", "",
         f"- Zorts input: {len(Z['tournaments'])}  |  Flag50 input: {len(F['tournaments'])} (raw {F.get('raw_count')})",
         f"- Girls-only removed: {len(girls_dropped)}  |  recategorized: {len(recats)}",
         f"- Final rows: {len(out)}  |  verified on both: {sum(r['verified'] for r in out)}",
         f"- Merge edges: {len(merges)}  |  near-misses not merged: {len(near)}  |  dropped: {sum(len(x[0]) for x in dropped)}", "",
         "## Merged groups", ""]
    for row, group in sorted(report_rows, key=lambda x: x[0]["start_date"]):
        kind = "cross-source" if row["verified"] else "within-source duplicate"
        L.append(f"### {row['start_date']} {row['name']} -> `{row['id']}` ({kind})")
        for g in group:
            L.append(f"- {g['source']} `{g['id']}`: {g['name']} | {g['start_date']}..{g['end_date']} | {g.get('city')} | {g.get('entry_fee') or 'no fee'} | {g['event_url']}")
        ids_in = {g["id"] for g in group}
        for kind2, i, j, why in merges:
            if recs[i]["id"] in ids_in and recs[j]["id"] in ids_in:
                L.append(f"  - reason ({kind2}): `{recs[i]['id']}` ~ `{recs[j]['id']}`: {why}")
        if row["conflicts"]: L.append(f"  - **conflicts:** {row['conflicts']}")
        L.append("")
    L += ["## Possible duplicates NOT merged", ""]
    for i, j, why in near:
        r1, r2 = recs[i], recs[j]
        L.append(f"- `{r1['id']}` {r1['name']} ({r1['start_date']}, {r1.get('city')}) vs `{r2['id']}` {r2['name']} ({r2['start_date']}, {r2.get('city')}): not merged: {why}")
    L += ["", "## Flag50 rows linked to a Zorts event missing from the Zorts feed (checked via the Zorts event page)", ""]
    for rid, tid, chk in link_checks:
        L.append(f"- `{rid}` -> Zorts {tid}: {chk['header']} ({chk['url']})")
    L += ["", f"## Girls-only tournaments removed ({len(girls_dropped)})", ""]
    for r, why in girls_dropped: L.append(f"- `{r['id']}` {r['name']} ({r['start_date']}, {r.get('city')}): {why}")
    L += ["", f"## Recategorized from non-girls divisions only ({len(recats)})", ""]
    for rid, nm, a0, b0 in recats: L.append(f"- `{rid}` {nm}: {a0} -> {b0}")
    L += ["", f"- Kept rows that also have girls divisions (has_girls_divisions): {sum(r['has_girls_divisions'] for r in out)}"]
    L += ["", "## Dropped", ""]
    for fs, why in dropped:
        for g in fs: L.append(f"- `{g['id']}` {g['name']} ({g['start_date']}, {g.get('city')}): {why}")
    open(os.path.join(a.outdir, "dedupe_report.md"), "w").write("\n".join(L) + "\n")
    from collections import Counter
    print(f"merged: {len(out)} rows ({dict(Counter(r['category'] for r in out))}), verified {sum(r['verified'] for r in out)}, "
          f"merge edges {len(merges)}, near-misses {len(near)}, dropped {sum(len(x[0]) for x in dropped)}", file=sys.stderr)
    try:
        import make_html
        make_html.build(os.path.join(a.outdir, "tournaments.json"), os.path.join(a.outdir, "tournaments.html"))
    except Exception as ex:
        print(f"html generation failed: {ex}", file=sys.stderr)

if __name__ == "__main__":
    main()
