#!/usr/bin/env bash
#
# FLOWRA — Idempotent deploy script.
# Runs on the Droplet, invoked by GitHub Actions on each push (or Run-workflow).
#
#   ./deploy/deploy.sh false   # full build + restart (default)
#   ./deploy/deploy.sh true    # restart only (no git pull, no build)
#
set -euo pipefail

RESTART_ONLY="${1:-false}"
APP_DIR="/var/www/Flowra_insights/tally-report"
cd "$APP_DIR"

log() { echo -e "\033[1;34m▸ $*\033[0m"; }

if [ "$RESTART_ONLY" = "false" ]; then
  log "Pulling latest code…"
  git fetch --all --prune
  git reset --hard origin/main

  log "Backend deps (Python venv)…"
  python3.11 -m venv .venv 2>/dev/null || true
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip wheel >/dev/null
  pip install -r backend/requirements.txt
  # Emergent LLM SDK isn't on PyPI — install from Emergent's mirror.
  pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || true
  deactivate

  log "Frontend build (Yarn)…"
  cd frontend
  yarn install --frozen-lockfile
  yarn build
  cd ..

  log "Syncing frontend build → /var/www/flowra"
  sudo mkdir -p /var/www/flowra
  sudo rsync -a --delete frontend/build/ /var/www/flowra/
fi

log "Restarting backend…"
sudo systemctl restart flowra-backend
sleep 3

log "Health-check backend…"
for i in {1..10}; do
  if curl -sf http://127.0.0.1:8001/api/health | grep -q '"ok":true'; then
    log "Backend healthy ✅"
    break
  fi
  log "Waiting for backend (try $i/10)…"
  sleep 2
done

log "Reloading nginx…"
sudo systemctl reload nginx

log "Done ✅"
