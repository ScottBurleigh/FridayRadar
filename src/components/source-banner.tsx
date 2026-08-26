import type { SourceStatus } from "@/lib/types";

export function SourceBanner({ sources }: { sources: SourceStatus[] }) {
  return (
    <div className="rounded-xl border border-amber-400/20 bg-[#121c2e] px-4 py-3 text-sm text-zinc-300">
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-200">
        Data sources
      </p>
      <ul className="grid gap-1 sm:grid-cols-2 lg:grid-cols-4">
        {sources.map((s) => (
          <li key={s.id} className="flex items-baseline gap-2">
            <span
              className={
                s.status === "live"
                  ? "text-emerald-400"
                  : s.status === "live-partial"
                    ? "text-amber-300"
                    : s.status === "sample"
                      ? "text-sky-300"
                      : "text-rose-400"
              }
            >
              {s.status === "live"
                ? "LIVE"
                : s.status === "live-partial"
                  ? "PARTIAL"
                  : s.status === "sample"
                    ? "SAMPLE"
                    : "BLOCKED"}
            </span>
            <span className="text-zinc-300">{s.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
