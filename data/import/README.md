# Scout + Matchup import files

Canonical v1 is a frozen Scout board plus a Matchup MaxPreps week slate. Drop these files in `site-data/` (preferred) or `data/import/` (this seed lives here until the full dump arrives). Then:

```bash
npx tsx scripts/import-site-data.ts
```

That rewrites `data/fridayradar.json`. It does **not** re-fetch 247Sports pagination.

## Four files

### `schools.json`

Array of Scout school rows (or `{ "schools": [...] }`).

```json
{
  "id": "fl-bradenton-img-academy",
  "name": "IMG Academy",
  "city": "Bradenton",
  "state": "FL",
  "zip": "34210",
  "zip5": "34210",
  "recruit_count": 28,
  "talent_score": 2263.49,
  "class_counts": { "2027": 20, "2028": 8 },
  "star_buckets": { "stars5": 4, "stars4": 12, "stars3": 12 },
  "maxpreps": {
    "schoolId": "7bdc339f-7cbf-4728-b0c8-ed898929cf68",
    "canonicalUrl": "https://www.maxpreps.com/fl/bradenton/img-academy-ascenders/",
    "zip": "34210",
    "mascot": "Ascenders",
    "footballUrl": "https://www.maxpreps.com/fl/bradenton/img-academy-ascenders/football/"
  },
  "recruits": [
    {
      "id": "espn-265222",
      "full_name": "…",
      "class_year": 2027,
      "position": "DT",
      "college_commit": "Texas Tech",
      "hometown": "Buford, GA",
      "ratings": [
        { "source": "247sports_composite", "stars": 5, "rating": 0.9912, "national_rank": 12, "position": "DT", "profile_url": "https://247sports.com/player/…" }
      ],
      "talent_points": 98,
      "sources": ["247sports_composite", "on3_rivals", "espn"]
    }
  ]
}
```

`id` is the FridayRadar slug (`School.id`). `Player.high_school_id` is that slug. Rankings **prefer** `talent_score` / `recruit_count` so the board matches Scout before every rating row is present.

Leave zip null for: American Heritage (Fort Lauderdale, FL), ALA Queen Creek AZ, Lexington Christian Academy KY, Notre Dame Sherman Oaks CA, San Antonio Roosevelt TX.

### `schools.summary.json`

Rollup the importer prints in `meta.sources`:

```json
{
  "schools": 1554,
  "players": 2986,
  "class_2027": 2135,
  "class_2028": 851,
  "note": "Scout 247+Rivals+ESPN 2027/2028 frozen ingest"
}
```

Canonical v1: **1,554 schools / 2,986 players** (2,135 class 2027, 851 class 2028). 1,144 schools with MaxPreps `schoolId`, 1,141 with zip.

### `games.json`

Matchup week slate. v1 is **2026-08-26 through 2026-08-29** (213 games in the full dump, 91 with both sides mapped). Do not use the Aug 24–30 wall scrape.

```json
{
  "week_start": "2026-08-26",
  "week_end": "2026-08-29",
  "games": [
    {
      "contest_id": "2c7f797f-6730-4bc5-a5a6-9e8a0f7578cb",
      "maxpreps_game_url": "https://www.maxpreps.com/…",
      "kickoff_local": "2026-08-29T19:00:00",
      "is_neutral": false,
      "home": { "maxpreps_id": "7bdc339f-…", "site_id": "fl-bradenton-img-academy", "name": "IMG Academy", "city": "Bradenton", "state": "FL", "zip": "34210", "talent_score": 2263.49, "mapped": true },
      "away": { "maxpreps_id": "0d4488fa-…", "site_id": "tx-san-antonio-cornerstone-christian", "name": "Cornerstone Christian", "city": "San Antonio", "state": "TX", "zip": null, "talent_score": 155, "mapped": true },
      "combined_talent": 2418.49,
      "mapped_sides": 2,
      "home_score": null,
      "away_score": null
    }
  ]
}
```

`Game.id` = `contest_id`. `home_school_id` / `away_school_id` = `site_id` when mapped. If a side is unmapped (`mapped: false`, no `site_id`), the importer still keeps the game and inserts a placeholder school so St. Frances @ DeLand is not dropped. Combined talent uses 0 for that side.

### Players from ingest 2027/2028

Scout already scored the frozen 2027/2028 ingest (247Sports composite + On3/Rivals + ESPN). Nested `recruits` on `schools.json` are those rows. Raw copies remain under `data/raw/{espn,247,on3}/{year}.json` for reference. **Do not re-run 247 Load More** (it 406s). The importer never invents recruit names.

## Official talent

Average available stars across `247sports_composite`, `on3_rivals` (else `on3_industry`, never both), ESPN. Interpolate onto 5=98, 4=85, 3=70, 2=55, 1=40, listed=25. School talent = sum of 2027+ points.

Check: IMG `fl-bradenton-img-academy`, MaxPreps `7bdc339f-7cbf-4728-b0c8-ed898929cf68`, zip 34210, talent 2263.49, 28 recruits. Buford zip 30518, MaxPreps `6d00b044-607e-4dee-aa9b-e1fc2c6a87bc`.
