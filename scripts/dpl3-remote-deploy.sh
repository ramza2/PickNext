#!/usr/bin/env bash
# PickNext DPL-3 remote deploy
#
# Usage (preferred — Git checkout already present):
#   cd /path/to/PickNext
#   # prepare .env.dpl3 first (do not commit secrets)
#   bash scripts/dpl3-remote-deploy.sh
#
# Optional archive mode (extracts into ~/apps/picknext-dpl3/releases/<id>):
#   bash scripts/dpl3-remote-deploy.sh /path/to/picknext-dpl3.tar.gz
#
# Order:
#   build → postgres up → wait healthy → alembic upgrade → run_seed()
#   → backend+frontend up → health + API smoke
#
# Does not print secrets. Does not automate sudo/SSH passwords.
set -euo pipefail

COMPOSE=(docker compose --env-file .env.dpl3 -p picknext-dpl3 -f compose.yaml -f compose.traefik.yaml)
HOST_NAME="${PICKNEXT_HOST:-picknext.ramza.duckdns.org}"

die() {
  echo "FAIL: $*" >&2
  exit 1
}

wait_postgres_healthy() {
  echo "===== wait postgres healthy ====="
  local i
  for i in $(seq 1 60); do
    local cid status
    cid="$(
      docker ps \
        --filter "label=com.docker.compose.project=picknext-dpl3" \
        --filter "label=com.docker.compose.service=postgres" \
        --format '{{.ID}}' \
        | head -n 1
    )"
    if [[ -n "${cid}" ]]; then
      status="$(docker inspect "${cid}" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')"
      echo "postgres status=${status} (try ${i}/60)"
      if [[ "${status}" == "healthy" ]]; then
        return 0
      fi
    else
      echo "postgres container not found yet (try ${i}/60)"
    fi
    sleep 3
  done
  die "postgres did not become healthy"
}

wait_service_healthy() {
  local service="$1"
  local i cid status
  for i in $(seq 1 60); do
    cid="$(
      docker ps \
        --filter "label=com.docker.compose.project=picknext-dpl3" \
        --filter "label=com.docker.compose.service=${service}" \
        --format '{{.ID}}' \
        | head -n 1
    )"
    if [[ -n "${cid}" ]]; then
      status="$(docker inspect "${cid}" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')"
      echo "${service} status=${status} (try ${i}/60)"
      if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
        # Prefer healthy when healthcheck exists
        if [[ "${status}" == "healthy" ]]; then
          return 0
        fi
        # No Health block → running is acceptable for short wait, but keep trying for healthy
        if ! docker inspect "${cid}" --format '{{json .State.Health}}' | grep -q '"Status"'; then
          return 0
        fi
      fi
    fi
    sleep 3
  done
  die "${service} did not become healthy"
}

assert_json_200() {
  local path="$1"
  local out="/tmp/picknext-dpl3-assert${path//\//-}.json"
  local code
  code="$(
    curl -k -sS -o "${out}" -w '%{http_code}' \
      --resolve "${HOST_NAME}:443:127.0.0.1" \
      "https://${HOST_NAME}${path}"
  )"
  [[ "${code}" == "200" ]] || die "${path} expected HTTP 200, got ${code}"
  head -c 1 "${out}" | grep -q '{' || die "${path} response is not JSON object"
  echo "OK ${path} → 200 JSON"
}

# ----- resolve working directory -----
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,20p' "$0"
  exit 0
fi

