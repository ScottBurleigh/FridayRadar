import Link from "next/link";
import { ChevronsDown, ChevronDown, Equal, ChevronUp, ChevronsUp } from "lucide-react";
import type { SchoolSchedule, ToughnessIcon } from "@/lib/types";
import { loadDataset, resolveOpponentHref } from "@/lib/data";
import { formatGameResult, formatScheduleDate, siteLabel } from "@/lib/format";
import { TOUGHNESS_DESCRIPTION, TOUGHNESS_SHORT } from "@/lib/toughness";
import { GameToughnessButton, ToughnessExplainButton } from "@/components/toughness-explain";

const TOUGHNESS: Record<Exclude<ToughnessIcon, "unknown">, { className: string; Icon: typeof Equal }> = {
  much_easier: { className: "text-emerald-400", Icon: ChevronsDown },
  easier: { className: "text-lime-400", Icon: ChevronDown },
  even: { className: "text-zinc-300", Icon: Equal },
  harder: { className: "text-orange-300", Icon: ChevronUp },
  much_harder: { className: "text-rose-400", Icon: ChevronsUp },
};

function ToughnessCell({ icon }: { icon: ToughnessIcon }) {
  if (icon === "unknown" || !(icon in TOUGHNESS)) {
    return null;
  }
  const spec = TOUGHNESS[icon];
  const Icon = spec.Icon;
  const label = TOUGHNESS_DESCRIPTION[icon];
  return (
    <span
      className={`inline-flex items-center justify-center gap-1 ${spec.className}`}
      title={label}
      aria-label={label}
    >
      <Icon className="size-4 shrink-0" strokeWidth={2.25} />
      <span className="hidden font-sans text-[10px] uppercase tracking-wide sm:inline">
        {TOUGHNESS_SHORT[icon]}
      </span>
    </span>
  );
}

export function SchoolScheduleTable({
  schedule,
  schoolName,
}: {
  schedule: SchoolSchedule;
  schoolName: string;
}) {
  if (!schedule.games.length) return null;
  const dataset = loadDataset();

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-amber-400/30 bg-[#17233d]">
        <table className="w-full caption-bottom font-mono text-[13px]">
          <thead>
            <tr className="border-b border-amber-400/30 text-left text-zinc-300">
              <th className="h-10 px-3 font-medium">Date</th>
              <th className="h-10 px-3 font-medium">Opponent</th>
              <th className="h-10 px-3 font-medium">Site</th>
              <th className="h-10 px-3 font-medium">Result</th>
              <th className="h-10 px-3 text-center font-medium">
                <span className="inline-flex items-center justify-center gap-0.5">
                  Tough
                  <ToughnessExplainButton
                    schoolName={schoolName}
                    teamStrength={schedule.teamStrength}
                  />
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {schedule.games.map((g, i) => {
              const oppHref = resolveOpponentHref(dataset, g.opponent);
              return (
                <tr key={g.contestId || `${g.date}-${g.opponent.name}-${i}`} className="border-b border-white/12">
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
                    {g.toughnessIcon === "unknown" ? null : (
                      <GameToughnessButton
                        schoolName={schoolName}
                        teamStrength={schedule.teamStrength}
                        opponentName={g.opponent.name}
                        opponentStrength={g.opponent.teamStrength}
                        icon={g.toughnessIcon}
                      >
                        <ToughnessCell icon={g.toughnessIcon} />
                      </GameToughnessButton>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-400">
        <li className="inline-flex items-center gap-1 text-emerald-400">
          <ChevronsDown className="size-3.5" /> {TOUGHNESS_SHORT.much_easier}
        </li>
        <li className="inline-flex items-center gap-1 text-lime-400">
          <ChevronDown className="size-3.5" /> {TOUGHNESS_SHORT.easier}
        </li>
        <li className="inline-flex items-center gap-1 text-zinc-300">
          <Equal className="size-3.5" /> {TOUGHNESS_SHORT.even}
        </li>
        <li className="inline-flex items-center gap-1 text-orange-300">
          <ChevronUp className="size-3.5" /> {TOUGHNESS_SHORT.harder}
        </li>
        <li className="inline-flex items-center gap-1 text-rose-400">
          <ChevronsUp className="size-3.5" /> {TOUGHNESS_SHORT.much_harder}
        </li>
      </ul>
      <p className="mt-1 text-xs text-zinc-400">
        Icons compare this team&apos;s strength to the opponent&apos;s. Unmapped opponents
        (no team_strength) skip SOS and show no toughness icon.
      </p>
    </div>
  );
}
