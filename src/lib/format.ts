export function formatTalent(n: number): string {
  const rounded = Math.round(n * 100) / 100;
  const decimals = Number.isInteger(rounded) ? 0 : String(rounded).split(".")[1]?.length ?? 0;
  return rounded.toLocaleString("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: decimals > 0 ? Math.min(2, decimals) : 0,
  });
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