if [[ $# -ge 1 && -n "${1:-}" ]]; then
  DEPLOY_ROOT="${HOME}/apps/picknext-dpl3"
  ARCHIVE="$1"
  RELEASE_ID="$(date +%Y%m%d-%H%M%S)"
  RELEASE_DIR="${DEPLOY_ROOT}/releases/${RELEASE_ID}"
  [[ -f "${ARCHIVE}" ]] || die "archive not found: ${ARCHIVE}"
  mkdir -p "${RELEASE_DIR}"
  tar -xzf "${ARCHIVE}" -C "${RELEASE_DIR}"
  cd "${RELEASE_DIR}"
  echo "RELEASE_DIR=${RELEASE_DIR}"
else
  # Git clone / checkout mode: run from repository root
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "${SCRIPT_DIR}/.."
  echo "REPO_DIR=$(pwd)"
fi

[[ -f compose.yaml ]] || die "compose.yaml missing in $(pwd)"
[[ -f compose.traefik.yaml ]] || die "compose.traefik.yaml missing in $(pwd)"

# ----- env file (never overwrite existing remote secrets) -----
if [[ ! -f .env.dpl3 ]]; then
  echo "===== creating .env.dpl3 (new secrets) ====="
  umask 077
  DB_PASSWORD="$(openssl rand -hex 24)"
  SECRET_KEY="$(openssl rand -hex 32)"
  SEED_PASSWORD="$(openssl rand -hex 16)"
  {
    echo "APP_NAME=PickNext"
    echo "APP_ENV=production"
    echo "DEBUG=false"
    echo "LOG_LEVEL=INFO"
    echo "SQL_ECHO=false"
    echo "API_V1_PREFIX=/api/v1"
    echo "CORS_ORIGINS=https://${HOST_NAME}"
    echo "SECRET_KEY=${SECRET_KEY}"
    echo "POSTGRES_HOST=postgres"
    echo "POSTGRES_PORT=5432"
    echo "POSTGRES_DB=picknext"
    echo "POSTGRES_USER=picknext"
    echo "POSTGRES_PASSWORD=${DB_PASSWORD}"
    echo "VITE_API_BASE_URL=/api/v1"
    echo "PICKNEXT_FRONTEND_IMAGE=picknext-frontend:dpl3"
    echo "PICKNEXT_HOST=${HOST_NAME}"
    echo "SEED_USER_EMAIL=dpl3@picknext.local"
    echo "SEED_USER_DISPLAY_NAME=DPL3 User"
    echo "SEED_USER_PASSWORD=${SEED_PASSWORD}"
  } > .env.dpl3
  chmod 600 .env.dpl3
  unset DB_PASSWORD SECRET_KEY SEED_PASSWORD
else
  echo "===== using existing .env.dpl3 (not overwritten) ====="
  chmod 600 .env.dpl3 || true
fi

# compose.yaml services use env_file: .env
ln -sfn .env.dpl3 .env

# Load PICKNEXT_HOST for smoke checks without echoing secrets
if grep -q '^PICKNEXT_HOST=' .env.dpl3; then
  HOST_NAME="$(grep '^PICKNEXT_HOST=' .env.dpl3 | head -n 1 | cut -d= -f2-)"
fi

echo "===== compose config ====="
"${COMPOSE[@]}" config --quiet

echo "===== build ====="
"${COMPOSE[@]}" build

echo "===== ensure clean start (no -v) ====="
"${COMPOSE[@]}" down --remove-orphans || true

echo "===== up postgres only ====="
"${COMPOSE[@]}" up -d postgres
wait_postgres_healthy

echo "===== alembic upgrade head ====="
"${COMPOSE[@]}" run --rm --no-deps backend alembic upgrade head

echo "===== alembic current (must be head) ====="
ALEMBIC_CURRENT="$("${COMPOSE[@]}" run --rm --no-deps backend alembic current)"
echo "${ALEMBIC_CURRENT}"
echo "${ALEMBIC_CURRENT}" | grep -Eqi 'head|\\(head\\)' \
  || die "alembic current is not at head"

echo "===== seed (app.services.seed.run_seed) ====="
SEED_OUT="$("${COMPOSE[@]}" run --rm --no-deps backend \
  python -c "from app.services.seed import run_seed; print(run_seed())")"
echo "${SEED_OUT}"

echo "===== verify seed in DB ====="
SEED_EMAIL="$(grep '^SEED_USER_EMAIL=' .env.dpl3 | head -n 1 | cut -d= -f2-)"
[[ -n "${SEED_EMAIL}" ]] || die "SEED_USER_EMAIL missing in .env.dpl3"

VERIFY_SQL="
SELECT
  (SELECT count(*) FROM users WHERE email = '${SEED_EMAIL}') AS seed_users,
  (SELECT count(*) FROM categories) AS category_count;
"
DB_CHECK="$("${COMPOSE[@]}" exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -F "," -c "'"${VERIFY_SQL}"'"')"
echo "db_check=${DB_CHECK}"
SEED_USERS="$(echo "${DB_CHECK}" | awk -F, 'NF>=2 {print $1}' | tr -d '[:space:]')"
CAT_COUNT="$(echo "${DB_CHECK}" | awk -F, 'NF>=2 {print $2}' | tr -d '[:space:]')"
[[ "${SEED_USERS}" == "1" ]] || die "expected 1 seed user for ${SEED_EMAIL}, got '${SEED_USERS}'"
[[ "${CAT_COUNT}" == "10" ]] || die "expected 10 categories, got '${CAT_COUNT}'"
echo "OK seed user=1 categories=10"

echo "===== up backend + frontend ====="
"${COMPOSE[@]}" up -d backend frontend
wait_service_healthy backend
wait_service_healthy frontend
"${COMPOSE[@]}" ps

echo "===== isolation ====="
docker ps --filter "label=com.docker.compose.project=picknext-dpl3" \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Networks}}'
docker volume ls --filter "label=com.docker.compose.project=picknext-dpl3"

