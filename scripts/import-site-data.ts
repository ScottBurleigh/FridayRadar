#!/usr/bin/env npx tsx
/**
 * Compile Scout + Matchup site-data into data/fridayradar.json.
 *
 * Looks for canonical Builder dumps in this order:
 *   1) site-data/{schools,schools.summary,games}.json
 *   2) data/import/{schools,schools.summary,games}.json
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

const ZIP_NULL = [
  { name: /american heritage/i, city: /fort lauderdale/i, state: "FL" },
  { name: /american leadership|ala\b/i, city: /queen creek/i, state: "AZ" },
  { name: /lexington christian/i, state: "KY" },
  { name: /notre dame/i, city: /sherman oaks/i, state: "CA" },
  { name: /roosevelt/i, city: /san antonio/i, state: "TX" },
];

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

type SiteGame = {
  contest_id: string;
  maxpreps_game_url?: string | null;
  kickoff_local?: string | null;
  is_neutral?: boolean;
  home: SiteSide;
  away: SiteSide;
  combined_talent?: number;
  mapped_sides?: number;
  home_score?: number | null;
  away_score?: number | null;
  is_time_tba?: boolean;
};

type SiteGamesFile = {
  week_start?: string;
  week_end?: string;
  games: SiteGame[];
};

function findImportDir(): string {
  const site = join(ROOT, "site-data");
  const fallback = join(ROOT, "data/import");
  if (existsSync(join(site, "schools.json"))) return site;
  return fallback;
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

function forceZipNull(name: string, city: string, state: string): boolean {
  const st = state.toUpperCase();
  return ZIP_NULL.some(
    (rule) =>
      rule.state === st &&
      rule.name.test(name) &&
      (!rule.city || rule.city.test(city)),
  );
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
  const zip = mapped && !forceZipNull(name, city, state) ? padZip(side.zip) : null;
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
  const gamesPath = join(dir, "games.json");
  const summaryPath = join(dir, "schools.summary.json");
  if (!existsSync(schoolsPath) || !existsSync(gamesPath)) {
    throw new Error(`Missing schools.json or games.json in ${dir}`);
  }

  const schoolRaw = await readJson<SiteSchool[] | { schools: SiteSchool[] }>(schoolsPath);
  const siteSchools = Array.isArray(schoolRaw) ? schoolRaw : schoolRaw.schools;
  const gamesFile = await readJson<SiteGamesFile>(gamesPath);
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
    const zipNull = forceZipNull(row.name, city, state);
    const zip = zipNull ? null : padZip(row.zip5 ?? row.zip ?? row.maxpreps?.zip);
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
      maxpreps: mp?.schoolId
        ? {
            schoolId: mp.schoolId,
            canonicalUrl: mp.canonicalUrl || "",
            formattedName: mp.formattedName ?? null,
            footballUrl: mp.footballUrl ?? null,
          }
        : null,
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
    const homeMapped = g.home.mapped !== false && Boolean(g.home.site_id);
    const awayMapped = g.away.mapped !== false && Boolean(g.away.site_id);
    const homeId = homeMapped ? String(g.home.site_id) : unmappedId(g.home);
    const awayId = awayMapped ? String(g.away.site_id) : unmappedId(g.away);
    ensureSchool(schools, homeId, g.home, homeMapped);
    ensureSchool(schools, awayId, g.away, awayMapped);
    games.push({
      id: g.contest_id,
      season: "26-27",
      kickoff: g.kickoff_local ?? null,
      home_school_id: homeId,
      away_school_id: awayId,
      home_score: g.home_score ?? null,
      away_score: g.away_score ?? null,
      is_gow: false,
      game_url: g.maxpreps_game_url ?? null,
      city: g.home.city || null,
      state: (g.home.state || "").toUpperCase() || null,
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
      detail: `Week ${gamesFile.week_start ?? "2026-08-26"} through ${gamesFile.week_end ?? "2026-08-29"}. One-sided talent kept.`,
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
        "Matchup week is 2026-08-26 through 2026-08-29. Unmapped opponents stay on /games with 0 talent.",
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
