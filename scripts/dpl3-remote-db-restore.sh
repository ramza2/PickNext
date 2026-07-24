#!/usr/bin/env bash
# PickNext DATA-1 — restore a local custom-format dump into picknext-dpl3 only.
#
# Usage:
#   bash scripts/dpl3-remote-db-restore.sh \
#     /home/ramza/picknext-db-transfer/<dump-file> \
#     /home/ramza/picknext-db-transfer/<manifest-file> \
#     /home/ramza/picknext-db-transfer/<checksum-file>
#
# Fixed target: /home/ramza/picknext · project picknext-dpl3 · .env.dpl3
# Does not print secrets. Does not auto-rollback. Does not touch Traefik.
set -euo pipefail

DEPLOY_ROOT="/home/ramza/picknext"
PROJECT_NAME="picknext-dpl3"
ENV_FILE=".env.dpl3"
PUBLIC_BASE="https://picknext.ramza.duckdns.org"

COMPOSE=(
  docker compose
  --env-file "$ENV_FILE"
  -p "$PROJECT_NAME"
  -f compose.yaml
  -f compose.traefik.yaml
)

die() {
  echo "FAIL: $*" >&2
  exit 1
}

info() {
  echo "===== $* ====="
}

require_args() {
  if [[ $# -ne 3 ]]; then
    cat >&2 <<'EOF'
Usage:
  bash scripts/dpl3-remote-db-restore.sh <dump> <manifest> <checksum>
EOF
    exit 1
  fi
}

read_manifest_value() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "$MANIFEST_FILE" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    die "Manifest missing key: $key"
  fi
  printf '%s\n' "${line#*=}"
}

read_env_dpl3_value() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "$ENV_FILE" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    die ".env.dpl3 missing key: $key"
  fi
  printf '%s\n' "${line#*=}"
}

wait_label_healthy() {
  local service="$1"
  local max_tries="${2:-60}"
  local i cid status
  for i in $(seq 1 "$max_tries"); do
    cid="$(
      docker ps \
        --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
        --filter "label=com.docker.compose.service=${service}" \
        --format '{{.ID}}' |
        head -n 1
    )"
    if [[ -n "${cid}" ]]; then
      status="$(
        docker inspect "${cid}" \
          --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
      )"
      echo "${service} status=${status} (try ${i}/${max_tries})"
      if [[ "${status}" == "healthy" ]]; then
        return 0
      fi
    else
      echo "${service} container not found yet (try ${i}/${max_tries})"
    fi
    sleep 2
  done
  die "${service} did not become healthy within limit"
}

psql_app() {
  docker exec "$POSTGRES_CONTAINER" \
    sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -v ON_ERROR_STOP=1 $*"
}

psql_app_at() {
  docker exec "$POSTGRES_CONTAINER" \
    sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -v ON_ERROR_STOP=1 -c \"$1\""
}

psql_admin() {
  # Connect to maintenance DB 'postgres' using app credentials.
  docker exec "$POSTGRES_CONTAINER" \
    sh -lc "psql -U \"\$POSTGRES_USER\" -d postgres -v ON_ERROR_STOP=1 $*"
}

count_or_missing() {
  local table="$1"
  local exists
  exists="$(psql_app_at "SELECT to_regclass('public.${table}') IS NOT NULL")"
  if [[ "$exists" != "t" ]]; then
    echo "missing"
    return 0
  fi
  psql_app_at "SELECT COUNT(*) FROM ${table}"
}

print_rollback_help() {
  local before_dump="$1"
  cat <<EOF

===== ROLLBACK (manual — not executed) =====
1) cd ${DEPLOY_ROOT}
2) ${COMPOSE[*]} stop backend
3) Restore before-restore dump:
   POSTGRES_CONTAINER=\$(${COMPOSE[*]} ps -q postgres)
   docker exec "\$POSTGRES_CONTAINER" sh -lc 'psql -U "\$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_setting(''\\''\$POSTGRES_DB'\\'\'') AND pid <> pg_backend_pid();"'
   # Drop/recreate public, then:
   docker cp "${before_dump}" "\${POSTGRES_CONTAINER}:/tmp/picknext-rollback.dump"
   docker exec "\$POSTGRES_CONTAINER" sh -lc '
     set -eu
     APP_DB="\$POSTGRES_DB"
     APP_USER="\$POSTGRES_USER"
     psql -U "\$APP_USER" -d "\$APP_DB" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION \"\$APP_USER\"; GRANT ALL ON SCHEMA public TO \"\$APP_USER\"; GRANT ALL ON SCHEMA public TO public;"
     pg_restore --exit-on-error --no-owner --no-privileges -U "\$APP_USER" -d "\$APP_DB" /tmp/picknext-rollback.dump
   '
