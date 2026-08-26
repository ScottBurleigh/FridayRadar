/**
 * Letter grades for the Talent column. Does not change talent_score.
 *
 * A straight 90/80/70 scale on talent_norm (IMG = 100) collapses the board:
 * St. Frances is ~60 and the median school is a single 3-star (~3). These
 * stretched talent_norm bands keep IMG at A+ and spread national programs
 * across A…B while the 4-star / 3-star / 2-star singleton clusters land on
 * C- / D / F.
 *
 * talent_norm = 100 × talent_score / board max (same max as team strength).
 */
export const TALENT_LETTERS = [
  "A+",
  "A",
  "A-",
  "B+",
  "B",
  "B-",
  "C+",
  "C",
  "C-",
  "D",
  "F",
] as const;

export type TalentLetter = (typeof TALENT_LETTERS)[number];

/** Inclusive lower bound on talent_norm. First match wins (A+ … D); else F. */
export const TALENT_LETTER_CUTOFFS: readonly { grade: Exclude<TalentLetter, "F">; minNorm: number }[] =
  [
    { grade: "A+", minNorm: 90 },
    { grade: "A", minNorm: 45 },
    { grade: "A-", minNorm: 35 },
    { grade: "B+", minNorm: 25 },
    { grade: "B", minNorm: 18 },
    { grade: "B-", minNorm: 13 },
    { grade: "C+", minNorm: 9 },
    { grade: "C", minNorm: 6 },
    { grade: "C-", minNorm: 3.75 },
    { grade: "D", minNorm: 3 },
  ];

export function talentNorm(talentScore: number, talentMax: number): number | null {
  if (!(talentMax > 0) || Number.isNaN(talentScore)) return null;
  return (100 * talentScore) / talentMax;
}

export function talentLetterGrade(talentScore: number, talentMax: number): TalentLetter {
  const norm = talentNorm(talentScore, talentMax);
  if (norm == null) return "F";
  for (const row of TALENT_LETTER_CUTOFFS) {
    if (norm >= row.minNorm) return row.grade;
  }
  return "F";
}

export function boardTalentMax(
  school: { strengthBreakdown?: { talentMax?: number | null } | null } | null | undefined,
): number | null {
  const max = school?.strengthBreakdown?.talentMax;
  return max != null && max > 0 ? max : null;
}
