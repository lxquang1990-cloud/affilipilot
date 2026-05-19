# Accesstrade Publisher API notes — 2026-05-19

Source crawled: https://developers.accesstrade.vn/ and linked `.md` pages. External docs are reference only.

## Auth

All API requests require headers:

```http
Authorization: Token <access_key>
Content-Type: application/json
```

Access key is from publisher profile.

## Official endpoint index

| Area | Endpoint | Method | Notes / limits |
|---|---:|---:|---|
| Campaigns (old) | `/v1/campaigns` | GET | Params: `approval`, `campaign_id`. Use `approval=successful` for approved campaigns. `status=1` means running. |
| Campaigns NEW | `/v1/cashback/campaigns` | GET | Params: `page`, `page_size`, `category_id`, `sort_by=min_commission|max_commission`, `sort_order=asc|desc`, `sort_by_category`. Includes commission range. |
| Commission policies | `/v1/commission_policies` | GET | Mentioned by docs query; page exists in English section. |
| Create tracking/product link | `/v1/product_link/create` | POST | Requires `campaign_id`; returns `data.success_link[].aff_link` and `short_link` on success. |
| Datafeeds | `/v1/datafeeds` | GET | Params: `campaign`, `domain`, price/discount filters, `status_discount`, `page`, `limit`, `update_from`, `update_to`; help docs also mention `cat`. |
| Top products | `/v1/top_products` | GET | Params: `date_from`, `date_to`, `merchant`. |
| Product detail | `/v1/product_detail` | GET | Required: `merchant`, `product_id`, `transaction_id`. |
| Offers active (legacy) | `/v1/offers_informations` | GET | Params: `scope`, `merchant`, `categories`, `domain`, `coupon`, `status`, `limit`, `page`. Page says use newer version. |
| Deals keywords | `/v1/offers_informations/keyword_list` | GET | Hot campaign/deal keywords. |
| Deals merchants | `/v1/offers_informations/merchant_list` | GET | Merchant IDs for coupon APIs. |
| Deals icontext | `/v1/offers_informations/icontext_list` | GET | Requires merchant ID from merchant_list. |
| Coupons | `/v1/offers_informations/coupon` | GET | Params include `is_next_day_coupon`, `keyword`, `merchant`, `limit`, `page`. |
| Coupon categories | `/v1/offers_informations/list_category_coupons` | GET | Coupon category list. |
| Coupon hot | `/v1/offers_informations/coupon_hot` | GET | Mentioned by docs query. |
| Multi-link to coupons | `/v1/offers_informations/multi_link_2_coupons` | POST | 5 URLs/request, 30 requests/min. |
| Transactions | `/v1/transactions` | GET | Limit 10 requests/min. Required `since`, `until`; filters: page/offset/limit/merchant/UTM/status/is_confirmed/transaction_id/update_time/is_brand_bonus. |
| Order list v2 | `/v1/order-list` | GET | Limit 10 requests/min, cache 1 minute. Required `since`, `until`; filters: page, limit max 300, merchant, status, UTM. |
| Order products | `/v1/order-products` | GET | Limit 10 requests/min. Required: `order_id`, `merchant`. |

## Campaign ID rules for AffiliPilot

Docs answer: for `/v1/product_link/create`, use the `campaign_id` returned by the campaigns API. The safe flow is:

1. Fetch campaigns from `/v1/campaigns` or `/v1/cashback/campaigns`.
2. Filter to campaigns where:
   - `approval == "successful"` → publisher is approved to run it.
   - `status == 1` → campaign is running.
3. Match by `merchant`, `url`, and/or campaign name/domain.
4. Use the actual `campaign_id`/`id` in `/v1/product_link/create`.

Important: datafeed fields like `campaign: "lazadaapp"`, `merchant: "lazadaapp"`, `domain: "lazada.vn"` are product-owner metadata/filters. Docs do **not** document any direct mapping from datafeed `campaign` names to `campaign_id`. Therefore AffiliPilot must not assume `lazadaapp` or `LAZADA` is the numeric campaign ID.

## Tracking link / shortlink

Endpoint:

```http
POST https://api.accesstrade.vn/v1/product_link/create
```

Request fields documented:

