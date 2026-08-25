#!/usr/bin/env npx tsx
/**
 * MaxPreps school-home JSON (lat/lng/zip/address) and football wall schedule.
 * Reads buildId live from a school page. Do not hardcode a stale buildId.
 *
 * JSON: GET https://www.maxpreps.com/_next/data/{buildId}/<path>.json
 * Season 26-27 is live. homeAwayType 0 home / 1 away / 2 neutral.
 * Skip isDeleted rows and "Varsity Opponent" placeholders.
 *
 * Full /football/{season}/schedule pages have 504'd from this environment;
 * we fall back to wallCards.schedule on the team football page.
 */
import { spawn } from "node:child_process";
import { join } from "node:path";

const script = join(import.meta.dirname, "ingest.py");
const child = spawn("python3", [script], { stdio: "inherit" });
child.on("exit", (code) => process.exit(code ?? 1));
