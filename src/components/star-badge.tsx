export function StarBadge({ stars, size = "md" }: { stars: number; size?: "sm" | "md" }) {
  const n = Math.max(0, Math.min(5, stars));
  const cls = size === "sm" ? "text-[11px] tracking-tight" : "text-xs tracking-wide";
  if (n <= 0) {
    return <span className={`font-mono text-zinc-500 ${cls}`}>listed</span>;
  }
  return (
    <span className={`font-mono text-amber-300 ${cls}`} aria-label={`${n} star`}>
      {"★".repeat(n)}
      <span className="text-zinc-700">{"★".repeat(5 - n)}</span>
    </span>
  );
}
