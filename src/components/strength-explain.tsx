"use client";

import { useState } from "react";
import { Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { StrengthBreakdown } from "@/lib/types";

function n(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    maximumFractionDigits: 3,
    minimumFractionDigits: 0,
  });
}

function Formula({ children }: { children: string }) {
  return <p className="font-mono text-[13px] leading-relaxed text-amber-100/90">{children}</p>;
}

export function StrengthExplainButton({
  schoolName,
  breakdown,
  teamStrength,
}: {
  schoolName: string;
  breakdown: StrengthBreakdown | null | undefined;
  teamStrength: number | null | undefined;
}) {
  const [open, setOpen] = useState(false);
  if (teamStrength == null || !breakdown) return null;

  const talentLine =
    breakdown.talentScore != null && breakdown.talentMax != null && breakdown.talentNorm != null
      ? `talent_norm = 100 × ${n(breakdown.talentScore)} / ${n(breakdown.talentMax)} = ${n(breakdown.talentNorm)}`
      : null;
  const on3Line =
    breakdown.on3Norm != null &&
    breakdown.on3Rating != null &&
    breakdown.on3Min != null &&
    breakdown.on3Max != null
      ? `on3_norm = 100 × (${n(breakdown.on3Rating)} − ${n(breakdown.on3Min)}) / (${n(breakdown.on3Max)} − ${n(breakdown.on3Min)}) = ${n(breakdown.on3Norm)}`
      : null;
  const mpLine =
    breakdown.maxprepsRank != null && breakdown.maxprepsNorm != null
      ? `maxpreps_norm = 100 × (101 − ${breakdown.maxprepsRank}) / 100 = ${n(breakdown.maxprepsNorm)}`
      : null;

  const rankingParts: string[] = [];
  if (breakdown.on3Norm != null) rankingParts.push(n(breakdown.on3Norm));
  if (breakdown.maxprepsNorm != null) rankingParts.push(n(breakdown.maxprepsNorm));
  const rankingLine =
    breakdown.rankingNorm != null && rankingParts.length
      ? rankingParts.length === 1
        ? `ranking_norm = ${rankingParts[0]}`
        : `ranking_norm = (${rankingParts.join(" + ")}) / ${rankingParts.length} = ${n(breakdown.rankingNorm)}`
      : null;

  const blendParts: string[] = [];
  if (breakdown.talentNorm != null) blendParts.push(n(breakdown.talentNorm));
  if (breakdown.rankingNorm != null) blendParts.push(n(breakdown.rankingNorm));
  const blendLine =
    breakdown.blended != null && blendParts.length
      ? blendParts.length === 1
        ? `blended = ${blendParts[0]}`
        : `blended = (${blendParts.join(" + ")}) / ${blendParts.length} = ${n(breakdown.blended)}`
      : null;

  const dctf = breakdown.dctfRank != null;
  const bonus = breakdown.bonus ?? 0;
  const bonusLine = dctf
    ? `bonus = 10 × (26 − ${breakdown.dctfRank}) / 25 = ${n(bonus)}`
    : `bonus = 0`;
  const result = breakdown.teamStrength ?? teamStrength;
  const blendedShown = breakdown.blended ?? result;
  const label = `How ${schoolName} team strength is calculated`;

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        className="-mr-1 text-zinc-500 hover:bg-white/10 hover:text-amber-300"
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <Info className="size-3.5" aria-hidden />
      </Button>
      {open ? (
      <Dialog open onOpenChange={setOpen}>
      <DialogContent
        className="max-h-[min(36rem,85vh)] overflow-y-auto bg-[#10141b] text-zinc-100 ring-white/15 sm:max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <DialogHeader>
          <DialogTitle className="pr-8 text-zinc-50">
            {schoolName} team strength
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Recruit talent mixed with national rankings when this school is on those
            boards. Missing boards are skipped, not counted as zero.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          {talentLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Recruit talent
              </h3>
              <p className="mt-1 text-zinc-300">
                Share of the board’s top talent score
                {breakdown.talentMaxName ? ` (${breakdown.talentMaxName})` : ""}.
              </p>
              <Formula>{talentLine}</Formula>
            </section>
          ) : null}
          {on3Line ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                On3 national
              </h3>
              <p className="mt-1 text-zinc-300">
                On3 rank #{breakdown.on3Rank}
                {breakdown.on3Rating != null ? ` · rating ${n(breakdown.on3Rating)}` : ""} on
                the 1,000-team board.
              </p>
              <Formula>{on3Line}</Formula>
            </section>
          ) : null}
          {mpLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                MaxPreps national
              </h3>
              <p className="mt-1 text-zinc-300">
                MaxPreps computer rank #{breakdown.maxprepsRank} of 100 (not the editorial
                Top 25).
              </p>
              <Formula>{mpLine}</Formula>
            </section>
          ) : null}
          {rankingLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Ranking average
              </h3>
              <p className="mt-1 text-zinc-300">
                Mean of whichever of On3 and MaxPreps exist for this school.
              </p>
              <Formula>{rankingLine}</Formula>
            </section>
          ) : null}
          {blendLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Blend
              </h3>
              <p className="mt-1 text-zinc-300">
                Mean of talent and the ranking average, using only the pieces this
                school has.
              </p>
              <Formula>{blendLine}</Formula>
            </section>
          ) : null}
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              DCTF 6A bonus
            </h3>
            <p className="mt-1 text-zinc-300">
              {dctf
                ? `Texas 6A Top 25 at #${breakdown.dctfRank}.`
                : "Not in the Dave Campbell’s Texas Football 6A Top 25."}
            </p>
            <Formula>{bonusLine}</Formula>
          </section>
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Team strength
            </h3>
            <p className="mt-1 text-zinc-300">Clamped to 0–100. This is the number on the page.</p>
            <Formula>{`team_strength = clamp(${n(blendedShown)} + ${n(bonus)}, 0, 100) = ${n(result)}`}</Formula>
          </section>
        </div>
      </DialogContent>
      </Dialog>
      ) : null}
    </>
  );
}
