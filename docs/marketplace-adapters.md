# Marketplace Adapters — Phase A

AffiliPilot now has a small marketplace adapter layer for Shopee/Lazada URL handling.

## Goal

Prevent channel/search/support URLs from entering the affiliate conversion and publish pipeline as if they were product offers.

## Package

```text
affilipilot/marketplaces/
├─ base.py
├─ lazada.py
├─ shopee.py
└─ __init__.py
```

## Interface

Adapters provide:

```python
class MarketplaceAdapter:
    def classify_url(url) -> UrlClassification
    def is_product_url(url) -> bool
    def is_channel_url(url) -> bool
    def discovery_advice(url) -> DiscoveryAdvice
    def normalize_candidate(product) -> ProductCandidate
```

## CLI

```bash
python -m affilipilot marketplace-classify \
  --url 'https://www.lazada.vn/tag/khan-sua-em-be/' \
  --allow-needs-discovery
```

Example output:

```text
Marketplace: LAZADA
Kind: tag
Action: discover_product_details
OK: False
```

## Lazada rules

- Product URLs: allowed for affiliate conversion.
- Tag/shop/search/channel URLs: discovery only.
- Support/sellercenter/navigation URLs: reject.

Never convert Lazada channel/tag URLs directly.

## Shopee rules

- Product URLs like `...-i.<shopid>.<itemid>` or `/product/<shopid>/<itemid>` are product URLs.
- `s.shopee.*` shortlinks require resolution before validation.
- Shop/search/listing URLs are discovery only.

## Next phases

- Phase B: wire adapters into `accesstrade-convert` and `scan-draft` as a hard preflight.
- Phase C: implement rendered product discovery for Lazada/Shopee dynamic pages.
- Phase D: optional official Shopee affiliate API adapter after credential/design review.

## Phase B — conversion preflight

`accesstrade-convert` now runs marketplace classification before any Accesstrade API call.

Blocked examples:

```bash
python -m affilipilot accesstrade-convert \
  --input lazada-tag.txt \
  --campaign-key LAZADA \
  --real
```

If the input contains `https://www.lazada.vn/tag/...`, conversion is blocked with:

```text
marketplace_preflight_block:LAZADA:tag
```

Shopee shortlinks are also blocked until resolved:

```text
marketplace_preflight_block:SHOPEE:shortlink
```

`write_converted_input` skips failed rows, so blocked channel/search URLs cannot silently flow into drafting.

There is a dev-only escape hatch:

```bash
--allow-channel-urls
```

Do not use it for production publishing.
