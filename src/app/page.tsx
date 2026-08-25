import Link from "next/link";
import { FilterBar } from "@/components/filter-bar";
import { RankingsTable } from "@/components/rankings-table";
import { SourceBanner } from "@/components/source-banner";
import { filteredRankings, loadDataset } from "@/lib/data";
import { coordsForZip } from "@/lib/geo";

const PAGE_SIZE = 100;

function buildQuery(opts: { state?: string; zip?: string; sort?: string; page?: number }) {
  const p = new URLSearchParams();
  if (opts.state) p.set("state", opts.state);
  if (opts.zip) p.set("zip", opts.zip);
  if (opts.sort && opts.sort !== "talent") p.set("sort", opts.sort);
  if (opts.page && opts.page > 1) p.set("page", String(opts.page));
  const s = p.toString();
  return s ? `/?${s}` : "/";
}

export default async function RankingsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string; zip?: string; sort?: string; page?: string }>;
}) {
  const params = await searchParams;
  const state = typeof params.state === "string" ? params.state : undefined;
  const zip = typeof params.zip === "string" ? params.zip.replace(/\D/g, "").slice(0, 5) : undefined;
  const sort = params.sort === "count" ? "count" : "talent";
  const page = Math.max(1, Number(params.page) || 1);
  const dataset = loadDataset();
  const zipOk = zip && zip.length === 5 ? coordsForZip(zip) : null;
  const zipError = zip && zip.length === 5 && !zipOk;
  const rows = filteredRankings(dataset, {
    state: state || undefined,
    zip: zipOk ? zip : undefined,
    sort,
  });
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, pages);
  const slice = rows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-amber-400/80">
            2027+ high school talent
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-50">
            Program rankings
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            High schools ranked by the recruiting talent on their 2027, 2028, and 2029+
            rosters. A player belongs to the school they attend — not the college they
            committed to.
          </p>
        </div>
        <p className="font-mono text-sm text-zinc-500">
          {rows.length.toLocaleString()} programs · as of {dataset.meta.as_of}
        </p>
      </div>
      <SourceBanner sources={dataset.meta.sources} />
      <div className="mt-4">
        <FilterBar action="/" state={state} zip={zip} sort={sort} />
      </div>
      {zipError ? (
        <p className="mt-3 text-sm text-rose-300">
          Zip {zip} is not in the centroid file, so the radius filter was ignored.
        </p>
      ) : zipOk && zip ? (
        <p className="mt-3 text-sm text-zinc-500">
          Showing schools within about 25 miles of {zip}.
        </p>
      ) : null}
      <div className="mt-6">
        <RankingsTable rows={slice} />
      </div>
      {pages > 1 ? (
        <nav className="mt-6 flex items-center justify-between gap-3 text-sm text-zinc-400">
          {safePage > 1 ? (
            <Link
              href={buildQuery({ state, zip, sort, page: safePage - 1 })}
              className="rounded-md border border-white/10 px-3 py-1.5 hover:text-amber-300"
            >
              Previous
            </Link>
          ) : (
            <span />
          )}
          <span className="font-mono">
            Page {safePage} / {pages}
          </span>
          {safePage < pages ? (
            <Link
              href={buildQuery({ state, zip, sort, page: safePage + 1 })}
              className="rounded-md border border-white/10 px-3 py-1.5 hover:text-amber-300"
            >
              Next
            </Link>
          ) : (
            <span />
          )}
        </nav>
      ) : null}
    </main>
  );
}
