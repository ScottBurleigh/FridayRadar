import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { FridayRadarDataset, ScheduleGame } from "./types";

/** Verified Texan Live event pages only. Never invent a path. */
export function isTexanLiveUrl(url: string): boolean {
  return /^https:\/\/(www\.)?texanlive\.com\/video\//.test(url);
}

/** Verified NFHS Network event pages only. Never invent a path. */
export function isNfhsUrl(url: string): boolean {
  return /^https:\/\/(www\.)?nfhsnetwork\.com\/events\//.test(url);
}

export type BroadcastUrls = {
  texanLiveUrl?: string;
  nfhsUrl?: string;
};

function broadcastPath(): string | null {
  const candidates = [
    join(process.cwd(), "site-data/broadcast-games.tsv"),
    join(process.cwd(), "data/import/broadcast-games.tsv"),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

/** contest_id → Texan Live and/or NFHS URLs from the TSV sidecar. Join key is contest_id only. */
export function loadBroadcastByContest(): Map<string, BroadcastUrls> {
  const path = broadcastPath();
  const out = new Map<string, BroadcastUrls>();
  if (!path) return out;
  const text = readFileSync(path, "utf8");
  const lines = text.split(/\n/);
  const header = (lines[0] ?? "").split("\t");
  if (
    header[0] !== "contest_id" ||
    header[5] !== "source" ||
    header[6] !== "url"
  ) {
    return out;
  }
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const cols = line.split("\t");
    const contestId = (cols[0] || "").trim();
    const source = (cols[5] || "").trim();
    const url = (cols[6] || "").trim();
    if (!contestId || !url) continue;
    const rec = out.get(contestId) ?? {};
    if (source === "texanlive" && isTexanLiveUrl(url)) rec.texanLiveUrl = url;
    else if (source === "nfhs" && isNfhsUrl(url)) rec.nfhsUrl = url;
    else continue;
    out.set(contestId, rec);
  }
  return out;
}

function stampGame(game: ScheduleGame, urls: BroadcastUrls): ScheduleGame {
  const texanLiveUrl = urls.texanLiveUrl ?? null;
  const nfhsUrl = urls.nfhsUrl ?? null;
  if ((game.texanLiveUrl ?? null) === texanLiveUrl && (game.nfhsUrl ?? null) === nfhsUrl) {
    return game;
  }
  return { ...game, texanLiveUrl, nfhsUrl };
}

/** Overlay TSV watch URLs onto every schedule row sharing that contestId (home and away). */
export function applyBroadcastOverlay(dataset: FridayRadarDataset): FridayRadarDataset {
  const byContest = loadBroadcastByContest();
  if (!byContest.size || !dataset.schedules) return dataset;
  const schedules: Record<string, (typeof dataset.schedules)[string]> = {};
  let any = false;
  for (const [sid, schedule] of Object.entries(dataset.schedules)) {
    let schoolChanged = false;
    const games = schedule.games.map((g) => {
      const cid = g.contestId;
      if (!cid) return g;
      const urls = byContest.get(cid);
      if (!urls) return g;
      const next = stampGame(g, urls);
      if (next !== g) schoolChanged = true;
      return next;
    });
    if (schoolChanged) {
      any = true;
      schedules[sid] = { ...schedule, games };
    } else {
      schedules[sid] = schedule;
    }
  }
  if (!any) return dataset;
  return { ...dataset, schedules };
}
