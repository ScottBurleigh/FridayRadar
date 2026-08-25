import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cache } from "react";
import type { FridayRadarDataset, Game, InlineRecruit, Player, Rating, School, SchoolSchedule } from "./types";
import { competitiveTalent, rankSchools, ratingsBySource } from "./ranking";
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

/** Stored MaxPreps schedule only. No schoolId or scheduleUrl ⇒ no link. */
export function maxprepsScheduleUrl(
  mp: School["maxpreps"] | null | undefined,
): string | null {
  if (!mp?.schoolId) return null;
  const stored = mp.scheduleUrl?.trim();
  return stored || null;
}

export function scheduleForSchool(
  dataset: FridayRadarDataset,
  schoolId: string,
): SchoolSchedule | null {
  return dataset.schedules?.[schoolId] ?? null;
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

function isPlaceholderName(name: string | undefined): boolean {
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

export function gamesOfTheWeek(
  dataset: FridayRadarDataset,
  opts: { state?: string; zip?: string; now?: Date } = {},
): { weekStart: Date | null; weekLabel: string; games: RankedGame[]; emptyReason: string | null } {
  const rankings = rankSchools(dataset.schools, dataset.players, dataset.ratings, "talent");
  const talentById = new Map(rankings.map((r) => [r.school.id, r]));
  const schools = schoolMap(dataset);

  const week = dataset.meta.matchup_week ?? DEFAULT_MATCHUP_WEEK;
  const weekStart = new Date(`${week.start}T00:00:00.000Z`);

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

  const usable = dataset.games.filter((g) => {
    const home = schools.get(g.home_school_id);
    const away = schools.get(g.away_school_id);
    if (isPlaceholderName(home?.name) || isPlaceholderName(away?.name)) return false;
    if (!home && !away) return false;
    const day = kickoffDate(g.kickoff);
    if (!day || day < week.start || day > week.end) return false;
    if (opts.state || opts.zip) return matchesVenue(g);
    return true;
  });

  if (usable.length === 0) {
    return {
      weekStart,
      weekLabel: `${week.start} – ${week.end}`,
      games: [],
      emptyReason: dataset.games.length
        ? "No two-sided games in the Matchup week slate match these venue filters."
        : "The Matchup MaxPreps week slate is not loaded.",
    };
  }

  const placeholder = (id: string): School => ({
    id,
    name: "Unmapped opponent",
    name_normalized: "unmapped opponent",
    aliases: [],
    mascot: null,
    city: "",
    state: "",
    zip: null,
    address: null,
    lat: null,
    lng: null,
    type: "unmapped",
    maxpreps: null,
    ids_247: { high_school_id: null },
    talentScore: 0,
    recruitCount: 0,
    mapped: false,
  });

  const ranked: RankedGame[] = usable
    .map((game) => {
      const home = schools.get(game.home_school_id) ?? placeholder(game.home_school_id);
      const away = schools.get(game.away_school_id) ?? placeholder(game.away_school_id);
      const homeStats = schoolTalent(home, talentById);
      const awayStats = schoolTalent(away, talentById);
      const homeMapped = home.mapped !== false;
      const awayMapped = away.mapped !== false;
      const combined = Math.round((homeStats.talent + awayStats.talent) * 100) / 100;
      const competitive =
        game.two_sided_talent != null && game.two_sided_talent > 0
          ? game.two_sided_talent
          : competitiveTalent(homeStats.talent, awayStats.talent);
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
        homeMapped,
        awayMapped,
      };
    })
    .filter((row) => row.homeMapped && row.awayMapped && row.competitive > 0)
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
    games: ranked,
    emptyReason: ranked.length
      ? null
      : "No two-sided games in the Matchup week slate match these venue filters.",
  };
}
