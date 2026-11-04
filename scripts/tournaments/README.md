# FridayRadar tournaments pipeline (Zorts + Flag50)

Builds `data/tournaments.json` for `/tournaments`.

```bash
python3 scripts/tournaments/refresh.py --states TX --no-find
# or: scripts/tournaments/refresh.sh TX
```

`--states` defaults to TX. Flag50 reads only `https://flag50.com/tournaments/in/<state>/` and its prerendered `_payload.json` — never `/api/`. Zorts uses public map (and optional `/season/find`) plus event detail pages. No login.

If either site returns 403 / captcha / Cloudflare, the scripts exit without writing. Monday `--week-refresh` then keeps the on-disk file.

## Files

| file | what |
|---|---|
| `fetch_zorts.py` | Zorts public map/find/event pages. `--no-find` = fast map mode. |
| `fetch_flag50.py` | Flag50 state hub page + `_payload.json`. Never `/api/`. |
| `merge_tournaments.py` | Cross-match + dedupe, then `girls_filter.classify` on every row. Writes `tournaments.json` (and csv/html into the merge workdir). |
| `girls_filter.py` | Splits girls vs open (boys/coed) divisions. Girls-only events are dropped. `category` is computed from open 7v7/flag divisions only. |
| `make_html.py` | Standalone filterable HTML from `tournaments.json`. |
| `states.py` | State codes and names. Default `STATES = ["TX"]`. |

## Girls-only filtering

Run inside `merge_tournaments.py` on every refresh (including Monday `--week-refresh`):

- A division counts as girls when it says Girl/Women/Lady/Female/GFF, uses an age like 8UG/HSG, or has no gender tag in an event whose sport is girls-only.
- Tournaments with no open 7v7 or flag division are removed (including events whose only boys divisions are tackle or lineman). Removed events are listed in `dedupe_report.md`.
- `category` is worked out from open divisions only, so boys flag + girls 7v7 is labeled `flag`.
- Additive JSON fields: `has_girls_divisions` (bool), `girls_divisions` (list), `open_divisions` (list).
