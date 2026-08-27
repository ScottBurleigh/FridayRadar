import type { SeasonRecord } from "@/lib/types";

/** "25-26" -> "2025–26", the way a season is normally written out. */
function seasonLabel(season: string): string {
  const m = season.match(/^(\d{2})-(\d{2})$/);
  if (!m) return season;
  return `20${m[1]}–${m[2]}`;
}

/** Sort key for a "YY-YY" season label; newest first. */
function seasonOrder(season: string): number {
  const m = season.match(/^(\d{2})-(\d{2})$/);
  return m ? Number(m[1]) : -1;
}

function winPct(r: SeasonRecord): number | null {
  const games = r.wins + r.losses + r.ties;
  if (!games) return null;
  return (r.wins + r.ties * 0.5) / games;
}

/** Winning seasons lean amber, losing seasons stay neutral — no red for a losing record. */
function toneFor(pct: number | null): string {
  if (pct == null) return "text-zinc-500";
  if (pct >= 0.75) return "text-amber-200";
  if (pct >= 0.5) return "text-zinc-100";
  return "text-zinc-400";
}

export function SeasonHistory({ seasons }: { seasons: SeasonRecord[] }) {
  if (!seasons.length) return null;

  const rows = [...seasons].sort((a, b) => seasonOrder(b.season) - seasonOrder(a.season));
  const played = rows.filter((s) => s.wins + s.losses + s.ties > 0);
  const totals = played.reduce(
    (acc, s) => ({
      wins: acc.wins + s.wins,
      losses: acc.losses + s.losses,
      ties: acc.ties + s.ties,
    }),
    { wins: 0, losses: 0, ties: 0 },
  );
  const totalGames = totals.wins + totals.losses + totals.ties;
  const combinedPct = totalGames ? (totals.wins + totals.ties * 0.5) / totalGames : null;

  return (
    <div className="max-w-md">
      <div className="overflow-x-auto rounded-xl border border-amber-400/30 bg-[#17233d]">
        <table className="w-full caption-bottom font-mono text-[13px]">
          <thead>
            <tr className="border-b border-amber-400/30 text-left text-zinc-300">
              <th className="h-10 px-3 font-medium">Year</th>
              <th className="h-10 px-3 text-right font-medium">Record</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const pct = winPct(s);
              const games = s.wins + s.losses + s.ties;
              return (
                <tr key={s.season} className="border-b border-white/12">
                  <td className="px-3 py-2 whitespace-nowrap text-zinc-300">
                    {seasonLabel(s.season)}
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-semibold tabular-nums ${toneFor(pct)}`}
                  >
                    {games ? s.record : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {played.length > 1 ? (
            <tfoot>
              <tr className="text-zinc-400">
                <td className="px-3 py-2 whitespace-nowrap">{played.length}-season total</td>
                <td className="px-3 py-2 text-right tabular-nums text-zinc-100">
                  {totals.wins}-{totals.losses}
                  {totals.ties ? `-${totals.ties}` : ""}
                  {combinedPct != null ? (
                    <span className="ml-2 font-normal text-zinc-400">
                      {(combinedPct * 100).toFixed(0)}%
                    </span>
                  ) : null}
                </td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
    </div>
  );
}
