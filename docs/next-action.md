# Next Action

`next-action` tells the operator the exact next safe step for a batch.

It does not publish and does not call external APIs.

## Command

```bash
PYTHONPATH=. python3 -m affilipilot next-action \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --outbox data/outbox/telegram.json \
  --plan data/publish/demo-day/facebook-plan.json
```

If `--batch-key` is omitted, the latest batch in SQLite is used.

## Decision order

The command recommends one of:

1. `create_batch` — no batch exists yet.
2. `queue_telegram` — batch exists but no outbox messages exist.
3. `mark_batch_delivered` — approval card/summary are not delivered with receipt.
4. `approve_or_reject` — delivery proof exists but operator has not approved.
5. `ready_to_publish` — approval/delivery exist but plan/report is missing.
6. `publish_safe` — at least one post passed all gates.
7. `inspect_ready_to_publish` — plan exists, but posts are blocked; inspect reasons.

Use this when you are unsure where the AffiliPilot pipeline stopped.
