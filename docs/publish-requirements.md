# Publish Requirements — Affiliate + Media Gate

AffiliPilot must not publish affiliate posts to Facebook unless both gates pass.

## Affiliate Link Gate

Allowed link examples:

- Accesstrade tracking/deep link domains, e.g. `go.isclix.com`, `pub.accesstrade.vn`, `accesstrade.vn`.
- Shopee short affiliate links such as `s.shopee.vn`.
- URLs containing explicit tracking markers such as `sub1`, `sub3`, or affiliate UTM markers.

Blocked:

- Plain `shopee.vn` product URLs.
- `example` / demo links.
- Empty links.

## Media Gate

A post must include at least one of:

- `image_url`
- `image_path`
- `video_url`
- `video_path`

Manual input example:

```text
https://go.isclix.com/deep_link/abc | title=Giỏ sắp xếp đồ bé | image_url=https://cdn.example/product.jpg | price=129000
```

## Current policy

No real Facebook publish if either gate fails. The workflow may still generate draft, digest, ready package, and dry-run report.
