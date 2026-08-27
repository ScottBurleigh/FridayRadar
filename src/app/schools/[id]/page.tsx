import type { Metadata } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { RecruitList } from "@/components/recruit-list";
import { SchoolScheduleTable } from "@/components/school-schedule";
import { StrengthExplainButton } from "@/components/strength-explain";
import { StrengthScore } from "@/components/strength-score";
import { loadDataset, playersAtSchool, maxprepsScheduleUrl, scheduleForSchool } from "@/lib/data";
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

function Stat({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-amber-400/30 bg-[#17233d] p-3">
      <dt className="text-xs uppercase tracking-wide text-zinc-300">{label}</dt>
      <dd className="mt-1 font-mono text-xl text-zinc-50">{children}</dd>
    </div>
  );
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
  const schedule = scheduleForSchool(dataset, school.id);
  const scheduleUrl = maxprepsScheduleUrl(school.maxpreps, schedule);
  const on3 = school.on3;
  const mpRank = school.maxprepsNational?.rank;
  const dctfRank = school.dctf?.rank;
  const hasSchedule = Boolean(schedule?.games.length);

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
      <p className="text-sm text-zinc-400">
        <Link href="/" className="hover:text-amber-300">
          Rankings
        </Link>
        <span className="px-2">/</span>
        {school.state}
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-50">
        {school.name}
        {school.mascot ? (
          <span className="ml-3 text-xl font-normal text-zinc-400">{school.mascot}</span>
        ) : null}
      </h1>
      <p className="mt-2 text-zinc-400">
        {formatLocation(school.city, school.state, school.zip)}
        {school.address ? ` · ${school.address}` : ""}
      </p>
      <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="2027+ recruits">{recruitCount}</Stat>
        <Stat label="Talent score">
          <span className="text-amber-200">{formatTalent(talent)}</span>
        </Stat>
        <Stat label="Team strength">
          <span className="inline-flex items-center gap-1">
            <StrengthScore value={school.teamStrength} showLabel />
            <StrengthExplainButton
              schoolName={school.name}
              breakdown={school.strengthBreakdown}
              teamStrength={school.teamStrength}
            />
          </span>
        </Stat>
        <Stat label="On3 national">
          <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            {on3?.rank != null ? (
              <span>
                #{on3.rank}
                {on3.rating != null ? (
                  <span className="ml-2 text-sm font-normal text-zinc-400">{on3.rating}</span>
                ) : null}
              </span>
            ) : (
              <span className="text-zinc-400">Unranked</span>
            )}
            {mpRank != null ? (
              <span className="text-base font-normal text-zinc-300">MaxPreps #{mpRank}</span>
            ) : null}
            {dctfRank != null ? (
              <span className="text-base font-normal text-zinc-300">DCTF #{dctfRank}</span>
            ) : null}
          </span>
        </Stat>
        <Stat label="Strength of schedule">
          <span className="inline-flex items-center gap-1">
            <StrengthScore value={school.sos} />
            {school.sosLabel ? (
              <span className="text-sm font-normal capitalize text-zinc-400">
                {school.sosLabel}
              </span>
            ) : null}
          </span>
        </Stat>
        <Stat label="Zip">{school.zip ?? "—"}</Stat>
      </dl>
      {school.maxpreps?.canonicalUrl || scheduleUrl ? (
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {school.maxpreps?.canonicalUrl ? (
            <a
              href={school.maxpreps.canonicalUrl}
              className="text-amber-300/90 hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              MaxPreps page
            </a>
          ) : null}
          {scheduleUrl ? (
            <a
              href={scheduleUrl}
              className="text-amber-300/90 hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              MaxPreps schedule
            </a>
          ) : null}
        </p>
      ) : null}
      <div className="mt-8">
        <RecruitList players={players} ratings={dataset.ratings} />
      </div>
      {hasSchedule && schedule ? (
        <section className="mt-10">
          <h2 className="text-lg font-semibold text-zinc-50">
            {schedule.season} football schedule
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            MaxPreps 26-27 contests for this team. Deleted rows and Varsity Opponent placeholders
            are omitted. Toughness is this team versus the opponent, not combined talent.
          </p>
          <div className="mt-4">
            <SchoolScheduleTable schedule={schedule} schoolName={school.name} />
          </div>
        </section>
      ) : null}
    </main>
  );
}