4) ${COMPOSE[*]} run --rm --no-deps backend alembic current
5) Verify seed email count = 1
6) ${COMPOSE[*]} up -d backend frontend
7) curl -fsS ${PUBLIC_BASE}/api/v1/health
Before-restore dump: ${before_dump}
EOF
}

require_args "$@"

DUMP_FILE="$(readlink -f "$1")"
MANIFEST_FILE="$(readlink -f "$2")"
CHECKSUM_FILE="$(readlink -f "$3")"

info "preflight"
[[ "$(id -un)" == "ramza" ]] || die "Must run as user ramza (got $(id -un))"
[[ -d "$DEPLOY_ROOT" ]] || die "DEPLOY_ROOT missing: $DEPLOY_ROOT"
cd "$DEPLOY_ROOT"
[[ -f compose.yaml ]] || die "compose.yaml missing"
[[ -f compose.traefik.yaml ]] || die "compose.traefik.yaml missing"
[[ -f "$ENV_FILE" ]] || die "$ENV_FILE missing"
[[ -f "$DUMP_FILE" ]] || die "Dump missing: $DUMP_FILE"
[[ -f "$MANIFEST_FILE" ]] || die "Manifest missing: $MANIFEST_FILE"
[[ -f "$CHECKSUM_FILE" ]] || die "Checksum missing: $CHECKSUM_FILE"
[[ -s "$DUMP_FILE" ]] || die "Dump is empty"
command -v docker >/dev/null || die "docker not available"
docker compose version >/dev/null || die "docker compose not available"
docker network inspect proxy >/dev/null || die "docker network 'proxy' missing"

info "checksum"
expected_hash="$(awk '{print $1}' "$CHECKSUM_FILE" | tr '[:upper:]' '[:lower:]')"
actual_hash="$(sha256sum "$DUMP_FILE" | awk '{print $1}' | tr '[:upper:]' '[:lower:]')"
[[ -n "$expected_hash" ]] || die "Checksum file empty"
[[ "$expected_hash" == "$actual_hash" ]] || die "Backup checksum mismatch"

info "manifest"
BACKUP_FORMAT="$(read_manifest_value BACKUP_FORMAT)"
SOURCE_DATABASE="$(read_manifest_value SOURCE_DATABASE)"
SOURCE_POSTGRES_MAJOR="$(read_manifest_value SOURCE_POSTGRES_MAJOR)"
SOURCE_ALEMBIC_REVISION="$(read_manifest_value SOURCE_ALEMBIC_REVISION)"
SOURCE_USERS="$(read_manifest_value SOURCE_USERS)"
SOURCE_CATEGORIES="$(read_manifest_value SOURCE_CATEGORIES)"
SOURCE_COLLECTIONS="$(read_manifest_value SOURCE_COLLECTIONS)"
SOURCE_ITEMS="$(read_manifest_value SOURCE_ITEMS)"
SOURCE_HISTORIES="$(read_manifest_value SOURCE_HISTORIES)"
SOURCE_SEED_USER_EMAIL="$(read_manifest_value SOURCE_SEED_USER_EMAIL)"
BACKUP_FILENAME="$(read_manifest_value BACKUP_FILENAME)"
BACKUP_SHA256="$(read_manifest_value BACKUP_SHA256 | tr '[:upper:]' '[:lower:]')"

[[ "$BACKUP_FORMAT" == "custom" ]] || die "BACKUP_FORMAT must be custom"
[[ "$BACKUP_SHA256" == "$actual_hash" ]] || die "Manifest BACKUP_SHA256 mismatch"
dump_base="$(basename "$DUMP_FILE")"
[[ "$dump_base" == "$BACKUP_FILENAME" ]] || die "Dump basename ($dump_base) != BACKUP_FILENAME ($BACKUP_FILENAME)"

