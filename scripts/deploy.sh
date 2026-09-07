#!/usr/bin/env bash
# PickNext production deploy (DPL-3 only)
#
# On the production host (repo root):
#   ./scripts/deploy.sh
#
# Rebuilds and recreates backend + frontend only.
# Does NOT touch PostgreSQL, Traefik, volumes, migrations, or seeds.
#
# Compose:
#   docker compose --env-file .env.dpl3 -p picknext-dpl3 \
#     -f compose.yaml -f compose.traefik.yaml ...
set -Eeuo pipefail

readonly ENV_FILE=".env.dpl3"
readonly COMPOSE_PROJECT="picknext-dpl3"
readonly PUBLIC_URL="${PICKNEXT_PUBLIC_URL:-https://picknext.ramza.duckdns.org/}"
readonly HEALTH_WAIT_TRIES="${DEPLOY_HEALTH_WAIT_TRIES:-36}"
readonly HEALTH_WAIT_SLEEP_SEC="${DEPLOY_HEALTH_WAIT_SLEEP_SEC:-5}"

COMPOSE=(
  docker compose
  --env-file "${ENV_FILE}"
  -p "${COMPOSE_PROJECT}"
  -f compose.yaml
  -f compose.traefik.yaml
)

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

log() {
  echo "[INFO] $*"
}

require_cmd() {
  local name="$1"
  command -v "${name}" >/dev/null 2>&1 || die "${name} is unavailable."
}

short_sha() {
  git rev-parse --short=12 HEAD
}

assert_repo_root() {
  local script_dir root
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  root="$(cd "${script_dir}/.." && pwd)"
  cd "${root}"
  [[ -f compose.yaml ]] || die "compose.yaml not found in repo root (${root})."
  [[ -d .git ]] || die "Not a Git repository: ${root}"
  log "Repo root: ${root}"
}

assert_git_ready() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "Not a Git repository."

  local branch
  branch="$(git branch --show-current 2>/dev/null || true)"
  [[ "${branch}" == "main" ]] \
    || die "Current branch must be 'main' (got '${branch:-detached}')."

  if [[ -d .git/rebase-merge || -d .git/rebase-apply ]]; then
    die "Git rebase in progress — resolve before deploy."
  fi
  if [[ -f .git/MERGE_HEAD ]]; then
    die "Git merge in progress — resolve before deploy."
  fi
  if [[ -f .git/CHERRY_PICK_HEAD ]]; then
    die "Git cherry-pick in progress — resolve before deploy."
  fi

  # Tracked / index changes only (untracked local notes are allowed).
  if ! git diff --quiet || ! git diff --cached --quiet; then
    die "Git working tree is not clean."
  fi
}

assert_production_files() {
  [[ -f compose.yaml ]] || die "compose.yaml not found."
  [[ -f compose.traefik.yaml ]] || die "compose.traefik.yaml not found."
  [[ -f "${ENV_FILE}" ]] || die "Production env file ${ENV_FILE} not found."

  # Warn only — never chmod or rewrite env files.
  # Do not require `.env` or an `.env -> .env.dpl3` symlink; deploy always
  # passes `--env-file .env.dpl3`.
  if [[ -f "${ENV_FILE}" ]]; then
    local mode
    mode="$(stat -c '%a' "${ENV_FILE}" 2>/dev/null || true)"
    if [[ -n "${mode}" && "${mode}" != "600" && "${mode}" != "400" ]]; then
      log "Warning: ${ENV_FILE} permissions are ${mode} (prefer 600)."
    fi
  fi
}

assert_docker() {
  require_cmd docker
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable."
  docker compose version >/dev/null 2>&1 \
    || die "docker compose is unavailable."
}

pull_main_ff_only() {
  local before after
  before="$(short_sha)"
  log "Current commit : ${before}"
  log "Pulling origin/main (ff-only)..."
  git pull --ff-only origin main \
    || die "git pull --ff-only origin main failed."
  after="$(short_sha)"
  log "Deploy commit  : ${after}"
  if [[ "${before}" == "${after}" ]]; then
    log "Already up to date with origin/main."
  else
    log "Updated ${before} → ${after}"
  fi
}

build_images() {
  log "Building backend and frontend images..."
  "${COMPOSE[@]}" build backend frontend \
    || die "Backend/frontend image build failed."
}

recreate_app_services() {
  log "Recreating backend and frontend (--no-deps)..."
  "${COMPOSE[@]}" up -d --force-recreate --no-deps backend frontend \
    || die "Service recreation failed."
}

service_health_status() {
  local service="$1"
  local cid
  cid="$(
    docker ps \
      --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
      --filter "label=com.docker.compose.service=${service}" \
      --format '{{.ID}}' \
      | head -n 1
  )"
  if [[ -z "${cid}" ]]; then
    echo "missing"
    return 0
  fi
  docker inspect "${cid}" \
    --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
}

wait_service_ready() {
  local service="$1"
  local i status
  for i in $(seq 1 "${HEALTH_WAIT_TRIES}"); do
    status="$(service_health_status "${service}")"
    log "${service} status=${status} (try ${i}/${HEALTH_WAIT_TRIES})"
    if [[ "${status}" == "healthy" ]]; then
      return 0
    fi
    # Accept plain "running" only when the container has no Health block.
    if [[ "${status}" == "running" ]]; then
      local cid
      cid="$(
        docker ps \
          --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
          --filter "label=com.docker.compose.service=${service}" \
          --format '{{.ID}}' \
          | head -n 1
      )"
      if [[ -n "${cid}" ]] \
        && ! docker inspect "${cid}" --format '{{json .State.Health}}' \
          | grep -q '"Status"'; then
        return 0
      fi
    fi
    sleep "${HEALTH_WAIT_SLEEP_SEC}"
  done
  die "${service} did not become healthy in time."
}

show_status() {
  log "Compose ps:"
  "${COMPOSE[@]}" ps
}

optional_public_check() {
  if ! command -v curl >/dev/null 2>&1; then
    log "curl unavailable — skipping public URL check."
    return 0
  fi
  local code
  # Frontend root only — do not call authenticated APIs.
  code="$(
    curl -fsS -o /dev/null -w '%{http_code}' \
      --connect-timeout 5 \
      --max-time 20 \
      "${PUBLIC_URL}" \
      || true
  )"
  if [[ "${code}" == "200" || "${code}" == "301" || "${code}" == "302" ]]; then
    log "Public URL check OK (${PUBLIC_URL} → HTTP ${code})."
  else
    log "Warning: public URL check did not return success (${PUBLIC_URL} → HTTP ${code:-n/a})."
  fi
}

print_summary() {
  local commit
  commit="$(short_sha)"
  cat <<EOF
========================================
PickNext production deployment complete
Commit: ${commit}
Services: backend, frontend
PostgreSQL: untouched
Traefik: untouched
========================================
EOF
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,16p' "$0"
    exit 0
  fi

  log "===== Step 1. Preflight ====="
  assert_repo_root
  assert_git_ready
  assert_production_files
  assert_docker

  log "===== Step 2. Update main ====="
  pull_main_ff_only
  # Re-check cleanliness after pull (should still be clean).
  assert_git_ready

  log "===== Step 3. Build backend/frontend ====="
  build_images

  log "===== Step 4. Recreate backend/frontend ====="
  recreate_app_services

  log "===== Step 5. Verify ====="
  show_status
  wait_service_ready backend
  wait_service_ready frontend
  optional_public_check
  print_summary
}

main "$@"
