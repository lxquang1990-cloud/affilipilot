# Facebook Dry-run Planner

The Facebook planner builds a Graph API publish plan for approved posts without sending any request.

## Command

```bash
PYTHONPATH=. python3 -m affilipilot facebook-plan \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --out data/publish/facebook-plan.json
```

## What it validates

- Post is approved by Snail.
- Compliance gate passes.
- Affiliate disclosure is present.
- Facebook Page ID/token are present.
- Post text is non-empty.
- Duplicate post text is blocked.

## What it outputs

- Summary in terminal.
- JSON plan containing endpoint and payload preview.

Example endpoint:

```text
/PAGE_ID/feed
```

Example payload fields:

```json
{
  "message": "...",
  "link": "https://shopee.vn/..."
}
```

## Guardrail

This command never POSTs to Facebook. Real publishing remains disabled until Snail explicitly approves the first public publish test.
