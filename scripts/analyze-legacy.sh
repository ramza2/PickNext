#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "${ROOT_DIR}/compose.yaml" exec backend \
  python -m app.scripts.analyze_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report \
  --pretty \
  "$@"
