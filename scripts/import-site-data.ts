#!/usr/bin/env npx tsx
/**
 * Compile Scout + Matchup site-data into data/fridayradar.json.
 *
 * Looks for canonical Builder dumps in this order:
 *   1) site-data/{schools,schools.summary,games-top213}.json
 *   2) data/import/{schools,schools.summary,games-top213}.json
 *
 * v1 /games is site-data/games-top213.json only (two-sided week
 * 2026-08-26..29, ranked by geometric mean). Never load games.json.
 *
 * Nested school.recruits become Player + Rating rows. Do not invent names.
 * Unmapped Matchup opponents become placeholder schools (mapped: false) so
 * one-sided games such as St. Frances @ DeLand stay on the board.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { slugify, normalizeSchoolName } from "../src/lib/ranking";
import { padZip } from "../src/lib/geo";
import type {
  FridayRadarDataset,
  Game,
  GameVenue,
  Player,
  Rating,
  RatingSource,
  School,
  SourceStatus,
} from "../src/lib/types";

const ROOT = join(import.meta.dirname, "..");

const RATING_SOURCES = new Set<RatingSource>([
  "247sports",
  "247sports_composite",
  "on3_rivals",
  "on3_industry",
  "espn",
]);

type SiteRating = {
  source?: string;
  stars?: number | null;
  rating?: number | null;
  national_rank?: number | null;
  position_rank?: number | null;
  state_rank?: number | null;
  position?: string | null;
  profile_url?: string | null;
  profile?: string | null;
  url?: string | null;
};

type SiteRecruit = {
  id?: string;
  full_name?: string;
  class_year?: number;
  position?: string | null;
  height?: string | null;
  weight?: number | null;
  college_commit?: string | null;
  hometown?: string | null;
  hometown_city?: string | null;
  hometown_state?: string | null;
  ratings?: SiteRating[];
  talent_points?: number;
  sources?: string[];
  source_ids?: Player["source_ids"];
};

type SiteSchool = {
  id: string;
  name: string;
  city?: string;
  state?: string;
  zip?: string | number | null;
  zip5?: string | number | null;
  recruit_count?: number;
  talent_score?: number;
  class_counts?: Record<string, number>;
  star_buckets?: { stars5?: number; stars4?: number; stars3?: number; "5"?: number; "4"?: number; "3"?: number };
  aliases?: string[];
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  type?: string | null;
  mapped?: boolean;
  ids_247?: { high_school_id?: string | null };
  maxpreps?: {
    schoolId?: string;
    canonicalUrl?: string;
    zip?: string | number | null;
    mascot?: string | null;
    footballUrl?: string | null;
    scheduleUrl?: string | null;
    formattedName?: string | null;
  } | null;
  recruits?: SiteRecruit[];
};

type SiteSide = {
  maxpreps_id?: string | null;
  site_id?: string | null;
  name?: string;
  city?: string;
  state?: string;
  zip?: string | number | null;
  talent_score?: number | null;
  mapped?: boolean;
};

type SiteVenue = {
  city?: string | null;
  state?: string | null;
  zip?: string | number | null;
  lat?: number | null;
  lng?: number | null;
  name?: string | null;
  source?: "home_school" | "contest_location" | string | null;
};

type SiteGame = {
  contest_id: string;
  maxpreps_game_url?: string | null;
  kickoff_local?: string | null;
  is_neutral?: boolean;
  home: SiteSide;
  away: SiteSide;
  combined_talent?: number;
  two_sided_talent?: number | null;
  mapped_sides?: number;
  home_score?: number | null;
  away_score?: number | null;
  is_time_tba?: boolean;
  season?: string;
  /** MaxPreps contest / site location when present. */
  venue?: SiteVenue | null;
  location_city?: string | null;
  location_state?: string | null;
  location_zip?: string | number | null;
  location_lat?: number | null;
  location_lng?: number | null;
};

type SiteGamesFile = {
  week_start?: string;
  week_end?: string;
  rank_by?: string;
  games: SiteGame[];
};

