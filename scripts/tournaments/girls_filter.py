"""Girls-division classification shared by the pipeline.
classify(row) -> dict(girls_only, category, has_girls_divisions, girls_divisions, open_divisions, reason)
- A division is 'girls' if it says Girl/Women/Lady/Ladies/Female/GFF or uses a G-suffixed age (8UG, HSG).
- Untagged divisions inherit gender from the sport field when every sport part is girls/women.
- Category is computed only from non-girls divisions (7v7 / flag). A tournament whose only 7v7/flag
  divisions are girls (e.g. boys tackle + girls flag) is treated as girls-only and removed."""
import re
GIRL = re.compile(r"girl|wom[ae]n|\blady\b|\bladies\b|\bfemale\b|\bgff\b|\b\d{1,2}\s*ug\b|\bhsg\b|\bgir7s\b", re.I)
OPEN = re.compile(r"\bboy|\bcoed\b|\bco-ed\b|(?<!wo)\bmen'?s\b|\bmale\b", re.I)
SEVEN = re.compile(r"\b7\s*-?\s*(?:v|vs\.?|on|x)\s*-?\s*7\b|\bseven\s*on\s*seven\b", re.I)
FLAG = re.compile(r"flag|\b[45]\s*(?:v|on)\s*[45]\b(?!\s*lineman)", re.I)
LINEMAN = re.compile(r"lineman|tackle|big man", re.I)

def fmt_of(text):
    if LINEMAN.search(text) and not SEVEN.search(text) and "flag" not in text.lower(): return None
    if SEVEN.search(text): return "7v7"
    if FLAG.search(text): return "flag"
    return None

def classify(r):
    sport = r.get("sport") or ""; name = r.get("name") or ""
    parts = [p.strip() for p in re.split(r",\s*(?=[A-Z])", sport) if p.strip()]
    # 'Girl's, Coed Football (5v5)' style: gender words separated by commas
    sport_all_girls = bool(parts) and all(GIRL.search(p) for p in parts) and not OPEN.search(sport)
    open_sports = [p for p in parts if not GIRL.search(p)]
    divs = [d.strip() for d in (r.get("divisions") or "").split(";") if d.strip()]
    girls, opens = [], []
    for d in divs:
        if GIRL.search(d): girls.append(d)
        elif OPEN.search(d): opens.append(d)
        elif sport_all_girls: girls.append(d)
        elif GIRL.search(name) and not OPEN.search(name): girls.append(d)   # e.g. 'Girls 5v5 & 7on7 ...' with untagged divs
        else: opens.append(d)
    seven = flag = False
    if divs:
        single = fmt_of(" ".join(open_sports)) if len(open_sports) == 1 else None
        for d in opens:
            f = fmt_of(d) or (single if not re.search(r"\(.*\)", d) else None)
            if f is None and not re.search(r"\(.*\)", d):
                f = fmt_of(" ".join(open_sports)) or fmt_of(name)
            seven |= f == "7v7"; flag |= f == "flag"
    else:
        if sport_all_girls or (GIRL.search(name) and not OPEN.search(name + " " + sport)):
            pass
        else:
            txt = " ".join(open_sports) + " " + re.sub(GIRL, "", name)
            seven = bool(SEVEN.search(txt)); flag = bool(FLAG.search(txt))
            if not seven and not flag: seven, flag = r.get("category") in ("7v7", "both"), r.get("category") in ("flag", "both")
    cat = "both" if seven and flag else "7v7" if seven else "flag" if flag else ""
    reason = ""
    if not cat:
        reason = ("all divisions are girls" if divs and not opens else
                  "only non-girls divisions are tackle/lineman; all 7v7/flag divisions are girls" if divs else
                  "sport/name is girls/women only")
    return dict(girls_only=not cat, category=cat, has_girls_divisions=bool(girls) or bool(GIRL.search(sport)),
                girls_divisions=girls, open_divisions=opens, reason=reason)
