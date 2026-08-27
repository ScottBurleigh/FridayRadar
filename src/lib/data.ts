import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cache } from "react";
import type {
  FridayRadarDataset,
  Game,
  InlineRecruit,
  Player,
  Rating,
  School,
  ScheduleGame,
  SchoolSchedule,
} from "./types";
import { competitiveTalent, normalizeSchoolName, rankSchools, ratingsBySource } from "./ranking";
import { schoolWithinZipRadius, venueWithinZipRadius } from "./geo";

export const loadDataset = cache((): FridayRadarDataset => {
  const path = join(process.cwd(), "data", "fridayradar.json");
  return JSON.parse(readFileSync(path, "utf8")) as FridayRadarDataset;
});

export function schoolMap(dataset: FridayRadarDataset): Map<string, School> {
  return new Map(dataset.schools.map((s) => [s.id, s]));
}

export function playersAtSchool(dataset: FridayRadarDataset, schoolId: string): Player[] {
  return dataset.players
    .filter((p) => p.high_school_id === schoolId)
    .sort((a, b) => a.class_year - b.class_year || a.full_name.localeCompare(b.full_name));
}

export function ratingsForPlayer(dataset: FridayRadarDataset, playerId: string): Rating[] {
  return dataset.ratings.filter((r) => r.player_id === playerId);
}

/** Stored MaxPreps schedule URL only. Requires schoolId; never invents a path. */
export function maxprepsScheduleUrl(
  mp: School["maxpreps"] | null | undefined,
  schedule?: SchoolSchedule | null,
): string | null {
  if (!mp?.schoolId) return null;
  const stored = mp.scheduleUrl?.trim() || schedule?.scheduleUrl?.trim();
  return stored || null;
}

export function scheduleForSchool(
  dataset: FridayRadarDataset,
  schoolId: string,
): SchoolSchedule | null {
  return dataset.schedules?.[schoolId] ?? null;
}

/**
 * Best-effort schedule opponent → school page link. Prefers the ingest's own
 * siteId match; falls back to a same-state normalized-name match (e.g. a
 * schedule opponent listed as "Lake Ridge" against a tracked "Mansfield Lake
 * Ridge") only when it's unique — ambiguous or unmatched opponents render as
 * plain text rather than risk linking the wrong school.
 */
export function resolveOpponentHref(
  dataset: FridayRadarDataset,
  opponent: { name: string; city: string | null; state: string | null; siteId: string | null },
): string | null {
  const schools = schoolMap(dataset);
  if (opponent.siteId && schools.has(opponent.siteId)) {
    return `/schools/${opponent.siteId}`;
  }
  if (!opponent.name || !opponent.state) return null;
  const nn = normalizeSchoolName(opponent.name);
  if (!nn) return null;
  const state = opponent.state.toUpperCase();
  const candidates = dataset.schools.filter((s) => {
    if (s.state !== state) return false;
    const sn = normalizeSchoolName(s.name);
    return sn === nn || sn.endsWith(` ${nn}`) || sn.startsWith(`${nn} `);
  });
  if (candidates.length === 1) return `/schools/${candidates[0].id}`;
  if (candidates.length > 1 && opponent.city) {
    const cityNorm = opponent.city.trim().toLowerCase();
    const cityMatches = candidates.filter((s) => s.city?.trim().toLowerCase() === cityNorm);
    if (cityMatches.length === 1) return `/schools/${cityMatches[0].id}`;
  }
  return null;
}

function profileUrlForPlayer(
  player: Player,
  bySrc: ReturnType<typeof ratingsBySource>,
): string | null {
  const from247 =
    bySrc["247sports_composite"]?.profile_url || bySrc["247sports"]?.profile_url;
  if (from247) return from247;
  const id247 = player.source_ids["247sports_player_id"];
  if (id247) return `https://247sports.com/player/${id247}/`;
  if (bySrc.espn?.profile_url) return bySrc.espn.profile_url;
  if (player.source_ids.espn_id) {
    return `https://www.espn.com/college-sports/football/recruiting/player/_/id/${player.source_ids.espn_id}`;
  }
  return null;
}

