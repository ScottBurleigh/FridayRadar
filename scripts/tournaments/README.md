# FridayRadar tournaments pipeline (Zorts + Flag50)

Builds `data/tournaments.json` for `/tournaments`.

```bash
python3 scripts/tournaments/refresh.py --states TX --no-find
# or: scripts/tournaments/refresh.sh TX
```

`--states` defaults to TX. Flag50 reads only `https://flag50.com/tournaments/in/<state>/` and its prerendered `_payload.json` — never `/api/`. Zorts uses public map (and optional `/season/find`) plus event detail pages. No login.

If either site returns 403 / captcha / Cloudflare, the scripts exit without writing. Monday `--week-refresh` then keeps the on-disk file.
