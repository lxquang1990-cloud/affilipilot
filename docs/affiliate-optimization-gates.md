# AffiliPilot Optimization Gates

AffiliPilot now separates **can publish** from **should publish**.

## Gate stack

1. **Technical gate** — approval, delivery proof, Facebook plan, config.
2. **Media gate** — local media exists and is trusted enough for production.
3. **Quality gate** — disclosure, provenance, product detail URL, duplicate/content sanity.
4. **Market-fit gate** — product/category/price/angle must match the Page audience.
5. **Offer gate** — URL must not be demo/test/localhost/example; optional network checks can catch 404/landing mismatch.

`publish-safe` runs all non-network production gates before any real Facebook POST.

## Useful commands

```bash
python -m affilipilot market-fit --input products.txt
python -m affilipilot content-variants --input products.txt --out-dir data/content-variants
python -m affilipilot offer-validate --url 'https://go.isclix.com/deep_link/v5/...'
python -m affilipilot strategy
python -m affilipilot performance-record --batch-key b --post-id p --clicks 10 --conversions 1
python -m affilipilot performance-summary
```

## Mother/baby audience rule

Do not push unrelated products through the generic mother/baby template.

Electronics can pass only when the post has a credible family angle, for example:

- camera for children/family moments
- battery for family travel
- storage for photos/videos
- warranty/price comparison for a high-ticket item

Blocked example:

> Một gợi ý nhỏ cho mẹ đang tìm đồ tiện dùng trong sinh hoạt hằng ngày với bé. Samsung Galaxy S26 Ultra...

Reasons:

- `market_fit:generic_mother_baby_template_mismatch`
- `market_fit:missing_family_electronics_angle`
