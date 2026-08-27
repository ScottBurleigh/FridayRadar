import type { ToughnessIcon } from "./types";

type KnownIcon = Exclude<ToughnessIcon, "unknown">;

/** Compact chip label, shown next to the icon. */
export const TOUGHNESS_SHORT: Record<KnownIcon, string> = {
  much_easier: "favorite",
  easier: "favored",
  even: "toss-up",
  harder: "underdog",
  much_harder: "big underdog",
};

/** Title-case label for headings, aria-labels, and legend text. */
export const TOUGHNESS_LABEL: Record<KnownIcon, string> = {
  much_easier: "Heavy favorite",
  easier: "Favored",
  even: "Toss-up",
  harder: "Underdog",
  much_harder: "Heavy underdog",
};

/** Full sentence for tooltips — from this team's point of view. */
export const TOUGHNESS_DESCRIPTION: Record<KnownIcon, string> = {
  much_easier: "Heavy favorite — this team's talent clearly outweighs the opponent's",
  easier: "Favored — this team is the stronger side",
  even: "Toss-up — team strengths are close enough to call it even",
  harder: "Underdog — the opponent is the stronger side",
  much_harder: "Heavy underdog — the opponent's talent clearly outweighs this team's",
};
