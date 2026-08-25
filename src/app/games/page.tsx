import type { Metadata } from "next";
import { FilterBar } from "@/components/filter-bar";
import { GamesTable } from "@/components/games-table";
import { SourceBanner } from "@/components/source-banner";
import { gamesOfTheWeek, loadDataset } from "@/lib/data";
import { coordsForZip } from "@/lib/geo";

export const metadata: Metadata = {
  title: "Games of the week",
};

export default async function GamesPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string; zip?: string }>;
}) {
  const params = await searchParams;
  const state = typeof params.state === "string" ? params.state : undefined;
  const zip = typeof params.zip === "string" ? params.zip.replace(/\D/g, "").slice(0, 5) : undefined;
  const dataset = loadDataset();
  const zipOk = zip && zip.length === 5 ? coordsForZip(zip) : null;
  const result = gamesOfTheWeek(dataset, {
    state: state || undefined,
    zip: zipOk ? zip : undefined,
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
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Ranked by geometric mean of home and away Scout talent (√(home × away)); combined talent is shown on each row and breaks ties. Games missing talent on either side are omitted. State and zip filters follow the game venue, not either school&apos;s home state.
        </p>
      </div>
      <SourceBanner sources={dataset.meta.sources} />
      <div className="mt-4">
        <FilterBar
          action="/games"
          state={state}
          zip={zip}
          showSort={false}
          stateLabel="Venue state"
          zipLabel="Venue zip (≈25 miles)"
        />
      </div>
      <p className="mt-4 font-mono text-sm text-zinc-500">
        {result.weekStart ? `Week of ${result.weekLabel}` : result.weekLabel}
        {result.games.length ? ` · ${result.games.length} games` : ""}
      </p>
      {result.emptyReason ? (
        <div className="mt-8 rounded-xl border border-dashed border-white/15 px-6 py-16 text-center">
          <p className="text-lg font-medium text-zinc-200">No games on the board</p>
          <p className="mx-auto mt-2 max-w-lg text-sm text-zinc-500">{result.emptyReason}</p>
          <p className="mt-4 text-sm text-zinc-600">
            Filters still apply. Rankings stay live even when the schedule is dark.
          </p>
        </div>
      ) : (
        <div className="mt-6">
          <GamesTable rows={result.games} />
        </div>
      )}
    </main>
  );
}
