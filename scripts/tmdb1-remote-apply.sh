#!/usr/bin/env bash
# PickNext TMDB-1 — safe remote apply on picknext-dpl3 only.
#
# Usage (on the Ubuntu host, after git pull):
#   cd /home/ramza/picknext
#   bash scripts/tmdb1-remote-apply.sh
#
# Fixed target: /home/ramza/picknext · project picknext-dpl3 · .env.dpl3
# Does not print secrets. Does not auto-rollback. Does not Seed.
# Does not modify Traefik. Does not touch other Compose projects.
set -euo pipefail

DEPLOY_ROOT="/home/ramza/picknext"
PROJECT_NAME="picknext-dpl3"
ENV_FILE=".env.dpl3"
PUBLIC_BASE_URL="https://picknext.ramza.duckdns.org"

EXPECTED_CURRENT_BEFORE="0004_remove_item_soft_delete"
EXPECTED_HEAD="0005_add_item_external_identity"
EXPECTED_USERS=1
EXPECTED_CATEGORIES=10
EXPECTED_COLLECTIONS=249
EXPECTED_ITEMS=7202
EXPECTED_HISTORIES=0

COMPOSE=(
  docker compose
  --env-file "$ENV_FILE"
  -p "$PROJECT_NAME"
  -f compose.yaml
  -f compose.traefik.yaml
)

BACKUP_DIR=""
BACKUP_BASENAME=""
BACKUP_DUMP=""
BACKUP_SHA=""
BACKUP_MANIFEST=""
MIGRATION_APPLIED=0
BACKEND_RUNNING=0
POSTGRES_CONTAINER=""

die() {
  echo "FAIL: $*" >&2
  echo "----- failure context -----" >&2
  echo "migration_applied=${MIGRATION_APPLIED}" >&2
  echo "backend_running=${BACKEND_RUNNING}" >&2
  if [[ -n "${BACKUP_DUMP}" ]]; then
    echo "backup_dump=${BACKUP_DUMP}" >&2
    if [[ -f "${BACKUP_SHA}" ]]; then
      echo "backup_sha256_file=${BACKUP_SHA}" >&2
      echo "backup_sha256=$(cut -d' ' -f1 "${BACKUP_SHA}" 2>/dev/null || true)" >&2
    fi
  fi
  if [[ -n "${POSTGRES_CONTAINER}" ]]; then
    echo "alembic_current_attempt:" >&2
    "${COMPOSE[@]}" run --rm --no-deps backend alembic current 2>&1 | tail -n 5 >&2 || true
  fi
  echo "Rollback is NOT automatic. See script footer notes." >&2
  exit 1
}

