import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { RecruitList } from "@/components/recruit-list";
import { loadDataset, playersAtSchool } from "@/lib/data";
import { formatLocation, formatTalent } from "@/lib/format";
import { officialStars, badgeStars, playerPoints, ratingsBySource } from "@/lib/ranking";
import type { RatedPlayer } from "@/lib/types";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const school = loadDataset().schools.find((s) => s.id === id);
  return { title: school?.name ?? "School" };
}

export default async function SchoolPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const dataset = loadDataset();
  const school = dataset.schools.find((s) => s.id === id);
  if (!school) notFound();

  const rawPlayers = playersAtSchool(dataset, school.id);
  const players: RatedPlayer[] = rawPlayers.map((p) => {
    const mine = dataset.ratings.filter((r) => r.player_id === p.id);
    const composite = officialStars(mine);
    return {
      ...p,
      compositeStars: composite,
      badgeStars: badgeStars(composite),
      points: playerPoints(composite),
      ratingsBySource: ratingsBySource(p.id, mine),
    };
  });
  players.sort((a, b) => b.points - a.points || a.full_name.localeCompare(b.full_name));

  const talent =
    school.talentScore != null
      ? school.talentScore
      : players.reduce((s, p) => s + p.points, 0);
  const recruitCount = school.recruitCount != null ? school.recruitCount : players.length;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
      <p className="text-sm text-zinc-500">
        <Link href="/" className="hover:text-amber-300">
          Rankings
        </Link>
        <span className="px-2">/</span>
        {school.state}
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-50">
        {school.name}
        {school.mascot ? (
          <span className="ml-3 text-xl font-normal text-zinc-500">{school.mascot}</span>
        ) : null}
      </h1>
      <p className="mt-2 text-zinc-400">
        {formatLocation(school.city, school.state, school.zip)}
        {school.address ? ` · ${school.address}` : ""}
      </p>
      <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <dt className="text-xs uppercase tracking-wide text-zinc-500">2027+ recruits</dt>
          <dd className="mt-1 font-mono text-xl text-zinc-50">{recruitCount}</dd>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Talent score</dt>
          <dd className="mt-1 font-mono text-xl text-amber-200">{formatTalent(talent)}</dd>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Zip</dt>
          <dd className="mt-1 font-mono text-xl text-zinc-50">{school.zip ?? "—"}</dd>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Type</dt>
          <dd className="mt-1 text-xl text-zinc-50">{school.type ?? "—"}</dd>
        </div>
      </dl>
      {school.maxpreps?.canonicalUrl ? (
        <p className="mt-3 text-sm">
          <a
            href={school.maxpreps.canonicalUrl}
            className="text-amber-300/90 hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            MaxPreps page
          </a>
        </p>
      ) : null}
      <div className="mt-8">
        <RecruitList players={players} ratings={dataset.ratings} />
      </div>
    </main>
  );
}
