import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { canonicalSchoolId } from "./school-ids";
import type { FridayRadarDataset } from "./types";

/** Same checks as scripts/import-site-data.ts applyHudlOverlay. Never invent URLs. */
export function isHudlTeamUrl(url: string): boolean {
  return url.startsWith("https://fan.hudl.com/") && url.includes("boys-varsity-football");
}

function hudlTeamsPath(): string | null {
  const candidates = [
    join(process.cwd(), "site-data/hudl-teams.tsv"),
    join(process.cwd(), "data/import/hudl-teams.tsv"),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

/** school_id (FridayRadar / canonical) → verified fan.hudl.com team URL. */
export function loadHudlTeamUrls(): Map<string, string> {
  const path = hudlTeamsPath();
  const out = new Map<string, string>();
  if (!path) return out;
  const text = readFileSync(path, "utf8");
  const lines = text.split(/\n/);
  const header = (lines[0] ?? "").split("\t");
  if (header[0] !== "school_id" || header[1] !== "hudl_team_url") return out;
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const [rawId, rawUrl] = line.split("\t");
    const sid = (rawId || "").trim();
    const url = (rawUrl || "").trim();
    if (!sid || !isHudlTeamUrl(url)) continue;
    const cid = canonicalSchoolId(sid);
    out.set(cid, url);
    if (cid !== sid) out.set(sid, url);
  }
  return out;
}

/** Overlay TSV team URLs onto schools. Unmatched school_id → no link. */
export function applyHudlTeamOverlay(dataset: FridayRadarDataset): FridayRadarDataset {
  const urls = loadHudlTeamUrls();
  return {
    ...dataset,
    schools: dataset.schools.map((school) => {
      const url = urls.get(school.id) ?? null;
      if ((school.hudlTeamUrl ?? null) === url) return school;
      return { ...school, hudlTeamUrl: url };
    }),
  };
}
