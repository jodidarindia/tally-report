#!/bin/bash
# ------------------------------------------------------------------
# FLOWRA — One-command droplet update
# ------------------------------------------------------------------
# Runs on the DigitalOcean droplet (NOT on Emergent).
# Assumes the standard layout from FLOWRA_Deployment_Guide.md:
#   • Repo path:  /home/flowra/app
#   • OS user:    flowra
#   • Backend:    PM2 process name "flowra-backend"
#   • Frontend:   Nginx serves /home/flowra/app/frontend/build
#
# Why is this needed?
#   `Save to Github` from Emergent pushes to your GitHub repo. It does
#   NOT touch the droplet. The droplet has to be told to pull the new
#   code and rebuild. This script does that in one shot.
#
# Usage (as root or via sudo):
#   bash /home/flowra/app/scripts/update_droplet.sh
# Or from any working dir:
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/scripts/update_droplet.sh | sudo bash
#
# Safe to re-run — idempotent.
# ------------------------------------------------------------------
set -euo pipefail

APP_DIR="${APP_DIR:-/home/flowra/app}"
APP_USER="${APP_USER:-flowra}"
BRANCH="${BRANCH:-main}"
PM2_NAME="${PM2_NAME:-flowra-backend}"

log() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
warn() { printf "\n\033[1;33m! %s\033[0m\n" "$*"; }
die() { printf "\n\033[1;31m✗ %s\033[0m\n" "$*"; exit 1; }

# ---------- Pre-flight ----------
[ -d "$APP_DIR/.git" ] || die "Repo not found at $APP_DIR. Set APP_DIR=... if your layout differs."
command -v git >/dev/null || die "git not installed"
command -v yarn >/dev/null || die "yarn not installed (npm install -g yarn)"
command -v pm2 >/dev/null || die "pm2 not installed (npm install -g pm2)"

# We must be root/sudo to restart nginx at the end.
if [ "$(id -u)" -ne 0 ]; then
  die "Please run with sudo (needed to restart nginx). Try:  sudo bash $0"
fi

cd "$APP_DIR"

# ---------- Pull code as the app user (keeps file ownership sane) ----------
log "Pulling latest from origin/$BRANCH"
sudo -u "$APP_USER" git fetch --all --prune
sudo -u "$APP_USER" git reset --hard "origin/$BRANCH"

# Show what changed so the operator sees Academy / other updates land
log "Newest 5 commits now on the droplet:"
sudo -u "$APP_USER" git log --oneline -5

# ---------- Backend ----------
if [ -d "$APP_DIR/backend" ]; then
  log "Updating backend dependencies"
  sudo -u "$APP_USER" bash -c "cd '$APP_DIR/backend' && \
      source venv/bin/activate && \
      pip install -q -r requirements.txt"
fi

# ---------- Frontend rebuild ----------
if [ -d "$APP_DIR/frontend" ]; then
  log "Rebuilding frontend (this takes 2–4 minutes on a 2 GB droplet)"
  sudo -u "$APP_USER" bash -c "cd '$APP_DIR/frontend' && \
      yarn install --frozen-lockfile && \
      CI=false yarn build"
  # Public tutorial assets (Academy lesson mp4s / slides / voiceovers)
  # ship under frontend/public/tutorials — CRA copies them into build/
  # automatically as long as `yarn build` was invoked above.
  if [ -d "$APP_DIR/frontend/build/tutorials" ]; then
    log "Academy lesson assets present in build/ ✓"
  else
    warn "No tutorials/ folder in build output — check frontend/public/tutorials exists in the repo."
  fi
fi

# ---------- Restart processes ----------
log "Restarting backend via PM2"
sudo -u "$APP_USER" pm2 restart "$PM2_NAME" --update-env || {
  warn "PM2 process '$PM2_NAME' not found, starting fresh"
  sudo -u "$APP_USER" bash -c "cd '$APP_DIR/backend' && \
      source venv/bin/activate && \
      pm2 start 'uvicorn server:app --host 0.0.0.0 --port 8001' --name '$PM2_NAME'"
}
sudo -u "$APP_USER" pm2 save

log "Reloading Nginx (to pick up new static files)"
nginx -t
systemctl reload nginx

# ---------- Smoke check ----------
log "Backend health check"
if curl -fsS --max-time 10 http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
  echo "   ✓ /api/health OK"
else
  warn "Backend health endpoint did not respond. Inspect: pm2 logs $PM2_NAME --lines 40"
fi

log "DONE — droplet is now on the latest commit."
echo
echo "   Verify in the browser:"
echo "     1) Hard refresh with Ctrl-Shift-R (or open incognito) to bypass the browser cache."
echo "     2) Check the What's New panel on the useradmin dashboard for the newest entry date."
echo "     3) Open FLOWRA Academy — new lessons should be listed."
echo
