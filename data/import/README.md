# Scout + Matchup import files

Canonical v1 is a frozen Scout board plus a Matchup MaxPreps week slate. Drop these files in `site-data/` (preferred) or `data/import/` (this directory). Then:

```bash
npx tsx scripts/import-site-data.ts
```

That rewrites `data/fridayradar.json`. It does **not** re-fetch 247Sports pagination.

Rebuild from frozen ingest already in `data/raw/`:

```bash
python3 scripts/compile-scout-matchup.py
npx tsx scripts/import-site-data.ts
```

## Files

### `schools.json`

Array of Scout school rows (or `{ "schools": [...] }`).

`id` is the FridayRadar slug (`School.id`). `Player.high_school_id` is that slug. Rankings **prefer** `talent_score` / `recruit_count` so the board matches Scout before every rating row is present.

Leave zip null for: American Heritage (Fort Lauderdale, FL), ALA Queen Creek AZ, Lexington Christian Academy KY, Notre Dame Sherman Oaks CA, San Antonio Roosevelt TX.

### `schools.summary.json`

Rollup the importer prints in `meta.sources`. Canonical v1: **1,554 schools / 2,986 players** (2,135 class 2027, 851 class 2028).

### `schedules.json`

MaxPreps **26-27** football schedules keyed by FridayRadar school id. Built by `python3 scripts/build-strength-and-schedules.py`. Deleted contests and Varsity Opponent rows are omitted. Each game has date, opponent, home/away/neutral, result, and `toughness_icon` from this team’s strength vs the opponent.

The importer copies this into `data/fridayradar.json` as `schedules`. SOS on each school is the mean of known opponents’ `team_strength` (talent share blended with On3 min–max and MaxPreps national computer rank; Texas 6A DCTF Top 25 bonus then clamp 0–100). It is never raw On3 `compositeScore`. Skip unmapped opponents. Missing SOS is an em dash, not zero.

### `games-top213.json` (v1 `/games`)

Matchup week **2026-08-26 through 2026-08-29**. This is the only games file the importer loads: **196 two-sided games** (`rank_by: two_sided_talent`). Do **not** load `games.json`.

Unknown / empty / Varsity Opponent names are dropped. St. Frances @ DeLand is not in this slice (DeLand is unmapped). Rank key is **√(home × away)**; combined talent is still on each row (Cornerstone Christian @ IMG 2418.49).

Venue: `venue {city,state,zip,name,source}`. Home games use the home school (`source: home_school`). Neutral sites use contest/site location only. Mater Dei @ Orem is Utah / 84097, not California. Missing venue state is unmatched for the state filter.

`Game.id` = `contest_id`. If a side is unmapped (`mapped: false`, no `site_id`), the importer keeps the game and inserts a placeholder school.

### Players from ingest 2027/2028

Scout already scored the frozen 2027/2028 ingest (247Sports composite + On3/Rivals + ESPN). Nested `recruits` on `schools.json` are those rows. Raw copies remain under `data/raw/{espn,247,on3}/{year}.json`. **Do not re-run 247 Load More** (it 406s). The importer never invents recruit names.

## Official talent

Average available stars across `247sports_composite`, `on3_rivals` (else `on3_industry`, never both), ESPN. Interpolate onto 5=98, 4=85, 3=70, 2=55, 1=40, listed=25. School talent = sum of 2027+ points.

Check: IMG `fl-bradenton-img-academy`, MaxPreps `7bdc339f-7cbf-4728-b0c8-ed898929cf68`, zip 34210, talent 2263.49, 28 recruits. Buford zip 30518, MaxPreps `6d00b044-607e-4dee-aa9b-e1fc2c6a87bc`.
