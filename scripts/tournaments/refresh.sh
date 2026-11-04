#!/usr/bin/env bash
# Weekly refresh: Zorts (fast map mode) + Flag50 -> merged data/tournaments.json
# Usage: ./refresh.sh [STATES]   e.g. ./refresh.sh TX   or   ./refresh.sh TX,OK,LA,NM,AR
set -euo pipefail
cd "$(dirname "$0")"
STATES="${1:-${STATES:-TX}}"
ROOT="$(cd ../.. && pwd)"
exec python3 refresh.py --states "$STATES" --no-find --outdir "$ROOT/data"
