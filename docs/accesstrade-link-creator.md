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

## Multi-campaign config

AffiliPilot supports one default campaign or multiple named campaigns.

### Generic default campaign

```text
ACCESSTRADE_TOKEN=...
ACCESSTRADE_CAMPAIGN_ID=6981366423833430236
ACCESSTRADE_CHANNEL_ID=5087153089503673507
```

### Multiple campaigns

```text
ACCESSTRADE_TOKEN=...

ACCESSTRADE_CAMPAIGN_SHOPEE=1111111111111111111
ACCESSTRADE_CAMPAIGN_SHOPEE_CHANNEL_ID=2222222222222222222
ACCESSTRADE_CAMPAIGN_SHOPEE_DOMAINS=shopee.vn,shopee.com

ACCESSTRADE_CAMPAIGN_LAZADA=6981366423833430236
ACCESSTRADE_CAMPAIGN_LAZADA_CHANNEL_ID=5087153089503673507
ACCESSTRADE_CAMPAIGN_LAZADA_DOMAINS=lazada.vn,lazada.com
```

Legacy key remains supported:

```text
ACCESSTRADE_SHOPEE_CAMPAIGN_ID=1111111111111111111
```

## Campaign selection

By default, campaign is auto-detected from product URL domain when configured:

- `shopee.vn` -> `SHOPEE`
- `lazada.vn` -> `LAZADA`
- `tiki.vn` -> `TIKI`

You can override selection explicitly:

```bash
PYTHONPATH=. python3 -m affilipilot accesstrade-convert \
  --input products.txt \
  --out data/accesstrade/lazada.json \
  --campaign-key LAZADA
```

## Real API call

Only use after campaign approval and dry-run review:

```bash
PYTHONPATH=. python3 -m affilipilot accesstrade-convert \
  --input products.txt \
  --out data/accesstrade/converted.json \
  --write-input data/accesstrade/converted.txt \
  --campaign-key LAZADA \
  --real
```

Required secrets:

```text
ACCESSTRADE_TOKEN
ACCESSTRADE_CAMPAIGN_ID or ACCESSTRADE_CAMPAIGN_<KEY>
```

## Endpoint

```text
POST https://api.accesstrade.vn/v1/product_link/create
```

Payload includes:

```text
campaign_id
channel_id (when configured)
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

If token or matching campaign ID is missing/pending, real conversion returns a failed item instead of crashing or publishing.
