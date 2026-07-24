#!/usr/bin/env bash
# PickNext DPL-3 remote investigation — paste on ramzaminiserver as user ramza
# Do not paste passwords into this script.
set -euo pipefail

echo "===== identity ====="
whoami
hostname
pwd
uname -a
date

echo "===== docker access ====="
groups
docker version --format 'Server={{.Server.Version}} Client={{.Client.Version}}' || true
docker compose version || true
docker info >/dev/null && echo docker-access-ok || echo docker-access-FAIL

echo "===== traefik container ====="
docker ps --filter "name=^/traefik$" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

echo "===== traefik cmd ====="
docker inspect traefik --format '{{range .Config.Cmd}}{{println .}}{{end}}' 2>/dev/null || echo "traefik inspect failed"

echo "===== traefik labels (truncated) ====="
docker inspect traefik --format '{{json .Config.Labels}}' 2>/dev/null | head -c 4000 || true
echo

echo "===== proxy network ====="
docker network inspect proxy --format 'Name={{.Name}} Driver={{.Driver}}' 2>/dev/null || echo "proxy network MISSING"
docker network inspect proxy --format '{{range $id, $c := .Containers}}{{println $c.Name}}{{end}}' 2>/dev/null || true

echo "===== compose projects / volumes (names only) ====="
docker compose ls || true
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Networks}}"
echo "--- volumes matching picknext ---"
docker volume ls | grep -i picknext || echo "(no picknext volumes)"

echo "===== router label collision check ====="
docker ps -q | xargs -r docker inspect --format '{{.Name}} {{json .Config.Labels}}' \
  | grep -E 'picknext-web|picknext-api|picknext-web-service|picknext-api-service' \
  || echo "(no picknext router label collision)"

echo "===== DNS ====="
getent ahostsv4 picknext.ramza.duckdns.org || true
getent ahostsv4 ramza.duckdns.org || true
dig +short picknext.ramza.duckdns.org A 2>/dev/null || true
dig +short ramza.duckdns.org A 2>/dev/null || true

echo "===== done ====="