REMOTE_SEED_EMAIL="$(read_env_dpl3_value SEED_USER_EMAIL)"
[[ "$REMOTE_SEED_EMAIL" == "$SOURCE_SEED_USER_EMAIL" ]] || \
  die "SEED_USER_EMAIL mismatch: .env.dpl3=$REMOTE_SEED_EMAIL manifest=$SOURCE_SEED_USER_EMAIL"

SOURCE_LEGACY_IMPORT_RUNS="$(grep -E '^SOURCE_LEGACY_IMPORT_RUNS=' "$MANIFEST_FILE" | head -n 1 | cut -d= -f2- || true)"
SOURCE_LEGACY_IMPORT_ITEMS="$(grep -E '^SOURCE_LEGACY_IMPORT_ITEMS=' "$MANIFEST_FILE" | head -n 1 | cut -d= -f2- || true)"
SOURCE_LEGACY_IMPORT_COLLECTIONS="$(grep -E '^SOURCE_LEGACY_IMPORT_COLLECTIONS=' "$MANIFEST_FILE" | head -n 1 | cut -d= -f2- || true)"
SOURCE_RECOMMENDATION_HISTORY_ITEMS="$(grep -E '^SOURCE_RECOMMENDATION_HISTORY_ITEMS=' "$MANIFEST_FILE" | head -n 1 | cut -d= -f2- || true)"

info "postgres up"
"${COMPOSE[@]}" up -d postgres
wait_label_healthy postgres 60

POSTGRES_CONTAINER="$("${COMPOSE[@]}" ps -q postgres | tr -d '[:space:]')"
[[ -n "$POSTGRES_CONTAINER" ]] || die "postgres container id empty"
container_count="$(
  docker ps -aq \
    --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
    --filter "label=com.docker.compose.service=postgres" |
    wc -l | tr -d '[:space:]'
)"
[[ "$container_count" == "1" ]] || die "Expected exactly 1 postgres container, got $container_count"

proj_label="$(docker inspect "$POSTGRES_CONTAINER" --format '{{index .Config.Labels "com.docker.compose.project"}}')"
svc_label="$(docker inspect "$POSTGRES_CONTAINER" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
[[ "$proj_label" == "$PROJECT_NAME" ]] || die "Compose project label mismatch: $proj_label"
[[ "$svc_label" == "postgres" ]] || die "Compose service label mismatch: $svc_label"

target_pg_major="$(
  docker exec "$POSTGRES_CONTAINER" sh -lc 'psql --version' |
    sed -E 's/.* ([0-9]+)\..*/\1/'
)"
echo "source_pg_major=${SOURCE_POSTGRES_MAJOR} target_pg_major=${target_pg_major}"
[[ "$target_pg_major" == "$SOURCE_POSTGRES_MAJOR" ]] || \
  die "PostgreSQL major mismatch (source=${SOURCE_POSTGRES_MAJOR} target=${target_pg_major})"

info "remote counts before restore"
echo "users=$(count_or_missing users)"
echo "categories=$(count_or_missing categories)"
echo "collections=$(count_or_missing collections)"
echo "items=$(count_or_missing items)"
echo "recommendation_history=$(count_or_missing recommendation_history)"
echo "recommendation_history_items=$(count_or_missing recommendation_history_items)"

info "backup current remote DB"
mkdir -p "${DEPLOY_ROOT}/backups"
BEFORE_TS="$(date -u +%Y%m%d-%H%M%S)"
BEFORE_DUMP_HOST="${DEPLOY_ROOT}/backups/picknext-dpl3-before-restore-${BEFORE_TS}.dump"
BEFORE_SHA_HOST="${DEPLOY_ROOT}/backups/picknext-dpl3-before-restore-${BEFORE_TS}.sha256"

docker exec "$POSTGRES_CONTAINER" sh -lc '
set -eu
rm -f /tmp/picknext-dpl3-before-restore.dump
pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/tmp/picknext-dpl3-before-restore.dump
test -s /tmp/picknext-dpl3-before-restore.dump
'
docker cp \
  "${POSTGRES_CONTAINER}:/tmp/picknext-dpl3-before-restore.dump" \
  "$BEFORE_DUMP_HOST"
