import Link from "next/link";
import { FilterBar } from "@/components/filter-bar";
import { RankingsTable } from "@/components/rankings-table";
import { StrengthLegend } from "@/components/strength-score";
import { filteredRankings, inlineRecruitsForSchools, loadDataset } from "@/lib/data";
import { coordsForZip } from "@/lib/geo";

const PAGE_SIZE = 100;

function buildQuery(opts: {
  state?: string;
  zip?: string;
  sort?: string;
  q?: string;
  page?: number;
}) {
  const p = new URLSearchParams();
  if (opts.q) p.set("q", opts.q);
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
  searchParams: Promise<{
    state?: string;
    zip?: string;
    sort?: string;
    q?: string;
    page?: string;
  }>;
}) {
  const params = await searchParams;
  const state = typeof params.state === "string" ? params.state : undefined;
  const q = typeof params.q === "string" ? params.q.trim().slice(0, 80) : undefined;
  const zip = typeof params.zip === "string" ? params.zip.replace(/\D/g, "").slice(0, 5) : undefined;
  const sort =
    params.sort === "count" || params.sort === "strength" ? params.sort : "talent";
  const page = Math.max(1, Number(params.page) || 1);
  const dataset = loadDataset();
  const zipOk = zip && zip.length === 5 ? coordsForZip(zip) : null;
  const zipError = zip && zip.length === 5 && !zipOk;
  const rows = filteredRankings(dataset, {
    state: state || undefined,
    zip: zipOk ? zip : undefined,
    sort,
    q: q || undefined,
    includeUnranked: true,
  });
  const withData = rows.filter((r) => r.school.mapped !== false).length;
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
        </div>
        <p className="font-mono text-sm text-zinc-400">
          {rows.length.toLocaleString()} programs ·{" "}
          <span className="text-zinc-300">{withData.toLocaleString()}</span> with recruiting
          data · as of {dataset.meta.as_of}
        </p>
      </div>
      <FilterBar action="/" state={state} zip={zip} sort={sort} q={q} />
      {q ? (
        <p className="mt-3 text-sm text-zinc-400">
          {rows.length.toLocaleString()} result{rows.length === 1 ? "" : "s"} for{" "}
          <span className="text-zinc-100">&ldquo;{q}&rdquo;</span>
          <Link href={buildQuery({ state, zip, sort })} className="ml-3 text-amber-300 hover:underline">
            Clear search
          </Link>
        </p>
      ) : null}
      {zipError ? (
        <p className="mt-3 text-sm text-rose-300">
          Zip {zip} is not in the centroid file, so the radius filter was ignored.
        </p>
      ) : zipOk && zip ? (
        <p className="mt-3 text-sm text-zinc-400">
          Showing schools within about 25 miles of {zip}.
        </p>
      ) : null}
      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="font-sans text-xs font-medium uppercase tracking-wide text-zinc-400">
          Strength score
        </span>
        <StrengthLegend />
      </div>
      <div className="mt-2">
        <RankingsTable
          rows={slice}
          recruitsBySchool={inlineRecruitsForSchools(
            dataset,
            slice.map((row) => row.school.id),
          )}
        />
      </div>
      {pages > 1 ? (
        <nav className="mt-6 flex items-center justify-between gap-3 text-sm text-zinc-400">
          {safePage > 1 ? (
            <Link
              href={buildQuery({ state, zip, sort, q, page: safePage - 1 })}
              className="rounded-md border border-amber-400/35 px-3 py-1.5 text-zinc-200 hover:text-amber-300"
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
              href={buildQuery({ state, zip, sort, q, page: safePage + 1 })}
              className="rounded-md border border-amber-400/35 px-3 py-1.5 text-zinc-200 hover:text-amber-300"
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
