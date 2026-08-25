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