[[ -s "$BEFORE_DUMP_HOST" ]] || die "Before-restore dump missing or empty"
before_hash="$(sha256sum "$BEFORE_DUMP_HOST" | awk '{print $1}')"
echo "${before_hash}  $(basename "$BEFORE_DUMP_HOST")" >"$BEFORE_SHA_HOST"
echo "before_restore_dump=${BEFORE_DUMP_HOST}"
echo "before_restore_sha256=${before_hash}"

info "stop backend"
set +e
"${COMPOSE[@]}" stop backend
stop_rc=$?
set -e
echo "backend stop rc=${stop_rc} (0/ok even if already stopped)"

info "terminate app DB sessions"
APP_DB_NAME="$(
  docker exec "$POSTGRES_CONTAINER" sh -lc 'printf %s "$POSTGRES_DB"'
)"
APP_USER_NAME="$(
  docker exec "$POSTGRES_CONTAINER" sh -lc 'printf %s "$POSTGRES_USER"'
)"
docker exec "$POSTGRES_CONTAINER" sh -lc "
set -eu
psql -U \"\$POSTGRES_USER\" -d postgres -v ON_ERROR_STOP=1 -c \"
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${APP_DB_NAME}'
  AND pid <> pg_backend_pid();
\"
"

info "copy incoming dump"
docker cp "$DUMP_FILE" "${POSTGRES_CONTAINER}:/tmp/picknext-incoming.dump"
docker exec "$POSTGRES_CONTAINER" test -s /tmp/picknext-incoming.dump

info "schema check"
schemas="$(psql_app_at "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")"
echo "$schemas"
# Allow only built-in catalogs + public. Reject any other application schema.
non_public="$(
  printf '%s\n' "$schemas" |
    grep -Ev '^(information_schema|pg_catalog|pg_toast|public)$' |
    grep -Ev '^pg_temp_' |
    grep -Ev '^pg_toast_temp_' || true
)"
if [[ -n "$non_public" ]]; then
  echo "$non_public" >&2
  die "Non-public application schemas present; refusing automatic DROP SCHEMA public"
fi

info "reset public schema"
docker exec "$POSTGRES_CONTAINER" sh -lc "
set -eu
psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -v ON_ERROR_STOP=1 <<SQL
DROP SCHEMA public CASCADE;
CREATE SCHEMA public AUTHORIZATION \"${APP_USER_NAME}\";
GRANT ALL ON SCHEMA public TO \"${APP_USER_NAME}\";
GRANT ALL ON SCHEMA public TO public;
SQL
"

info "pg_restore"
if ! docker exec "$POSTGRES_CONTAINER" sh -lc '
set -eu
pg_restore \
  --exit-on-error \
  --no-owner \
  --no-privileges \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  /tmp/picknext-incoming.dump
'; then
  echo "FAIL: pg_restore failed. Backend not restarted. Incoming dump kept in container." >&2
  print_rollback_help "$BEFORE_DUMP_HOST"
  exit 1
fi

info "alembic revision"
current_rev="$(
  "${COMPOSE[@]}" run --rm --no-deps backend alembic current 2>/dev/null |
    grep -E '^[0-9a-zA-Z_]+' |
    head -n 1 |
    awk '{print $1}'
)"
heads_rev="$(
  "${COMPOSE[@]}" run --rm --no-deps backend alembic heads 2>/dev/null |
    grep -E '^[0-9a-zA-Z_]+' |
    head -n 1 |
    awk '{print $1}'
)"
echo "alembic current=${current_rev}"
echo "alembic heads=${heads_rev}"
echo "manifest revision=${SOURCE_ALEMBIC_REVISION}"
[[ "$current_rev" == "$heads_rev" ]] || {
  print_rollback_help "$BEFORE_DUMP_HOST"
  die "alembic current != heads"
}
[[ "$current_rev" == "$SOURCE_ALEMBIC_REVISION" ]] || {
  print_rollback_help "$BEFORE_DUMP_HOST"
  die "alembic current != manifest SOURCE_ALEMBIC_REVISION"
}

info "seed user"
seed_count="$(psql_app_at "SELECT COUNT(*) FROM users WHERE email = '${SOURCE_SEED_USER_EMAIL}'")"
echo "seed_email=${SOURCE_SEED_USER_EMAIL} count=${seed_count}"
[[ "$seed_count" == "1" ]] || {
  print_rollback_help "$BEFORE_DUMP_HOST"
  die "Seed user count must be 1"
}

