#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR="${AFFILIPILOT_E2E_WORK_DIR:-data/e2e-fixture-smoke}"
DB_PATH="${AFFILIPILOT_E2E_DB:-data/e2e-fixture-smoke.db}"
BATCH_KEY="${AFFILIPILOT_E2E_BATCH_KEY:-e2e-fixture-smoke}"
OUTBOX="${AFFILIPILOT_E2E_OUTBOX:-$WORK_DIR/outbox.json}"
SEND_TELEGRAM="${AFFILIPILOT_E2E_SEND_TELEGRAM:-0}"
TELEGRAM_TARGET="${AFFILIPILOT_E2E_TELEGRAM_TARGET:-640968010}"

rm -rf "$WORK_DIR" "$DB_PATH"
mkdir -p "$WORK_DIR/demo-media"
printf '\xff\xd8\xff\xe0%s' "$(printf '0%.0s' {1..100})" > "$WORK_DIR/demo-media/a.jpg"
printf '\xff\xd8\xff\xe0%s' "$(printf '0%.0s' {1..100})" > "$WORK_DIR/demo-media/b.jpg"
printf '\xff\xd8\xff\xe0%s' "$(printf '0%.0s' {1..100})" > "$WORK_DIR/demo-media/c.jpg"

cat > "$WORK_DIR/input.links.txt" <<EOF
https://go.isclix.com/deep_link/product-a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path=$WORK_DIR/demo-media/a.jpg | media_source=user_uploaded_image | media_confidence=trusted | campaign_id=fixture-campaign
https://go.isclix.com/deep_link/product-b | title=Yếm ăn dặm silicone mềm | category=feeding | price=79000 | image_path=$WORK_DIR/demo-media/b.jpg | media_source=user_uploaded_image | media_confidence=trusted | campaign_id=fixture-campaign
https://go.isclix.com/deep_link/product-c | title=Khăn sữa cotton mềm | category=baby-care | price=59000 | image_path=$WORK_DIR/demo-media/c.jpg | media_source=user_uploaded_image | media_confidence=trusted | campaign_id=fixture-campaign
EOF

env FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
  FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-placeholder}" \
  PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot draft-links \
  --input "$WORK_DIR/input.links.txt" \
  --work-dir "$WORK_DIR" \
  --db "$DB_PATH" \
  --batch-key "$BATCH_KEY" \
  --limit 3 \
  --outbox "$OUTBOX" \
  --show-preview > "$WORK_DIR/draft-links.out"

post_id="$(grep -o 'post_[0-9][^ ]*' "$WORK_DIR/draft-links.out" | head -1 | sed 's/[,|:].*$//')"

if [[ -z "$post_id" ]]; then
  echo "E2E fixture smoke: FAIL — no post_id found" >&2
  cat "$WORK_DIR/draft-links.out"
  exit 2
fi

env FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
  FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-placeholder}" \
  PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot deliver-telegram \
  --outbox "$OUTBOX" \
  --mark-delivered \
  --receipt "fixture:e2e:$BATCH_KEY" > "$WORK_DIR/deliver.out"

env FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
  FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-placeholder}" \
  PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot decide \
  --db "$DB_PATH" \
  --batch-key "$BATCH_KEY" \
  --post-id "$post_id" \
  --decision approved \
  --reason "fixture e2e" > "$WORK_DIR/decide.out"

FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-placeholder}" \
python3 - <<PY
import json
from pathlib import Path
from affilipilot.db import AffiliPilotDB

db_path = Path("$DB_PATH")
batch_key = "$BATCH_KEY"
post_id = "$post_id"
db = AffiliPilotDB(db_path)
batch = db.get_batch(batch_key)
manifest = batch["manifest"]
for post in manifest["posts"]:
    if post["post_id"] == post_id:
        post["caption"] = "Giỏ sắp xếp gọn để gom khăn, đồ chơi và đồ lặt vặt ở bếp hoặc phòng tắm, giúp mặt bàn đỡ rối mà khi cần vẫn lấy ra rất nhanh.\n\nGiá tham khảo trên sàn 129.000đ, link affiliate 👇\n#sapxepnhacua #dogiadung #muasamthongminh"
        post_file = Path(post["files"]["post_text"])
        post_file.write_text(post["caption"] + "\n", encoding="utf-8")
        post["product"]["campaign_id"] = post["product"].get("campaign_id") or "fixture-campaign"
        break
else:
    raise SystemExit(f"post not found: {post_id}")
db.save_batch(batch_key, batch.get("source", "fixture"), manifest)
PY

env FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
  FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-placeholder}" \
  PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot approve-ready \
  --db "$DB_PATH" \
  --batch-key "$BATCH_KEY" \
  --out-dir "$WORK_DIR/approved" > "$WORK_DIR/approve-ready.out"

env FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-page}" \
  FACEBOOK_PAGE_ACCESS_TOKEN="${FACEBOOK_PAGE_ACCESS_TOKEN:-placeholder}" \
  PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot campaign-status \
  --db "$DB_PATH" \
  --batch-key "$BATCH_KEY" \
  --outbox "$OUTBOX" \
  --out-dir "$WORK_DIR/publish" > "$WORK_DIR/campaign-status.out"

if [[ "$SEND_TELEGRAM" == "1" ]]; then
  PYTHONPATH=. "${PYTHON_BIN:-python3}" -m affilipilot openclaw-telegram-send \
    --outbox "$OUTBOX" \
    --reply-channel telegram \
    --reply-to "$TELEGRAM_TARGET" \
    --limit 5 > "$WORK_DIR/openclaw-send.out"
fi

cat "$WORK_DIR/draft-links.out"
echo "--- deliver ---"
cat "$WORK_DIR/deliver.out"
echo "--- approve-ready ---"
cat "$WORK_DIR/approve-ready.out"
echo "--- campaign-status ---"
cat "$WORK_DIR/campaign-status.out"

grep -q "Products: 3 considered" "$WORK_DIR/draft-links.out"
grep -q "messages queued" "$WORK_DIR/draft-links.out"
grep -q "Ready package:" "$WORK_DIR/approve-ready.out"
grep -q "Facebook dry-run plan" "$WORK_DIR/approve-ready.out"
grep -q "Publishable dry-run: 1" "$WORK_DIR/approve-ready.out"
grep -q "System: OK" "$WORK_DIR/campaign-status.out"
test -f "$WORK_DIR/approved/facebook-plan.json"
test -f "$WORK_DIR/approved/ready/ready_package.json"

echo "AffiliPilot fixture E2E smoke: PASS"
echo "Work dir: $WORK_DIR"
echo "DB: $DB_PATH"
echo "Outbox: $OUTBOX"
