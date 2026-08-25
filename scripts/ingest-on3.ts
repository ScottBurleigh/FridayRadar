#!/usr/bin/env npx tsx
/**
 * On3/Rivals OWN ranking list (SSR __NEXT_DATA__).
 * Industry list is often Cloudflare-blocked; this /rivals/rankings payload includes
 * own (On3), Rivals, Industry, 247, and ESPN ratings plus 247/ESPN profile URLs.
 *
 * High school comes from person.highSchool + slug state (buford-ga), NOT hometown
 * (Brewster hometown can still say Cedar Hill, TX after the transfer).
 *
 * https://www.on3.com/rivals/rankings/player/football/{year}/
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const YEARS = [2027, 2028, 2029];
const ROOT = join(import.meta.dirname, "..");

async function fetchYear(year: number) {
  const url = `https://www.on3.com/rivals/rankings/player/football/${year}/`;
  const res = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      Accept: "text/html",
    },
  });
  if (!res.ok) throw new Error(`On3 ${year} ${res.status}`);
  const html = await res.text();
  const m = html.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  if (!m) throw new Error(`On3 ${year}: no __NEXT_DATA__ (likely blocked)`);
  const data = JSON.parse(m[1]);
  const list = data?.props?.pageProps?.playerData?.list ?? [];
  const players = list.map((p: Record<string, unknown>) => {
    const person = (p.person ?? {}) as Record<string, unknown>;
    const hs = (person.highSchool ?? {}) as Record<string, unknown>;
    const status = (person.status ?? {}) as Record<string, unknown>;
    return {
      key: p.key ?? person.key,
      name: person.name,
      slug: person.slug,
      class_year: person.classYear,
      position: p.positionAbbreviation ?? person.positionAbbreviation,
      height: person.formattedHeight,
      weight: person.weight,
      hometown: person.homeTownName,
      hs_name: person.highSchoolName ?? hs.name,
      hs_full: hs.fullName,
      hs_mascot: hs.mascot,
      hs_slug: hs.slug,
      hs_url_slug: hs.urlSlug,
      hs_key: hs.key,
      state: p.stateAbbreviation,
      overall_rank: p.overallRank,
      position_rank: p.positionRank,
      state_rank: p.stateRank,
      college_slug: status.committedOrganizationSlug,
      committed: status.isCommitted,
      ratings: p.ratings ?? [],
      profile: person.slug ? `https://www.on3.com/rivals/players/${person.slug}/` : null,
    };
  });
  const dir = join(ROOT, "data/raw/on3");
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, `${year}.json`), JSON.stringify({ year, count: players.length, players }));
  console.log("wrote on3", year, players.length);
}

async function main() {
  for (const year of YEARS) {
    try {
      await fetchYear(year);
    } catch (err) {
      console.error(err);
    }
  }
}

main();
