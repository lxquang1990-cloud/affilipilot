# Lazada Channel/Tag Links

Lazada tag/channel URLs such as:

- `https://www.lazada.vn/tag/khan-sua-em-be/`
- `https://www.lazada.vn/tag/binh-thia-an-dam-cho-be/`

are **listing/channel pages**, not product detail pages. AffiliPilot must not convert or publish them directly.

## Root cause

Static `scan-products` previously fell back to generic anchor parsing. On Lazada listing pages this captured navigation links such as:

- `sellercenter.lazada.vn/...` — seller registration
- `helpcenter.lazada.vn/...` — support pages
- app promo links
- tag/category links

Those links are not product offers and should not enter the affiliate publish flow.

## Current behavior

For Lazada listing/channel pages, scanner now emits only product-detail URLs matching the quality gate, e.g.:

```text
https://www.lazada.vn/products/<slug>-i<item>-s<sku>.html
```

If no product-detail URL is available in static HTML, `scan-products` returns 0 items. This is intentional and safe.

## Recommended workflow

1. Try static scan:

```bash
python -m affilipilot scan-products \
  --url 'https://www.lazada.vn/tag/khan-sua-em-be/' \
  --source LAZADA \
  --category baby_care \
  --campaign-key LAZADA \
  --out data/scans/lazada-khan-sua.json \
  --limit 10
```

2. If result is 0, do **not** convert the channel URL. Use a rendered discovery path:

```bash
python -m affilipilot browser-discover \
  --url 'https://www.lazada.vn/tag/khan-sua-em-be/' \
  --source LAZADA \
  --category baby_care \
  --out data/scans/lazada-khan-sua-browser.json \
  --limit 10
```

3. If browser discovery is unavailable, manually paste real product-detail URLs from Lazada product cards.

## Hard rule

Never feed Lazada tag/channel/search/support/sellercenter URLs into `accesstrade-convert` for production posts. Convert only validated product-detail URLs.
