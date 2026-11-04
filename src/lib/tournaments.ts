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
