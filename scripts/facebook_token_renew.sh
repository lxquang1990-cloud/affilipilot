#!/usr/bin/env bash
set -euo pipefail

cd /home/snail/.openclaw/workspace/affilipilot
LOG_DIR=/home/snail/.openclaw/workspace/affilipilot/logs
mkdir -p "$LOG_DIR"

{
  printf '[%s] facebook token renew start\n' "$(date -Is)"
  python3 -m affilipilot facebook-token-manager --action refresh --auto --threshold-days 15
  python3 -m affilipilot facebook-token-check
  printf '[%s] facebook token renew done\n' "$(date -Is)"
} >> "$LOG_DIR/facebook-token-renew.log" 2>&1