info "count compare"
got_users="$(psql_app_at 'SELECT COUNT(*) FROM users')"
got_categories="$(psql_app_at 'SELECT COUNT(*) FROM categories')"
got_collections="$(psql_app_at 'SELECT COUNT(*) FROM collections')"
got_items="$(psql_app_at 'SELECT COUNT(*) FROM items')"
got_histories="$(psql_app_at 'SELECT COUNT(*) FROM recommendation_history')"
got_history_items="$(psql_app_at 'SELECT COUNT(*) FROM recommendation_history_items')"

echo "users: expected=${SOURCE_USERS} got=${got_users}"
echo "categories: expected=${SOURCE_CATEGORIES} got=${got_categories}"
echo "collections: expected=${SOURCE_COLLECTIONS} got=${got_collections}"
echo "items: expected=${SOURCE_ITEMS} got=${got_items}"
echo "histories: expected=${SOURCE_HISTORIES} got=${got_histories}"

[[ "$got_users" == "$SOURCE_USERS" ]] || die "users count mismatch"
[[ "$got_categories" == "$SOURCE_CATEGORIES" ]] || die "categories count mismatch"
[[ "$got_collections" == "$SOURCE_COLLECTIONS" ]] || die "collections count mismatch"
[[ "$got_items" == "$SOURCE_ITEMS" ]] || die "items count mismatch"
[[ "$got_histories" == "$SOURCE_HISTORIES" ]] || die "histories count mismatch"

if [[ -n "${SOURCE_RECOMMENDATION_HISTORY_ITEMS}" ]]; then
  echo "history_items: expected=${SOURCE_RECOMMENDATION_HISTORY_ITEMS} got=${got_history_items}"
  [[ "$got_history_items" == "$SOURCE_RECOMMENDATION_HISTORY_ITEMS" ]] || \
    die "recommendation_history_items count mismatch"
fi

if [[ -n "${SOURCE_LEGACY_IMPORT_RUNS}" ]]; then
  got_legacy_runs="$(psql_app_at 'SELECT COUNT(*) FROM legacy_import_runs')"
  got_legacy_items="$(psql_app_at 'SELECT COUNT(*) FROM legacy_import_items')"
  got_legacy_collections="$(psql_app_at 'SELECT COUNT(*) FROM legacy_import_collections')"
  echo "legacy_runs: expected=${SOURCE_LEGACY_IMPORT_RUNS} got=${got_legacy_runs}"
  echo "legacy_items: expected=${SOURCE_LEGACY_IMPORT_ITEMS} got=${got_legacy_items}"
  echo "legacy_collections: expected=${SOURCE_LEGACY_IMPORT_COLLECTIONS} got=${got_legacy_collections}"
  [[ "$got_legacy_runs" == "$SOURCE_LEGACY_IMPORT_RUNS" ]] || die "legacy_import_runs mismatch"
  [[ "$got_legacy_items" == "$SOURCE_LEGACY_IMPORT_ITEMS" ]] || die "legacy_import_items mismatch"
  [[ "$got_legacy_collections" == "$SOURCE_LEGACY_IMPORT_COLLECTIONS" ]] || die "legacy_import_collections mismatch"
fi

info "FK integrity"
orphan_cats="$(psql_app_at 'SELECT COUNT(*) FROM categories c LEFT JOIN users u ON u.id = c.user_id WHERE u.id IS NULL')"
orphan_cols="$(psql_app_at 'SELECT COUNT(*) FROM collections c LEFT JOIN users u ON u.id = c.user_id WHERE u.id IS NULL')"
orphan_items_user="$(psql_app_at 'SELECT COUNT(*) FROM items i LEFT JOIN users u ON u.id = i.user_id WHERE u.id IS NULL')"
orphan_items_col="$(psql_app_at 'SELECT COUNT(*) FROM items i LEFT JOIN collections c ON c.id = i.collection_id WHERE i.collection_id IS NOT NULL AND c.id IS NULL')"
echo "orphan categories.user_id=${orphan_cats}"
echo "orphan collections.user_id=${orphan_cols}"
echo "orphan items.user_id=${orphan_items_user}"
echo "orphan items.collection_id=${orphan_items_col}"
[[ "$orphan_cats" == "0" && "$orphan_cols" == "0" && "$orphan_items_user" == "0" && "$orphan_items_col" == "0" ]] || \
  die "FK integrity check failed"

