"use client";

import { useId } from "react";
import { XIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatTalent } from "@/lib/format";
import {
  TALENT_LETTER_CUTOFFS,
  boardTalentMax,
  talentLetterGrade,
  talentNorm,
  type TalentLetter,
} from "@/lib/talent-grade";
import type { StrengthBreakdown } from "@/lib/types";

function n(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  });
}

export function TalentGrade({
  schoolName,
  talentScore,
  breakdown,
  size = "table",
}: {
  schoolName: string;
  talentScore: number;
  breakdown?: StrengthBreakdown | null;
  size?: "table" | "stat";
}) {
  const reactId = useId();
  const talentMax = boardTalentMax({ strengthBreakdown: breakdown });
  const grade: TalentLetter = talentMax != null ? talentLetterGrade(talentScore, talentMax) : "F";
  const norm = talentMax != null ? talentNorm(talentScore, talentMax) : null;
  const total = formatTalent(talentScore);
  const panelId = `talent-grade-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const label = `${schoolName} talent grade ${grade}, total ${total}`;
  const letterClass =
    size === "stat"
      ? "font-mono text-xl font-semibold text-amber-200"
      : "font-mono font-semibold text-amber-200";

  return (
    <>
      <button
        type="button"
        className={cn(
          letterClass,
          "cursor-pointer rounded-md px-1 text-right hover:bg-white/10 hover:text-amber-100 focus-visible:ring-2 focus-visible:ring-amber-400/60 focus-visible:outline-none",
        )}
        title={`Talent ${total}`}
        aria-label={label}
        popoverTarget={panelId}
        popoverTargetAction="toggle"
      >
        {grade}
      </button>
      <div
        id={panelId}
        popover="auto"
        role="dialog"
        aria-label={`${schoolName} talent`}
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
        <h2 className="pr-8 text-base font-medium text-zinc-50">{schoolName} talent</h2>
        <p className="mt-2 font-mono text-2xl font-semibold text-amber-200">
          {grade}
          <span className="ml-3 text-lg font-normal text-zinc-100">{total}</span>
        </p>
        <p className="mt-2 text-sm text-zinc-400">
          Letter grade from stretched talent_norm on this 1,554-school board. The talent
          total itself is unchanged.
        </p>
        <div className="mt-4 space-y-4 text-sm">
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
              This school
            </h3>
            <p className="mt-1 font-mono text-[13px] leading-relaxed text-amber-100/90">
              talent = {total}
            </p>
            <p className="font-mono text-[13px] leading-relaxed text-amber-100/90">
              {talentMax != null && norm != null
                ? `talent_norm = 100 × ${n(talentScore)} / ${n(talentMax)} = ${n(norm)}`
                : "talent_norm = —"}
            </p>
          </section>
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">
              Cutoffs
            </h3>
            <p className="mt-1 text-zinc-300">
              Inclusive lower bound on talent_norm (IMG = 100). A 90/80/70 curve on that
              share would mark almost the whole board F.
            </p>
            <ul className="mt-2 space-y-0.5 font-mono text-[13px] text-amber-100/90">
              {TALENT_LETTER_CUTOFFS.map((row, i) => {
                const next = i === 0 ? null : TALENT_LETTER_CUTOFFS[i - 1];
                const range = next ? `≥ ${n(row.minNorm)} and < ${n(next.minNorm)}` : `≥ ${n(row.minNorm)}`;
                return (
                  <li key={row.grade}>
                    <span className="inline-block w-8 text-zinc-50">{row.grade}</span>
                    {range}
                  </li>
                );
              })}
              <li>
                <span className="inline-block w-8 text-zinc-50">F</span>
                {"< 3"}
              </li>
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
