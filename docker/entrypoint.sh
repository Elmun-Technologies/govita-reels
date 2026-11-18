#!/usr/bin/env bash
set -euo pipefail
cd /app

# Bind-mount qilingan repo'da node_modules bo'lmasa (yoki eskirgan bo'lsa) o'rnatamiz
if [ ! -d node_modules/hyperframes ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  echo "[entrypoint] npm ci..."
  npm ci --no-audit --no-fund
fi
mkdir -p runs bank data

# Claude Code birinchi ishga tushishda onboarding so'ramasligi uchun
if [ ! -f "$HOME/.claude.json" ]; then
  echo '{"hasCompletedOnboarding": true}' > "$HOME/.claude.json"
fi

case "${1:-cron}" in
  cron)
    echo "[entrypoint] supercronic ishga tushdi (TZ=$TZ)"
    exec supercronic -passthrough-logs docker/crontab
    ;;
  bot)
    exec python3 -m agency.bot_listener
    ;;
  run)
    shift
    exec bin/run-daily "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
