# Accesstrade Link Creator

This module prepares product link conversion through Accesstrade.

## Default: dry-run

```bash
PYTHONPATH=. python3 -m affilipilot accesstrade-convert \
  --input products.txt \
  --out data/accesstrade/converted.json \
  --write-input data/accesstrade/converted.txt
```

Dry-run builds the payload and sub_id/UTM structure without calling Accesstrade.

## Real API call

Only use after Shopee campaign approval:

```bash
PYTHONPATH=. python3 -m affilipilot accesstrade-convert \
  --input products.txt \
  --out data/accesstrade/converted.json \
  --write-input data/accesstrade/converted.txt \
  --real
```

Required secrets:

```text
ACCESSTRADE_TOKEN
ACCESSTRADE_SHOPEE_CAMPAIGN_ID
```

## Endpoint

```text
POST https://api.accesstrade.vn/v1/product_link/create
```

Payload includes:

```text
campaign_id
urls
utm_source
utm_medium
utm_campaign
utm_content
sub1
sub2
sub3
sub4
```

## Safety

If token or campaign ID is missing/pending, real conversion returns a failed item instead of crashing or publishing.