FRONTEND_CONTAINER="$(
  docker ps \
    --filter "label=com.docker.compose.project=picknext-dpl3" \
    --filter "label=com.docker.compose.service=frontend" \
    --format '{{.Names}}' | head -n 1
)"
BACKEND_CONTAINER="$(
  docker ps \
    --filter "label=com.docker.compose.project=picknext-dpl3" \
    --filter "label=com.docker.compose.service=backend" \
    --format '{{.Names}}' | head -n 1
)"
POSTGRES_CONTAINER="$(
  docker ps \
    --filter "label=com.docker.compose.project=picknext-dpl3" \
    --filter "label=com.docker.compose.service=postgres" \
    --format '{{.Names}}' | head -n 1
)"

[[ -n "${FRONTEND_CONTAINER}" && -n "${BACKEND_CONTAINER}" && -n "${POSTGRES_CONTAINER}" ]] \
  || die "missing containers"

docker inspect "${FRONTEND_CONTAINER}" --format 'frontend networks={{json .NetworkSettings.Networks}}'
docker inspect "${BACKEND_CONTAINER}" --format 'backend networks={{json .NetworkSettings.Networks}}'
docker inspect "${POSTGRES_CONTAINER}" --format 'postgres networks={{json .NetworkSettings.Networks}}'

echo "===== proxy internal health ====="
docker run --rm --network proxy curlimages/curl:8.12.1 -fsS \
  "http://${FRONTEND_CONTAINER}:80/health" \
  || docker exec "${FRONTEND_CONTAINER}" wget -q -O - http://127.0.0.1/health
echo
docker run --rm --network proxy curlimages/curl:8.12.1 -fsS \
  "http://${BACKEND_CONTAINER}:8000/api/v1/health" \
  || docker exec "${BACKEND_CONTAINER}" curl -fsS http://127.0.0.1:8000/api/v1/health
echo

echo "===== HTTPS API smoke (Traefik --resolve) ====="
assert_json_200 /api/v1/health
assert_json_200 /api/v1/categories
assert_json_200 /api/v1/collections
assert_json_200 /api/v1/items

echo "===== DONE deploy (migrate + seed before public services) ====="
echo "Host=${HOST_NAME}"
echo "Working dir=$(pwd)"
echo "Secrets remain in .env.dpl3 (chmod 600) — do not paste that file."
