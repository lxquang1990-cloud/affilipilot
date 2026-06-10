#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/home/snail/.openclaw/workspace/affilipilot"
# Cron runs with a minimal PATH; OpenClaw CLI lives in ~/.npm-global/bin.
export PATH="/home/snail/.npm-global/bin:/home/snail/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
cd "$ROOT"

mkdir -p "$ROOT/logs" "$ROOT/data/outbox" "$ROOT/data/runs"

lock_file="$ROOT/data/scheduled_e2e_queue.lock"
exec 9>"$lock_file"
if ! flock -n 9; then
  echo "===== $(date --iso-8601=seconds) skip: previous scheduled E2E still running =====" >> "$ROOT/logs/scheduled-e2e.log"
  exit 0
fi

slot="${AFFILIPILOT_SLOT:-$(date +%H%M)}"
batch="auto-source-scheduled-$(date +%Y%m%d)-${slot}"
work_dir="data/runs/${batch}"
outbox="data/outbox/${batch}.json"
log_file="$ROOT/logs/scheduled-e2e.log"

{
  echo "===== $(date --iso-8601=seconds) batch=${batch} start ====="
  set +e
  timeout 45m env PYTHONPATH=. /usr/bin/python3 -m affilipilot profit-e2e \
    --batch-key "$batch" \
    --work-dir "$work_dir" \
    --db data/affilipilot.db \
    --outbox "$outbox" \
    --discover-limit 80 \
    --limit 3 \
    --real-accesstrade
  code=$?
  set -e
  echo "===== $(date --iso-8601=seconds) batch=${batch} hunter_exit=${code} work_dir=${work_dir} outbox=${outbox} ====="

  # Always notify the operator that the scheduled job ran, including the
  # valid no-post case. profit-e2e writes a digest message to the
  # outbox even when no publish-ready card is produced.
  if [[ -s "$outbox" ]]; then
    echo "===== $(date --iso-8601=seconds) batch=${batch} telegram_delivery_start outbox=${outbox} ====="
    env PYTHONPATH=. /usr/bin/python3 -m affilipilot telegram-bot-send \
      --outbox "$outbox" \
      --secret-path /home/snail/.openclaw/workspace/secrets/affilipilot.env \
      --limit 5
    delivery_code=$?
    echo "===== $(date --iso-8601=seconds) batch=${batch} telegram_delivery_exit=${delivery_code} ====="
    if [[ "$delivery_code" -ne 0 ]]; then
      code="$delivery_code"
    elif [[ "$code" -eq 2 ]]; then
      # AffiliPilot uses exit=2 for a safe BLOCK/no-post run. Once the
      # operator digest is delivered, cron should treat this as handled.
      code=0
    fi
  else
    echo "===== $(date --iso-8601=seconds) batch=${batch} telegram_delivery_skip reason=missing_or_empty_outbox outbox=${outbox} ====="
  fi

  echo "===== $(date --iso-8601=seconds) batch=${batch} exit=${code} work_dir=${work_dir} outbox=${outbox} ====="
  exit "$code"
} >> "$log_file" 2>&1
