export type TournamentCategory = "7v7" | "flag" | "both" | "";

export type Tournament = {
  id: string;
  category: TournamentCategory | string;
  name: string;
  start_date: string;
  end_date: string;
  city: string;
  venue: string;
  sport: string;
  age_groups: string;
  divisions: string;
  entry_fee: string;
  registration_ends: string;
  organizer: string;
  contact_email: string;
  contact_phone: string;
  event_url: string;
  clubhouse_url: string;
  source: string;
  state?: string;
  sources?: string[];
  verified?: boolean;
  conflicts?: string;
  zorts_url?: string;
  flag50_url?: string;
  also_listed_as?: string[];
  has_girls_divisions?: boolean;
  girls_divisions?: string[];
  open_divisions?: string[];
};

export type TournamentBoard = {
  generated: string;
  window: [string, string] | string[];
  count: number;
  tournaments: Tournament[];
};

/** Calendar date in America/Chicago (YYYY-MM-DD). Never invented. */
export function centralToday(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Chicago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

export function parseEntryFeeUsd(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const m = raw.replace(/,/g, "").match(/\$?\s*(\d+(?:\.\d+)?)/);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}

export function upcomingTournaments(rows: Tournament[], today = centralToday()): Tournament[] {
  return rows.filter((t) => {
    const end = (t.end_date || t.start_date || "").slice(0, 10);
    return end >= today;
  });
}

/** Age-bucket keys from open (boys/coed) divisions, matching make_html.py. */
export function divisionBuckets(t: Tournament): string[] {
  const src =
    t.open_divisions ??
    (t.divisions || "")
      .split(";")
      .map((s) => s.trim())
      .filter(Boolean);
  const keys = new Set<string>();
  for (const d of src) {
    for (const m of d.matchAll(/\b(\d{1,2})\s*-?\s*u\b/gi)) {
      keys.add(`${Number(m[1])}U`);
    }
    if (/high school|\bhs\b|\b18u\b|senior/i.test(d)) keys.add("HS");
    if (/middle school|\bms\b/i.test(d)) keys.add("MS");
    if (/adult|\bmen'?s\b|open/i.test(d)) keys.add("Adult/Open");
    const g = d.match(/(\d{1,2})(?:st|nd|rd|th)\s*grade/i);
    if (g) keys.add(`Grade ${g[1]}`);
  }
  if (keys.size === 0 && t.age_groups) {
    for (const m of t.age_groups.matchAll(/\b(\d{1,2})u\b/gi)) {
      keys.add(`${Number(m[1])}U`);
    }
  }
  return [...keys].sort(compareDivisionBuckets);
}

export function compareDivisionBuckets(a: string, b: string): number {
  return bucketRank(a) - bucketRank(b) || a.localeCompare(b);
}

function bucketRank(a: string): number {
  const m = /^(\d+)U$/.exec(a);
  if (m) return Number(m[1]);
  if (a === "MS") return 14.5;
  if (a === "HS") return 19;
  const g = /^Grade (\d+)$/.exec(a);
  if (g) return 30 + Number(g[1]);
  return 99;
}

/** Google Maps query from venue + city + the row's state (TX today). */
export function mapsQuery(t: Tournament): string {
  const st = (t.state || "TX").trim() || "TX";
  const city = (t.city || "").trim();
  const venue = (t.venue || "").trim();
  if (venue) {
    let q = venue;
    if (city && !venue.toLowerCase().includes(city.toLowerCase())) q += `, ${city}`;
    if (!new RegExp(`\\b${st}\\b`).test(q)) q += `, ${st}`;
    return q;
  }
  return city ? `${city}, ${st}` : "";
}

export function mapsSearchUrl(query: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

export function mapsDirectionsUrl(query: string): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(query)}`;
}
