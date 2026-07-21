#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env first."
  exit 1
fi

docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.services.seed
