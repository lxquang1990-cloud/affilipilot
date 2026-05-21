# ACCESSTRADE Shopee sourcing notes

Sources:
- ACCESSTRADE - Hướng dẫn dành chung cho các bạn chạy chiến dịch Shopee: https://docs.google.com/presentation/d/1ow2iK7cYVQWHoNPVS1n4chUD0wY9XAX-R08B-XZNJhU/edit
- ACCESSTRADE - SHOPEE - HOA HỒNG BRAND BONUS: https://docs.google.com/spreadsheets/d/1Xb8Mf33wVc8lNn1wFj4icmC_UsbHSNnzTU78sjkpS7c/edit

Fetched artifacts:
- `docs/accesstrade/shopee-guide.txt`
- `docs/accesstrade/shopee-guide.pdf`
- `docs/accesstrade/shopee-brand-bonus-2025.csv`

## Operational notes

1. Use Shopee campaign links / smartlink flow via Accesstrade, not raw marketplace links.
2. Convert product or promo URLs via Accesstrade convert-link/deep-link before publishing.
3. Brand Bonus / Commission Xtra matters:
   - Cột G: Brand Commission.
   - Cột H: Start date.
   - Cột I: End date.
   - Cột J: Shop Link.
   - Cột K: Apply to: some products or whole shop.
4. Prefer products/shops with Brand Bonus active and valid by date.
5. Spike days and monthly sale days are important sourcing windows: 7.x, 15.x, 25.x, payday/campaign day.
6. Shopee campaign updates schedule:
   - Monthly around day 28-31: calendar/overview, new buyer campaign, full-month campaigns.
   - Weekly Thursday: BAU campaigns and support mass comms.
   - Campaign day D-3: Overall, Hot voucher, Hot SKU/Deal, Hot Collection, Rush hour.
7. Prioritize:
   - Mall + VCX / Mall Xtra Discount.
   - Freeship / Voucher Xtra.
   - Shopee Choice.
   - Video + Livestream / hot SKU/Deal when relevant.
8. Optional coupon flow: Accesstrade tool/deal_coupon can provide Shopee codes/affiliate coupon links.

## AffiliPilot sourcing implications

Add scoring boosts when candidate has evidence:
- `brand_bonus_active`: strong boost.
- `brand_commission_pct`: proportional boost.
- `shop_link_from_brand_bonus`: strong trust/source boost.
- `apply_to=whole_shop`: shop-wide sourcing allowed.
- `apply_to=specific_products`: only use listed product URLs/SKUs.
- `campaign_window=spike|mid_month|payday|monthly_sale`: timed boost.
- `mall_or_voucher_xtra|shopee_choice|hot_sku|hot_collection`: source boost.

Guardrails:
- Do not publish raw Shopee URLs; require Accesstrade converted link.
- Do not treat a shop link as product-ready unless product-level title/media can be fetched or manually supplied.
- If product title/media cannot be verified, hold draft instead of generic caption.
- If Brand Bonus row has expired Start/End window, do not apply bonus scoring.