info() {
  echo "===== $* ====="
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command missing: $1"
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

psql_app_at() {
  docker exec "$POSTGRES_CONTAINER" \
    sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -v ON_ERROR_STOP=1 -c \"$1\""
}

count_table() {
  local table="$1"
  local exists
  exists="$(psql_app_at "SELECT to_regclass('public.${table}') IS NOT NULL")"
  if [[ "$exists" != "t" ]]; then
    echo "missing"
    return 0
  fi
  psql_app_at "SELECT COUNT(*) FROM ${table}"
}

read_env_file_value() {
  local key="$1"
  local file="$2"
  local line
  line="$(grep -E "^${key}=" "$file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf ''
    return 0
  fi
  printf '%s\n' "${line#*=}"
}

# Print shape only — never the secret value.
report_tmdb_env_shape() {
  local key="$1"
  local value
  value="$(read_env_file_value "$key" "$ENV_FILE")"
  if [[ -z "${value}" ]]; then
    echo "${key}: set=false, length=0, jwt_like=false"
    return 1
  fi
  local trimmed="${value#"${value%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  # strip optional surrounding quotes without echoing value
  if [[ "${trimmed}" == \"*\" && "${trimmed}" == *\" ]]; then
    trimmed="${trimmed:1:-1}"
  elif [[ "${trimmed}" == \'*\' && "${trimmed}" == *\' ]]; then
    trimmed="${trimmed:1:-1}"
  fi
  local len="${#trimmed}"
  local jwt_like=false
  if [[ "${trimmed}" == eyJ* ]]; then
    jwt_like=true
  fi
  echo "${key}: set=true, length=${len}, jwt_like=${jwt_like}"
  return 0
}

assert_tmdb_env_shapes() {
  info "TMDB env shape check (.env.dpl3 — values not printed)"
  local key_ok=0 token_ok=0
  report_tmdb_env_shape "TMDB_API_KEY" || true
  report_tmdb_env_shape "TMDB_API_READ_ACCESS_TOKEN" || true
  report_tmdb_env_shape "TMDB_LANGUAGE" || true
  report_tmdb_env_shape "TMDB_REGION" || true

  local api_key token
  api_key="$(read_env_file_value "TMDB_API_KEY" "$ENV_FILE")"
  token="$(read_env_file_value "TMDB_API_READ_ACCESS_TOKEN" "$ENV_FILE")"
  [[ -n "${api_key}" ]] || die "TMDB_API_KEY missing in .env.dpl3"
  [[ -n "${token}" ]] || die "TMDB_API_READ_ACCESS_TOKEN missing in .env.dpl3"

  local key_trim token_trim
  key_trim="${api_key#"${api_key%%[![:space:]]*}"}"
  key_trim="${key_trim%"${key_trim##*[![:space:]]}"}"
  token_trim="${token#"${token%%[![:space:]]*}"}"
  token_trim="${token_trim%"${token_trim##*[![:space:]]}"}"

  if [[ "${key_trim}" == \"*\" ]]; then key_trim="${key_trim:1:-1}"; fi
  if [[ "${token_trim}" == \"*\" ]]; then token_trim="${token_trim:1:-1}"; fi

  # Suspected swap: key looks like JWT and token is short (~32).
  if [[ "${key_trim}" == eyJ* ]] && [[ "${#token_trim}" -le 40 ]]; then
    die "TMDB_API_KEY / TMDB_API_READ_ACCESS_TOKEN appear swapped in .env.dpl3. Fix manually, then re-run. Script will not auto-swap."
  fi
  if [[ "${token_trim}" != eyJ* ]]; then
    die "TMDB_API_READ_ACCESS_TOKEN does not look like a JWT (expected eyJ...). Fix .env.dpl3 manually."
  fi
  if [[ "${key_trim}" == eyJ* ]]; then
    die "TMDB_API_KEY looks like a JWT. Expected ~32-char API key. Fix .env.dpl3 manually."
  fi
  if [[ "${#key_trim}" -lt 20 || "${#key_trim}" -gt 64 ]]; then
    die "TMDB_API_KEY length unexpected (${#key_trim}). Fix .env.dpl3 manually."
  fi
  echo "TMDB env shape: OK (bearer token preferred)"
}

curl_public() {
  local path="$1"
  local out="$2"
  curl -k -sS -o "$out" -w '%{http_code}' \
    --resolve "picknext.ramza.duckdns.org:443:127.0.0.1" \
    "${PUBLIC_BASE_URL}${path}"
}

python_json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
path, expr = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
# expr like a.b.c or a[0].b — limited dotted path
cur = data
for part in expr.split("."):
    if part.endswith("]") and "[" in part:
        name, idx = part[:-1].split("[", 1)
        if name:
            cur = cur[name]
        cur = cur[int(idx)]
    else:
        cur = cur[part]
if isinstance(cur, bool):
    print("true" if cur else "false")
elif cur is None:
    print("null")
else:
    print(cur)
PY
}

# ---------- start ----------
info "TMDB-1 remote apply (picknext-dpl3 only)"
echo "NOTE: Backend will be stopped during backup/migration — short API downtime expected."

require_cmd docker
require_cmd curl
require_cmd python3
require_cmd sha256sum
require_cmd date

[[ -d "$DEPLOY_ROOT" ]] || die "DEPLOY_ROOT missing: $DEPLOY_ROOT"
cd "$DEPLOY_ROOT"
[[ -f compose.yaml ]] || die "compose.yaml missing"
[[ -f compose.traefik.yaml ]] || die "compose.traefik.yaml missing"
[[ -f "$ENV_FILE" ]] || die "$ENV_FILE missing"

info "git working tree"
# .env.dpl3 / .env are expected local secrets (must not be committed).
# Other dirty tracked files still block apply.
GIT_DIRTY="$(
  git status --short --untracked-files=all |
    grep -Ev '^\?\? \.env(\.dpl3)?$' |
    grep -Ev '^!! ' ||
    true
)"
if [[ -n "${GIT_DIRTY}" ]]; then
  echo "${GIT_DIRTY}"
  die "Git working tree has unexpected changes. Reset or stash them, then re-run. (.env / .env.dpl3 alone are allowed.)"
fi
echo "git_clean=true (secrets env files ignored)"
echo "git_head=$(git rev-parse --short HEAD)"

info "docker / compose"
docker info >/dev/null 2>&1 || die "Docker not available"
docker compose version >/dev/null 2>&1 || die "Docker Compose not available"

info "compose config"
"${COMPOSE[@]}" config --quiet

info "postgres container identity"
mapfile -t PG_IDS < <(
  docker ps \
    --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
    --filter "label=com.docker.compose.service=postgres" \
    --format '{{.ID}}'
)
[[ "${#PG_IDS[@]}" -eq 1 ]] || die "Expected exactly 1 postgres container for ${PROJECT_NAME}, found ${#PG_IDS[@]}"
POSTGRES_CONTAINER="${PG_IDS[0]}"
PG_PROJECT="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$POSTGRES_CONTAINER")"
PG_SERVICE="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$POSTGRES_CONTAINER")"
[[ "$PG_PROJECT" == "$PROJECT_NAME" ]] || die "postgres project label mismatch: $PG_PROJECT"
[[ "$PG_SERVICE" == "postgres" ]] || die "postgres service label mismatch: $PG_SERVICE"
wait_label_healthy postgres 30

assert_tmdb_env_shapes

info "pre-migration alembic + counts"
CURRENT_BEFORE="$("${COMPOSE[@]}" run --rm --no-deps backend alembic current 2>/dev/null | grep -E '^[0-9a-z_]+' | head -n 1 || true)"
# alembic current may print "revision (head)" — take first token
CURRENT_BEFORE="$(echo "$CURRENT_BEFORE" | awk '{print $1}')"
HEADS="$("${COMPOSE[@]}" run --rm --no-deps backend alembic heads 2>/dev/null | grep -E '^[0-9a-z_]+' | head -n 1 || true)"
HEADS="$(echo "$HEADS" | awk '{print $1}')"
echo "alembic_current=${CURRENT_BEFORE}"
echo "alembic_heads=${HEADS}"
[[ "$CURRENT_BEFORE" == "$EXPECTED_CURRENT_BEFORE" ]] || die "Unexpected alembic current (want ${EXPECTED_CURRENT_BEFORE}, got ${CURRENT_BEFORE})"
[[ "$HEADS" == "$EXPECTED_HEAD" ]] || die "Unexpected alembic heads (want ${EXPECTED_HEAD}, got ${HEADS})"

USERS="$(count_table users)"
CATEGORIES="$(count_table categories)"
COLLECTIONS="$(count_table collections)"
ITEMS="$(count_table items)"
HISTORIES="$(count_table recommendation_history)"
echo "users=${USERS} categories=${CATEGORIES} collections=${COLLECTIONS} items=${ITEMS} histories=${HISTORIES}"
[[ "$USERS" == "$EXPECTED_USERS" ]] || die "users count mismatch"
[[ "$CATEGORIES" == "$EXPECTED_CATEGORIES" ]] || die "categories count mismatch"
[[ "$COLLECTIONS" == "$EXPECTED_COLLECTIONS" ]] || die "collections count mismatch"
[[ "$ITEMS" == "$EXPECTED_ITEMS" ]] || die "items count mismatch"
[[ "$HISTORIES" == "$EXPECTED_HISTORIES" ]] || die "recommendation_history count mismatch"

info "build backend image (before DB change)"
"${COMPOSE[@]}" build backend

info "stop backend (API write freeze)"
"${COMPOSE[@]}" stop backend
BACKEND_RUNNING=0
echo "Backend stopped. Frontend/Traefik remain up. Short /api downtime until recreate."

info "server DB backup (current 7202-item state)"
BACKUP_DIR="${DEPLOY_ROOT}/backups"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_BASENAME="picknext-dpl3-before-tmdb1-${STAMP}"
TMP_DUMP="/tmp/${BACKUP_BASENAME}.dump"
BACKUP_DUMP="${BACKUP_DIR}/${BACKUP_BASENAME}.dump"
BACKUP_SHA="${BACKUP_DIR}/${BACKUP_BASENAME}.sha256"
BACKUP_MANIFEST="${BACKUP_DIR}/${BACKUP_BASENAME}.manifest.env"

docker exec "$POSTGRES_CONTAINER" \
  sh -lc "pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --format=custom --no-owner --no-privileges -f '${TMP_DUMP}'"

DUMP_SIZE="$(docker exec "$POSTGRES_CONTAINER" sh -lc "stat -c%s '${TMP_DUMP}'")"
[[ "${DUMP_SIZE}" -gt 0 ]] || die "backup dump size is 0"
echo "container_tmp_dump_bytes=${DUMP_SIZE}"

docker cp "${POSTGRES_CONTAINER}:${TMP_DUMP}" "$BACKUP_DUMP"
HOST_SIZE="$(stat -c%s "$BACKUP_DUMP" 2>/dev/null || wc -c <"$BACKUP_DUMP")"
[[ "${HOST_SIZE}" -gt 0 ]] || die "host backup dump size is 0"
echo "host_dump_bytes=${HOST_SIZE}"

info "pg_restore --list integrity"
LIST_LINES="$(docker run --rm -v "${BACKUP_DIR}:/backup:ro" postgres:16-alpine \
  pg_restore --list "/backup/${BACKUP_BASENAME}.dump" | wc -l | tr -d ' ')"
[[ "${LIST_LINES}" -gt 10 ]] || die "pg_restore --list failed or too short (lines=${LIST_LINES})"
echo "restore_list_lines=${LIST_LINES}"

sha256sum "$BACKUP_DUMP" | awk '{print $1"  '"${BACKUP_BASENAME}.dump"'"}' >"$BACKUP_SHA"
SHA_VALUE="$(cut -d' ' -f1 "$BACKUP_SHA")"
GIT_COMMIT="$(git rev-parse HEAD)"
CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat >"$BACKUP_MANIFEST" <<EOF
BACKUP_FORMAT=custom
PURPOSE=before-tmdb1-migration
SOURCE_ALEMBIC_REVISION=${EXPECTED_CURRENT_BEFORE}
SOURCE_USERS=${EXPECTED_USERS}
SOURCE_CATEGORIES=${EXPECTED_CATEGORIES}
SOURCE_COLLECTIONS=${EXPECTED_COLLECTIONS}
SOURCE_ITEMS=${EXPECTED_ITEMS}
SOURCE_HISTORIES=${EXPECTED_HISTORIES}
TARGET_ALEMBIC_REVISION=${EXPECTED_HEAD}
BACKUP_FILENAME=${BACKUP_BASENAME}.dump
BACKUP_SHA256=${SHA_VALUE}
CREATED_AT_UTC=${CREATED_AT}
SOURCE_GIT_COMMIT=${GIT_COMMIT}
EOF

docker exec "$POSTGRES_CONTAINER" rm -f "$TMP_DUMP"
echo "backup_ok dump=${BACKUP_DUMP}"
echo "backup_sha256=${SHA_VALUE}"
echo "backup_manifest=${BACKUP_MANIFEST}"

info "alembic upgrade head"
if ! "${COMPOSE[@]}" run --rm --no-deps backend alembic upgrade head; then
  die "alembic upgrade head failed"
fi
MIGRATION_APPLIED=1

info "post-migration revision"
CURRENT_AFTER="$("${COMPOSE[@]}" run --rm --no-deps backend alembic current 2>/dev/null | grep -E '^[0-9a-z_]+' | head -n 1 | awk '{print $1}')"
HEADS_AFTER="$("${COMPOSE[@]}" run --rm --no-deps backend alembic heads 2>/dev/null | grep -E '^[0-9a-z_]+' | head -n 1 | awk '{print $1}')"
echo "alembic_current=${CURRENT_AFTER}"
echo "alembic_heads=${HEADS_AFTER}"
[[ "$CURRENT_AFTER" == "$EXPECTED_HEAD" ]] || die "post current mismatch"
[[ "$HEADS_AFTER" == "$EXPECTED_HEAD" ]] || die "post heads mismatch"
[[ "$CURRENT_AFTER" == "$HEADS_AFTER" ]] || die "current != heads"

info "post-migration counts + external nulls"
USERS2="$(count_table users)"
CATEGORIES2="$(count_table categories)"
COLLECTIONS2="$(count_table collections)"
ITEMS2="$(count_table items)"
HISTORIES2="$(count_table recommendation_history)"
echo "users=${USERS2} categories=${CATEGORIES2} collections=${COLLECTIONS2} items=${ITEMS2} histories=${HISTORIES2}"
[[ "$USERS2" == "$EXPECTED_USERS" ]] || die "post users mismatch"
[[ "$CATEGORIES2" == "$EXPECTED_CATEGORIES" ]] || die "post categories mismatch"
[[ "$COLLECTIONS2" == "$EXPECTED_COLLECTIONS" ]] || die "post collections mismatch"
[[ "$ITEMS2" == "$EXPECTED_ITEMS" ]] || die "post items mismatch"
[[ "$HISTORIES2" == "$EXPECTED_HISTORIES" ]] || die "post histories mismatch"

EXT_NONNULL="$(psql_app_at "SELECT COUNT(*) FROM items WHERE external_source IS NOT NULL OR external_id IS NOT NULL OR external_media_type IS NOT NULL")"
EXT_NULL="$(psql_app_at "SELECT COUNT(*) FROM items WHERE external_source IS NULL AND external_id IS NULL AND external_media_type IS NULL")"
echo "external_nonnull=${EXT_NONNULL} external_all_null=${EXT_NULL}"
[[ "$EXT_NONNULL" == "0" ]] || die "expected 0 non-null external identity rows"
[[ "$EXT_NULL" == "$EXPECTED_ITEMS" ]] || die "expected all items external identity NULL"

COLS="$(psql_app_at "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='items' AND column_name IN ('external_source','external_id','external_media_type','original_title','original_language','poster_path','backdrop_path','external_metadata_updated_at')")"
[[ "$COLS" == "8" ]] || die "expected 8 new item columns, got ${COLS}"

IDX="$(psql_app_at "SELECT COUNT(*) FROM pg_indexes WHERE tablename='items' AND indexname='uq_items_user_external_identity'")"
[[ "$IDX" == "1" ]] || die "uq_items_user_external_identity missing"
IDXDEF="$(psql_app_at "SELECT indexdef FROM pg_indexes WHERE indexname='uq_items_user_external_identity'")"
echo "$IDXDEF" | grep -q 'external_id IS NOT NULL' || die "partial unique index WHERE clause missing"

CK="$(psql_app_at "SELECT COUNT(*) FROM pg_constraint WHERE conname='ck_items_external_identity_all_or_none'")"
[[ "$CK" == "1" ]] || die "check constraint missing"

ORPHAN_ITEM_USER="$(psql_app_at "SELECT COUNT(*) FROM items i LEFT JOIN users u ON u.id=i.user_id WHERE u.id IS NULL")"
ORPHAN_ITEM_CAT="$(psql_app_at "SELECT COUNT(*) FROM items i LEFT JOIN categories c ON c.id=i.category_id WHERE c.id IS NULL")"
ORPHAN_ITEM_COL="$(psql_app_at "SELECT COUNT(*) FROM items i LEFT JOIN collections col ON col.id=i.collection_id WHERE i.collection_id IS NOT NULL AND col.id IS NULL")"
[[ "$ORPHAN_ITEM_USER" == "0" && "$ORPHAN_ITEM_CAT" == "0" && "$ORPHAN_ITEM_COL" == "0" ]] || die "orphan FK detected"

info "backend force-recreate"
"${COMPOSE[@]}" up -d --force-recreate backend
wait_label_healthy backend 60
BACKEND_RUNNING=1
wait_label_healthy frontend 30
wait_label_healthy postgres 10

info "existing API regression (public)"
TMPDIR_SMOKE="$(mktemp -d)"
trap 'rm -rf "${TMPDIR_SMOKE}"' EXIT

code="$(curl_public "/api/v1/health" "${TMPDIR_SMOKE}/health.json")"
[[ "$code" == "200" ]] || die "health HTTP ${code}"
CT="$(file -b --mime-type "${TMPDIR_SMOKE}/health.json" 2>/dev/null || echo application/json)"
echo "health http=${code}"

code="$(curl_public "/api/v1/items?page_size=1" "${TMPDIR_SMOKE}/items.json")"
[[ "$code" == "200" ]] || die "items HTTP ${code}"
ITEMS_TOTAL="$(python_json_get "${TMPDIR_SMOKE}/items.json" "total")"
EXT0="$(python_json_get "${TMPDIR_SMOKE}/items.json" "items[0].external_source")"
ITEM_ID="$(python_json_get "${TMPDIR_SMOKE}/items.json" "items[0].id")"
[[ "$ITEMS_TOTAL" == "$EXPECTED_ITEMS" ]] || die "items total API mismatch: ${ITEMS_TOTAL}"
[[ "$EXT0" == "null" ]] || die "items[0].external_source expected null"
echo "items http=200 total=${ITEMS_TOTAL} external_source=null"

code="$(curl_public "/api/v1/items/${ITEM_ID}" "${TMPDIR_SMOKE}/item.json")"
[[ "$code" == "200" ]] || die "item detail HTTP ${code}"
echo "item_detail http=200 id=${ITEM_ID}"

code="$(curl_public "/api/v1/collections?page_size=1" "${TMPDIR_SMOKE}/cols.json")"
[[ "$code" == "200" ]] || die "collections HTTP ${code}"
COL_TOTAL="$(python_json_get "${TMPDIR_SMOKE}/cols.json" "total")"
[[ "$COL_TOTAL" == "$EXPECTED_COLLECTIONS" ]] || die "collections total mismatch"
echo "collections http=200 total=${COL_TOTAL}"

code="$(curl_public "/api/v1/categories" "${TMPDIR_SMOKE}/cats.json")"
[[ "$code" == "200" ]] || die "categories HTTP ${code}"
CAT_COUNT="$(python3 - "${TMPDIR_SMOKE}/cats.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
cats=d["categories"] if isinstance(d,dict) and "categories" in d else d
print(len(cats))
PY
)"
[[ "$CAT_COUNT" == "$EXPECTED_CATEGORIES" ]] || die "categories count mismatch"
echo "categories http=200 count=${CAT_COUNT}"

info "TMDB Live Smoke (summaries only)"
code="$(curl_public "/api/v1/tmdb/status" "${TMPDIR_SMOKE}/tmdb_status.json")"
[[ "$code" == "200" ]] || die "tmdb status HTTP ${code}"
ST_STATUS="$(python_json_get "${TMPDIR_SMOKE}/tmdb_status.json" "status")"
ST_CFG="$(python_json_get "${TMPDIR_SMOKE}/tmdb_status.json" "configured")"
ST_AVAIL="$(python_json_get "${TMPDIR_SMOKE}/tmdb_status.json" "available")"
ST_AUTH="$(python_json_get "${TMPDIR_SMOKE}/tmdb_status.json" "auth_mode")"
ST_LANG="$(python_json_get "${TMPDIR_SMOKE}/tmdb_status.json" "language")"
ST_REG="$(python_json_get "${TMPDIR_SMOKE}/tmdb_status.json" "region")"
echo "tmdb_status http=200 status=${ST_STATUS} configured=${ST_CFG} available=${ST_AVAIL} auth_mode=${ST_AUTH} language=${ST_LANG} region=${ST_REG}"
[[ "$ST_STATUS" == "AVAILABLE" ]] || die "tmdb status not AVAILABLE"
[[ "$ST_CFG" == "true" && "$ST_AVAIL" == "true" ]] || die "tmdb not configured/available"
[[ "$ST_AUTH" == "bearer" ]] || die "expected auth_mode=bearer"
grep -Eiq 'eyJ|Bearer |api_key=' "${TMPDIR_SMOKE}/tmdb_status.json" && die "secret-like content in tmdb status JSON" || true

# URL-encode via python
MOVIE_Q="$(python3 -c 'import urllib.parse; print(urllib.parse.urlencode({"query":"오펜하이머","media_type":"movie","page":"1"}))')"
code="$(curl_public "/api/v1/tmdb/search?${MOVIE_Q}" "${TMPDIR_SMOKE}/movie.json")"
[[ "$code" == "200" ]] || die "movie search HTTP ${code}"
M_RET="$(python_json_get "${TMPDIR_SMOKE}/movie.json" "returned_count")"
M_ID="$(python_json_get "${TMPDIR_SMOKE}/movie.json" "results[0].tmdb_id")"
M_TITLE="$(python_json_get "${TMPDIR_SMOKE}/movie.json" "results[0].title")"
M_MEDIA="$(python_json_get "${TMPDIR_SMOKE}/movie.json" "results[0].media_type")"
M_POSTER="$(python_json_get "${TMPDIR_SMOKE}/movie.json" "results[0].poster_url")"
M_REG="$(python_json_get "${TMPDIR_SMOKE}/movie.json" "results[0].registered")"
M_POSTER_HTTPS=false
[[ "${M_POSTER}" == https://* ]] && M_POSTER_HTTPS=true
echo "movie_search http=200 returned=${M_RET} tmdb_id=${M_ID} title=${M_TITLE} media=${M_MEDIA} poster_https=${M_POSTER_HTTPS} registered=${M_REG}"
[[ "$M_MEDIA" == "movie" ]] || die "movie search media_type"
[[ "$M_REG" == "false" ]] || die "movie registered expected false"
[[ "$M_POSTER_HTTPS" == "true" ]] || die "movie poster_url not https"

TV_Q="$(python3 -c 'import urllib.parse; print(urllib.parse.urlencode({"query":"오징어 게임","media_type":"tv","page":"1"}))')"
code="$(curl_public "/api/v1/tmdb/search?${TV_Q}" "${TMPDIR_SMOKE}/tv.json")"
[[ "$code" == "200" ]] || die "tv search HTTP ${code}"
T_ID="$(python_json_get "${TMPDIR_SMOKE}/tv.json" "results[0].tmdb_id")"
T_TITLE="$(python_json_get "${TMPDIR_SMOKE}/tv.json" "results[0].title")"
T_MEDIA="$(python_json_get "${TMPDIR_SMOKE}/tv.json" "results[0].media_type")"
echo "tv_search http=200 tmdb_id=${T_ID} title=${T_TITLE} media=${T_MEDIA}"
[[ "$T_MEDIA" == "tv" ]] || die "tv search media_type"

ALL_Q="$(python3 -c 'import urllib.parse; print(urllib.parse.urlencode({"query":"배트맨","media_type":"all","page":"1"}))')"
code="$(curl_public "/api/v1/tmdb/search?${ALL_Q}" "${TMPDIR_SMOKE}/multi.json")"
[[ "$code" == "200" ]] || die "multi search HTTP ${code}"
A_RET="$(python_json_get "${TMPDIR_SMOKE}/multi.json" "returned_count")"
A_UP="$(python_json_get "${TMPDIR_SMOKE}/multi.json" "upstream_total_results")"
PERSON_COUNT="$(python3 - "${TMPDIR_SMOKE}/multi.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
print(sum(1 for r in d.get("results") or [] if r.get("media_type")=="person"))
PY
)"
echo "multi_search http=200 returned=${A_RET} upstream_total_results=${A_UP} person=${PERSON_COUNT}"
[[ "$PERSON_COUNT" == "0" ]] || die "person results must be 0"

code="$(curl_public "/api/v1/tmdb/details/movie/${M_ID}" "${TMPDIR_SMOKE}/detail.json")"
[[ "$code" == "200" ]] || die "detail HTTP ${code}"
D_TITLE="$(python_json_get "${TMPDIR_SMOKE}/detail.json" "title")"
D_CAST="$(python3 - "${TMPDIR_SMOKE}/detail.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
print(len(d.get("cast") or []))
PY
)"
D_POSTER="$(python_json_get "${TMPDIR_SMOKE}/detail.json" "poster_url")"
D_REG="$(python_json_get "${TMPDIR_SMOKE}/detail.json" "registered")"
D_HTTPS=false
[[ "${D_POSTER}" == https://* || "${D_POSTER}" == "null" ]] && D_HTTPS=true
echo "detail http=200 tmdb_id=${M_ID} title=${D_TITLE} cast=${D_CAST} poster_ok=${D_HTTPS} registered=${D_REG}"
[[ "${D_CAST}" -le 10 ]] || die "cast exceeds 10"
[[ "$D_REG" == "false" ]] || die "detail registered expected false"
grep -Eiq 'eyJ|Bearer |api_key=' "${TMPDIR_SMOKE}/detail.json" && die "secret-like content in detail JSON" || true
echo "include_adult=true verified by automated Mock tests (not printed as live URL)"

info "router / container check"
"${COMPOSE[@]}" ps
code="$(curl_public "/api/not-existing" "${TMPDIR_SMOKE}/api404.txt")"
# Backend FastAPI JSON 404 expected (not SPA HTML)
head -c 200 "${TMPDIR_SMOKE}/api404.txt" | grep -qi '<html' && die "/api/not-existing returned HTML (frontend leak)"
echo "api_not_existing http=${code} (JSON body expected, not HTML)"
[[ "$code" == "404" ]] || echo "WARN: expected 404 for /api/not-existing, got ${code}"

info "TMDB-1 remote apply PASS"
echo "backup_dump=${BACKUP_DUMP}"
echo "backup_sha256=${SHA_VALUE}"
echo "alembic_current=${CURRENT_AFTER}"
echo "items=${ITEMS2}"
echo "migration_applied=1"
echo "backend_running=1"
echo
echo "Rollback is NOT automatic."
echo "If you must reverse schema only (user approval required):"
echo "  \"\${COMPOSE[@]}\" run --rm --no-deps backend alembic downgrade ${EXPECTED_CURRENT_BEFORE}"
echo "If data restore from this backup is needed, use a dedicated restore procedure with:"
echo "  ${BACKUP_DUMP}"
exit 0