export function inlineRecruitsForSchools(
  dataset: FridayRadarDataset,
  schoolIds: string[],
): Record<string, InlineRecruit[]> {
  const want = new Set(schoolIds);
  const out: Record<string, InlineRecruit[]> = {};
  for (const id of schoolIds) out[id] = [];
  const ratingsByPlayer = new Map<string, Rating[]>();
  for (const r of dataset.ratings) {
    const list = ratingsByPlayer.get(r.player_id);
    if (list) list.push(r);
    else ratingsByPlayer.set(r.player_id, [r]);
  }
  for (const player of dataset.players) {
    if (!want.has(player.high_school_id) || player.class_year < 2027) continue;
    const mine = ratingsByPlayer.get(player.id) ?? [];
    const bySrc = ratingsBySource(player.id, mine);
    out[player.high_school_id].push({
      id: player.id,
      name: player.full_name,
      position: player.position,
      classYear: player.class_year,
      stars247: bySrc["247sports_composite"]?.stars ?? bySrc["247sports"]?.stars ?? null,
      starsOn3: bySrc.on3_rivals?.stars ?? bySrc.on3_industry?.stars ?? null,
      starsEspn: bySrc.espn?.stars ?? null,
      profileUrl: profileUrlForPlayer(player, bySrc),
    });
  }
  for (const id of schoolIds) {
    out[id].sort((a, b) => a.classYear - b.classYear || a.name.localeCompare(b.name));
  }
  return out;
}

export function filteredRankings(
  dataset: FridayRadarDataset,
  opts: { state?: string; zip?: string; sort?: "talent" | "count" | "strength" },
) {
  let schools = dataset.schools;
  if (opts.state) {
    const st = opts.state.toUpperCase();
    schools = schools.filter((s) => s.state === st);
  }
  if (opts.zip) {
    schools = schools.filter((s) => schoolWithinZipRadius(s, opts.zip!));
  }
  return rankSchools(schools, dataset.players, dataset.ratings, opts.sort ?? "talent");
}

export function mondayOf(date: Date): Date {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay();
  const diff = (day + 6) % 7; // Monday = 0
  d.setUTCDate(d.getUTCDate() - diff);
  d.setUTCHours(0, 0, 0, 0);
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setUTCDate(d.getUTCDate() + days);
  return d;
}

export type RankedGame = {
  game: Game;
  home: School;
  away: School;
  homeTalent: number;
  awayTalent: number;
  homeRecruits: number;
  awayRecruits: number;
  combined: number;
  competitive: number;
  rank: number;
  homeMapped: boolean;
  awayMapped: boolean;
};

const DEFAULT_MATCHUP_WEEK = { start: "2026-08-26", end: "2026-08-29" };

function kickoffDate(iso: string | null): string | null {
  if (!iso) return null;
  return iso.slice(0, 10);
}

function isPlaceholderName(name: string | undefined | null): boolean {
  if (!name?.trim()) return true;
  const n = name.trim();
  if (/varsity opponent/i.test(n)) return true;
  return /^(unknown|tba|tbd|n\/a|na|opponent)$/i.test(n);
}

