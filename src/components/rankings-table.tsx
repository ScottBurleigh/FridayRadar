"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { InlineRecruit, SchoolRankingRow, SosLabel } from "@/lib/types";
import { formatTalent } from "@/lib/format";
import { StrengthExplainButton } from "@/components/strength-explain";
import { StrengthScore } from "@/components/strength-score";

function SosCell({
  sos,
  label,
  compact = false,
  hidePrefix = false,
}: {
  sos: number | null;
  label: SosLabel | null;
  compact?: boolean;
  hidePrefix?: boolean;
}) {
  if (sos == null) {
    return <span className="text-zinc-500">—</span>;
  }
  const tag =
    label === "tough"
      ? "text-rose-300/90"
      : label === "light"
        ? "text-emerald-400/80"
        : "text-zinc-400";
  if (compact) {
    return (
      <span className="font-mono text-xs text-zinc-300">
        {hidePrefix ? "" : "SOS "}
        {formatTalent(sos)}
        {label ? <span className={`ml-1 font-sans ${tag}`}>{label}</span> : null}
      </span>
    );
  }
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className="text-zinc-100">{formatTalent(sos)}</span>
      {label ? (
        <span className={`font-sans text-[10px] uppercase tracking-wide ${tag}`}>{label}</span>
      ) : null}
    </span>
  );
}

function SourceStars({ label, stars }: { label: string; stars: number | null }) {
  if (stars == null) return null;
  return (
    <span className="font-mono text-[11px] text-zinc-400">
      {label} <span className="text-amber-300">{stars}★</span>
    </span>
  );
}

