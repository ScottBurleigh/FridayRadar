import type { School, SchoolSchedule } from "./types";

/** Live MaxPreps football season on disk. */
export const CURRENT_FOOTBALL_SEASON = "26-27";

const RECORD_RE = /^(\d+)-(\d+)(?:-(\d+))?$/;

function playedRecord(raw: string | null | undefined): string | null {
  const rec = (raw ?? "").trim();
  const m = RECORD_RE.exec(rec);
  if (!m) return null;
  const wins = Number(m[1]);
  const losses = Number(m[2]);
  const ties = m[3] ? Number(m[3]) : 0;
  if (wins + losses + ties <= 0) return null;
  return rec;
}

/** Official 26-27 W-L from MaxPreps standings (season-history). Never invented. */
export function recordFromStandings(
  school: School,
  season = CURRENT_FOOTBALL_SEASON,
): string | null {
  const hit = school.seasonHistory?.find((s) => s.season === season);
  return playedRecord(hit?.record);
}

/** W-L-T counted from stored schedule results. Missing results are skipped, not guessed. */
export function recordFromSchedule(schedule: SchoolSchedule | undefined | null): string | null {
  if (!schedule?.games.length) return null;
  let wins = 0;
  let losses = 0;
  let ties = 0;
  for (const g of schedule.games) {
    const result = (g.result ?? "").trim().toUpperCase();
    if (result === "W") wins += 1;
    else if (result === "L") losses += 1;
    else if (result === "T") ties += 1;
  }
  if (wins + losses + ties <= 0) return null;
  return ties ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
}

/** Prefer MaxPreps standings; fall back to this season's schedule W/L. */
export function currentSeasonRecord(
  school: School,
  schedule?: SchoolSchedule | null,
  season = CURRENT_FOOTBALL_SEASON,
): string | null {
  return recordFromStandings(school, season) ?? recordFromSchedule(schedule);
}
