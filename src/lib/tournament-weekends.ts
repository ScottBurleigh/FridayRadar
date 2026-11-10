/** Fri–Sun weekends from the viewer's local calendar, not baked into JSON. */

const MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export type Weekend = {
  /** Friday ISO date (YYYY-MM-DD), used as the multi-select value. */
  id: string;
  fri: string;
  sat: string;
  sun: string;
  label: string;
  month: string;
};

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function ymd(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

/**
 * Weekends from the current Fri–Sun (if today is Fri/Sat/Sun) or the next Friday,
 * through July 31 of this year — or next year if today is already past July 31.
 */
export function weekendList(now = new Date()): Weekend[] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dow = today.getDay();
  let fri: Date;
  if (dow === 0) fri = addDays(today, -2);
  else if (dow === 6) fri = addDays(today, -1);
  else if (dow === 5) fri = today;
  else fri = addDays(today, 5 - dow);
  let y = today.getFullYear();
  if (today.getMonth() > 6) y += 1;
  const end = new Date(y, 6, 31);
  const out: Weekend[] = [];
  while (fri <= end) {
    const sat = addDays(fri, 1);
    const sun = addDays(fri, 2);
    out.push({
      id: ymd(fri),
      fri: ymd(fri),
      sat: ymd(sat),
      sun: ymd(sun),
      label: `${DN[sat.getDay()]} ${MN[sat.getMonth()]} ${sat.getDate()} – ${DN[sun.getDay()]} ${MN[sun.getMonth()]} ${sun.getDate()}`,
      month: `${MN[fri.getMonth()]} ${fri.getFullYear()}`,
    });
    fri = addDays(fri, 7);
  }
  return out;
}

export function overlapsWeekend(start: string, end: string | undefined, w: Weekend): boolean {
  const a = start;
  const b = end || start;
  return Boolean(a) && a <= w.sun && b >= w.fri;
}

export function weekendsOf(start: string, end: string | undefined, weekends: Weekend[]): Weekend[] {
  return weekends.filter((w) => overlapsWeekend(start, end, w));
}

export function hiddenByWeekends(
  start: string,
  end: string | undefined,
  selectedFridayIds: Iterable<string>,
  weekends: Weekend[],
): boolean {
  const sel = selectedFridayIds instanceof Set ? selectedFridayIds : new Set(selectedFridayIds);
  if (!sel.size) return false;
  for (const w of weekends) {
    if (sel.has(w.id) && overlapsWeekend(start, end, w)) return true;
  }
  return false;
}
