#!/usr/bin/env npx tsx
/**
 * 247Sports Composite rankings (High School institution group).
 *
 * Public HTML ranking pages only — never the gated `.json` API (it 500s).
 * Stars come from CSS `icon-starsolid yellow` on each list row, not from score text.
 *
 * Paging that actually works in this environment:
 * - `curl --compressed` plus a browser HTML Accept header (JSON Accept → 406).
 * - Page=1 often 406; Page=2+ with `X-Requested-With: XMLHttpRequest`.
 * - After a burst, Varnish 406s; back off and retry the same page.
 * - Union with any larger file already on disk so a short scrape cannot clobber.
 *
 * https://247sports.com/season/{year}-football/compositerecruitrankings/?InstitutionGroup=Highschool
 */
import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const YEARS = [2027, 2028, 2029];
const ROOT = join(import.meta.dirname, "..");
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

type PlayerRow = {
  name: string;
  url: string;
  player_id: string | null;
  high_school_id: string | null;
  hs_meta: string | null;
  position: string | null;
  metrics: string | null;
  rating: number | null;
  stars: number | null;
  national_rank: number | null;
  position_rank: number | null;
  state_rank: number | null;
  college_commit: string | null;
  rank: number | null;
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function parsePage(html: string) {
  const players: PlayerRow[] = [];
  const itemRe = /<li class="rankings-page__list-item">([\s\S]*?)<\/li>/g;
  let m: RegExpExecArray | null;
  while ((m = itemRe.exec(html))) {
    const block = m[1];
    const nameM = block.match(/rankings-page__name-link" href="([^"]+)">([^<]+)/);
    if (!nameM) continue;
    const href = nameM[1];
    const name = nameM[2].replace(/&amp;/g, "&").trim();
    if (!name) continue;
    const ids = href.match(/\/player\/[^/]+-(\d+)\/high-school-(\d+)/);
    const stars = (block.match(/icon-starsolid yellow/g) ?? []).length;
    const num = (re: RegExp) => {
      const x = block.match(re)?.[1]?.trim();
      return x && /^\d+$/.test(x) ? Number(x) : null;
    };
    players.push({
      name,
      url: href.startsWith("http") ? href : `https://247sports.com${href}`,
      player_id: ids?.[1] ?? null,
      high_school_id: ids?.[2] ?? null,
      hs_meta: block.match(/class="meta">\s*([^<]+)/)?.[1]?.trim() ?? null,
      position: block.match(/class="position">\s*([^<]+)/)?.[1]?.trim() ?? null,
      metrics: block.match(/class="metrics">\s*([^<]+)/)?.[1]?.trim() ?? null,
      rating: Number(block.match(/class="score">([^<]+)/)?.[1] ?? "") || null,
      stars: stars || null,
      national_rank: num(/class="natrank"[^>]*>([^<]+)/),
      position_rank: num(/class="posrank"[^>]*>([^<]+)/),
      state_rank: num(/class="sttrank"[^>]*>([^<]+)/),
      college_commit: block.match(/class="status">[\s\S]*?title="([^"]+)"/)?.[1] ?? null,
      rank: num(/class="primary">\s*([^<]+)/),
    });
  }
  const count = Number(html.match(/class="count">\s*\((\d+)\)/)?.[1] ?? "") || null;
  return { players, count };
}

async function curlGet(
  url: string,
  cookieJar: string,
  xhr: boolean,
): Promise<{ status: number; body: string }> {
  const args = [
    "-sS",
    "--compressed",
    "-o",
    "-",
    "-w",
    "\n__HTTP_STATUS__:%{http_code}",
    "-c",
    cookieJar,
    "-b",
    cookieJar,
    "-H",
    `User-Agent: ${UA}`,
    "-H",
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "-H",
    "Accept-Language: en-US,en;q=0.9",
    "-H",
    "Referer: https://247sports.com/",
  ];
  if (xhr) args.push("-H", "X-Requested-With: XMLHttpRequest");
  args.push(url);
  try {
    const { stdout } = await execFileAsync("curl", args, {
      maxBuffer: 20 * 1024 * 1024,
    });
    const marker = "\n__HTTP_STATUS__:";
    const idx = stdout.lastIndexOf(marker);
    if (idx < 0) return { status: 0, body: stdout };
    const body = stdout.slice(0, idx);
    const status = Number(stdout.slice(idx + marker.length).trim()) || 0;
    return { status, body };
  } catch (err) {
    console.warn("curl fail", url, err);
    return { status: 0, body: "" };
  }
}

function rankingUrl(year: number, page: number) {
  return `https://247sports.com/Season/${year}-Football/CompositeRecruitRankings/?InstitutionGroup=HighSchool&Page=${page}`;
}

function mergePlayers(into: Map<string, PlayerRow>, rows: PlayerRow[]) {
  for (const p of rows) {
    if (!p.name || !p.stars) continue;
    const k = String(p.player_id ?? p.name);
    const prev = into.get(k);
    if (!prev || (p.stars ?? 0) > (prev.stars ?? 0)) into.set(k, p);
  }
}

async function loadExisting(path: string): Promise<PlayerRow[]> {
  try {
    const raw = JSON.parse(await readFile(path, "utf8")) as { players?: PlayerRow[] };
    return raw.players ?? [];
  } catch {
    return [];
  }
}

async function fetchYear(year: number, cookieJar: string) {
  const destDir = join(ROOT, "data/raw/247");
  const dest = join(destDir, `${year}.json`);
  const tmpDest = join("/tmp/ingest-raw/247", `${year}.json`);
  const byId = new Map<string, PlayerRow>();
  mergePlayers(byId, await loadExisting(dest));
  const before = byId.size;

  let listed: number | null = null;
  let page = 2; // Page=1 commonly 406; ranks 1–50 also appear on later pages / existing file
  let consecutiveEmpty = 0;
  const maxPage = year === 2027 ? 50 : year === 2028 ? 25 : 15;

  while (page <= maxPage) {
    const url = rankingUrl(year, page);
    let status = 0;
    let body = "";
    let delay = 4000;
    for (let attempt = 0; attempt < 5; attempt++) {
      const res = await curlGet(url, cookieJar, true);
      status = res.status;
      body = res.body;
      if (status === 200 && body.includes("rankings-page__list-item")) break;
      if (status === 406 || status === 0) {
        console.warn(`247 ${year} p${page} ${status || "err"} — backoff ${delay}ms`);
        await sleep(delay);
        delay = Math.min(delay * 2, 32000);
        continue;
      }
      break;
    }
    if (status !== 200 || !body.includes("rankings-page__list-item")) {
      consecutiveEmpty += 1;
      console.warn(`247 ${year} p${page} ${status} empty=${consecutiveEmpty}`);
      if (consecutiveEmpty >= 3) break;
      page += 1;
      await sleep(800);
      continue;
    }
    const { players, count } = parsePage(body);
    if (count) listed = count;
    if (!players.length) {
      consecutiveEmpty += 1;
      if (consecutiveEmpty >= 2) break;
    } else {
      consecutiveEmpty = 0;
      const sizeBefore = byId.size;
      mergePlayers(byId, players);
      console.log(
        `247 ${year} p${page} +${players.length} unique ${byId.size}/${listed ?? "?"} (new ${byId.size - sizeBefore})`,
      );
      if (listed && byId.size >= listed) break;
      // last page is a short remainder
      if (players.length < 40 && page > 2) {
        page += 1;
        break;
      }
    }
    page += 1;
    await sleep(750);
  }

  const players = [...byId.values()].filter((p) => p.name && p.stars);
  const stars: Record<string, number> = {};
  for (const p of players) {
    const k = String(p.stars);
    stars[k] = (stars[k] ?? 0) + 1;
  }
  await mkdir(destDir, { recursive: true });
  await mkdir(join("/tmp/ingest-raw/247"), { recursive: true });
  const payload = JSON.stringify({
    year,
    count: players.length,
    listed,
    stars,
    players,
  });
  // Never shrink a good local scrape.
  if (players.length < before) {
    console.warn(`247 ${year} keeping existing ${before} (scrape ${players.length})`);
    return;
  }
  await writeFile(dest, payload);
  await writeFile(tmpDest, payload);
  console.log("wrote", year, players.length, "stars", stars, "was", before);
}

async function main() {
  const cookieJar = join(tmpdir(), `247sports-${process.pid}.cj`);
  // Warm cookies; 406 here is fine as long as Set-Cookie lands.
  await curlGet(
    "https://247sports.com/Guest/ManageMyCookies/",
    cookieJar,
    true,
  );
  for (const year of YEARS) await fetchYear(year, cookieJar);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
