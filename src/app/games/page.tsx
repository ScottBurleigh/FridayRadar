import type { Metadata } from "next";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { FilterBar } from "@/components/filter-bar";
import { GamesTable } from "@/components/games-table";
import { gamesOfTheWeek, loadDataset } from "@/lib/data";
import { coordsForZip } from "@/lib/geo";

export const metadata: Metadata = {
  title: "Games of the week",
};

function buildQuery(opts: { state?: string; zip?: string; week?: number }) {
  const p = new URLSearchParams();
  if (opts.state) p.set("state", opts.state);
  if (opts.zip) p.set("zip", opts.zip);
  if (opts.week) p.set("week", String(opts.week));
  const s = p.toString();
  return s ? `/games?${s}` : "/games";
}

export default async function GamesPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string; zip?: string; week?: string }>;
}) {
  const params = await searchParams;
  const state = typeof params.state === "string" ? params.state : undefined;
  const zip = typeof params.zip === "string" ? params.zip.replace(/\D/g, "").slice(0, 5) : undefined;
  const weekOffset = Number.isFinite(Number(params.week)) ? Math.trunc(Number(params.week)) : 0;
  const dataset = loadDataset();
  const zipOk = zip && zip.length === 5 ? coordsForZip(zip) : null;
  const result = gamesOfTheWeek(dataset, {
    state: state || undefined,
    zip: zipOk ? zip : undefined,
    weekOffset,
  });

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-amber-400/80">
          Competitive two-sided talent
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-50">
          Games of the week
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-300">
          Ranked by geometric mean of home and away Scout talent (√(home × away)); combined talent is shown on each row and breaks ties. Played games show the MaxPreps score as away–home (never invented). Games missing talent on either side are omitted. State and zip filters follow the game venue, not either school&apos;s home state.
        </p>
      </div>
      <FilterBar
        action="/games"
        state={state}
        zip={zip}
        showSort={false}
        showSearch={false}
        stateLabel="Venue state"
        zipLabel="Venue zip (≈25 miles)"
      />
      <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-amber-400/30 bg-white/5 px-2 py-2">
        <Link
          href={buildQuery({ state, zip, week: weekOffset - 1 })}
          className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-sm text-zinc-200 hover:bg-white/10 hover:text-amber-300"
        >
          <ChevronLeft className="size-4" aria-hidden />
          <span className="hidden sm:inline">Previous week</span>
        </Link>
        <p className="font-mono text-sm text-zinc-100">
          {result.weekStart ? `Week of ${result.weekLabel}` : result.weekLabel}
          {result.games.length ? (
            <span className="ml-2 text-zinc-400">· {result.games.length} games</span>
          ) : null}
        </p>
        <Link
          href={buildQuery({ state, zip, week: weekOffset + 1 })}
          className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-sm text-zinc-200 hover:bg-white/10 hover:text-amber-300"
        >
          <span className="hidden sm:inline">Next week</span>
          <ChevronRight className="size-4" aria-hidden />
        </Link>
      </div>
      {result.emptyReason ? (
        <div className="mt-8 rounded-xl border border-dashed border-amber-400/35 bg-[#17233d] px-6 py-16 text-center">
          <p className="text-lg font-medium text-zinc-100">No games on the board</p>
          <p className="mx-auto mt-2 max-w-lg text-sm text-zinc-400">{result.emptyReason}</p>
          {weekOffset !== 0 ? (
            <p className="mt-4">
              <Link
                href={buildQuery({ state, zip, week: 0 })}
                className="text-sm text-amber-300 hover:underline"
              >
                Jump back to the current week
              </Link>
            </p>
          ) : (
            <p className="mt-4 text-sm text-zinc-400">
              Filters still apply. Rankings stay live even when the schedule is dark.
            </p>
          )}
        </div>
      ) : (
        <div className="mt-6">
          <GamesTable rows={result.games} />
        </div>
      )}
    </main>
  );
}
