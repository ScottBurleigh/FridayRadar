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
import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const YEARS = [2027, 2028, 2029];
const ROOT = join(import.meta.dirname, "..");

async function chromeDump(url: string): Promise<string> {
  const chrome = "/usr/bin/google-chrome-stable";
  const dir = `/tmp/chrome-on3-${process.pid}-${Date.now()}`;
  try {
    const { stdout } = await execFileAsync(
      chrome,
      [
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--virtual-time-budget=25000",
        `--user-data-dir=${dir}`,
        "--dump-dom",
        url,
      ],
      { timeout: 90000, maxBuffer: 40 * 1024 * 1024 },
    );
    return stdout || "";
  } catch (err) {
    const stdout = (err as { stdout?: string }).stdout;
    return stdout || "";
  }
}

async function fetchYear(year: number) {
  const url = `https://www.on3.com/rivals/rankings/player/football/${year}/`;
  let html = "";
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        Accept: "text/html",
      },
    });
    if (res.ok) html = await res.text();
    else console.warn(`On3 ${year} fetch ${res.status} — trying Chrome`);
  } catch (err) {
    console.warn(`On3 ${year} fetch fail`, err);
  }
  if (!html.includes("__NEXT_DATA__")) {
    html = await chromeDump(url);
  }
  const m = html.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  if (!m) throw new Error(`On3 ${year}: no __NEXT_DATA__ (likely blocked)`);
  const data = JSON.parse(m[1]);
  const playerData = data?.props?.pageProps?.playerData ?? {};
  const list = playerData.list ?? [];
  const pagination = playerData.pagination ?? null;
  console.log(
    "on3",
    year,
    "list",
    Array.isArray(list) ? list.length : 0,
    "pagination",
    JSON.stringify(pagination),
  );
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
  const dest = join(dir, `${year}.json`);
  let before = 0;
  try {
    const prev = JSON.parse(await readFile(dest, "utf8")) as { players?: unknown[] };
    before = prev.players?.length ?? 0;
  } catch {
    before = 0;
  }
  if (!players.length) {
    console.warn(`on3 ${year} empty fetch — keeping existing ${before}`);
    return;
  }
  if (before && players.length < before * 0.5) {
    console.warn(`on3 ${year} keeping existing ${before} (scrape ${players.length})`);
    return;
  }
  await mkdir(dir, { recursive: true });
  const asOf = new Date().toISOString();
  await writeFile(
    dest,
    JSON.stringify({ year, count: players.length, as_of: asOf, pagination, players }),
  );
  console.log("wrote on3", year, players.length, asOf, "was", before);
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