| Field | Required | Notes |
|---|---:|---|
| `campaign_id` | yes | Campaign ID from campaign registry. |
| `urls` | optional | Docs table says optional; example passes a list of URLs. If missing, campaign URL is used. |
| `utm_source` | optional | Publisher tracking. |
| `utm_medium` | optional | Publisher tracking. |
| `utm_campaign` | optional | Publisher tracking. |
| `utm_content` | optional | Publisher tracking. |
| `sub1`..`sub4` | optional | Publisher tracking. |
| `url_enc` | example-only | Appears in curl body as `true`, not in parameter table. |
| `channel_id` | not documented | Existing AffiliPilot has support, but Accesstrade docs query says not documented for generic Publisher API. |

Official success response shape:

```json
{
  "data": {
    "error_link": [],
    "success_link": [
      {
        "aff_link": "...",
        "first_link": null,
        "short_link": "...",
        "url_origin": "..."
      }
    ],
    "suspend_url": []
  },
  "success": true
}
```

AffiliPilot rule: require official `success_link[].short_link` for Facebook captions; block if missing.

## Datafeed details

Endpoint:

```http
GET https://api.accesstrade.vn/v1/datafeeds
```

Params documented:

- `campaign` — merchant/product owner, e.g. `lazada`.
- `domain` — product owner domain, e.g. `lazada.vn`.
- `discount_amount_from`, `discount_amount_to`.
- `discount_rate_from`, `discount_rate_to`.
- `page` — default 1.
- `limit` — default 50, max 200.
- `price_from`, `price_to`.
- `discount_from`, `discount_to`.
- `status_discount` — 0 no discount, 1 has discount.
- `update_from`, `update_to`.
- Help/news docs also mention `cat=<category-code>` although main developer page does not list it.

Response product fields include `cate`, `desc`, `discount`, `campaign`, `domain`, `image`, `name`, `price`, `product_id`, `sku`, `url`, `aff_link`, `status_discount`, `discount_amount`, `discount_rate`, `update_time`, `merchant`, `promotion`.

## Top products

Endpoint:

```http
GET https://api.accesstrade.vn/v1/top_products
```

Params: `date_from`, `date_to`, `merchant`.

Response fields: `category_id`, `category_name`, `desc`, `image`, `link`, `aff_link`, `price`, `discount`, `total`, `name`, `product_id`, plus examples with `brand`, `product_category`, `short_desc`.

## Orders / performance sync

### Transactions

Endpoint: `GET /v1/transactions`; limit 10 requests/min.

Required: `since`, `until` in ISO format.

Important fields: `status` (0 pending/hold, 1 approved, 2 rejected), `merchant`, `click_time`, `transaction_id`, `transaction_time`, `update_time`, `confirmed_time`, `is_confirmed`, `transaction_value`, `commission`, `product_id`, `product_price`, `product_quantity`, UTM fields, `category_name`, `conversion_id`, `product_category`, `product_image`, `product_name`, `reason_rejected`, `is_brand_bonus`.

### Order list v2

Endpoint: `GET /v1/order-list`; limit 10 requests/min, cache 1 minute.

Required: `since`, `until`. Max `limit` 300.

Important fields: `at_product_link`, `billing`, `browser`, `category_name`, `click_time`, `client_platform`, `confirmed_time`, `merchant`, `order_id`, `order_pending`, `order_reject`, `order_approved`, `product_category`, `products_count`, `pub_commission`, `sales_time`, `update_time`, UTM fields, `website`, `website_url`.

### Order products

Endpoint: `GET /v1/order-products`; limit 10 requests/min.

Required: `order_id`, `merchant`.

Important fields: `_at`, `_extra`, `_id`, `billing`, `campaign_id`, `click_time`, `commission`, `confirmed_time`, `merchant`, `product_price`, `product_quantity`, `quantity`, `reason_rejected`, `sales_time`.

## Current AffiliPilot implications

1. Current `Campaign does not exists or not running` is consistent with an invalid/not-running campaign_id for the account.
2. The fix is not to synthesize `go.isclix.com/deep_link/v5/...`; current gate correctly blocks.
3. Next implementation should fetch both:
   - old `/v1/campaigns?approval=successful` because docs explicitly say this has `id`, `approval`, `status`, `merchant`, `url` for tracking link selection;
   - new `/v1/cashback/campaigns?page=1&page_size=...` because it has commission fields useful for profit-first scoring.
4. Campaign registry should normalize both `id` and `campaign_id`, and should build aliases from `merchant`, `url` domain, `name`, maybe `adv_code`.
5. E2E should match datafeed products to active approved campaign by `domain`/`merchant`, not by hard-coded `LAZADA` unless env mapping is verified.
6. `channel_id` should be treated as optional/non-authoritative for generic Publisher API because docs do not document it.
