# AffiliPilot Lite Quickstart

This quickstart runs a local, safe Sprint 1 simulation. It does not call Accesstrade, does not send Telegram, and does not publish Facebook.

## 1. Check readiness

```bash
cd /home/snail/.openclaw/workspace/affilipilot
python3 -m affilipilot readiness
```

## 2. Run the happy-path smoke

```bash
python3 -m affilipilot demo-happy-path
```

Expected signals:

```text
Drafts selected: 3/3
Outbox queued: 4 messages
Ready package: 1 ready, 2 held
Publishable dry-run: 1
```

## 3. Prepare product links

Use one URL per line. Optional metadata can be added after `|`.

```text
https://go.isclix.com/deep_link/product | title=Giỏ sắp xếp đồ bé | category=storage | price=129000 | image_url=https://cdn.example/product.jpg
```

Example files:

```text
examples/product_links.txt
examples/mom_baby_links.txt
examples/products.csv
```

## 4. Generate drafts and approval cards

```bash
python3 -m affilipilot draft-links \
  --input examples/mom_baby_links.txt \
  --work-dir data/runs/manual \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --limit 5 \
  --outbox data/outbox/manual-001.json \
  --show-preview
```

Outputs:

- `data/runs/manual/manual-001/drafts/manifest.json`
- `data/runs/manual/manual-001/drafts/approval_batch_preview.txt`
- `data/outbox/manual-001.json`
- SQLite approval state in `data/affilipilot.db`

## 5. Review local Telegram outbox

```bash
python3 -m affilipilot outbox --outbox data/outbox/manual-001.json
```

Local delivery dry-run:

```bash
python3 -m affilipilot deliver-telegram --outbox data/outbox/manual-001.json --limit 1
```

Mark one processed locally:

```bash
python3 -m affilipilot deliver-telegram --outbox data/outbox/manual-001.json --limit 1 --mark-sent
```

## 6. Approve/reject locally

```bash
python3 -m affilipilot decide \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --post-id post_20260516_001 \
  --decision approved \
  --reason "ok"
```

## 7. Build ready package + Facebook dry-run plan

```bash
FACEBOOK_PAGE_ID=page FACEBOOK_PAGE_ACCESS_TOKEN=.placeholder-token \
python3 -m affilipilot approve-ready \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --out-dir data/runs/manual/manual-001-approved
```

This writes:

- `data/runs/manual/manual-001-approved/ready/ready_package.json`
- `data/runs/manual/manual-001-approved/ready/<post_id>.ready-to-post.txt`
- `data/runs/manual/manual-001-approved/facebook-plan.json`

## 8. Inspect full batch status

```bash
python3 -m affilipilot batch-status \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --facebook-plan data/runs/manual/manual-001-approved/facebook-plan.json
```

## 9. Verify everything

```bash
scripts/verify_all.sh
```

## Stop before real integrations

Do not enable real Accesstrade or Facebook publishing until:

- secrets are present in `/home/snail/.openclaw/workspace/secrets/affilipilot.env`
- `readiness` passes the relevant integration gates
- `facebook-token-check` passes for Facebook publish
- one harmless API health-check passes
- Snail explicitly approves the first real publish test
