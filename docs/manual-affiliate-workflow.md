# Manual Affiliate-ready Workflow

Use this while waiting for Accesstrade campaign approval/config (`ACCESSTRADE_CAMPAIGN_ID` or `ACCESSTRADE_CAMPAIGN_<KEY>`).

## Required input per product

Each line must contain:

- affiliate/tracking URL, not plain Shopee URL
- title
- image URL or local image path
- optional price/category/notes

Example:

```text
https://go.isclix.com/deep_link/abc | title=Giỏ sắp xếp đồ bé | image_url=https://cdn.example/product.jpg | price=129000 | category=storage
```

## Validate before running

```bash
PYTHONPATH=. python3 -m affilipilot validate-input --input products.txt
```

## Run local day

```bash
PYTHONPATH=. python3 -m affilipilot run-day \
  --input products.txt \
  --work-dir data/runs \
  --db data/affilipilot.db \
  --batch-key manual-affiliate-day \
  --limit 5
```

## Approval and plan

```bash
PYTHONPATH=. python3 -m affilipilot decide \
  --db data/affilipilot.db \
  --batch-key manual-affiliate-day \
  --post-id post_20260516_001 \
  --decision approved

PYTHONPATH=. python3 -m affilipilot facebook-plan \
  --db data/affilipilot.db \
  --batch-key manual-affiliate-day \
  --out data/publish/manual-affiliate-day-plan.json
```

If media is present, the plan uses:

```text
/PAGE_ID/photos
```

Real publish still requires an approved post and passing gates.
