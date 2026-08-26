import { useId } from "react";
import { Info, XIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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
  const reactId = useId();
  if (teamStrength == null || !breakdown) return null;

  const panelId = `strength-formula-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
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
      <button
        type="button"
        className={cn(
          buttonVariants({ variant: "ghost", size: "icon-xs" }),
          "-mr-1 text-zinc-400 hover:bg-white/10 hover:text-amber-300",
        )}
        aria-label={label}
        popoverTarget={panelId}
        popoverTargetAction="toggle"
      >
        <Info className="size-3.5" aria-hidden />
      </button>
      <div
        id={panelId}
        popover="auto"
        role="dialog"
        aria-label={`${schoolName} team strength`}
        className="relative w-[min(32rem,calc(100%-2rem))] max-h-[min(36rem,85vh)] overflow-y-auto rounded-xl bg-[#121c2e] p-4 text-zinc-100 shadow-xl ring-1 ring-amber-400/25 [&::backdrop]:bg-[#0a1220]/75"
        style={{
          position: "fixed",
          inset: "unset",
          top: "50%",
          left: "50%",
          margin: 0,
          transform: "translate(-50%, -50%)",
        }}
      >
        <button
          type="button"
          className={cn(
            buttonVariants({ variant: "ghost", size: "icon-sm" }),
            "absolute top-2 right-2 text-zinc-400 hover:text-zinc-50",
          )}
          aria-label="Close"
          popoverTarget={panelId}
          popoverTargetAction="hide"
        >
          <XIcon className="size-4" />
        </button>
        <h2 className="pr-8 text-base font-medium text-zinc-50">{schoolName} team strength</h2>
        <p className="mt-2 text-sm text-zinc-400">
          Recruit talent mixed with national rankings when this school is on those boards.
          Missing boards are skipped, not counted as zero.
        </p>
        <div className="mt-4 space-y-4 text-sm">
          {talentLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
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
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
                On3 national
              </h3>
              <p className="mt-1 text-zinc-300">
                On3 rank #{breakdown.on3Rank}
                {breakdown.on3Rating != null ? ` · rating ${n(breakdown.on3Rating)}` : ""} on the
                1,000-team board.
              </p>
              <Formula>{on3Line}</Formula>
            </section>
          ) : null}
          {mpLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
                MaxPreps national
              </h3>
              <p className="mt-1 text-zinc-300">
                MaxPreps computer rank #{breakdown.maxprepsRank} of 100 (not the editorial Top
                25).
              </p>
              <Formula>{mpLine}</Formula>
            </section>
          ) : null}
          {rankingLine ? (
            <section>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
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
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">Blend</h3>
              <p className="mt-1 text-zinc-300">
                Mean of talent and the ranking average, using only the pieces this school has.
              </p>
              <Formula>{blendLine}</Formula>
            </section>
          ) : null}
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
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
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
              Team strength
            </h3>
            <p className="mt-1 text-zinc-300">Clamped to 0–100. This is the number on the page.</p>
            <Formula>{`team_strength = clamp(${n(blendedShown)} + ${n(bonus)}, 0, 100) = ${n(result)}`}</Formula>
          </section>
        </div>
      </div>
    </>
  );
}
