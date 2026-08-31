import { Star } from "lucide-react";

const SIZES = {
  sm: { icon: "size-3", gap: "gap-[1px]" },
  md: { icon: "size-3.5", gap: "gap-0.5" },
  lg: { icon: "size-4", gap: "gap-1" },
} as const;

export function StarBadge({
  stars,
  size = "md",
}: {
  stars: number;
  size?: "sm" | "md" | "lg";
}) {
  const n = Math.max(0, Math.min(5, stars));
  const { icon, gap } = SIZES[size];
  if (n <= 0) {
    return <span className="font-sans text-xs text-zinc-400">Listed</span>;
  }
  return (
    <span className={`inline-flex items-center ${gap}`} aria-label={`${n} star`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={i < n ? `${icon} fill-amber-300 text-amber-300` : `${icon} fill-none text-zinc-600`}
          strokeWidth={i < n ? 1.5 : 1.75}
        />
      ))}
    </span>
  );
}
