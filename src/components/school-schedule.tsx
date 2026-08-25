import Link from "next/link";
import { ChevronsDown, ChevronDown, Equal, ChevronUp, ChevronsUp } from "lucide-react";
import type { SchoolSchedule, ToughnessIcon } from "@/lib/types";
import { formatGameResult, formatScheduleDate, siteLabel } from "@/lib/format";

const TOUGHNESS: Record<
  Exclude<ToughnessIcon, "unknown">,
  { label: string; className: string; Icon: typeof Equal }
> = {
  much_easier: {
    label: "Mismatch-easy — cupcake from this team's strength",
    className: "text-emerald-400",
    Icon: ChevronsDown,
  },
  easier: {
    label: "Lean-easy — this team is clearly stronger",
    className: "text-lime-400",
    Icon: ChevronDown,
  },
  even: {
    label: "Toss-up — strengths are within a close band",
    className: "text-zinc-300",
    Icon: Equal,
  },
  harder: {
    label: "Lean-hard — opponent is clearly stronger",
    className: "text-orange-300",
    Icon: ChevronUp,
  },
  much_harder: {
    label: "Mismatch-hard — loaded opponent from this team's view",
    className: "text-rose-400",
    Icon: ChevronsUp,
  },
};

function ToughnessCell({ icon }: { icon: ToughnessIcon }) {
  if (icon === "unknown" || !(icon in TOUGHNESS)) {
    return null;
  }
  const spec = TOUGHNESS[icon];
  const Icon = spec.Icon;
  const short =
    icon === "much_easier"
      ? "easy"
      : icon === "easier"
        ? "lean-easy"
        : icon === "even"
          ? "toss-up"
          : icon === "harder"
            ? "lean-hard"
            : "hard";
  return (
    <span
      className={`inline-flex items-center justify-center gap-1 ${spec.className}`}
      title={spec.label}
      aria-label={spec.label}
    >
      <Icon className="size-4 shrink-0" strokeWidth={2.25} />
      <span className="hidden font-sans text-[10px] uppercase tracking-wide sm:inline">{short}</span>
    </span>
  );
}

export function SchoolScheduleTable({ schedule }: { schedule: SchoolSchedule }) {
  if (!schedule.games.length) return null;

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full caption-bottom font-mono text-[13px]">
          <thead>
            <tr className="border-b border-white/10 text-left text-zinc-500">
              <th className="h-10 px-3 font-medium">Date</th>
              <th className="h-10 px-3 font-medium">Opponent</th>
              <th className="h-10 px-3 font-medium">Site</th>
              <th className="h-10 px-3 font-medium">Result</th>
              <th className="h-10 px-3 text-center font-medium">Tough</th>
            </tr>
          </thead>
          <tbody>
            {schedule.games.map((g, i) => {
              const oppHref = g.opponent.siteId ? `/schools/${g.opponent.siteId}` : null;
              return (
                <tr key={g.contestId || `${g.date}-${g.opponent.name}-${i}`} className="border-b border-white/8">
                  <td className="px-3 py-2 whitespace-nowrap text-zinc-300">
                    {formatScheduleDate(g.date, g.kickoff)}
                  </td>
                  <td className="px-3 py-2 font-sans whitespace-normal text-zinc-100">
                    {oppHref ? (
                      <Link href={oppHref} className="hover:text-amber-300">
                        {g.opponent.name}
                      </Link>
                    ) : (
                      g.opponent.name
                    )}
                    {g.opponent.city || g.opponent.state ? (
                      <span className="ml-2 text-xs text-zinc-500">
                        {[g.opponent.city, g.opponent.state].filter(Boolean).join(", ")}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-zinc-400">{siteLabel(g.homeAway)}</td>
                  <td className="px-3 py-2 text-zinc-200">
                    {g.maxprepsGameUrl && formatGameResult(g.result, g.score, g.oppScore) !== "—" ? (
                      <a
                        href={g.maxprepsGameUrl}
                        className="text-amber-300/90 hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {formatGameResult(g.result, g.score, g.oppScore)}
                      </a>
                    ) : (
                      formatGameResult(g.result, g.score, g.oppScore)
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <ToughnessCell icon={g.toughnessIcon} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
        <li className="inline-flex items-center gap-1 text-emerald-400">
          <ChevronsDown className="size-3.5" /> mismatch-easy
        </li>
        <li className="inline-flex items-center gap-1 text-lime-400">
          <ChevronDown className="size-3.5" /> lean-easy
        </li>
        <li className="inline-flex items-center gap-1 text-zinc-300">
          <Equal className="size-3.5" /> toss-up
        </li>
        <li className="inline-flex items-center gap-1 text-orange-300">
          <ChevronUp className="size-3.5" /> lean-hard
        </li>
        <li className="inline-flex items-center gap-1 text-rose-400">
          <ChevronsUp className="size-3.5" /> mismatch-hard
        </li>
      </ul>
      <p className="mt-1 text-xs text-zinc-600">
        Icons compare this team&apos;s strength to the opponent&apos;s. Unmapped opponents
        (no team_strength) skip SOS and show no toughness icon.
      </p>
    </div>
  );
}