info "sequence note"
# UUID PKs with gen_random_uuid(); no serial sequences expected for core tables.
seq_count="$(psql_app_at "SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'S' AND n.nspname = 'public'")"
echo "public_sequences=${seq_count}"

info "start backend frontend"
"${COMPOSE[@]}" up -d backend frontend
wait_label_healthy postgres 60
wait_label_healthy backend 90
wait_label_healthy frontend 60

info "API smoke"
health_tmp="$(mktemp)"
code="$(curl -sS -o "$health_tmp" -w '%{http_code}' "${PUBLIC_BASE}/api/v1/health")"
echo "GET /api/v1/health -> HTTP ${code}"
[[ "$code" == "200" ]] || die "health HTTP $code"
grep -qi '<html' "$health_tmp" && die "health returned HTML"
head -c 200 "$health_tmp" | tr '\n' ' '
echo
rm -f "$health_tmp"

cat_tmp="$(mktemp)"
code="$(curl -sS -o "$cat_tmp" -w '%{http_code}' "${PUBLIC_BASE}/api/v1/categories")"
[[ "$code" == "200" ]] || die "categories HTTP $code"
grep -qi '<html' "$cat_tmp" && die "categories returned HTML"
# CategoryListResponse: {"categories":[...]}
cat_count="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get("categories",[])))' "$cat_tmp")"
echo "categories response count=${cat_count} expected=${SOURCE_CATEGORIES}"
[[ "$cat_count" == "$SOURCE_CATEGORIES" ]] || die "categories API count mismatch"
rm -f "$cat_tmp"

col_tmp="$(mktemp)"
code="$(curl -sS -o "$col_tmp" -w '%{http_code}' "${PUBLIC_BASE}/api/v1/collections?page_size=1")"
[[ "$code" == "200" ]] || die "collections HTTP $code"
grep -qi '<html' "$col_tmp" && die "collections returned HTML"
col_total="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("total"))' "$col_tmp")"
echo "collections total=${col_total} expected=${SOURCE_COLLECTIONS}"
[[ "$col_total" == "$SOURCE_COLLECTIONS" ]] || die "collections API total mismatch"
rm -f "$col_tmp"

item_tmp="$(mktemp)"
code="$(curl -sS -o "$item_tmp" -w '%{http_code}' "${PUBLIC_BASE}/api/v1/items?page_size=1")"
[[ "$code" == "200" ]] || die "items HTTP $code"
grep -qi '<html' "$item_tmp" && die "items returned HTML"
item_total="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("total"))' "$item_tmp")"
echo "items total=${item_total} expected=${SOURCE_ITEMS}"
[[ "$item_total" == "$SOURCE_ITEMS" ]] || die "items API total mismatch"
rm -f "$item_tmp"

info "router priority"
curl -sS -D - \
  "${PUBLIC_BASE}/api/not-existing" \
  -o /tmp/picknext-api-not-existing.txt | head -n 20
if grep -qi '<!doctype html\|<html' /tmp/picknext-api-not-existing.txt; then
  die "/api/not-existing returned Frontend HTML"
fi
echo "api not-existing body (first 200 bytes):"
head -c 200 /tmp/picknext-api-not-existing.txt || true
echo

info "cleanup container temp dumps"
docker exec "$POSTGRES_CONTAINER" rm -f \
  /tmp/picknext-incoming.dump \
  /tmp/picknext-dpl3-before-restore.dump || true

info "browser checklist"
cat <<EOF
Please verify in browser (hard refresh / clear PWA SW if needed):
- Category ≈ ${SOURCE_CATEGORIES}
- Collection ≈ ${SOURCE_COLLECTIONS}
- Item ≈ ${SOURCE_ITEMS}
- Collection detail / Item detail / History
- Poster/image display (schema has no poster columns; expect text-only unless FE uses other sources)
- Do NOT create/update/delete yet
EOF

print_rollback_help "$BEFORE_DUMP_HOST"

info "PASS"
echo "restored dump=${DUMP_FILE}"
echo "before restore backup=${BEFORE_DUMP_HOST}"
echo "project=${PROJECT_NAME}"
"${COMPOSE[@]}" ps