function findImportDir(): string {
  const site = join(ROOT, "site-data");
  const fallback = join(ROOT, "data/import");
  if (existsSync(join(site, "schools.json"))) return site;
  return fallback;
}

function isPlaceholderName(name?: string | null): boolean {
  if (!name?.trim()) return true;
  const n = name.trim();
  if (/varsity opponent/i.test(n)) return true;
  return /^(unknown|tba|tbd|n\/a|na|opponent)$/i.test(n);
}

function findGamesPath(dir: string): string {
  const p = join(dir, "games-top213.json");
  if (!existsSync(p)) {
    throw new Error(
      `v1 /games requires games-top213.json in ${dir}. Do not load games.json.`,
    );
  }
  return p;
}

function twoSidedTalent(g: SiteGame): number {
  if (g.two_sided_talent != null && g.two_sided_talent > 0) return g.two_sided_talent;
  const h = g.home?.talent_score ?? 0;
  const a = g.away?.talent_score ?? 0;
  if (h <= 0 || a <= 0) return 0;
  return Math.round(Math.sqrt(h * a) * 100) / 100;
}

function v1Games(games: SiteGame[]): SiteGame[] {
  const cleaned = games.filter(
    (g) => !isPlaceholderName(g.home?.name) && !isPlaceholderName(g.away?.name),
  );
  const both = cleaned.filter((g) => {
    const homeOk = g.home?.mapped !== false && Boolean(g.home?.site_id);
    const awayOk = g.away?.mapped !== false && Boolean(g.away?.site_id);
    const mapped = g.mapped_sides == null ? homeOk && awayOk : g.mapped_sides === 2;
    return mapped && twoSidedTalent(g) > 0;
  });
  both.sort((a, b) => {
    const dt = twoSidedTalent(b) - twoSidedTalent(a);
    if (dt !== 0) return dt;
    const dc = (b.combined_talent ?? 0) - (a.combined_talent ?? 0);
    if (dc !== 0) return dc;
    return (a.home?.name || "").localeCompare(b.home?.name || "");
  });
  return both;
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

function footballSeasonFromGames(file: SiteGamesFile): string {
  const fromGame = file.games.find((g) => g.season)?.season?.trim();
  if (fromGame) return fromGame;
  const year = file.week_start?.slice(2, 4);
  if (year && /^\d{2}$/.test(year)) {
    return `${year}-${String(Number(year) + 1).padStart(2, "0")}`;
  }
  return "26-27";
}

function siteMaxPreps(mp: SiteSchool["maxpreps"]): School["maxpreps"] {
  if (!mp?.schoolId) return null;
  const schedule = (mp.scheduleUrl || "").trim();
  return {
    schoolId: mp.schoolId,
    canonicalUrl: (mp.canonicalUrl || "").trim(),
    formattedName: mp.formattedName ?? null,
    footballUrl: (mp.footballUrl || "").trim() || null,
    scheduleUrl: schedule || null,
  };
}

function asSource(raw: string | undefined): RatingSource | null {
  if (!raw) return null;
  const key = raw.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const aliases: Record<string, RatingSource> = {
    "247sports_composite": "247sports_composite",
    "247_composite": "247sports_composite",
    composite: "247sports_composite",
    "247sports": "247sports",
    "247": "247sports",
    on3_rivals: "on3_rivals",
    rivals: "on3_rivals",
    on3: "on3_rivals",
    on3_industry: "on3_industry",
    industry: "on3_industry",
    espn: "espn",
  };
  const mapped = aliases[key] ?? (RATING_SOURCES.has(raw as RatingSource) ? (raw as RatingSource) : null);
  return mapped;
}

function parseHometown(text: string | null | undefined): { city: string | null; state: string | null } {
  if (!text) return { city: null, state: null };
  const m = text.trim().match(/^(.*),\s*([A-Z]{2})\s*$/);
  if (m) return { city: m[1].trim(), state: m[2] };
  return { city: text.trim(), state: null };
}

function unmappedId(side: SiteSide): string {
  if (side.site_id) return side.site_id;
  const st = (side.state || "xx").toLowerCase();
  return `unmapped-${st}-${slugify(side.name || "opponent")}`;
}

function blank(value?: string | null): string | null {
  const t = value?.trim();
  return t ? t : null;
}

function contestVenue(g: SiteGame): {
  city: string | null;
  state: string | null;
  zip: string | null;
  lat: number | null;
  lng: number | null;
} {
  const v = g.venue;
  const city = blank(v?.city) ?? blank(g.location_city);
  const state = (blank(v?.state) ?? blank(g.location_state))?.toUpperCase() ?? null;
  const zip = padZip(v?.zip ?? g.location_zip);
  const lat = v?.lat ?? g.location_lat ?? null;
  const lng = v?.lng ?? g.location_lng ?? null;
  return { city, state, zip, lat, lng };
}

function homeVenue(
  g: SiteGame,
  homeSchool: School | undefined,
): {
  city: string | null;
  state: string | null;
  zip: string | null;
  lat: number | null;
  lng: number | null;
  name: string | null;
  source: GameVenue["source"];
} {
  return {
    city: blank(homeSchool?.city) || blank(g.home.city),
    state: blank(homeSchool?.state)?.toUpperCase() || blank(g.home.state)?.toUpperCase() || null,
    zip: homeSchool?.zip || padZip(g.home.zip),
    lat: homeSchool?.lat ?? null,
    lng: homeSchool?.lng ?? null,
    name: blank(homeSchool?.name) || blank(g.home.name),
    source: "home_school",
  };
}

/** Contest/play-at location when MaxPreps has one; otherwise HOME school only (never away). */
function resolveVenue(
  g: SiteGame,
  homeSchool: School | undefined,
): {
  city: string | null;
  state: string | null;
  zip: string | null;
  lat: number | null;
  lng: number | null;
  name: string | null;
  source: GameVenue["source"];
} {
  const home = homeVenue(g, homeSchool);
  const fromFile = g.venue;
  const contest = contestVenue(g);
  const contestHasSite = Boolean(contest.city || contest.state || contest.zip || (contest.lat != null && contest.lng != null));

  if (fromFile?.source === "contest_location" && (blank(fromFile.city) || blank(fromFile.state) || fromFile.zip)) {
    return {
      city: blank(fromFile.city),
      state: blank(fromFile.state)?.toUpperCase() || null,
      zip: padZip(fromFile.zip),
      lat: fromFile.lat ?? null,
      lng: fromFile.lng ?? null,
      name: blank(fromFile.name),
      source: "contest_location",
    };
  }
  if (g.is_neutral && contestHasSite) {
    return {
      ...contest,
      name: blank(fromFile?.name),
      source: "contest_location",
    };
  }
  return {
    city: blank(fromFile?.city) || home.city,
    state: blank(fromFile?.state)?.toUpperCase() || home.state,
    zip: padZip(fromFile?.zip) || home.zip,
    lat: fromFile?.lat ?? home.lat,
    lng: fromFile?.lng ?? home.lng,
    name: blank(fromFile?.name) || home.name,
    source: "home_school",
  };
}

function ensureSchool(
  schools: Map<string, School>,
  id: string,
  side: SiteSide,
  mapped: boolean,
) {
  if (schools.has(id)) return;
  const name = (side.name || "Unmapped opponent").trim();
  const city = side.city || "";
  const state = (side.state || "").toUpperCase();
  const zip = mapped ? padZip(side.zip) : null;
  schools.set(id, {
    id,
    name,
    name_normalized: normalizeSchoolName(name),
    aliases: [],
    mascot: null,
    city,
    state,
    zip,
    address: null,
    lat: null,
    lng: null,
    type: mapped ? null : "unmapped",
    maxpreps: side.maxpreps_id
      ? { schoolId: side.maxpreps_id, canonicalUrl: "", formattedName: name }
      : null,
    ids_247: { high_school_id: null },
    talentScore: side.talent_score ?? 0,
    recruitCount: mapped ? undefined : 0,
    mapped,
  });
}

export async function importSiteData(): Promise<FridayRadarDataset> {
  const dir = findImportDir();
  const schoolsPath = join(dir, "schools.json");
  const gamesPath = findGamesPath(dir);
  const summaryPath = join(dir, "schools.summary.json");
  if (!existsSync(schoolsPath)) {
    throw new Error(`Missing schools.json in ${dir}`);
  }

  const schoolRaw = await readJson<SiteSchool[] | { schools: SiteSchool[] }>(schoolsPath);
  const siteSchools = Array.isArray(schoolRaw) ? schoolRaw : schoolRaw.schools;
  const gamesFile = await readJson<SiteGamesFile>(gamesPath);
  gamesFile.games = v1Games(gamesFile.games || []);
  const footballSeason = footballSeasonFromGames(gamesFile);
  const summary = existsSync(summaryPath)
    ? await readJson<Record<string, unknown>>(summaryPath)
    : {};

  const schools = new Map<string, School>();
  const players: Player[] = [];
  const ratings: Rating[] = [];
  const asOf = new Date().toISOString().slice(0, 10);

  for (const row of siteSchools) {
    const city = row.city || "";
    const state = (row.state || "").toUpperCase();
    const zip = padZip(row.zip5 ?? row.zip ?? row.maxpreps?.zip);
    const mp = row.maxpreps;
    const school: School = {
      id: row.id,
      name: row.name,
      name_normalized: normalizeSchoolName(row.name),
      aliases: row.aliases ?? [],
      mascot: mp?.mascot ?? null,
      city,
      state,
      zip,
      address: row.address ?? null,
      lat: row.lat ?? null,
      lng: row.lng ?? null,
      type: row.type ?? null,
      maxpreps: siteMaxPreps(mp),
      ids_247: { high_school_id: row.ids_247?.high_school_id ?? null },
      talentScore: row.talent_score ?? null,
      recruitCount: row.recruit_count ?? null,
      stars5: row.star_buckets?.stars5 ?? row.star_buckets?.["5"] ?? null,
      stars4: row.star_buckets?.stars4 ?? row.star_buckets?.["4"] ?? null,
      stars3: row.star_buckets?.stars3 ?? row.star_buckets?.["3"] ?? null,
      mapped: row.mapped !== false,
    };
    schools.set(school.id, school);

    for (const rec of row.recruits || []) {
      if (!rec.full_name || !rec.class_year || rec.class_year < 2027) continue;
      const ht = parseHometown(rec.hometown);
      const player: Player = {
        id: String(rec.id || `${school.id}-${slugify(rec.full_name)}-${rec.class_year}`),
        full_name: rec.full_name,
        class_year: rec.class_year,
        position: rec.position ?? null,
        height: rec.height ?? null,
        weight: rec.weight ?? null,
        hometown_city: rec.hometown_city ?? ht.city,
        hometown_state: rec.hometown_state ?? ht.state,
        high_school_id: school.id,
        college_commit: rec.college_commit ?? null,
        source_ids: rec.source_ids ?? {},
      };
      players.push(player);
      for (const rt of rec.ratings || []) {
        const source = asSource(rt.source);
        if (!source) continue;
        ratings.push({
          player_id: player.id,
          source,
          class_year: rec.class_year,
          as_of: asOf,
          national_rank: rt.national_rank ?? null,
          position_rank: rt.position_rank ?? null,
          state_rank: rt.state_rank ?? null,
          stars: rt.stars ?? null,
          rating: rt.rating ?? null,
          position: rt.position ?? rec.position ?? null,
          high_school_name_raw: `${row.name} (${city}, ${state})`.trim(),
          profile_url: rt.profile_url ?? rt.profile ?? rt.url ?? null,
        });
      }
    }
  }

  const games: Game[] = [];
  for (const g of gamesFile.games || []) {
    if (!g.contest_id || !g.home || !g.away) continue;
    if (isPlaceholderName(g.home.name) || isPlaceholderName(g.away.name)) continue;
    const homeMapped = g.home.mapped !== false && Boolean(g.home.site_id);
    const awayMapped = g.away.mapped !== false && Boolean(g.away.site_id);
    const homeId = homeMapped ? String(g.home.site_id) : unmappedId(g.home);
    const awayId = awayMapped ? String(g.away.site_id) : unmappedId(g.away);
    ensureSchool(schools, homeId, g.home, homeMapped);
    ensureSchool(schools, awayId, g.away, awayMapped);
    const venue = resolveVenue(g, schools.get(homeId));
    games.push({
      id: g.contest_id,
      season: g.season || footballSeason,
      kickoff: g.kickoff_local ?? null,
      home_school_id: homeId,
      away_school_id: awayId,
      home_score: g.home_score ?? null,
      away_score: g.away_score ?? null,
      is_gow: false,
      game_url: g.maxpreps_game_url ?? null,
      city: venue.city,
      state: venue.state,
      zip: venue.zip,
      lat: venue.lat,
      lng: venue.lng,
      venue: {
        city: venue.city,
        state: venue.state,
        zip: venue.zip,
        name: venue.name,
        source: venue.source,
      },
      two_sided_talent: twoSidedTalent(g) || null,
      is_time_tba: Boolean(g.is_time_tba),
      home_away_type: g.is_neutral ? 2 : 0,
    });
  }

  const sources: SourceStatus[] = [
    {
      id: "scout",
      label: "Scout 247+Rivals+ESPN 2027/2028 frozen ingest",
      status: "live",
      detail:
        "Frozen Scout board. Composite stars = avg of 247sports_composite, on3_rivals (else on3_industry, never both), ESPN. Rankings use precomputed school talentScore.",
      counts: {
        schools: Number(summary.schools ?? schools.size),
        players: Number(summary.players ?? players.length),
      },
    },
    {
      id: "matchup",
      label: "Matchup MaxPreps week slate",
      status: "live",
      detail: `Week ${gamesFile.week_start ?? "2026-08-26"} through ${gamesFile.week_end ?? "2026-08-29"} from games-top213.json (${games.length} two-sided games). Ranked by geometric mean of home/away talent; combined talent is display only. Venue state/zip, not either school. Never games.json.`,
      counts: { games: games.length },
    },
  ];

  const dataset: FridayRadarDataset = {
    meta: {
      generated_at: new Date().toISOString(),
      as_of: asOf,
      min_class_year: 2027,
      sources,
      notes: [
        "High schools are ranked, not colleges.",
        "School talentScore is the Scout precomputed sum of 2027+ player points.",
        "Player composite = average of 247sports_composite, on3_rivals (else on3_industry, never both), and ESPN.",
        "Matchup week is 2026-08-26 through 2026-08-29. /games ranks two-sided talent as √(home × away); combined talent is display + tie-break. Filters use the game venue.",
        String(summary.note ?? "Canonical v1: 1,554 schools / 2,986 players when the full Scout dump is imported."),
      ],
      matchup_week: {
        start: gamesFile.week_start ?? "2026-08-26",
        end: gamesFile.week_end ?? "2026-08-29",
      },
    },
    schools: [...schools.values()],
    players,
    ratings,
    games,
  };
  return dataset;
}

async function main() {
  const dataset = await importSiteData();
  const dest = join(ROOT, "data/fridayradar.json");
  await mkdir(join(ROOT, "data"), { recursive: true });
  await writeFile(dest, JSON.stringify(dataset));
  console.log(
    "wrote",
    dest,
    "schools",
    dataset.schools.length,
    "players",
    dataset.players.length,
    "ratings",
    dataset.ratings.length,
    "games",
    dataset.games.length,
  );
}

const isMain = process.argv[1]?.endsWith("import-site-data.ts");
if (isMain) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
