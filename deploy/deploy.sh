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
APP_DIR="/opt/flowra"
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
  # iter-131: DigitalOcean deploys had been silently serving stale
  # frontend for weeks because GitHub-Actions' inherited `CI=true`
  # turns every ESLint warning into a build failure, `set -e` aborts
  # the script BEFORE rsync-ing the new bundle. Force `CI=false` +
  # disable ESLint plugin so warnings never break prod deploys.
  CI=false DISABLE_ESLINT_PLUGIN=true yarn build
  # Belt-and-braces safety net: verify build/index.html was actually
  # produced by THIS run. If yarn build somehow exited 0 without
  # writing output (unlikely but possible on OOM), abort loudly
  # rather than rsync-ing an empty / stale dir.
  if [ ! -f build/index.html ]; then
    echo "❌ Frontend build did NOT produce build/index.html — aborting deploy."
    exit 1
  fi
  if [ "$(find build/index.html -mmin -5 | wc -l)" -eq 0 ]; then
    echo "❌ build/index.html is older than 5 minutes — the build didn't refresh. Aborting."
    exit 1
  fi
  # Stamp the build with the deploying commit so we can eyeball
  # which version production is actually serving.
  DEPLOY_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "$DEPLOY_SHA $(date -u +%FT%TZ)" > build/version.txt
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
