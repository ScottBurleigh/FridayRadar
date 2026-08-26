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

- **Rankings (home)** — programs sorted by **team strength** (default), talent, or recruit count. The Talent cell is a letter grade; the numeric talent total and the grade cutoffs are in the hover/popover. Star columns are labeled 5-star / 4-star / 3-star. The table also shows strength of schedule (mean of this season’s opponents’ team strength, with a tough/average/light label). Missing SOS is an em dash, not zero. Filters: US state, zip code (≈25-mile haversine). The chevron next to a school name expands **every** 2027+ recruit on that roster (name, position, stars, and spaced 247 · On3 · ESPN · Hudl chips when those URLs exist). The school name still opens `/schools/[id]`.
- **School drill-down** — 2027 / 2028 / 2029+ recruits with 247Sports, On3/Rivals, and ESPN ratings (stars, numeric rating/composite, national rank). A profile-links row under each recruit shows **247 · On3 · ESPN · Hudl** only when that URL is on file — missing Hudl is omitted, not a dead chip. Talent is the same letter grade as the rankings table (numeric total in the popover). Team strength, On3 national rank (only when joined), MaxPreps national computer rank when joined (e.g. MaxPreps #4), DCTF #N for Texas 6A Top 25, and strength of schedule sit in the header. Verified Hudl team pages (fan.hudl.com boys-varsity-football) sit next to the MaxPreps schedule link when known. Under recruits, the MaxPreps 26-27 football schedule is a table (date, opponent, site, result, toughness icon/label) when `schedules.json` has a row for that school — omitted entirely if not. MaxPreps schedule link when `schoolId` and a stored `scheduleUrl` exist (from the school row or the schedule dump). Unknown toughness is skipped, not shown as a fake icon.
- **Games of the week** — Matchup MaxPreps slate for **2026-08-26 through 2026-08-29**, ranked by **geometric mean** of home and away Scout talent (`√(home × away)`). Combined talent is still shown on each row and is the tie-break. Games missing talent on either side (unmapped / 0) are omitted. State and zip filters use the **game venue** (home school for home games; contest site for neutrals), not either roster’s home state.

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

**School talent score** = Scout precomputed sum of 2027+ player points (`School.talentScore`). Rankings prefer that field so the board matches Scout before every rating row is imported. If it is missing, FridayRadar sums imported 2027+ player points. Talent remains its own number under the hood and its own sortable column; the cell shows a letter grade from stretched `talent_norm` (`100 × talent / board-max`, IMG = 100): A+ ≥90, A ≥45, A- ≥35, B+ ≥25, B ≥18, B- ≥13, C+ ≥9, C ≥6, C- ≥3.75, D ≥3, else F. A 90/80/70 curve on that share would mark almost the whole board F. Default rankings sort is team strength, then talent.

**Team strength** does not invent ranks. `talent_norm` is `100 × talent / board-max` (IMG = 100 on talent only). `on3_norm` is On3 `compositeScore` min–max on the 1000-team board (board min → 0, board max → 100). `maxpreps_norm` is `100 × (N + 1 − rank) / N` on the 100-team MaxPreps **national computer** board (rank 1 = 100, rank 100 = 1). Unranked boards are omitted, never 0. `ranking_norm` is the mean of whichever of On3 and MaxPreps exist. `team_strength` is the mean of whichever of talent_norm and ranking_norm exist — so talent only is talent_norm; talent + one ranking is 50/50; talent + On3 + MaxPreps is 50% talent + 25% On3 + 25% MaxPreps. IMG is not forced to 100 when MaxPreps has them at #4. Texas 6A DCTF Top 25 then adds `10 × (26 − rank) / 25` (#1 +10.00, #25 +0.40) and the result is clamped 0–100. Unranked Texas get 0 extra, not a penalty. SOS is the mean of this-season MaxPreps opponents’ team_strength (played + remaining). Skip deleted contests, Varsity Opponent, IMG Blue-White, and any opponent with no team_strength. Tough/average/light labels are the top/middle/bottom quartile of SOS among schools with at least two known opponents. Game toughness icons compare this team’s strength to the opponent’s; unmapped opponents are `unknown` (no icon), not cupcakes.

**Star badge counts** on the rankings table = composite stars rounded to the nearest star.

**Games of the week rank** = geometric mean `√(home talent × away talent)`. Combined talent (home + away) is shown on each row and used only as a tie-break. Games with missing talent on either side are omitted so a superteam vs a cupcake cannot sit above two loaded programs. State/zip filters use the venue (home campus for home games; contest site for neutrals).

ESPN 300 star images are mapped from grade: 90+=5, 80–89=4, then 70–79=3, 60–69=2, 50–59=1.

## Refresh data

Canonical v1 is **Scout + Matchup on disk**, not a live 247 scrape (Load More 406s). Drop the Builder dump in `site-data/` (or `data/import/`) and compile:

```bash
npm run import:site
python3 scripts/fill-missing-zips.py   # MaxPreps / Census / public geocode for missing zips (never invents)
npm run rebuild:games                  # refresh venue = contest site or HOME school
npm run build:strength                 # On3 national board + MaxPreps 26-27 schedules → strength / SOS / toughness
```

Or rebuild from the frozen ingest already in this repo (never re-pages 247):

```bash
npm run compile:scout
```

v1 `/games` reads **`site-data/games-top213.json` only** — two-sided Matchup games for 2026-08-26..29 (`rank_by: two_sided_talent`). Do **not** load `games.json`.

See `data/import/README.md` for `schools.json`, `schools.summary.json`, `games-top213.json`, and how frozen 2027/2028 ingest players nest on school rows.

Do **not** re-run `npm run ingest:247`. Frozen 2027/2028 composite copies live under `data/raw/247/`. Canonical v1: **1,554 schools / 2,986 players**. `/games` is **`games-top213.json`** (**196** two-sided games, ranked by geometric mean; all have `venue.zip`).

Verified Hudl athlete profiles live in `site-data/hudl.json` (343 payload rows / 333 unique recruits; unmatched skipped). Davion Jones (Hough) is intentionally unlinked — athlete 19494412 is West Charlotte. Re-apply with `python3 scripts/apply-hudl.py` then `npm run import:site`. Do not invent Hudl URLs.

School ids are slugs (`fl-bradenton-img-academy`). Game ids are MaxPreps `contestId`.

## Source URLs

- 247Sports Composite: https://247sports.com/season/2027-football/compositerecruitrankings/?InstitutionGroup=Highschool — HTML ranking pages and CSS `icon-starsolid yellow` (not the gated JSON API). Page=1 often 406; Load More is `Page=2+` with `X-Requested-With: XMLHttpRequest` and gzip. The public 2027 HS composite is ~2093 named players with stars.
- On3/Rivals own list: https://www.on3.com/rivals/rankings/player/football/2027/
- ESPN 2027 API: https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/recruiting/2027/athletes?limit=300
- On3 national HS football: https://www.on3.com/high-school/rankings/football/national/ — captured via `GET https://api.on3.com/rdb/v1/organization-composite-rankings?sportKey=1&orgType=HighSchool&year=2026&page={1-40}` (25/page, 1,000 teams). Joined to PrepTalent by normalized name + city/state. Ranks are never invented for unranked schools.
- MaxPreps school JSON: `GET https://www.maxpreps.com/_next/data/{buildId}/<state>/<city>/<name-mascot>.json` — **read `buildId` from the live site**, never hardcode a stale one. Season `26-27` is live. `homeAwayType` 0 = home, 1 = away, 2 = neutral. Drop `isDeleted` contests, “Varsity Opponent” placeholders, and any game missing a real opponent school name. IMG Academy is Bradenton, FL.

If a source blocks (247Sports Load More has returned HTTP 406 from this environment; On3 industry list is often Cloudflare-walled), ingest keeps any live rows it already has and labels the source `PARTIAL` or `BLOCKED` in the UI. It does not invent recruit names.

## Schema

Stored in `data/fridayradar.json`:

- **School** — `id` (slug, e.g. `fl-bradenton-img-academy`), `name`, `name_normalized`, `aliases`, `mascot`, `city`, `state`, `zip`, `address`, `lat`, `lng`, `type`, `maxpreps {schoolId, canonicalUrl, formattedName, scheduleUrl}`, `ids_247.high_school_id`, optional Scout `talentScore` / `recruitCount`, `teamStrength`, `hudlTeamUrl` (fan.hudl.com boys-varsity-football when verified), `on3 {rank, rating, orgKey}`, `sos` / `sosLabel`, `mapped`
- **SchoolSchedule** — keyed by school id in `schedules`; `season` (`26-27`), games with date, opponent, home/away/neutral, result, `toughnessIcon`
- **Player** — `id`, `full_name`, `class_year`, `position`, `height`, `weight`, `hometown_city`, `hometown_state`, `high_school_id` (school slug), `college_commit`, `source_ids {247sports_player_id, on3_rivals_id, espn_id, hudl}`, optional `profile_urls {247sports_composite, on3_rivals, espn, hudl}`. Hudl athlete URLs are only the verified batch in `site-data/hudl.json` (never invented).
- **Rating** — `player_id`, `source` (`247sports` | `247sports_composite` | `on3_rivals` | `on3_industry` | `espn`), `class_year`, `as_of`, `national_rank`, `position_rank`, `state_rank`, `stars`, `rating`, `position`, `high_school_name_raw`, `profile_url`
- **Game** — `id` (MaxPreps contestId), `season`, `kickoff`, `home_school_id`, `away_school_id`, `home_score`, `away_score`, `is_gow`, `game_url`, venue `city` / `state` / `zip` / `lat` / `lng` plus `venue {city,state,zip,name,source}`, `two_sided_talent`, `home_away_type` (0 home, 2 neutral)

**Games rank key:** geometric mean `√(home talent × away talent)`. Combined (home + away) is the displayed number and the tie-break. Cornerstone Christian @ IMG stays on the board with combined 2418.49 but ranks below two loaded programs (Mater Dei @ Orem, Sierra Canyon @ Chaminade-Madonna).

Zip filter: input zip → centroid in `data/zip-centroids.json` → haversine ≤ 25 miles. Rankings measure distance to the **school**. `/games` measures distance to the **venue** only. Missing venue state/coords leaves the game unmatched for that filter — it is not treated as both teams’ states.
