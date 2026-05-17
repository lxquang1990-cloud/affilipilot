# Integration Readiness Checklist

This checklist exists so AffiliPilot can advance without repeatedly asking Snail, while still stopping before risky actions.

## Sprint 1 manual-ready

Required:

- Secret file exists with secure permissions, even if mostly empty.
- Product input is available through pasted links or CSV.
- Compliance policy is active.
- Telegram/mock approval workflow works.
- Ready-to-post fallback works.

Command:

```bash
PYTHONPATH=. python3 -m affilipilot readiness
```

## Accesstrade API-ready

Required:

- `ACCESSTRADE_TOKEN` present in `/home/snail/.openclaw/workspace/secrets/affilipilot.env`.
- `ACCESSTRADE_SHOPEE_CAMPAIGN_ID` known/present.
- Tracking payload can be generated.
- Real API call must be added behind a health-check and tested with one harmless link first.

## Facebook publish-ready

Required:

- `FACEBOOK_PAGE_ID` present.
- `FACEBOOK_PAGE_ACCESS_TOKEN` present.
- Page token permissions verified.
- A publish dry-run passes.
- Snail explicitly approves first real test post.
- Kill switch exists.

## Stop conditions

Stop and ask Snail if:

- Token is missing or invalid.
- Facebook permission is unclear.
- A post has high-risk mother/baby compliance flags.
- Budget mode is `hard_stop`.
- Any command would publish publicly for the first time.
