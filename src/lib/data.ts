import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cache } from "react";
import type { FridayRadarDataset, Game, Player, Rating, School } from "./types";
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
};

export function gamesOfTheWeek(
  dataset: FridayRadarDataset,
  opts: { state?: string; zip?: string; now?: Date } = {},
): { weekStart: Date | null; weekLabel: string; games: RankedGame[]; emptyReason: string | null } {
  const rankings = rankSchools(dataset.schools, dataset.players, dataset.ratings, "talent");
  const talentById = new Map(rankings.map((r) => [r.school.id, r]));
  const schools = schoolMap(dataset);

  const now = opts.now ?? new Date();
  const thisMonday = mondayOf(now);
  const thisSunday = addDays(thisMonday, 7);

  const matchesFilter = (school: School | undefined) => {
    if (!school) return false;
    if (opts.state && school.state !== opts.state.toUpperCase()) return false;
    if (opts.zip && !schoolWithinZipRadius(school, opts.zip)) return false;
    return true;
  };

  const usable = dataset.games.filter((g) => {
    const home = schools.get(g.home_school_id);
    const away = schools.get(g.away_school_id);
    if (!home || !away) return false;
    if (opts.state || opts.zip) {
      return matchesFilter(home) || matchesFilter(away);
    }
    return true;
  });

  const inRange = (start: Date, end: Date) =>
    usable.filter((g) => {
      if (!g.kickoff) return false;
      const t = new Date(g.kickoff).getTime();
      return t >= start.getTime() && t < end.getTime();
    });

  let weekStart = thisMonday;
  let weekGames = inRange(thisMonday, thisSunday);

  if (weekGames.length === 0) {
    const future = usable
      .filter((g) => g.kickoff && new Date(g.kickoff).getTime() >= thisMonday.getTime())
      .sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    if (future.length) {
      weekStart = mondayOf(new Date(future[0].kickoff!));
      weekGames = inRange(weekStart, addDays(weekStart, 7));
    } else {
      return {
        weekStart: null,
        weekLabel: "Offseason",
        games: [],
        emptyReason: usable.length
          ? "No upcoming games in the loaded MaxPreps schedules."
          : "No high school games are loaded. Football season may be over, or MaxPreps schedule pages were unreachable during ingest.",
      };
    }
  }

  const ranked: RankedGame[] = weekGames
    .map((game) => {
      const home = schools.get(game.home_school_id)!;
      const away = schools.get(game.away_school_id)!;
      const homeRow = talentById.get(home.id);
      const awayRow = talentById.get(away.id);
      const homeTalent = homeRow?.talentScore ?? 0;
      const awayTalent = awayRow?.talentScore ?? 0;
      return {
        game,
        home,
        away,
        homeTalent,
        awayTalent,
        homeRecruits: homeRow?.recruitCount ?? 0,
        awayRecruits: awayRow?.recruitCount ?? 0,
        combined: Math.round((homeTalent + awayTalent) * 10) / 10,
        rank: 0,
      };
    })
    .sort((a, b) => b.combined - a.combined || a.home.name.localeCompare(b.home.name))
    .map((row, i) => ({ ...row, rank: i + 1 }));

  const label = `${weekStart.toISOString().slice(0, 10)} – ${addDays(weekStart, 6).toISOString().slice(0, 10)}`;
  return { weekStart, weekLabel: label, games: ranked, emptyReason: null };
}
