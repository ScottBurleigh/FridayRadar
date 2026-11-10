import type { Tournament } from "./tournaments";
import { weekendsOf, type Weekend } from "./tournament-weekends";

export const LS_WEEKENDS = "fr.tournaments.v1.weekends";
export const LS_SCHEDULE = "fr.tournaments.v1.schedule";

export type ScheduleFee = { value: number | null; label: string };

/** First number in entry_fee ($100-$250 → $100). Blank → TBD. $0 → free. */
export function parseScheduleFee(entryFee: string | null | undefined): ScheduleFee {
  const s = entryFee ? String(entryFee) : "";
  const m = s.match(/\$?\s*([\d,]+(?:\.\d+)?)/);
  if (m) {
    const n = Number.parseFloat(m[1].replace(/,/g, ""));
    if (!Number.isNaN(n)) {
      if (n === 0) return { value: 0, label: "free" };
      return { value: n, label: `$${Math.round(n).toLocaleString("en-US")}` };
    }
  }
  return { value: null, label: "TBD" };
}

export function feeTotal(items: Pick<Tournament, "entry_fee">[]): {
  sum: number;
  tbd: number;
  label: string;
} {
  let sum = 0;
  let tbd = 0;
  for (const r of items) {
    const f = parseScheduleFee(r.entry_fee);
    if (f.value == null) tbd += 1;
    else sum += f.value;
  }
  return {
    sum,
    tbd,
    label: `$${Math.round(sum).toLocaleString("en-US")}${tbd ? ` (+${tbd} TBD)` : ""}`,
  };
}

const MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatScheduleRange(start: string, end: string): string {
  function fd(s: string): string {
    const p = s.split("-");
    if (p.length < 3) return s || "—";
    return `${MN[Number(p[1]) - 1]} ${Number(p[2])}, ${p[0]}`;
  }
  if (!start) return "—";
  if (!end || end === start) return fd(start);
  const pa = start.split("-");
  const pb = end.split("-");
  if (pa[0] === pb[0] && pa[1] === pb[1]) {
    return `${MN[Number(pa[1]) - 1]} ${Number(pa[2])}–${Number(pb[2])}, ${pa[0]}`;
  }
  return `${fd(start)} – ${fd(end)}`;
}

export type ScheduleNote = {
  type: "overlap" | "weekend" | "excluded";
  ids: string[];
  text: string;
};

export function conflictNotes(
  items: Tournament[],
  weekends: Weekend[],
  excludedFridayIds: Iterable<string>,
): ScheduleNote[] {
  const excluded = excludedFridayIds instanceof Set ? excludedFridayIds : new Set(excludedFridayIds);
  const notes: ScheduleNote[] = [];
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i];
      const b = items[j];
      const a2 = a.end_date || a.start_date;
      const b2 = b.end_date || b.start_date;
      const overlap = a.start_date <= b2 && b.start_date <= a2;
      const shared = weekendsOf(a.start_date, a.end_date, weekends).filter((w) =>
        weekendsOf(b.start_date, b.end_date, weekends).some((x) => x.id === w.id),
      );
      if (overlap) {
        notes.push({
          type: "overlap",
          ids: [a.id, b.id],
          text: `Date overlap: “${a.name}” and “${b.name}”.`,
        });
      } else if (shared.length) {
        notes.push({
          type: "weekend",
          ids: [a.id, b.id],
          text: `Same weekend (${shared.map((w) => w.label).join(", ")}): “${a.name}” and “${b.name}”.`,
        });
      }
    }
  }
  for (const r of items) {
    const ex = weekendsOf(r.start_date, r.end_date, weekends).filter((w) => excluded.has(w.id));
    if (ex.length) {
      notes.push({
        type: "excluded",
        ids: [r.id],
        text: `“${r.name}” falls on an excluded weekend (${ex.map((w) => w.label).join(", ")}).`,
      });
    }
  }
  return notes;
}

export function readLocalStringArray(key: string): string[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string");
  } catch {
    return [];
  }
}

export function writeLocalStringArray(key: string, values: string[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(values));
  } catch {
    /* quota / private mode */
  }
}

export function readHashScheduleIds(knownIds: Set<string>): string[] | null {
  if (typeof window === "undefined") return null;
  const h = (window.location.hash || "").replace(/^#/, "");
  if (!h) return null;
  const p = new URLSearchParams(h.includes("=") ? h : `sched=${h}`);
  const s = p.get("sched") || p.get("schedule");
  if (!s) return null;
  return s
    .split(",")
    .map((x) => x.trim())
    .filter((id) => knownIds.has(id));
}

export function writeHashScheduleIds(ids: string[]): void {
  if (typeof window === "undefined") return;
  try {
    const next = ids.length ? `#sched=${ids.join(",")}` : `${window.location.pathname}${window.location.search}`;
    window.history.replaceState(null, "", next);
  } catch {
    /* ignore */
  }
}

export function schedulePlainText(
  items: Tournament[],
  generated: string,
  totLabel: string,
  notes: ScheduleNote[],
  categoryLabel: (cat: string) => string,
): string {
  const lines = ["My Tournament Schedule", "", `Generated from FridayRadar tournaments · ${generated || ""}`, ""];
  for (const r of items) {
    const f = parseScheduleFee(r.entry_fee);
    lines.push(formatScheduleRange(r.start_date, r.end_date));
    lines.push(`  ${r.name}  (${categoryLabel(r.category)})`);
    lines.push(`  ${r.city || "—"}${r.venue ? ` · ${r.venue}` : ""}  ·  ${f.label}`);
    if (r.event_url) lines.push(`  ${r.event_url}`);
    lines.push("");
  }
  lines.push(`Total: ${totLabel}`);
  for (const n of notes) lines.push(`⚠ ${n.text}`);
  return lines.join("\n");
}
