#!/bin/bash
# rebuild-and-deploy-vps.sh — LeCarbu.fr
# Executed daily at 02:30 via crontab on Contabo VPS
set -euo pipefail

LOG="/var/log/lecarbu-rebuild.log"
APP_DIR="/var/www/lecarbu.fr"
CF_PROJECT="lecarbu"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
if [ -d "${HOME:-/root}/.nvm" ]; then
  export NVM_DIR="${HOME:-/root}/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "============================================================"
log "Starting LeCarbu.fr Daily Ingestion & Cloudflare Deploy..."

cd "$APP_DIR"

# 1. Update git code
if [ -d .git ]; then
  log "Fetching latest code from GitHub..."
  git fetch origin main || true
  git reset --hard origin/main || true
fi

# 2. Ingest fresh French Government Fuel Data
log "Ingesting latest French Government Open Fuel Data & generating datasets..."
python3 scripts/build-fr-database.py 2>&1 | tee -a "$LOG"

# 3. Dependencies
if [ ! -d "node_modules" ]; then
  log "Installing npm dependencies..."
  npm install --legacy-peer-deps 2>&1 | tee -a "$LOG"
fi

# 4. Build 18,900+ static pages
log "Building Astro static site (18,900+ pages)..."
NODE_OPTIONS="--max-old-space-size=4096" npm run build 2>&1 | tee -a "$LOG"

# 5. Deploy to Cloudflare Pages
log "Deploying to Cloudflare Pages project=$CF_PROJECT ..."
export CLOUDFLARE_API_KEY="${CLOUDFLARE_API_KEY:-9578b8b72ddb8947067606c42533c784203b6}"
export CLOUDFLARE_EMAIL="${CLOUDFLARE_EMAIL:-romolo.velati@gmail.com}"
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-383050c9ba92a1ab1144bc18d44f586c}"

npx --yes wrangler@4 pages deploy dist \
  --project-name="$CF_PROJECT" \
  --branch=main \
  --commit-dirty=true 2>&1 | tee -a "$LOG"

# 6. IndexNow Ping
log "Pinging IndexNow for Bing & search engines..."
node scripts/notify-indexnow.js 2>&1 | tee -a "$LOG" || true

log "LeCarbu.fr Rebuild & Deploy SUCCESS!"
log "============================================================"
