# Publish Safe Gate

`publish-safe` is the recommended final gate before any real Facebook publish.

It validates all required production preconditions without exposing secrets:

1. Batch and selected `post_id` exist in SQLite.
2. Approval state in SQLite is `approved` for the selected `post_id`.
3. Telegram delivery proof exists for both:
   - `<batch_key>:summary`
   - `<batch_key>:<post_id>`
4. Both outbox messages are `delivered` and include non-empty receipts.
5. Facebook plan contains the post with status `publishable_dry_run`.
6. Quality gate passes: affiliate link, media, provenance, disclosure, duplicate/content sanity.
7. Market-fit gate passes: product category, audience, price point, hook, benefits, CTA, and hashtags match the target audience.
8. Offer validation passes offline: URL exists, is not demo/test/localhost/example, and has a supported scheme.

Typical hard-block reasons include:

- `quality:media_not_downloaded`
- `quality:audience_product_mismatch`
- `market_fit:generic_mother_baby_template_mismatch`
- `market_fit:missing_family_electronics_angle`
- `offer:demo_or_test_offer_url`

## Check only

```bash
PYTHONPATH=. python3 -m affilipilot publish-safe \
  --check-only \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --post-id post_20260516_001 \
  --plan data/publish/facebook-plan.json \
  --outbox data/outbox/telegram.json
```

## Publish after pass

Omit `--check-only` only after reviewing the validation output:

```bash
PYTHONPATH=. python3 -m affilipilot publish-safe \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --post-id post_20260516_001 \
  --plan data/publish/facebook-plan.json \
  --outbox data/outbox/telegram.json \
  --out data/publish/facebook-result.json
```

`facebook-publish-one` now uses the same validation internally unless explicitly bypassed with `--unsafe-skip-telegram-gate` for tests/dev only.
