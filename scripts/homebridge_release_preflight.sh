#!/usr/bin/env bash
# Read-only HomeBridge release preflight. Does not pull code, run migrations,
# restart containers, or modify files. Run from the Oracle host as ubuntu.
set -uo pipefail

ROOT="/opt/homebridge"
APP="$ROOT/app"
COMPOSE="$ROOT/docker-compose.yml"
CONTAINER="homebridge"
PUBLIC_URL="https://homebridge.cyphertech.co.zw"

section() { printf '\n=== %s ===\n' "$1"; }
status() { printf '%-34s %s\n' "$1" "$2"; }

section "Host and disk"
hostname
df -h "$ROOT" 2>/dev/null || true

section "Repository"
if [ -d "$APP/.git" ]; then
  status "HEAD" "$(git -C "$APP" rev-parse --short HEAD 2>/dev/null || echo unavailable)"
  status "Branch" "$(git -C "$APP" branch --show-current 2>/dev/null || echo unavailable)"
  if [ -z "$(git -C "$APP" status --porcelain 2>/dev/null)" ]; then
    status "Working tree" "clean"
  else
    status "Working tree" "has local changes (review before deployment)"
    git -C "$APP" status --short
  fi
else
  status "Repository" "not found at $APP"
fi

section "Docker Compose"
if [ -f "$COMPOSE" ]; then
  docker compose -f "$COMPOSE" config --quiet
  status "Compose configuration" "$([ "$?" -eq 0 ] && echo valid || echo invalid)"
  docker compose -f "$COMPOSE" ps
else
  status "Compose file" "not found at $COMPOSE"
fi

section "HomeBridge container"
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  docker inspect "$CONTAINER" --format 'State={{.State.Status}} Image={{.Config.Image}} WorkingDir={{.Config.WorkingDir}}'
  echo "Mounted volumes:"
  docker inspect "$CONTAINER" --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
  echo "Relevant environment variable names (values intentionally hidden):"
  docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | awk -F= '{print $1"=<set>"}' \
    | grep -E '^(FLASK_ENV|SECRET_KEY|DATABASE_URL|PRIVATE_UPLOAD_FOLDER|ADMIN_EMAIL)=' || true
  private_path="$(docker exec "$CONTAINER" sh -lc 'printf "%s" "${PRIVATE_UPLOAD_FOLDER:-}"' 2>/dev/null || true)"
  if [ -n "$private_path" ]; then
    status "PRIVATE_UPLOAD_FOLDER" "configured"
    docker exec "$CONTAINER" stat -c 'Mode=%a Owner=%U:%G Path=%n' "$private_path" 2>/dev/null || echo "Private directory not present or not readable"
  else
    status "PRIVATE_UPLOAD_FOLDER" "NOT SET in container environment"
  fi
else
  status "Container" "$CONTAINER not found"
fi

section "HTTP health checks"
for target in "http://127.0.0.1:5001/properties" "$PUBLIC_URL/properties"; do
  code="$(curl --silent --show-error --output /dev/null --max-time 12 --write-out '%{http_code}' "$target" 2>/dev/null || echo unavailable)"
  status "$target" "$code"
done

section "Nginx"
if command -v nginx >/dev/null 2>&1; then
  sudo nginx -t 2>&1 || true
  for dir in /etc/nginx/sites-enabled /etc/nginx/conf.d; do
    [ -d "$dir" ] || continue
    for file in "$dir"/*; do
      [ -f "$file" ] || continue
      if sudo grep -q 'homebridge.cyphertech.co.zw' "$file" 2>/dev/null; then
        echo "HomeBridge Nginx file: $file"
        sudo grep -nE 'server_name|location|proxy_pass|root|alias' "$file" || true
      fi
    done
  done
else
  status "Nginx" "not installed or not on PATH"
fi

section "Legacy public payment proofs"
LEGACY="$APP/app/static/uploads/proofs"
if [ -d "$LEGACY" ]; then
  count="$(find "$LEGACY" -maxdepth 1 -type f 2>/dev/null | wc -l)"
  status "Legacy proof files" "$count"
  sample="$(find "$LEGACY" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | head -n 1)"
  if [ -n "$sample" ]; then
    code="$(curl --silent --output /dev/null --max-time 12 --write-out '%{http_code}' "$PUBLIC_URL/static/uploads/proofs/$sample" 2>/dev/null || echo unavailable)"
    status "Sample legacy proof HTTP status" "$code (404 expected; file name hidden)"
  fi
else
  status "Legacy proof directory" "not found"
fi

section "Existing backups"
if [ -d "$ROOT/backups" ]; then
  find "$ROOT/backups" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %s bytes %f\n' 2>/dev/null | sort | tail -n 10
else
  status "Backup directory" "not found at $ROOT/backups"
fi

printf '\nPreflight complete. This script made no deployment or database changes.\n'
