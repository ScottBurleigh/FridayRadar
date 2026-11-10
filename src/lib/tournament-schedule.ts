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

function ageOrder(a: string): number {
  const m = /^(\d+)(?:\/(\d+))?U$/.exec(a);
  if (m) return Number(m[1]);
  if (a === "MS") return 14.5;
  if (a === "Freshman") return 17;
  if (a === "JV") return 18;
  if (a === "Varsity" || a === "HS") return 19;
  if (a === "Adult") return 21;
  const g = /^Grade (\d+)$/.exec(a);
  if (g) return 30 + Number(g[1]);
  const r = /^(\d+)U/.exec(a);
  if (r) return Number(r[1]);
  return 99;
}

function sortAges(arr: string[]): string[] {
  return [...arr].sort((a, b) => ageOrder(a) - ageOrder(b) || (a < b ? -1 : a > b ? 1 : 0));
}

/** Discrete age brackets from one division / age_groups fragment. 13/14U stays combined; 18U stays 18U. */
export function ageTokens(s: string | null | undefined): string[] {
  if (s == null || s === "") return [];
  let rest = String(s);
  const found: string[] = [];
  const seen: Record<string, number> = {};
  function add(tok: string) {
    if (!tok) return;
    const k = tok.toUpperCase();
    if (seen[k]) return;
    seen[k] = 1;
    found.push(tok);
  }
  rest = rest.replace(/\b(\d{1,2})\s*[\/\-]\s*(\d{1,2})\s*-?\s*u\s*g?\b/gi, (_, a, b) => {
    add(`${Number(a)}/${Number(b)}U`);
    return " ";
  });
  rest = rest.replace(/\b(\d{1,2})\s*-?\s*u\s*g?\b/gi, (_, a) => {
    add(`${Number(a)}U`);
    return " ";
  });
  if (/high\s*school|\bhsg\b|\bhs\b|\bsenior\b/i.test(rest)) add("HS");
  if (/middle\s*school|\bms\b/i.test(rest)) add("MS");
  if (/\bfreshman\b/i.test(rest)) add("Freshman");
  if (/\bjv\b|junior\s*varsity/i.test(rest)) add("JV");
  if (/\bvarsity\b/i.test(rest)) add("Varsity");
  if (/\badult\b|\bwomen'?s\b|\bmen'?s\b/i.test(rest)) add("Adult");
  const g = rest.match(/(\d{1,2})(?:st|nd|rd|th)\s*grade/i);
  if (g) add(`Grade ${Number(g[1])}`);
  return found;
}

/** `6u to 18u` / `6u to adult` → `6U–18U`. Empty when the string is not a range. */
export function formatAgeRange(s: string | null | undefined): string {
  const m = /^\s*(\d{1,2})\s*u\s+to\s+(?:(\d{1,2})\s*u|(adult|hs|high\s*school))\s*$/i.exec(s || "");
  if (!m) return "";
  const a = `${Number(m[1])}U`;
  const b = m[2] ? `${Number(m[2])}U` : /adult/i.test(m[3] ?? "") ? "Adult" : "HS";
  return `${a}\u2013${b}`;
}

export function collectAges(list: Iterable<string> | null | undefined): string[] {
  const out: string[] = [];
  for (const d of list || []) {
    for (const tok of ageTokens(d)) {
      if (!out.includes(tok)) out.push(tok);
    }
  }
  return sortAges(out);
}

const GIRL_DIV =
  /\bgirl|\bwomen|\blady|\bfemale|\bgff\b|\b\d{1,2}ug\b|\bhsg\b/i;

/**
 * Comma-delimited ages for the schedule builder.
 * Prefer open_divisions, then divisions; age_groups range only when there is no
 * division list. Girls brackets append as `(girls: 12U, HS)`. Empty → `Ages TBD`.
 */
export function ageLine(r: Pick<Tournament, "open_divisions" | "girls_divisions" | "divisions" | "age_groups">): string {
  let open = collectAges(r.open_divisions && r.open_divisions.length ? r.open_divisions : null);
  let girls = collectAges(r.girls_divisions && r.girls_divisions.length ? r.girls_divisions : null);
  if (!open.length && r.divisions) {
    const parts = String(r.divisions)
      .split(/[;|,]/)
      .map((x) => x.trim())
      .filter(Boolean);
    const o: string[] = [];
    const g: string[] = [];
    for (const p of parts) {
      const dest = GIRL_DIV.test(p) ? g : o;
      for (const tok of ageTokens(p)) {
        if (!dest.includes(tok)) dest.push(tok);
      }
    }
    if (!open.length) open = sortAges(o);
    if (!girls.length) girls = sortAges(g);
  }
  if (!open.length && r.age_groups) {
    const ag = String(r.age_groups).trim();
    const rng = formatAgeRange(ag);
    if (rng) open = [rng];
    else {
      const toks: string[] = [];
      for (const p of String(ag).split(/[;|,]/)) {
        for (const tok of ageTokens(p)) {
          if (!toks.includes(tok)) toks.push(tok);
        }
      }
      open = sortAges(toks);
    }
  }
  if (!open.length && !girls.length) return "Ages TBD";
  let s = open.join(", ");
  if (girls.length) s += (s ? " " : "") + `(girls: ${girls.join(", ")})`;
  return s;
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
    const ages = ageLine(r);
    lines.push(`  ${r.name}  (${categoryLabel(r.category)})`);
    lines.push(`  ${r.city || "—"}${r.venue ? ` · ${r.venue}` : ""}  ·  ${f.label}`);
    lines.push(`  Ages: ${ages === "Ages TBD" ? "TBD" : ages}`);
    if (r.event_url) lines.push(`  ${r.event_url}`);
    lines.push("");
  }
  lines.push(`Total: ${totLabel}`);
  for (const n of notes) lines.push(`⚠ ${n.text}`);
  return lines.join("\n");
}
