# AffiliPilot Operations Guide

AffiliPilot Lite is a local-first, approval-gated affiliate workflow for the Facebook Page `Nâng Niu Trái Ngọt Tình Yêu`.

## Safety model

Default behavior is safe:

- no real Accesstrade API call unless `accesstrade-convert --real` is used and secrets are configured
- no real Facebook publish unless `facebook-publish-one` is explicitly run against a publishable dry-run plan
- no direct Telegram Bot API call from delivery commands
- no open-ended auto-approval; any auto mode must be explicitly time-boxed and circuit-breaker protected
- every Facebook publish path requires approval state or explicit test-window override + compliance pass + affiliate link + media + Facebook config
- `/tmp/affilipilot.KILL` immediately pauses scheduler automation

## Primary local workflow

```bash
cd /home/snail/.openclaw/workspace/affilipilot
```

### 1. Create drafts from links

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

### 2. Review local Telegram outbox

```bash
python3 -m affilipilot outbox --outbox data/outbox/manual-001.json
```

Dry-run delivery / mark processed locally:

```bash
python3 -m affilipilot deliver-telegram --outbox data/outbox/manual-001.json --limit 1
python3 -m affilipilot deliver-telegram --outbox data/outbox/manual-001.json --limit 1 --mark-sent
```

### 3. Approve or reject posts

```bash
python3 -m affilipilot decide \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --post-id post_20260516_001 \
  --decision approved \
  --reason "ok"
```

Allowed decisions:

- `approved`
- `rejected`
- `needs_edit`
- `blacklisted`
- `pending`

### 4. Build ready package and Facebook dry-run plan

```bash
FACEBOOK_PAGE_ID=page FACEBOOK_PAGE_ACCESS_TOKEN=.placeholder-token \
python3 -m affilipilot approve-ready \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --out-dir data/runs/manual/manual-001-approved
```

This does not publish. It writes:

- `ready/ready_package.json`
- `ready/<post_id>.ready-to-post.txt`
- `facebook-plan.json`

### 5. Inspect full batch status

```bash
python3 -m affilipilot batch-status \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --facebook-plan data/runs/manual/manual-001-approved/facebook-plan.json
```


## Automation-first source workflow

Use Auto Source Hunter when the operator wants AffiliPilot to find cleaner product inputs, convert them, gate content/media/link safety, and queue only vetted approval cards.

```bash
python3 -m affilipilot auto-source-hunter \
  --batch-key auto-source-$(date +%Y%m%dT%H%M%S) \
  --work-dir data/runs/auto-source-$(date +%Y%m%dT%H%M%S) \
  --db data/affilipilot.db \
  --outbox data/outbox/auto-source.json \
  --limit 5 \
  --real-accesstrade
```

Operational notes:

- Accesstrade datafeeds are broad/fallback input, not keyword/category search. Do not send undocumented `cat` filters.
- Local `target_category` metadata is allowed for filtering/reporting.
- Tiki conversion can use the known Tiki CPS fallback campaign mapping when campaign discovery is unavailable.
- Approval cards should be sent only after content gates, media gates, affiliate-link safety, and publish metadata pass.
- If PDP enrichment finds only thumbnails/static app assets, hold the item instead of publishing weak media.

## Caption/disclosure policy

Generated captions should be product/category-aware, not generic template copy. Avoid broad checklist dumps such as:

```text
Khi xem sản phẩm, nên check kỹ: dung tích, công suất, kích thước để bàn, dễ vệ sinh, bảo hành/đổi trả.
```

Use short product-specific hints instead. Affiliate disclosure remains required by default for transparency/compliance, using the current concise wording:

```text
Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link.
```

## Automation operations

Check circuit status:

```bash
python3 -m affilipilot circuit-status
```

Pause or resume automation:

```bash
python3 -m affilipilot kill-switch on --reason "operator pause"
python3 -m affilipilot kill-switch off
```

Inspect automation/audit events:

```bash
python3 -m affilipilot event-log --limit 30
```

Score draft/seed inputs into automation tiers:

```bash
python3 -m affilipilot score-tier --input data/runs/seed-hunter/seed-hunter.input.txt
```

Record or summarize local conversion/ROI data:

```bash
python3 -m affilipilot conversion-record --sub-id ap_b001_d001_20260519 --order-id order-001 --status approved --commission-vnd 12000 --order-value-vnd 200000
python3 -m affilipilot conversion-summary
```

Full automation guide: [`automation-first.md`](automation-first.md).

## Smoke test

Run the deterministic happy path:

```bash
python3 -m affilipilot demo-happy-path \
  --work-dir data/demo-happy-path \
  --db data/demo-happy-path.db \
  --batch-key demo-happy-path
```

Or use the script:

```bash
scripts/smoke_affilipilot.sh
```

## Verification

```bash
scripts/verify_all.sh
```

The verification suite compiles code, runs tests, scans for obvious secrets, and runs the happy-path smoke test.

## Real Facebook publish policy

Only run `facebook-publish-one` when all are true:

1. `facebook-token-check` passes.
2. `approve-ready` produced `publishable_dry_run` for the target post.
3. The post was explicitly approved in the DB.
4. The target post has delivery proof and Snail explicitly approved the real publish.
5. `publish-safe` reports PASS for the concrete post/plan.

Example:

```bash
python3 -m affilipilot facebook-publish-one \
  --plan data/runs/manual/manual-001-approved/facebook-plan.json \
  --post-id post_20260516_001 \
  --out data/publish/manual-001-post_20260516_001-result.json
```

Do not use this command in unattended automation.

## First real publish checklist

Before any real publish, follow [`first-real-publish-checklist.md`](first-real-publish-checklist.md).


## OpenClaw Telegram bridge

For real Telegram delivery handoff, use the plan-only bridge in [`openclaw-telegram-bridge.md`](openclaw-telegram-bridge.md). It renders `openclaw agent --deliver` commands and does not send automatically.


## Facebook token manager

Use [`facebook-token-manager.md`](facebook-token-manager.md) for inspect/exchange/page-token/refresh flows. It never prints token values and cannot renew already-expired user tokens without a fresh OAuth short-lived token.
