import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cache } from "react";
import type { FridayRadarDataset, Player, Rating, School } from "./types";
import { rankSchools } from "./ranking";
import { schoolWithinZipRadius } from "./geo";

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

export function getSchool(dataset: FridayRadarDataset, id: string): School | undefined {
  return dataset.schools.find((s) => s.id === id);
}

export function filteredRankings(
  dataset: FridayRadarDataset,
  opts: { state?: string; zip?: string; sort?: "talent" | "count" },
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

  const matchesFilter = (school: School | undefined) => {
    if (!school) return false;
    if (opts.state && school.state !== opts.state.toUpperCase()) return false;
    if (opts.zip && !schoolWithinZipRadius(school, opts.zip)) return false;
    return true;
  };

  const usable = dataset.games.filter((g) => {
    const home = schools.get(g.home_school_id);
    const away = schools.get(g.away_school_id);
    if (isPlaceholderName(home?.name) || isPlaceholderName(away?.name)) return false;
    if (!home && !away) return false;
    const day = kickoffDate(g.kickoff);
    if (!day || day < week.start || day > week.end) return false;
    if (opts.state || opts.zip) {
      return matchesFilter(home) || matchesFilter(away);
    }
    return true;
  });

  if (usable.length === 0) {
    return {
      weekStart,
      weekLabel: `${week.start} – ${week.end}`,
      games: [],
      emptyReason: dataset.games.length
        ? "No games in the Matchup week slate match these filters."
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
      const combined = Math.round((homeStats.talent + awayStats.talent) * 100) / 100;
      return {
        game,
        home,
        away,
        homeTalent: homeStats.talent,
        awayTalent: awayStats.talent,
        homeRecruits: homeStats.recruits,
        awayRecruits: awayStats.recruits,
        combined,
        rank: 0,
        homeMapped: home.mapped !== false,
        awayMapped: away.mapped !== false,
      };
    })
    .sort((a, b) => b.combined - a.combined || a.home.name.localeCompare(b.home.name))
    .map((row, i) => ({ ...row, rank: i + 1 }));

  return {
    weekStart,
    weekLabel: `${week.start} – ${week.end}`,
    games: ranked,
    emptyReason: null,
  };
}
