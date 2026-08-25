# FridayRadar

FridayRadar ranks **U.S. high school football programs** by the recruiting talent on their **2027-and-later** rosters. It is not a college team ranking. A player belongs to the high school they attend.

## Run locally

```bash
npm install
npm run ingest    # optional if data/fridayradar.json is already present
npm run dev       # http://127.0.0.1:43123
```

Requires Node 22+ and Python 3. The compiled dataset ships in `data/fridayradar.json`, so the app comes up without a live scrape.

## Product pages

- **Rankings (home)** — programs sorted by talent score (default) or recruit count. Filters: US state, zip code (≈25-mile haversine). Click a row for the school drill-down.
- **School drill-down** — 2027 / 2028 / 2029+ recruits with 247Sports, On3/Rivals, and ESPN ratings (stars, numeric rating/composite, national rank, profile link when known).
- **Games of the week** — this week's (or the next upcoming week's) MaxPreps games ranked by combined home + away talent. Same state and zip filters. Offseason shows an honest empty state.

## Ranking math

Eligible: `class_year >= 2027`. Never 2026 or earlier.

**Dedupe** a player on `class_year + normalized name + position family`. High-school name/state is a tie-break only — the three source HS strings do not have to match on the same day.

**High school vs college commit.** On 247 and ESPN ranking tables, Team/SCHOOL is the **college commit**. FridayRadar never uses that as the high school.

- 247Sports HS token: `Buford (Buford, GA)` plus the player URL `/player/{slug}-{id}/high-school-{hsId}/`.
- ESPN HS object: `highSchool.properName` + address (not `schools[].team`).
- On3: HS token + slug state (`buford-ga`). Hometown city can lag after transfers — Brewster is Buford, GA, not Cedar Hill, TX.

**Player composite stars** = average of available source star ratings.

**Player points** (interpolate non-integers; 4.5 is halfway between 85 and 98):

| Composite stars | Points |
| --- | --- |
| 5 | 98 |
| 4 | 85 |
| 3 | 70 |
| 2 | 55 |
| 1 | 40 |
| listed / unranked | 25 |

**School talent score** = sum of player points on the 2027+ roster.

**Star badge counts** on the rankings table = composite stars rounded to the nearest star.

ESPN 300 star images are mapped from grade: 90+=5, 80–89=4, then 70–79=3, 60–69=2, 50–59=1.

## Refresh data

```bash
npm run ingest:espn      # ESPN recruiting API, classes 2027–2029
npm run ingest:247       # 247Sports Composite HTML (Load More pages)
npm run ingest:on3       # On3/Rivals OWN SSR list
npm run ingest:maxpreps  # MaxPreps school-home coords + football wall schedules
# or everything:
npm run ingest
```

`scripts/ingest.py` merges raw files, matches MaxPreps, writes `data/fridayradar.json` and `data/zip-centroids.json`.

## Source URLs

- 247Sports Composite: https://247sports.com/season/2027-football/compositerecruitrankings/?InstitutionGroup=Highschool
- On3/Rivals own list: https://www.on3.com/rivals/rankings/player/football/2027/
- ESPN 2027 API: https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/recruiting/2027/athletes?limit=300
- ESPN class chips: `/_/view/rn300/class/2027` and `2028` (no 2029 football 300 yet)
- MaxPreps school JSON: `GET https://www.maxpreps.com/_next/data/{buildId}/<state>/<city>/<name-mascot>.json` — **read `buildId` from the live site**, never hardcode a stale one. Season `26-27` is live. `homeAwayType` 0 = home, 1 = away, 2 = neutral. Skip `isDeleted` rows and “Varsity Opponent” placeholders. IMG Academy is Bradenton, FL.

If a source blocks (247Sports Load More has returned HTTP 406 from this environment; On3 industry list is often Cloudflare-walled), ingest keeps any live rows it already has and labels the source `PARTIAL` or `BLOCKED` in the UI. It does not invent recruit names.

## Schema

Stored in `data/fridayradar.json`:

- **School** — `id` (MaxPreps `schoolId` GUID when matched), `name`, `name_normalized`, `aliases`, `mascot`, `city`, `state`, `zip`, `address`, `lat`, `lng`, `type`, `maxpreps {schoolId, canonicalUrl, formattedName}`, `ids_247.high_school_id`
- **Player** — `id`, `full_name`, `class_year`, `position`, `height`, `weight`, `hometown_city`, `hometown_state`, `high_school_id`, `college_commit`, `source_ids {247sports_player_id, on3_rivals_id, espn_id}`
- **Rating** — `player_id`, `source` (`247sports` | `247sports_composite` | `on3_rivals` | `on3_industry` | `espn`), `class_year`, `as_of`, `national_rank`, `position_rank`, `state_rank`, `stars`, `rating`, `position`, `high_school_name_raw`, `profile_url`
- **Game** — `id` (contestId), `season`, `kickoff`, `home_school_id`, `away_school_id`, `home_score`, `away_score`, `is_gow`, `game_url`

Zip filter: input zip → centroid in `data/zip-centroids.json` → haversine ≤ 25 miles against MaxPreps coords, or the school's own zip centroid when MaxPreps did not match.
