import { formatStrength, strengthTier } from "@/lib/format";

export function StrengthScore({
  value,
  showLabel = false,
  className = "",
}: {
  value: number | null | undefined;
  showLabel?: boolean;
  className?: string;
}) {
  const tier = strengthTier(value);
  if (!tier) return <span className={`text-zinc-500 ${className}`}>—</span>;
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span className={`size-1.5 shrink-0 rounded-full ${tier.dot}`} aria-hidden />
      <span className={`font-semibold ${tier.text}`}>{formatStrength(value)}</span>
      {showLabel ? (
        <span className={`font-sans text-[10px] font-medium uppercase tracking-wide ${tier.text}`}>
          {tier.label}
        </span>
      ) : null}
    </span>
  );
}

export function StrengthLegend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-zinc-400">
      <li className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-emerald-400" /> Elite 45+
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-amber-300" /> Strong 20–45
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-sky-300" /> Solid 7–20
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-zinc-400" /> Building &lt;7
      </li>
    </ul>
  );
}