function schoolTalent(school: School | undefined, talentById: Map<string, { talentScore: number; recruitCount: number }>) {
  if (!school || school.mapped === false) {
    return { talent: 0, recruits: 0 };
  }
  if (school.talentScore != null) {
    return { talent: school.talentScore, recruits: school.recruitCount ?? 0 };
  }
  const row = talentById.get(school.id);
  return { talent: row?.talentScore ?? 0, recruits: row?.recruitCount ?? 0 };
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** "Allen, TX" (always the real game site, home or away) → { city, state }. */
function parseLocation(location: string | null): { city: string | null; state: string | null } {
  if (!location) return { city: null, state: null };
  const parts = location.split(",").map((s) => s.trim()).filter(Boolean);
  if (parts.length >= 2) return { city: parts[0], state: parts[parts.length - 1] };
  if (parts.length === 1) return { city: parts[0], state: null };
  return { city: null, state: null };
}

/** MaxPreps stamps unknown kickoff times as midnight; treat those as TBA. */
function isTbaKickoff(kickoff: string | null): boolean {
  if (!kickoff) return true;
  return /T00:00:00(\.\d+)?$/.test(kickoff);
}

type ResolvedContest = { homeId: string; awayId: string; g: ScheduleGame };

/**
 * Every real contest appears on up to two schedules (one per participating
 * school), each stamped with the same contestId. Dedupe on that id, and
 * prefer the "home" row to resolve which side is which; both sides are
 * dropped unless the opponent is itself a tracked school (siteId resolves),
 * matching the "omit one-sided" rule the old Matchup-week board used.
 */
function dedupedContests(
  dataset: FridayRadarDataset,
  weekStart: string,
  weekEnd: string,
): ResolvedContest[] {
  const schedules = dataset.schedules ?? {};
  const schools = schoolMap(dataset);
  const byContest = new Map<string, Array<{ ownerId: string; g: ScheduleGame }>>();

  for (const [ownerId, schedule] of Object.entries(schedules)) {
    for (const g of schedule.games) {
      const day = kickoffDate(g.kickoff) ?? g.date;
      if (!day || day < weekStart || day > weekEnd) continue;
      if (isPlaceholderName(g.opponent?.name)) continue;
      if (!g.opponent?.siteId || !schools.has(g.opponent.siteId)) continue;
      const key = g.contestId ?? `${day}|${[ownerId, g.opponent.siteId].sort().join("|")}`;
      const list = byContest.get(key);
      if (list) list.push({ ownerId, g });
      else byContest.set(key, [{ ownerId, g }]);
    }
  }

  const out: ResolvedContest[] = [];
  for (const rows of byContest.values()) {
    const homeRow = rows.find((r) => r.g.homeAway === "home");
    const awayRow = rows.find((r) => r.g.homeAway === "away");
    let homeId: string | null = null;
    let awayId: string | null = null;
    let chosen: ScheduleGame;
    if (homeRow) {
      homeId = homeRow.ownerId;
      awayId = homeRow.g.opponent.siteId ?? awayRow?.ownerId ?? null;
      chosen = homeRow.g;
    } else if (awayRow) {
      awayId = awayRow.ownerId;
      homeId = awayRow.g.opponent.siteId ?? null;
      chosen = awayRow.g;
    } else {
      const first = rows[0];
      awayId = first.ownerId;
      homeId = first.g.opponent.siteId ?? null;
      chosen = first.g;
    }
    if (!homeId || !awayId || homeId === awayId) continue;
    if (!schools.has(homeId) || !schools.has(awayId)) continue;
    out.push({ homeId, awayId, g: chosen });
  }
  return out;
}

function buildScheduleGame(contest: ResolvedContest): Game {
  const { g } = contest;
  const { city, state } = parseLocation(g.location);
  return {
    id: g.contestId ?? `${contest.homeId}-${contest.awayId}-${g.date ?? ""}`,
    season: "",
    kickoff: g.kickoff,
    home_school_id: contest.homeId,
    away_school_id: contest.awayId,
    home_score: null,
    away_score: null,
    is_gow: false,
    game_url: g.maxprepsGameUrl,
    city,
    state,
    zip: null,
    lat: null,
    lng: null,
    venue: null,
    two_sided_talent: null,
    is_time_tba: isTbaKickoff(g.kickoff),
    home_away_type: g.homeAway === "neutral" ? 2 : 0,
  };
}

/** Min/max date (within the dataset's season year) across every loaded schedule. */
function scheduleSeasonRange(dataset: FridayRadarDataset, seasonYear: string): { start: string; end: string } | null {
  let min: string | null = null;
  let max: string | null = null;
  for (const schedule of Object.values(dataset.schedules ?? {})) {
    for (const g of schedule.games) {
      const day = kickoffDate(g.kickoff) ?? g.date;
      if (!day || !day.startsWith(seasonYear)) continue;
      if (!min || day < min) min = day;
      if (!max || day > max) max = day;
    }
  }
  if (!min || !max) return null;
  return { start: min, end: max };
}

export function gamesOfTheWeek(
  dataset: FridayRadarDataset,
  opts: { state?: string; zip?: string; now?: Date; weekOffset?: number } = {},
): {
  weekStart: Date | null;
  weekLabel: string;
  games: RankedGame[];
  emptyReason: string | null;
  weekOffset: number;
  loadedWeekLabel: string;
} {
  const rankings = rankSchools(dataset.schools, dataset.players, dataset.ratings, "talent");
  const talentById = new Map(rankings.map((r) => [r.school.id, r]));
  const schools = schoolMap(dataset);

  const anchorWeek = dataset.meta.matchup_week ?? DEFAULT_MATCHUP_WEEK;
  const weekOffset = Number.isFinite(opts.weekOffset) ? Math.trunc(opts.weekOffset!) : 0;
  const spanDays = Math.round(
    (new Date(`${anchorWeek.end}T00:00:00.000Z`).getTime() -
      new Date(`${anchorWeek.start}T00:00:00.000Z`).getTime()) /
      86_400_000,
  );
  const baseStart = new Date(`${anchorWeek.start}T00:00:00.000Z`);
  const weekStart = addDays(baseStart, weekOffset * 7);
  const weekEndDate = addDays(weekStart, spanDays);
  const week = { start: isoDate(weekStart), end: isoDate(weekEndDate) };

  const seasonYear = anchorWeek.start.slice(0, 4);
  const seasonRange = scheduleSeasonRange(dataset, seasonYear);
  const loadedWeekLabel = seasonRange
    ? `${seasonRange.start} – ${seasonRange.end}`
    : `${anchorWeek.start} – ${anchorWeek.end}`;
  const inSeason = !seasonRange || (week.start <= seasonRange.end && week.end >= seasonRange.start);

  const matchesVenue = (game: Game) => {
    const venueState = game.venue?.state || game.state;
    const venueZip = game.venue?.zip || game.zip;
    if (opts.state) {
      if (!venueState || venueState !== opts.state.toUpperCase()) return false;
    }
    if (opts.zip) {
      if (!venueWithinZipRadius({ ...game, zip: venueZip ?? game.zip }, opts.zip)) return false;
    }
    return true;
  };

  const contests = dedupedContests(dataset, week.start, week.end);

  const ranked: RankedGame[] = contests
    .map((contest) => buildScheduleGame(contest))
    .filter((game) => !(opts.state || opts.zip) || matchesVenue(game))
    .map((game) => {
      const home = schools.get(game.home_school_id)!;
      const away = schools.get(game.away_school_id)!;
      const homeStats = schoolTalent(home, talentById);
      const awayStats = schoolTalent(away, talentById);
      const combined = Math.round((homeStats.talent + awayStats.talent) * 100) / 100;
      const competitive = competitiveTalent(homeStats.talent, awayStats.talent);
      return {
        game,
        home,
        away,
        homeTalent: homeStats.talent,
        awayTalent: awayStats.talent,
        homeRecruits: homeStats.recruits,
        awayRecruits: awayStats.recruits,
        combined,
        competitive,
        rank: 0,
        homeMapped: true,
        awayMapped: true,
      };
    })
    .filter((row) => row.competitive > 0)
    .sort(
      (a, b) =>
        b.competitive - a.competitive ||
        b.combined - a.combined ||
        a.home.name.localeCompare(b.home.name) ||
        a.away.name.localeCompare(b.away.name),
    )
    .map((row, i) => ({ ...row, rank: i + 1 }));

  return {
    weekStart,
    weekLabel: `${week.start} – ${week.end}`,
    weekOffset,
    loadedWeekLabel,
    games: ranked,
    emptyReason: ranked.length
      ? null
      : !inSeason
        ? `This week falls outside the loaded season schedule (${loadedWeekLabel}).`
        : "No two-sided games with a tracked opponent are scheduled this week — filters still apply, and bye weeks happen.",
  };
}
