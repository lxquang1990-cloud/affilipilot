# Publish Gate

AffiliPilot must never publish directly to Facebook unless every gate passes.

## Required conditions

- Snail approved the post.
- Compliance status is `pass`.
- Affiliate disclosure is present in post text.
- Facebook config is verified.
- Publish dry-run passed.
- Kill switch is off.

## Fallback

If a post is approved but Facebook is not verified or dry-run did not pass, AffiliPilot creates a ready-to-post package instead of publishing.

Command:

```bash
PYTHONPATH=. python3 -m affilipilot ready-package \
  --db data/affilipilot.db \
  --batch-key <batch_key> \
  --out-dir data/ready/<batch_key>
```

Output:

- `ready_package.json`
- `<post_id>.ready-to-post.txt`

## Real publish status

Real Facebook publish is intentionally disabled in Sprint 0. `publish_post()` raises a RuntimeError until an explicit integration step is approved and verified.
