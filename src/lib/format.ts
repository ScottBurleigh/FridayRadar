export function formatTalent(n: number): string {
  const rounded = Math.round(n * 100) / 100;
  const decimals = Number.isInteger(rounded) ? 0 : String(rounded).split(".")[1]?.length ?? 0;
  return rounded.toLocaleString("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: decimals > 0 ? Math.min(2, decimals) : 0,
  });
}

export function formatStrength(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return formatTalent(n);
}

export type StrengthTier = {
  label: string;
  text: string;
  dot: string;
  chipBg: string;
  chipText: string;
};

/**
 * team_strength (and SOS, same 0–100 scale) is heavily right-skewed: most
 * schools never touch the On3/MaxPreps boards, so the vast majority sit
 * under ~7. Thresholds are picked from the real distribution (~8/18/13/60%
 * of schools) rather than splitting 0–100 evenly, so "building" isn't a
 * judgment — it's most programs.
 */
const STRENGTH_TIERS: Array<{ min: number } & StrengthTier> = [
  {
    min: 45,
    label: "Elite",
    text: "text-emerald-300",
    dot: "bg-emerald-400",
    chipBg: "bg-emerald-400/15 ring-1 ring-emerald-400/40",
    chipText: "text-emerald-300",
  },
  {
    min: 20,
    label: "Strong",
    text: "text-amber-300",
    dot: "bg-amber-300",
    chipBg: "bg-amber-400/15 ring-1 ring-amber-400/40",
    chipText: "text-amber-300",
  },
  {
    min: 7,
    label: "Solid",
    text: "text-sky-300",
    dot: "bg-sky-300",
    chipBg: "bg-sky-400/15 ring-1 ring-sky-400/40",
    chipText: "text-sky-300",
  },
  {
    min: -Infinity,
    label: "Building",
    text: "text-zinc-300",
    dot: "bg-zinc-400",
    chipBg: "bg-zinc-400/10 ring-1 ring-zinc-400/25",
    chipText: "text-zinc-300",
  },
];

export function strengthTier(n: number | null | undefined): StrengthTier | null {
  if (n == null || Number.isNaN(n)) return null;
  const tier = STRENGTH_TIERS.find((t) => n >= t.min)!;
  return tier;
}

export function formatScheduleDate(isoDate: string | null, kickoff: string | null): string {
  const raw = kickoff || isoDate;
  if (!raw) return "TBD";
  const d = new Date(raw.length <= 10 ? `${raw}T12:00:00-04:00` : raw);
  if (Number.isNaN(d.getTime())) return isoDate || "TBD";
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });
}

export function formatGameResult(
  result: string | null | undefined,
  score: number | null | undefined,
  oppScore: number | null | undefined,
): string {
  const letter = (result || "").trim().toUpperCase();
  if (letter && score != null && oppScore != null) {
    return `${letter} ${score}–${oppScore}`;
  }
  if (letter) return letter;
  if (score != null && oppScore != null) return `${score}–${oppScore}`;
  return "—";
}

export function siteLabel(homeAway: string): string {
  if (homeAway === "away") return "Away";
  if (homeAway === "neutral") return "Neutral";
  return "Home";
}

export function formatKickoff(iso: string | null, tba: boolean): string {
  if (!iso) return "TBD";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "TBD";
  const date = d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });
  if (tba) return `${date} · TBD`;
  const time = d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
  return `${date} · ${time} ET`;
}

export function formatLocation(city: string, state: string, zip?: string | null): string {
  const bits = [city, state].filter(Boolean).join(", ");
  return zip ? `${bits} ${zip}` : bits;
}

export function sourceLabel(source: string): string {
  switch (source) {
    case "247sports":
      return "247Sports";
    case "247sports_composite":
      return "247 Composite";
    case "on3_rivals":
      return "On3/Rivals";
    case "on3_industry":
      return "On3 Industry";
    case "espn":
      return "ESPN";
    default:
      return source;
  }
}