function InlineRecruitList({ players }: { players: InlineRecruit[] }) {
  if (!players.length) {
    return <p className="text-sm text-zinc-400">No 2027+ recruits on file for this school.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {players.map((p) => (
        <li
          key={p.id}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 font-sans text-sm whitespace-normal"
        >
          <span className="text-zinc-100">{p.name}</span>
          <span className="text-zinc-400">{p.position ?? "ATH"}</span>
          <span className="font-mono text-[11px] text-zinc-500">{p.classYear}</span>
          <span className="flex flex-wrap gap-x-2">
            <SourceStars label="247" stars={p.stars247} />
            <SourceStars label="On3" stars={p.starsOn3} />
            <SourceStars label="ESPN" stars={p.starsEspn} />
          </span>
          {p.profileUrl ? (
            <a
              href={p.profileUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-amber-300/90 hover:underline"
            >
              Profile
            </a>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function SchoolRosterCell({
  href,
  name,
  mascot,
  recruits,
}: {
  href: string;
  name: string;
  mascot: string | null;
  recruits: InlineRecruit[];
}) {
  return (
    <details name="rankings-roster" className="group w-full">
      <summary className="flex cursor-pointer list-none items-start gap-0.5 [&::-webkit-details-marker]:hidden">
        <span
          className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md text-zinc-400 group-open:text-amber-300 hover:bg-white/10 hover:text-amber-300"
          aria-label={`Show ${name} recruits`}
        >
          <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
        </span>
        <Link
          href={href}
          className="pt-0.5 font-sans font-medium text-zinc-100 hover:text-amber-300"
          onClick={(e) => e.stopPropagation()}
        >
          {name}
          {mascot ? <span className="ml-2 font-normal text-zinc-400">{mascot}</span> : null}
        </Link>
      </summary>
      <div className="mt-2 ml-7 max-h-[min(28rem,70vh)] overflow-y-auto whitespace-normal border-t border-amber-400/30 pt-2">
        <p className="mb-2 font-sans text-xs text-zinc-400">
          {recruits.length
            ? `${recruits.length} recruit${recruits.length === 1 ? "" : "s"} on the 2027+ roster`
            : "Empty 2027+ roster"}
        </p>
        <InlineRecruitList players={recruits} />
      </div>
    </details>
  );
}

function StarCountChip({ n, label }: { n: number; label: string }) {
  if (!n) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-amber-400/10 px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-amber-400/25">
      <span className="font-semibold text-amber-200">{n}</span>
      <span className="text-amber-300/80">{label}</span>
    </span>
  );
}

function MobileStat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-0.5 rounded-lg bg-white/5 px-2 py-1.5 text-center">
      <span className="font-sans text-[10px] font-medium uppercase tracking-wide text-zinc-400">
        {label}
      </span>
      <span className="font-mono text-sm">{children}</span>
    </div>
  );
}

export function RankingsTable({
  rows,
  recruitsBySchool,
}: {
  rows: SchoolRankingRow[];
  recruitsBySchool: Record<string, InlineRecruit[]>;
}) {
  if (!rows.length) {
    return (
      <div className="rounded-xl border border-dashed border-amber-400/35 bg-[#17233d] px-6 py-16 text-center">
        <p className="text-lg font-medium text-zinc-100">No programs match these filters</p>
        <p className="mt-2 text-sm text-zinc-400">
          Clear the state or zip filter to return to the nationwide 2027+ talent board.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="hidden md:block">
        <table className="w-full caption-bottom font-mono text-[13px]">
          <thead>
            <tr className="border-b border-amber-400/30">
              <th className="h-10 w-14 px-2 text-left font-medium text-zinc-300">Rk</th>
              <th className="h-10 px-2 text-left font-medium text-zinc-300">School</th>
              <th className="h-10 px-2 text-left font-medium text-zinc-300">City</th>
              <th className="h-10 w-12 px-2 text-left font-medium text-zinc-300">St</th>
              <th className="h-10 w-16 px-2 text-left font-medium text-zinc-300">Zip</th>
              <th className="h-10 w-16 px-2 text-right font-medium text-zinc-300">Rec</th>
              <th className="h-10 w-12 px-2 text-right font-medium text-zinc-300">5★</th>
              <th className="h-10 w-12 px-2 text-right font-medium text-zinc-300">4★</th>
              <th className="h-10 w-12 px-2 text-right font-medium text-zinc-300">3★</th>
              <th className="h-10 w-24 px-2 text-right font-medium text-zinc-300">Talent</th>
              <th className="h-10 w-28 px-2 text-right font-medium text-zinc-300">Strength</th>
              <th
                className="h-10 w-24 px-2 text-right font-medium text-zinc-300"
                title="Mean of this season’s MaxPreps opponents’ team strength"
              >
                SOS
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const recruits = recruitsBySchool[row.school.id] ?? [];
              return (
                <tr key={row.school.id} className="border-b border-white/12 hover:bg-amber-400/8">
                  <td className="p-2 align-top text-zinc-400">{row.rank}</td>
                  <td className="p-2 align-top whitespace-normal">
                    <SchoolRosterCell
                      href={`/schools/${row.school.id}`}
                      name={row.school.name}
                      mascot={row.school.mascot}
                      recruits={recruits}
                    />
                  </td>
                  <td className="p-2 align-top font-sans whitespace-nowrap text-zinc-300">
                    {row.school.city}
                  </td>
                  <td className="p-2 align-top text-zinc-200">{row.school.state}</td>
                  <td className="p-2 align-top text-zinc-300">{row.school.zip ?? "—"}</td>
                  <td className="p-2 align-top text-right text-zinc-100">{row.recruitCount}</td>
                  <td className="p-2 align-top text-right text-amber-300">{row.stars5 || "—"}</td>
                  <td className="p-2 align-top text-right text-zinc-200">{row.stars4 || "—"}</td>
                  <td className="p-2 align-top text-right text-zinc-300">{row.stars3 || "—"}</td>
                  <td className="p-2 align-top text-right font-semibold text-amber-200">
                    {formatTalent(row.talentScore)}
                  </td>
                  <td className="p-2 align-top text-right">
                    {row.teamStrength != null ? (
                      <span className="inline-flex items-center justify-end gap-0.5">
                        <StrengthScore value={row.teamStrength} />
                        <StrengthExplainButton
                          schoolName={row.school.name}
                          breakdown={row.school.strengthBreakdown}
                          teamStrength={row.teamStrength}
                        />
                      </span>
                    ) : (
                      <span className="text-zinc-500">—</span>
                    )}
                  </td>
                  <td className="p-2 align-top text-right">
                    <SosCell sos={row.sos} label={row.sosLabel} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="space-y-2.5 md:hidden">
        {rows.map((row) => {
          const recruits = recruitsBySchool[row.school.id] ?? [];
          return (
            <li
              key={row.school.id}
              className="rounded-xl border border-amber-400/30 bg-[#17233d] p-3.5"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="mt-1 font-mono text-xs text-zinc-400">#{row.rank}</span>
                <div className="min-w-0 flex-1">
                  <SchoolRosterCell
                    href={`/schools/${row.school.id}`}
                    name={row.school.name}
                    mascot={row.school.mascot}
                    recruits={recruits}
                  />
                </div>
              </div>
              <p className="mt-1 pl-7 text-sm text-zinc-400">
                {row.school.city}, {row.school.state} {row.school.zip ?? ""}
              </p>

              <div className="mt-3 grid grid-cols-3 gap-1.5 pl-7">
                <MobileStat label="Talent">
                  <span className="font-semibold text-amber-200">
                    {formatTalent(row.talentScore)}
                  </span>
                </MobileStat>
                <MobileStat label="Strength">
                  {row.teamStrength != null ? (
                    <span className="inline-flex items-center gap-0.5">
                      <StrengthScore value={row.teamStrength} />
                      <StrengthExplainButton
                        schoolName={row.school.name}
                        breakdown={row.school.strengthBreakdown}
                        teamStrength={row.teamStrength}
                      />
                    </span>
                  ) : (
                    <span className="text-zinc-500">—</span>
                  )}
                </MobileStat>
                <MobileStat label="SOS">
                  <SosCell sos={row.sos} label={row.sosLabel} compact hidePrefix />
                </MobileStat>
              </div>

              <div className="mt-2.5 flex flex-wrap items-center gap-1.5 pl-7">
                <StarCountChip n={row.stars5} label="5★" />
                <StarCountChip n={row.stars4} label="4★" />
                <StarCountChip n={row.stars3} label="3★" />
                <span className="font-sans text-xs text-zinc-400">
                  {row.recruitCount} recruit{row.recruitCount === 1 ? "" : "s"}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
