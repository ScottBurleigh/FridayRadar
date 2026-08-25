import type { Player, Rating, RatingSource, School, SchoolRankingRow } from "./types";

export const MIN_CLASS_YEAR = 2027;

export const STAR_POINTS: Record<number, number> = {
  5: 98,
  4: 85,
  3: 70,
  2: 55,
  1: 40,
  0: 25,
};

export const POSITION_FAMILY: Record<string, string> = {
  QB: "QB",
  "QB-DT": "QB",
  DUAL: "QB",
  PRO: "QB",
  RB: "RB",
  FB: "RB",
  TB: "RB",
  HB: "RB",
  WR: "WR",
  SLOT: "WR",
  TE: "TE",
  OT: "OL",
  IOL: "OL",
  OG: "OL",
  OC: "OL",
  OL: "OL",
  C: "OL",
  G: "OL",
  DL: "DL",
  DT: "DL",
  NT: "DL",
  IDL: "DL",
  EDGE: "EDGE",
  DE: "EDGE",
  LB: "LB",
  ILB: "LB",
  OLB: "LB",
  MLB: "LB",
  CB: "DB",
  S: "DB",
  SAF: "DB",
  FS: "DB",
  SS: "DB",
  DB: "DB",
  ATH: "ATH",
  K: "ST",
  P: "ST",
  LS: "ST",
  RET: "ST",
  PK: "ST",
};

export function positionFamily(position: string | null | undefined): string {
  if (!position) return "UNK";
  const key = position.toUpperCase().replace(/[^A-Z0-9-]/g, "");
  return POSITION_FAMILY[key] ?? key;
}

export function normalizeName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[.’']/g, "")
    .replace(/\./g, "")
    .replace(/,/g, " ")
    .replace(/\b(jr|sr|ii|iii|iv|v)\b/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

export function normalizeSchoolName(name: string): string {
  let n = name.toLowerCase();
  n = n.replace(/&amp;/g, "and");
  n = n.replace(/\(([^)]*)\)/g, " ");
  n = n.replace(/\b(high school|hs|high|school|collegiate|prep school)\b/g, " ");
  n = n.replace(/[.’']/g, "");
  n = n.replace(/[^a-z0-9]+/g, " ");
  n = n.replace(/\s+/g, " ").trim();
  if (n.endsWith(" prep")) {
    // keep prep — St. Joseph's Prep vs generic
  }
  return n;
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** ESPN 300 maps grade 90+=5, 80-89=4. Extend the same 10-point bands downward. */
export function espnGradeToStars(grade: number | null | undefined): number | null {
  if (grade == null || Number.isNaN(grade)) return null;
  if (grade >= 90) return 5;
  if (grade >= 80) return 4;
  if (grade >= 70) return 3;
  if (grade >= 60) return 2;
  if (grade >= 50) return 1;
  return null;
}

/**
 * Player points from composite stars.
 * 5=98, 4=85, 3=70, 2=55, 1=40, listed/unranked=25.
 * Non-integers interpolate (4.5 is halfway between 85 and 98).
 */
export function playerPoints(stars: number | null | undefined): number {
  if (stars == null || Number.isNaN(stars) || stars <= 0) {
    return STAR_POINTS[0];
  }
  if (stars >= 5) return STAR_POINTS[5];
  const lo = Math.floor(stars);
  const hi = Math.ceil(stars);
  if (lo === hi) {
    return STAR_POINTS[lo] ?? STAR_POINTS[0];
  }
  const t = stars - lo;
  const loPts = STAR_POINTS[lo] ?? STAR_POINTS[0];
  const hiPts = STAR_POINTS[hi] ?? STAR_POINTS[5];
  return loPts + t * (hiPts - loPts);
}

export function averageStars(starList: Array<number | null | undefined>): number | null {
  const values = starList.filter((s): s is number => s != null && !Number.isNaN(s) && s > 0);
  if (!values.length) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function badgeStars(composite: number | null): number {
  if (composite == null) return 0;
  return Math.max(0, Math.min(5, Math.round(composite)));
}

export function compositeStarsForPlayer(
  playerId: string,
  ratings: Rating[],
): number | null {
  const mine = ratings.filter((r) => r.player_id === playerId);
  return averageStars(mine.map((r) => r.stars));
}

export function ratingsBySource(playerId: string, ratings: Rating[]): Partial<Record<RatingSource, Rating>> {
  const out: Partial<Record<RatingSource, Rating>> = {};
  for (const r of ratings) {
    if (r.player_id !== playerId) continue;
    const prev = out[r.source];
    if (!prev || (r.stars ?? 0) >= (prev.stars ?? 0)) {
      out[r.source] = r;
    }
  }
  return out;
}

export function rankSchools(
  schools: School[],
  players: Player[],
  ratings: Rating[],
  sort: "talent" | "count" = "talent",
): SchoolRankingRow[] {
  const ratingsByPlayer = new Map<string, Rating[]>();
  for (const r of ratings) {
    const list = ratingsByPlayer.get(r.player_id) ?? [];
    list.push(r);
    ratingsByPlayer.set(r.player_id, list);
  }

  const bySchool = new Map<
    string,
    { count: number; stars5: number; stars4: number; stars3: number; talent: number }
  >();

  for (const school of schools) {
    bySchool.set(school.id, { count: 0, stars5: 0, stars4: 0, stars3: 0, talent: 0 });
  }

  for (const player of players) {
    if (player.class_year < MIN_CLASS_YEAR) continue;
    const bucket = bySchool.get(player.high_school_id);
    if (!bucket) continue;
    const stars = averageStars((ratingsByPlayer.get(player.id) ?? []).map((r) => r.stars));
    const badge = badgeStars(stars);
    bucket.count += 1;
    bucket.talent += playerPoints(stars);
    if (badge >= 5) bucket.stars5 += 1;
    else if (badge === 4) bucket.stars4 += 1;
    else if (badge === 3) bucket.stars3 += 1;
  }

  const rows: SchoolRankingRow[] = schools
    .map((school) => {
      const stats = bySchool.get(school.id)!;
      return {
        rank: 0,
        school,
        recruitCount: stats.count,
        stars5: stats.stars5,
        stars4: stats.stars4,
        stars3: stats.stars3,
        talentScore: Math.round(stats.talent * 10) / 10,
      };
    })
    .filter((row) => row.recruitCount > 0);

  rows.sort((a, b) => {
    if (sort === "count") {
      if (b.recruitCount !== a.recruitCount) return b.recruitCount - a.recruitCount;
      if (b.talentScore !== a.talentScore) return b.talentScore - a.talentScore;
    } else {
      if (b.talentScore !== a.talentScore) return b.talentScore - a.talentScore;
      if (b.recruitCount !== a.recruitCount) return b.recruitCount - a.recruitCount;
    }
    return a.school.name.localeCompare(b.school.name);
  });

  return rows.map((row, i) => ({ ...row, rank: i + 1 }));
}

export function dedupeKey(
  classYear: number,
  fullName: string,
  position: string | null,
): string {
  return `${classYear}|${normalizeName(fullName)}|${positionFamily(position)}`;
}
