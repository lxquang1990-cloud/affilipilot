# Product Scanner + Post Generator

AffiliPilot can scan a category/deal page, extract product candidates, score them, generate Facebook drafts, and queue Telegram approval cards.

## Safety model

- Scanner fetches/read HTML and extracts candidates only.
- No Facebook publish happens during scan or draft.
- Accesstrade conversion is dry-run unless `--real-accesstrade` is explicitly set.
- Publish still requires approval + compliance + affiliate link + media + Facebook dry-run plan.

## 1. Scan products from a page

```bash
python3 -m affilipilot scan-products \
  --url "https://cellphones.com.vn/danh-sach-khuyen-mai" \
  --source CELLPHONES \
  --category deal \
  --campaign-key CELLPHONES \
  --limit 10 \
  --out data/scans/cellphones-deals.json
```

Output:

```text
AffiliPilot scan-products: <n> items
Output JSON: data/scans/cellphones-deals.json
```

The scanner currently supports:

- JSON-LD Product extraction
- generic anchor/card extraction
- meta title/image fallback
- domain/category/source tagging
- price parsing for VND strings

## 2. Turn scan into approval drafts

```bash
python3 -m affilipilot scan-draft \
  --scan data/scans/cellphones-deals.json \
  --work-dir data/runs/cellphones-deals \
  --db data/affilipilot.db \
  --batch-key cellphones-deals-001 \
  --outbox data/outbox/cellphones-deals-001.json \
  --limit 5
```

This runs:

```text
scan JSON -> input txt -> score -> draft -> compliance -> approval DB -> Telegram outbox
```

## 3. Optional Accesstrade conversion

Dry-run conversion before drafting:

```bash
python3 -m affilipilot scan-draft \
  --scan data/scans/cellphones-deals.json \
  --work-dir data/runs/cellphones-deals \
  --db data/affilipilot.db \
  --batch-key cellphones-deals-001 \
  --outbox data/outbox/cellphones-deals-001.json \
  --limit 5 \
  --convert-affiliate \
  --campaign-key CELLPHONES
```

Real Accesstrade API call requires explicit flag:

```bash
python3 -m affilipilot scan-draft ... \
  --convert-affiliate \
  --real-accesstrade \
  --campaign-key CELLPHONES
```

## 4. Review and approve

```bash
python3 -m affilipilot outbox --outbox data/outbox/cellphones-deals-001.json

python3 -m affilipilot decide \
  --db data/affilipilot.db \
  --batch-key cellphones-deals-001 \
  --post-id post_20260516_001 \
  --decision approved
```

## 5. Build ready package / Facebook plan

```bash
python3 -m affilipilot approve-ready \
  --db data/affilipilot.db \
  --batch-key cellphones-deals-001 \
  --out-dir data/runs/cellphones-deals/approved
```

Only then consider `facebook-publish-one`, and only for a `publishable_dry_run` plan item.

## Notes

Lazada/Shopee pages may be heavily dynamic/anti-bot. For those sources, prefer affiliate/deeplink lists or API feeds when available. CellphoneS/static promotion pages are better first scanner targets.
