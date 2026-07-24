#!/usr/bin/env bash
# PickNext DPL-3 remote deploy — run on ramzaminiserver after archive upload
# Usage:
#   bash dpl3-remote-deploy.sh [/home/ramza/apps/picknext-dpl3/picknext-dpl3.tar.gz]
# Does not print secrets. Does not use sudo password automation.
set -euo pipefail

DEPLOY_ROOT="${HOME}/apps/picknext-dpl3"
ARCHIVE="${1:-${DEPLOY_ROOT}/picknext-dpl3.tar.gz}"
RELEASE_ID="$(date +%Y%m%d-%H%M%S)"
RELEASE_DIR="${DEPLOY_ROOT}/releases/${RELEASE_ID}"
COMPOSE=(docker compose --env-file .env.dpl3 -p picknext-dpl3 -f compose.yaml -f compose.traefik.yaml)

if [[ ! -f "${ARCHIVE}" ]]; then
  echo "FAIL: archive not found: ${ARCHIVE}" >&2
  exit 1
fi

mkdir -p "${RELEASE_DIR}"
tar -xzf "${ARCHIVE}" -C "${RELEASE_DIR}"
cd "${RELEASE_DIR}"
echo "RELEASE_DIR=${RELEASE_DIR}"

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
  echo "CORS_ORIGINS=https://picknext.ramza.duckdns.org"
  echo "SECRET_KEY=${SECRET_KEY}"
  echo "POSTGRES_HOST=postgres"
  echo "POSTGRES_PORT=5432"
  echo "POSTGRES_DB=picknext"
  echo "POSTGRES_USER=picknext"
  echo "POSTGRES_PASSWORD=${DB_PASSWORD}"
  echo "VITE_API_BASE_URL=/api/v1"
  echo "PICKNEXT_FRONTEND_IMAGE=picknext-frontend:dpl3"
  echo "PICKNEXT_HOST=picknext.ramza.duckdns.org"
  echo "SEED_USER_EMAIL=dpl3@picknext.local"
  echo "SEED_USER_DISPLAY_NAME=DPL3 User"
  echo "SEED_USER_PASSWORD=${SEED_PASSWORD}"
} > .env.dpl3
chmod 600 .env.dpl3
# compose.yaml services use env_file: .env
ln -sfn .env.dpl3 .env
unset DB_PASSWORD SECRET_KEY SEED_PASSWORD

echo "===== compose config ====="
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" config > /tmp/picknext-dpl3-compose.yaml
# Drop secret-bearing lines from on-screen summary
grep -E 'Host\(|picknext-|priority|server.port|name:|external:|published' /tmp/picknext-dpl3-compose.yaml | head -n 80 || true

echo "===== build ====="
"${COMPOSE[@]}" build

echo "===== down (no -v) ====="
"${COMPOSE[@]}" down --remove-orphans || true

echo "===== up ====="
"${COMPOSE[@]}" up -d

echo "===== wait health ====="
for i in $(seq 1 60); do
  "${COMPOSE[@]}" ps
  if "${COMPOSE[@]}" ps | grep -E 'frontend|backend|postgres' | grep -qi '(healthy)'; then
    # Require all three healthy when possible
    healthy_count="$("${COMPOSE[@]}" ps --format json 2>/dev/null | grep -c '"Healthy"' || true)"
    if [[ "${healthy_count}" -ge 3 ]] || "${COMPOSE[@]}" ps | grep -c 'healthy' | grep -Eq '^[3-9]'; then
      break
    fi
  fi
  sleep 5
done
"${COMPOSE[@]}" ps

echo "===== migrate + seed ====="
"${COMPOSE[@]}" exec -T backend alembic upgrade head
"${COMPOSE[@]}" exec -T backend python -m app.services.seed

echo "===== isolation ====="
docker ps --filter "label=com.docker.compose.project=picknext-dpl3" --format 'table {{.Names}}\t{{.Status}}\t{{.Networks}}'
docker volume ls --filter "label=com.docker.compose.project=picknext-dpl3"

FRONTEND_CONTAINER="$(docker ps --filter "label=com.docker.compose.project=picknext-dpl3" --filter "label=com.docker.compose.service=frontend" --format '{{.Names}}' | head -n 1)"
BACKEND_CONTAINER="$(docker ps --filter "label=com.docker.compose.project=picknext-dpl3" --filter "label=com.docker.compose.service=backend" --format '{{.Names}}' | head -n 1)"
POSTGRES_CONTAINER="$(docker ps --filter "label=com.docker.compose.project=picknext-dpl3" --filter "label=com.docker.compose.service=postgres" --format '{{.Names}}' | head -n 1)"

