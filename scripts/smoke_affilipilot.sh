#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR="${AFFILIPILOT_SMOKE_WORK_DIR:-data/smoke-happy-path}"
DB_PATH="${AFFILIPILOT_SMOKE_DB:-data/smoke-happy-path.db}"
BATCH_KEY="${AFFILIPILOT_SMOKE_BATCH_KEY:-smoke-happy-path}"

rm -rf "$WORK_DIR" "$DB_PATH"
FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-token}" \
PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot demo-happy-path \
  --work-dir "$WORK_DIR" \
  --db "$DB_PATH" \
  --batch-key "$BATCH_KEY" >/tmp/affilipilot-smoke.out

cat /tmp/affilipilot-smoke.out

grep -q "Publishable dry-run: 1" /tmp/affilipilot-smoke.out
grep -q "approval=approved plan=publishable_dry_run" /tmp/affilipilot-smoke.out
test -f "$WORK_DIR/approved/facebook-plan.json"
test -f "$WORK_DIR/approved/ready/ready_package.json"

printf 'AffiliPilot smoke: PASS\n'
