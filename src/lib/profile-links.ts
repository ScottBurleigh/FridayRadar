import { ratingsBySource } from "@/lib/ranking";
import type { Player, ProfileLink } from "@/lib/types";

/** Labeled chips. Hudl only when that recruit was in the verified payload. */
export function profileLinksForPlayer(
  player: Player,
  bySrc: ReturnType<typeof ratingsBySource>,
): ProfileLink[] {
  const stored = player.profile_urls ?? {};
  const links: ProfileLink[] = [];
  const u247 =
    stored["247sports_composite"] ||
    bySrc["247sports_composite"]?.profile_url ||
    bySrc["247sports"]?.profile_url;
  if (u247) links.push({ label: "247", href: u247 });
  const on3 =
    stored.on3_rivals ||
    bySrc.on3_rivals?.profile_url ||
    bySrc.on3_industry?.profile_url;
  if (on3) links.push({ label: "On3", href: on3 });
  const espn = stored.espn || bySrc.espn?.profile_url;
  if (espn) links.push({ label: "ESPN", href: espn });
  const hudl = stored.hudl;
  if (hudl) links.push({ label: "Hudl", href: hudl });
  return links;
}
