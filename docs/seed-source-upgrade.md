# Seed Source Upgrade

Seed Source Upgrade adds a curated-seed path for products that are discovered outside the noisy broad Accesstrade feeds.

## Why

The broad feed can over-index risky or low-fit products (medical, supplements, niche replacement parts). Shopee public search/detail APIs may also return anti-bot `403 / 90309999` from this Pi. The safe path is to accept curated PDP links, validate them, convert with official Accesstrade shortlinks, then run the normal quality and publish-safe gates.

## Workflow

Script:

```text
scripts/seed_to_auto_e2e.py
```

Flow:

```text
curated seed file
→ Seed Hunter validation/scoring
→ Accesstrade conversion / official shortlink
→ draft-links
→ ready-to-publish
→ optional publish-safe guarded publish
→ structured event log
```

## Input format

Use one product per line:

```text
https://shopee.vn/product/<shop_id>/<item_id> | title=... | category=... | price=299000 | image_url=... | notes=rating=4.8;sold=100 | campaign_key=shopee
```

Recommended metadata:

```text
title
category
price
image_url or image_urls
video_url or video_urls if available
notes=rating=...;sold=...;review_count=...
campaign_key or campaign_id
```

## Dry-run smoke

```bash
python3 scripts/seed_to_auto_e2e.py \
  --seed-file data/manual-seeds.input.txt \
  --batch-key seed-auto-smoke \
  --work-dir data/runs/seed-auto/seed-auto-smoke \
  --limit 1 \
  --campaign-key shopee
```

By default this does not call real Accesstrade and does not publish.

## Real conversion, no publish

```bash
python3 scripts/seed_to_auto_e2e.py \
  --seed-file data/manual-seeds.input.txt \
  --batch-key seed-auto-real-convert \
  --work-dir data/runs/seed-auto/seed-auto-real-convert \
  --limit 1 \
  --campaign-key shopee \
  --real-accesstrade
```

## Optional guarded publish

Only use inside an explicit test window and after checking circuit status:

```bash
python3 -m affilipilot.cli circuit-status

python3 scripts/seed_to_auto_e2e.py \
  --seed-file data/manual-seeds.input.txt \
  --batch-key seed-auto-publish \
  --work-dir data/runs/seed-auto/seed-auto-publish \
  --limit 1 \
  --campaign-key shopee \
  --real-accesstrade \
  --publish
```

The script still uses `ready-to-publish` and `publish-safe`; if no post passes gates, it exits with `published=0`.

## Events

Events are written to:

```text
data/logs/affilipilot-events.jsonl
```

Relevant events:

```text
seed_auto_started
seed_auto_no_valid_seeds
seed_auto_conversion_failed
seed_auto_ready
seed_auto_publish_blocked
seed_auto_publish_succeeded
seed_auto_publish_failed
seed_auto_done
```

## Safety notes

- The script does not bypass Shopee/Lazada anti-bot systems.
- `--publish` still checks the circuit breaker and local state TTL.
- If no product passes approval/delivery/publish-safe gates, nothing is published.
- Keep `data/auto_publish_state.json` local; do not commit it.
