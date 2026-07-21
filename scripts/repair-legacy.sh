#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-dry-run}"
shift || true

ARGS=(
  --input /app/legacy-data/movie.json
  --report-dir /app/migration-report/repair
  --pretty
)

if [[ "${MODE}" == "apply" ]]; then
  ARGS+=(--apply)
elif [[ "${MODE}" == "dry-run" ]]; then
  ARGS+=(--dry-run)
else
  echo "Usage: $0 [dry-run|apply] [extra args...]" >&2
  exit 2
fi

docker compose -f "${ROOT_DIR}/compose.yaml" exec backend \
  python -m app.scripts.repair_legacy_import_data \
  "${ARGS[@]}" \
  "$@"
