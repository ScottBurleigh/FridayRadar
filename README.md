# FridayRadar

FridayRadar ranks **U.S. high school football programs** by the recruiting talent on their **2027-and-later** rosters. It is not a college team ranking. A player belongs to the high school they attend.

## Run locally

```bash
npm install
npx tsx scripts/import-site-data.ts   # compiles site-data/ or data/import/ → data/fridayradar.json
# or: npm run compile:scout            # rebuilds the frozen board + top-213 week slice, then imports
npm run dev                           # http://127.0.0.1:43123
```

Requires Node 22+ and Python 3. The compiled dataset ships in `data/fridayradar.json`, so the app comes up without a live scrape.

## Product pages

- **Rankings (home)** — programs sorted by talent score (default) or recruit count. Filters: US state, zip code (≈25-mile haversine). Click a row for the school drill-down.
- **School drill-down** — 2027 / 2028 / 2029+ recruits with 247Sports, On3/Rivals, and ESPN ratings (stars, numeric rating/composite, national rank, profile link when known).
- **Games of the week** — Matchup MaxPreps slate for **2026-08-26 through 2026-08-29**, ranked by combined home + away Scout talent. Unmapped opponents count as 0; one-sided games stay on the board. Same state and zip filters.

## Ranking math

Eligible: `class_year >= 2027`. Never 2026 or earlier.

**Dedupe** a player on `class_year + normalized name + position family`. High-school name/state is a tie-break only — the three source HS strings do not have to match on the same day.

**High school vs college commit.** On 247 and ESPN ranking tables, Team/SCHOOL is the **college commit**. FridayRadar never uses that as the high school.

- 247Sports HS token: `Buford (Buford, GA)` plus the player URL `/player/{slug}-{id}/high-school-{hsId}/`.
- ESPN HS object: `highSchool.properName` + address (not `schools[].team`).
- On3: HS token + slug state (`buford-ga`). Hometown city can lag after transfers — Brewster is Buford, GA, not Cedar Hill, TX.

**Player composite stars** = average of available stars from `247sports_composite`, `on3_rivals` (else `on3_industry`, never both), and ESPN.

**Player points** (interpolate non-integers; 4.5 is halfway between 85 and 98):

| Composite stars | Points |
| --- | --- |
| 5 | 98 |
| 4 | 85 |
| 3 | 70 |
| 2 | 55 |
| 1 | 40 |
| listed / unranked | 25 |

**School talent score** = Scout precomputed sum of 2027+ player points (`School.talentScore`). Rankings prefer that field so the board matches Scout before every rating row is imported. If it is missing, FridayRadar sums imported 2027+ player points.

**Star badge counts** on the rankings table = composite stars rounded to the nearest star.

ESPN 300 star images are mapped from grade: 90+=5, 80–89=4, then 70–79=3, 60–69=2, 50–59=1.

## Refresh data

Canonical v1 is **Scout + Matchup on disk**, not a live 247 scrape (Load More 406s). Drop the Builder dump in `site-data/` (or `data/import/`) and compile:

```bash
npm run import:site
```

Or rebuild from the frozen ingest already in this repo (never re-pages 247):

```bash
npm run compile:scout
```

v1 `/games` reads **`games-top213.json`** (top 213 by combined Scout talent for 2026-08-26..29). Do not load a full 837-game `games.json` as the site slate; the importer slices anything longer down to 213.

See `data/import/README.md` for `schools.json`, `schools.summary.json`, `games-top213.json`, and how frozen 2027/2028 ingest players nest on school rows.

Do **not** re-run `npm run ingest:247`. Frozen 2027/2028 composite copies live under `data/raw/247/`. Canonical v1: **1,554 schools / 2,986 players**. `/games` is the top **213** Matchup-week games by combined talent.

School ids are slugs (`fl-bradenton-img-academy`). Game ids are MaxPreps `contestId`.

## Source URLs

- 247Sports Composite: https://247sports.com/season/2027-football/compositerecruitrankings/?InstitutionGroup=Highschool — HTML ranking pages and CSS `icon-starsolid yellow` (not the gated JSON API). Page=1 often 406; Load More is `Page=2+` with `X-Requested-With: XMLHttpRequest` and gzip. The public 2027 HS composite is ~2093 named players with stars.
- On3/Rivals own list: https://www.on3.com/rivals/rankings/player/football/2027/
- ESPN 2027 API: https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/recruiting/2027/athletes?limit=300
- ESPN class chips: `/_/view/rn300/class/2027` and `2028` (no 2029 football 300 yet)
- MaxPreps school JSON: `GET https://www.maxpreps.com/_next/data/{buildId}/<state>/<city>/<name-mascot>.json` — **read `buildId` from the live site**, never hardcode a stale one. Season `26-27` is live. `homeAwayType` 0 = home, 1 = away, 2 = neutral. Drop `isDeleted` contests, “Varsity Opponent” placeholders, and any game missing a real opponent school name. IMG Academy is Bradenton, FL.

If a source blocks (247Sports Load More has returned HTTP 406 from this environment; On3 industry list is often Cloudflare-walled), ingest keeps any live rows it already has and labels the source `PARTIAL` or `BLOCKED` in the UI. It does not invent recruit names.

## Schema

Stored in `data/fridayradar.json`:

- **School** — `id` (slug, e.g. `fl-bradenton-img-academy`), `name`, `name_normalized`, `aliases`, `mascot`, `city`, `state`, `zip`, `address`, `lat`, `lng`, `type`, `maxpreps {schoolId, canonicalUrl, formattedName}`, `ids_247.high_school_id`, optional Scout `talentScore` / `recruitCount`, `mapped`
- **Player** — `id`, `full_name`, `class_year`, `position`, `height`, `weight`, `hometown_city`, `hometown_state`, `high_school_id` (school slug), `college_commit`, `source_ids {247sports_player_id, on3_rivals_id, espn_id}`
- **Rating** — `player_id`, `source` (`247sports` | `247sports_composite` | `on3_rivals` | `on3_industry` | `espn`), `class_year`, `as_of`, `national_rank`, `position_rank`, `state_rank`, `stars`, `rating`, `position`, `high_school_name_raw`, `profile_url`
- **Game** — `id` (MaxPreps contestId), `season`, `kickoff`, `home_school_id`, `away_school_id` (slugs; unmapped sides use a placeholder school), `home_score`, `away_score`, `is_gow`, `game_url`

Zip filter: input zip → centroid in `data/zip-centroids.json` → haversine ≤ 25 miles against MaxPreps coords, or the school's own zip centroid when MaxPreps did not match.
