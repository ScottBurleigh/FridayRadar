#!/usr/bin/env npx tsx
/**
 * Fetch ESPN college-football recruiting athletes for 2027, 2028, 2029.
 * Writes slim JSON to data/raw/espn/{year}.json
 *
 * Source: https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/recruiting/{year}/athletes
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const YEARS = [2027, 2028, 2029];
const ROOT = join(import.meta.dirname, "..");

type EspnItem = {
  athlete?: {
    id?: string;
    fullName?: string;
    displayName?: string;
    height?: number;
    weight?: number;
    links?: { href?: string }[];
    position?: { abbreviation?: string };
    hometown?: { city?: string; stateAbbreviation?: string };
    highSchool?: {
      id?: string;
      name?: string;
      properName?: string;
      address?: { city?: string; stateAbbreviation?: string; zipCode?: string; address1?: string };
    };
  };
  recruitingClass?: number;
  grade?: number;
  attributes?: { name?: string; value?: number }[];
  schools?: { status?: { id?: number }; team?: { $ref?: string } }[];
};

async function fetchJson(url: string) {
  const res = await fetch(url, { headers: { "User-Agent": "FridayRadar/1.0" } });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

async function fetchYear(year: number) {
  const items: EspnItem[] = [];
  let page = 1;
  while (true) {
    const url = `https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/recruiting/${year}/athletes?limit=300&page=${page}`;
    const data = await fetchJson(url);
    const batch = data.items ?? [];
    items.push(...batch);
    console.log(`espn ${year} p${data.pageIndex}/${data.pageCount} +${batch.length} total ${items.length}`);
    if (page >= (data.pageCount ?? 1) || !batch.length) break;
    page += 1;
  }
  const slim = items.map((it) => {
    const a = it.athlete ?? {};
    const hs = a.highSchool ?? {};
    const addr = hs.address ?? {};
    const ranks = Object.fromEntries((it.attributes ?? []).map((x) => [x.name, x]));
    return {
      espn_id: a.id,
      full_name: a.fullName ?? a.displayName,
      class_year: it.recruitingClass,
      position: a.position?.abbreviation,
      height: a.height,
      weight: a.weight,
      hometown_city: a.hometown?.city,
      hometown_state: a.hometown?.stateAbbreviation,
      hs_id: hs.id,
      hs_name: hs.properName ?? hs.name,
      hs_city: addr.city,
      hs_state: addr.stateAbbreviation,
      hs_zip: addr.zipCode,
      hs_address: addr.address1,
      grade: it.grade,
      national_rank: ranks.rank?.value,
      position_rank: ranks.positionRank?.value,
      state_rank: ranks.stateRank?.value,
      profile: a.links?.find((l) => l.href)?.href,
    };
  });
  const dir = join(ROOT, "data/raw/espn");
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, `${year}.json`), JSON.stringify({ year, count: slim.length, players: slim }));
  console.log("wrote", year, slim.length);
}

async function main() {
  for (const year of YEARS) await fetchYear(year);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
