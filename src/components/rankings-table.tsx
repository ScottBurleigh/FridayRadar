"use client";

import { Fragment, useId, useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import type { InlineRecruit, SchoolRankingRow } from "@/lib/types";
import { formatTalent } from "@/lib/format";

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
    return <p className="text-sm text-zinc-500">No 2027+ recruits on file.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {players.map((p) => (
        <li
          key={p.id}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 font-sans text-sm"
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

function ExpandButton({
  schoolName,
  open,
  controlsId,
  onToggle,
}: {
  schoolName: string;
  open: boolean;
  controlsId: string;
  onToggle: () => void;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-xs"
      aria-expanded={open}
      aria-controls={controlsId}
      aria-label={open ? `Hide ${schoolName} recruits` : `Show ${schoolName} recruits`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onToggle();
      }}
      className="text-zinc-500 hover:text-amber-300"
    >
      <ChevronRight className={open ? "rotate-90 transition-transform" : "transition-transform"} />
    </Button>
  );
}

export function RankingsTable({
  rows,
  recruitsBySchool,
}: {
  rows: SchoolRankingRow[];
  recruitsBySchool: Record<string, InlineRecruit[]>;
}) {
  const uid = useId();
  const [openId, setOpenId] = useState<string | null>(null);

  if (!rows.length) {
    return (
      <div className="rounded-xl border border-dashed border-white/15 px-6 py-16 text-center">
        <p className="text-lg font-medium text-zinc-200">No programs match these filters</p>
        <p className="mt-2 text-sm text-zinc-500">
          Clear the state or zip filter to return to the nationwide 2027+ talent board.
        </p>
      </div>
    );
  }

  const toggle = (id: string) => setOpenId((cur) => (cur === id ? null : id));

  return (
    <>
      <div className="hidden md:block">
        <Table className="font-mono text-[13px]">
          <TableHeader>
            <TableRow className="border-white/10 hover:bg-transparent">
              <TableHead className="w-14 text-zinc-500">Rk</TableHead>
              <TableHead className="text-zinc-500">School</TableHead>
              <TableHead className="text-zinc-500">City</TableHead>
              <TableHead className="w-12 text-zinc-500">St</TableHead>
              <TableHead className="w-16 text-zinc-500">Zip</TableHead>
              <TableHead className="w-16 text-right text-zinc-500">Rec</TableHead>
              <TableHead className="w-12 text-right text-zinc-500">5★</TableHead>
              <TableHead className="w-12 text-right text-zinc-500">4★</TableHead>
              <TableHead className="w-12 text-right text-zinc-500">3★</TableHead>
              <TableHead className="w-24 text-right text-zinc-500">Talent</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const open = openId === row.school.id;
              const panelId = `${uid}-${row.school.id}`;
              const recruits = recruitsBySchool[row.school.id] ?? [];
              return (
                <Fragment key={row.school.id}>
                  <TableRow className="border-white/8 hover:bg-amber-400/5">
                    <TableCell className="text-zinc-400">{row.rank}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-0.5">
                        <ExpandButton
                          schoolName={row.school.name}
                          open={open}
                          controlsId={panelId}
                          onToggle={() => toggle(row.school.id)}
                        />
                        <Link
                          href={`/schools/${row.school.id}`}
                          className="font-sans font-medium text-zinc-100 hover:text-amber-300"
                        >
                          {row.school.name}
                          {row.school.mascot ? (
                            <span className="ml-2 font-normal text-zinc-500">{row.school.mascot}</span>
                          ) : null}
                        </Link>
                      </div>
                    </TableCell>
                    <TableCell className="font-sans text-zinc-400">{row.school.city}</TableCell>
                    <TableCell className="text-zinc-300">{row.school.state}</TableCell>
                    <TableCell className="text-zinc-400">{row.school.zip ?? "—"}</TableCell>
                    <TableCell className="text-right text-zinc-200">{row.recruitCount}</TableCell>
                    <TableCell className="text-right text-amber-300">{row.stars5 || "—"}</TableCell>
                    <TableCell className="text-right text-zinc-300">{row.stars4 || "—"}</TableCell>
                    <TableCell className="text-right text-zinc-400">{row.stars3 || "—"}</TableCell>
                    <TableCell className="text-right font-semibold text-amber-200">
                      {formatTalent(row.talentScore)}
                    </TableCell>
                  </TableRow>
                  {open ? (
                    <TableRow className="border-white/8 hover:bg-transparent">
                      <TableCell colSpan={10} className="whitespace-normal bg-black/25 px-4 py-3">
                        <div id={panelId}>
                          <InlineRecruitList players={recruits} />
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : null}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <ul className="space-y-2 md:hidden">
        {rows.map((row) => {
          const open = openId === row.school.id;
          const panelId = `${uid}-m-${row.school.id}`;
          const recruits = recruitsBySchool[row.school.id] ?? [];
          return (
            <li
              key={row.school.id}
              className="rounded-xl border border-white/10 bg-white/[0.03] p-3"
            >
              <div className="flex items-start gap-1">
                <ExpandButton
                  schoolName={row.school.name}
                  open={open}
                  controlsId={panelId}
                  onToggle={() => toggle(row.school.id)}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-mono text-xs text-zinc-500">#{row.rank}</span>
                    <span className="font-mono text-sm font-semibold text-amber-200">
                      {formatTalent(row.talentScore)}
                    </span>
                  </div>
                  <p className="mt-1 font-medium text-zinc-50">
                    <Link href={`/schools/${row.school.id}`} className="hover:text-amber-300">
                      {row.school.name}
                    </Link>
                  </p>
                  <p className="text-sm text-zinc-500">
                    {row.school.city}, {row.school.state} {row.school.zip ?? ""}
                  </p>
                  <p className="mt-2 font-mono text-xs text-zinc-400">
                    {row.recruitCount} recruits · {row.stars5} 5★ · {row.stars4} 4★ · {row.stars3}{" "}
                    3★
                  </p>
                </div>
              </div>
              {open ? (
                <div id={panelId} className="mt-3 border-t border-white/10 pt-3">
                  <InlineRecruitList players={recruits} />
                </div>
              ) : (
                <div id={panelId} hidden />
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