echo "FRONTEND=${FRONTEND_CONTAINER}"
echo "BACKEND=${BACKEND_CONTAINER}"
echo "POSTGRES=${POSTGRES_CONTAINER}"

docker inspect "${FRONTEND_CONTAINER}" --format 'frontend networks={{json .NetworkSettings.Networks}}'
docker inspect "${BACKEND_CONTAINER}" --format 'backend networks={{json .NetworkSettings.Networks}}'
docker inspect "${POSTGRES_CONTAINER}" --format 'postgres networks={{json .NetworkSettings.Networks}}'
docker inspect "${POSTGRES_CONTAINER}" --format '{{range .Mounts}}{{println .Name .Source "->" .Destination}}{{end}}'

echo "===== labels (no secrets) ====="
docker inspect "${FRONTEND_CONTAINER}" --format '{{index .Config.Labels "traefik.http.routers.picknext-web.rule"}} priority={{index .Config.Labels "traefik.http.routers.picknext-web.priority"}} port={{index .Config.Labels "traefik.http.services.picknext-web-service.loadbalancer.server.port"}}'
docker inspect "${BACKEND_CONTAINER}" --format '{{index .Config.Labels "traefik.http.routers.picknext-api.rule"}} priority={{index .Config.Labels "traefik.http.routers.picknext-api.priority"}} port={{index .Config.Labels "traefik.http.services.picknext-api-service.loadbalancer.server.port"}}'

echo "===== proxy internal ====="
docker run --rm --network proxy curlimages/curl:8.12.1 -fsS "http://${FRONTEND_CONTAINER}:80/health" || \
  docker exec "${FRONTEND_CONTAINER}" wget -q -O - http://127.0.0.1/health
echo
docker run --rm --network proxy curlimages/curl:8.12.1 -fsS "http://${BACKEND_CONTAINER}:8000/api/v1/health" || \
  docker exec "${BACKEND_CONTAINER}" curl -fsS http://127.0.0.1:8000/api/v1/health
echo

echo "===== routing via traefik (--resolve) ====="
curl -sS -I --resolve picknext.ramza.duckdns.org:80:127.0.0.1 http://picknext.ramza.duckdns.org/ | head -n 20
curl -sS -I --resolve picknext.ramza.duckdns.org:80:127.0.0.1 http://picknext.ramza.duckdns.org/api/v1/health | head -n 20

curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
  https://picknext.ramza.duckdns.org/ -o /tmp/picknext-dpl3-index.html | head -n 25
grep -Ei '<title>|id="root"|PickNext' /tmp/picknext-dpl3-index.html || true

curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
  https://picknext.ramza.duckdns.org/api/v1/health -o /tmp/picknext-dpl3-health.json | head -n 25
head -c 300 /tmp/picknext-dpl3-health.json; echo

for path in /api/v1/categories /api/v1/items /api/v1/collections; do
  echo "----- ${path} -----"
  curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
    "https://picknext.ramza.duckdns.org${path}" -o "/tmp/picknext-dpl3${path//\//-}.json" | head -n 15
  head -c 120 "/tmp/picknext-dpl3${path//\//-}.json"; echo
done

echo "===== api 404 priority ====="
curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
  https://picknext.ramza.duckdns.org/api/not-existing -o /tmp/picknext-dpl3-api-404.txt | head -n 20
head -c 200 /tmp/picknext-dpl3-api-404.txt; echo

echo "===== spa ====="
curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
  https://picknext.ramza.duckdns.org/items -o /tmp/picknext-dpl3-items-page.html | head -n 15
grep -Ei '<title>|id="root"' /tmp/picknext-dpl3-items-page.html || true

echo "===== pwa ====="
curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
  https://picknext.ramza.duckdns.org/manifest.webmanifest -o /tmp/picknext-dpl3-manifest.json | head -n 20
curl -k -sS -D - --resolve picknext.ramza.duckdns.org:443:127.0.0.1 \
  https://picknext.ramza.duckdns.org/sw.js -o /tmp/picknext-dpl3-sw.js | head -n 20

echo "===== cert (public, may fail until ACME) ====="
curl -sS -I https://picknext.ramza.duckdns.org/ 2>&1 | head -n 20 || true

echo "===== traefik log snippet ====="
docker logs traefik --since 15m 2>&1 | grep -Ei 'picknext|error|acme|certificate' | tail -n 40 || true

echo "===== DONE deploy smoke ====="
echo "RELEASE_DIR=${RELEASE_DIR}"
echo "Next: paste this full output back to Cursor. Secrets are in .env.dpl3 (chmod 600) — do not paste that file."
