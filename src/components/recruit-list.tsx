import { ProfileLinks } from "@/components/profile-links";
import { StarBadge } from "@/components/star-badge";
import { sourceLabel } from "@/lib/format";
import { profileLinksForPlayer } from "@/lib/profile-links";
import { ratingsBySource } from "@/lib/ranking";
import type { RatedPlayer, Rating } from "@/lib/types";

const SOURCE_ORDER = [
  "247sports_composite",
  "247sports",
  "on3_rivals",
  "on3_industry",
  "espn",
] as const;

export function RecruitList({
  players,
  ratings,
}: {
  players: RatedPlayer[];
  ratings: Rating[];
}) {
  if (!players.length) {
    return (
      <div className="rounded-xl border border-dashed border-amber-400/25 bg-[#121c2e] px-6 py-12 text-center text-zinc-400">
        No 2027-or-later recruits are on file for this school.
      </div>
    );
  }

  const byYear = new Map<number, RatedPlayer[]>();
  for (const p of players) {
    const list = byYear.get(p.class_year) ?? [];
    list.push(p);
    byYear.set(p.class_year, list);
  }
  const years = [...byYear.keys()].sort();

  return (
    <div className="space-y-8">
      {years.map((year) => (
        <section key={year}>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-zinc-300">
            Class of {year}
          </h2>
          <ul className="space-y-3">
            {(byYear.get(year) ?? []).map((p) => {
              const bySrc = p.ratingsBySource ?? ratingsBySource(p.id, ratings);
              return (
                <li
                  key={p.id}
                  className="rounded-xl border border-amber-400/20 bg-[#121c2e] p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-base font-medium text-zinc-50">{p.full_name}</p>
                      <p className="mt-0.5 text-sm text-zinc-400">
                        {p.position ?? "ATH"}
                        {p.height ? ` · ${p.height}` : ""}
                        {p.weight ? ` / ${p.weight}` : ""}
                        {p.hometown_city
                          ? ` · ${p.hometown_city}${p.hometown_state ? `, ${p.hometown_state}` : ""}`
                          : ""}
                        {p.college_commit ? ` · commit: ${p.college_commit}` : ""}
                      </p>
                    </div>
                    <div className="text-right">
                      <StarBadge stars={p.badgeStars} />
                      <p className="mt-1 font-mono text-xs text-zinc-400">
                        {p.points.toFixed(1)} pts
                        {p.compositeStars != null
                          ? ` · ${p.compositeStars.toFixed(2)}★ avg`
                          : ""}
                      </p>
                    </div>
                  </div>
                  <ProfileLinks
                    links={profileLinksForPlayer(p, bySrc)}
                    className="mt-2"
                  />
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {SOURCE_ORDER.map((src) => {
                      const r = bySrc[src];
                      if (!r) {
                        return (
                          <div
                            key={src}
                            className="rounded-lg border border-amber-400/15 px-3 py-2 text-xs text-zinc-400"
                          >
                            {sourceLabel(src)}
                            <span className="ml-2">—</span>
                          </div>
                        );
                      }
                      return (
                        <div
                          key={src}
                          className="rounded-lg border border-amber-400/20 bg-[#0d1628] px-3 py-2 text-xs"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-zinc-400">{sourceLabel(src)}</span>
                            <StarBadge stars={r.stars ?? 0} size="sm" />
                          </div>
                          <p className="mt-1 font-mono text-zinc-300">
                            {r.rating != null ? r.rating.toFixed(r.rating < 2 ? 4 : 1) : "—"}
                            {r.national_rank != null ? ` · Nat #${r.national_rank}` : ""}
                          </p>
                          {r.profile_url ? (
                            <a
                              href={r.profile_url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-1 inline-block text-amber-300/90 hover:underline"
                            >
                              Profile
                            </a>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
