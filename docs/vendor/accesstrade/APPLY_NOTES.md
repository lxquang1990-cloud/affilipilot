# Accesstrade API — AffiliPilot apply notes

Source: `official-api-2026-05-27.md` provided by operator on 2026-05-27.

Policy: AffiliPilot should prefer official Accesstrade APIs for product discovery, tracking links, commission/order reporting, and product detail enrichment. Marketplace scraping/public endpoints are fallback-only when Accesstrade data is missing a field required for content quality, e.g. product video.

Key endpoints:
- `GET /v1/campaigns` — approved/running campaign discovery.
- `POST /v1/product_link/create` — tracking/deep link generation with UTM + `sub1..sub4`.
- `GET /v1/commission_policies` — commission by campaign/category/product.
- `GET /v1/transactions` — transaction reporting; rate limit 10/min.
- `GET /v1/order-list` — order reporting v2; rate limit 10/min, cache 1 min.
- `GET /v1/order-products` — products for an order; rate limit 10/min.
- `GET /v1/product_detail` — official product detail by `merchant` + `product_id`.
- `GET /v1/datafeeds` — product datafeed; official fields: `price`=original price, `discount`=sale price, `discount_amount`=discount value, `discount_rate`=discount percent.
- `GET /v1/offers_informations` — offers/promotions/coupons.
- `GET /v1/top_products` — best sellers.
- `GET /v1/orders_detail` — order detail.

Implementation notes:
- Header is `Authorization: Token <access_key>`.
- Keep access key only in secrets; never log it.
- For docs consistency, datafeed sale price should prefer `discount` when it is a real money value; if observed data uses percent-like `discount <= 100` with `price`, compute sale price from percent as a defensive compatibility fallback.
- Serialize bursts for 10/min endpoints and cache order-list at least 60s.
