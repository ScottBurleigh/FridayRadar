"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { InlineRecruit, SchoolRankingRow, SosLabel } from "@/lib/types";
import { formatTalent } from "@/lib/format";
import { StrengthExplainButton } from "@/components/strength-explain";

function SosCell({
  sos,
  label,
  compact = false,
}: {
  sos: number | null;
  label: SosLabel | null;
  compact?: boolean;
}) {
  if (sos == null) {
    return <span className="text-zinc-600">—</span>;
  }
  const tag =
    label === "tough"
      ? "text-rose-300/90"
      : label === "light"
        ? "text-emerald-400/80"
        : "text-zinc-500";
  if (compact) {
    return (
      <span className="font-mono text-xs text-zinc-400">
        SOS {formatTalent(sos)}
        {label ? <span className={`ml-1 font-sans ${tag}`}>{label}</span> : null}
      </span>
    );
  }
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className="text-zinc-200">{formatTalent(sos)}</span>
      {label ? (
        <span className={`font-sans text-[10px] uppercase tracking-wide ${tag}`}>{label}</span>
      ) : null}
    </span>
  );
}

function SourceStars({ label, stars }: { label: string; stars: number | null }) {
  if (stars == null) return null;
  return (
    <span className="font-mono text-[11px] text-zinc-500">
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
          <span className="text-zinc-500">{p.position ?? "ATH"}</span>
          <span className="font-mono text-[11px] text-zinc-600">{p.classYear}</span>
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
      <div className="mt-2 ml-7 max-h-[min(28rem,70vh)] overflow-y-auto whitespace-normal border-t border-amber-400/20 pt-2">
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

export function RankingsTable({
  rows,
  recruitsBySchool,
}: {
  rows: SchoolRankingRow[];
  recruitsBySchool: Record<string, InlineRecruit[]>;
}) {
  if (!rows.length) {
    return (
      <div className="rounded-xl border border-dashed border-amber-400/25 bg-[#121c2e] px-6 py-16 text-center">
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
            <tr className="border-b border-amber-400/20">
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
              <th className="h-10 w-24 px-2 text-right font-medium text-zinc-300">Strength</th>
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
                <tr key={row.school.id} className="border-b border-white/8 hover:bg-amber-400/5">
                  <td className="p-2 align-top text-zinc-400">{row.rank}</td>
                  <td className="p-2 align-top whitespace-normal">
                    <SchoolRosterCell
                      href={`/schools/${row.school.id}`}
                      name={row.school.name}
                      mascot={row.school.mascot}
                      recruits={recruits}
                    />
                  </td>
                  <td className="p-2 align-top font-sans whitespace-nowrap text-zinc-400">
                    {row.school.city}
                  </td>
                  <td className="p-2 align-top text-zinc-300">{row.school.state}</td>
                  <td className="p-2 align-top text-zinc-400">{row.school.zip ?? "—"}</td>
                  <td className="p-2 align-top text-right text-zinc-200">{row.recruitCount}</td>
                  <td className="p-2 align-top text-right text-amber-300">{row.stars5 || "—"}</td>
                  <td className="p-2 align-top text-right text-zinc-300">{row.stars4 || "—"}</td>
                  <td className="p-2 align-top text-right text-zinc-400">{row.stars3 || "—"}</td>
                  <td className="p-2 align-top text-right font-semibold text-amber-200">
                    {formatTalent(row.talentScore)}
                  </td>
                  <td className="p-2 align-top text-right text-zinc-200">
                    {row.teamStrength != null ? (
                      <span className="inline-flex items-center justify-end gap-0.5">
                        {formatTalent(row.teamStrength)}
                        <StrengthExplainButton
                          schoolName={row.school.name}
                          breakdown={row.school.strengthBreakdown}
                          teamStrength={row.teamStrength}
                        />
                      </span>
                    ) : (
                      "—"
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
      <ul className="space-y-2 md:hidden">
        {rows.map((row) => {
          const recruits = recruitsBySchool[row.school.id] ?? [];
          return (
            <li
              key={row.school.id}
              className="rounded-xl border border-amber-400/20 bg-[#121c2e] p-3"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-mono text-xs text-zinc-400">#{row.rank}</span>
                <span className="font-mono text-sm font-semibold text-amber-200">
                  {formatTalent(row.talentScore)}
                  {row.teamStrength != null ? (
                    <span className="ml-2 inline-flex items-center gap-0.5 font-normal text-zinc-400">
                      str {formatTalent(row.teamStrength)}
                      <StrengthExplainButton
                        schoolName={row.school.name}
                        breakdown={row.school.strengthBreakdown}
                        teamStrength={row.teamStrength}
                      />
                    </span>
                  ) : null}
                </span>
              </div>
              <div className="mt-1">
                <SchoolRosterCell
                  href={`/schools/${row.school.id}`}
                  name={row.school.name}
                  mascot={row.school.mascot}
                  recruits={recruits}
                />
              </div>
              <p className="mt-1 pl-7 text-sm text-zinc-400">
                {row.school.city}, {row.school.state} {row.school.zip ?? ""}
              </p>
              <p className="mt-2 pl-7 font-mono text-xs text-zinc-400">
                {row.recruitCount} recruits · {row.stars5} 5★ · {row.stars4} 4★ · {row.stars3} 3★
              </p>
              <p className="mt-1 pl-7">
                <SosCell sos={row.sos} label={row.sosLabel} compact />
              </p>
            </li>
          );
        })}
      </ul>
    </>
  );
}
