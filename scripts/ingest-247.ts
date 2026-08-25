#!/usr/bin/env npx tsx
/**
 * 247Sports Composite rankings (High School institution group).
 * Paginated HTML list. Player URLs include /player/{slug}-{id}/high-school-{hsId}/.
 * HS token is `Buford (Buford, GA)` — never the Team/college commit column.
 *
 * https://247sports.com/season/{year}-football/compositerecruitrankings/?InstitutionGroup=Highschool
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const YEARS = [2027, 2028, 2029];
const ROOT = join(import.meta.dirname, "..");
const UA = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
};

function parsePage(html: string) {
  const players: Record<string, unknown>[] = [];
  const itemRe = /<li class="rankings-page__list-item">([\s\S]*?)<\/li>/g;
  let m: RegExpExecArray | null;
  while ((m = itemRe.exec(html))) {
    const block = m[1];
    const nameM = block.match(/rankings-page__name-link" href="([^"]+)">([^<]+)/);
    if (!nameM) continue;
    const href = nameM[1];
    const ids = href.match(/\/player\/[^/]+-(\d+)\/high-school-(\d+)/);
    const stars = (block.match(/icon-starsolid yellow/g) ?? []).length;
    const num = (re: RegExp) => {
      const x = block.match(re)?.[1]?.trim();
      return x && /^\d+$/.test(x) ? Number(x) : null;
    };
    players.push({
      name: nameM[2].replace(/&amp;/g, "&").trim(),
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

async function fetchYear(year: number) {
  const all: Record<string, unknown>[] = [];
  let page = 1;
  let empty = 0;
  while (page <= 80) {
    const url = `https://247sports.com/Season/${year}-Football/CompositeRecruitRankings/?InstitutionGroup=HighSchool&Page=${page}`;
    const res = await fetch(url, { headers: UA });
    if (!res.ok) {
      console.warn(`247 ${year} p${page} ${res.status}`);
      empty += 1;
      if (empty >= 2) break;
      page += 1;
      continue;
    }
    const html = await res.text();
    const { players, count } = parsePage(html);
    if (!players.length) {
      empty += 1;
      if (empty >= 2) break;
    } else {
      empty = 0;
      all.push(...players);
      console.log(`247 ${year} p${page} +${players.length} total ${all.length}/${count ?? "?"}`);
      if (count && all.length >= count) break;
    }
    page += 1;
    await new Promise((r) => setTimeout(r, 300));
  }
  const seen = new Set<string>();
  const uniq = all.filter((p) => {
    const k = String(p.player_id ?? p.name);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  const dir = join(ROOT, "data/raw/247");
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, `${year}.json`), JSON.stringify({ year, count: uniq.length, players: uniq }));
  console.log("wrote", year, uniq.length);
}

async function main() {
  for (const year of YEARS) await fetchYear(year);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
