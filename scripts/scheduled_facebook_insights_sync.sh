#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/snail/.openclaw/workspace/affilipilot"
cd "$ROOT"
export PATH="/home/snail/.npm-global/bin:/home/snail/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

mkdir -p "$ROOT/logs"
log_file="$ROOT/logs/facebook-insights-sync.log"
{
  echo "===== $(date --iso-8601=seconds) facebook insights sync ====="
  python3 -m affilipilot facebook-insights-sync-scheduled --queue --outbox data/outbox/telegram.json
  python3 -m affilipilot openclaw-telegram-send --outbox data/outbox/telegram.json --to telegram:640968010 || true
} >> "$log_file" 2>&1
