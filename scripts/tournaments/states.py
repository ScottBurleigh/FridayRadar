"""Shared US state config. Add a state by passing its code in --states (all 50 + DC are known)."""
import re

STATES = ["TX"]  # default
NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}


def parse_states(s):
    codes = [c.strip().upper() for c in (s or "").split(",") if c.strip()] or list(STATES)
    bad = [c for c in codes if c not in NAMES]
    if bad:
        raise SystemExit(f"unknown state code(s): {bad}")
    return codes


def slug(code):  # flag50 hub slug, e.g. NM -> new-mexico
    return NAMES[code].lower().replace(" ", "-")


def state_of(location, codes):
    """Return the state code found in a free-text location, limited to codes."""
    loc = location or ""
    for c in codes:
        if re.search(r",\s*" + c + r"\b", loc) or re.search(
            r"\b" + re.escape(NAMES[c]) + r"\b", loc, re.I
        ):
            return c
    return ""
