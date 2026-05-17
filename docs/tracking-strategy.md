# Tracking Strategy — Accesstrade / Shopee

## Goal

Every post must have a unique tracking identity so later clicks/conversions can be mapped back to channel, page, post, and product.

## Accesstrade tracking link endpoint

Accesstrade documentation describes:

```text
POST https://api.accesstrade.vn/v1/product_link/create
```

Key parameters:

- `campaign_id`
- `urls`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_content`
- `sub1`
- `sub2`
- `sub3`
- `sub4`

## Standard mapping

```text
sub1 = channel
sub2 = property/page/account
sub3 = post_id
sub4 = product_or_campaign_id
```

For the first Facebook Page:

```text
sub1 = facebook
sub2 = nangniutraingottinhyeu
sub3 = post_YYYYMMDD_NNN
sub4 = product_slug_or_id
```

UTM:

```text
utm_source = facebook
utm_medium = page_post
utm_campaign = affilipilot_mom_baby_YYYYMM
utm_content = post_YYYYMMDD_NNN
```

## Examples

```text
sub1=facebook
sub2=nangniutraingottinhyeu
sub3=post_20260516_001
sub4=hop-chia-sua-001
```

Later TikTok:

```text
sub1=tiktok
sub2=account_name
sub3=video_YYYYMMDD_NNN
sub4=product_slug_or_id
```

Later YouTube:

```text
sub1=youtube
sub2=shorts_channel
sub3=short_YYYYMMDD_NNN
sub4=product_slug_or_id
```

## Rule

No content should be published without a tracking identity. If Accesstrade API is unavailable, store the intended tracking identity in the draft and mark the link as `manual_tracking_required`.
