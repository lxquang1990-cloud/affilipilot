# Ready To Publish

`ready-to-publish` is the operator dashboard command before a real Facebook publish.

It performs no network calls and does not publish. It bundles three safe steps:

1. Build the ready-to-post package.
2. Build the Facebook dry-run plan.
3. Run `publish-safe` validation for every post in the batch.

## Command

```bash
PYTHONPATH=. python3 -m affilipilot ready-to-publish \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --outbox data/outbox/telegram.json \
  --out-dir data/publish/demo-day
```

## Output

The command prints a human summary and writes:

- `ready/ready_package.json`
- `facebook-plan.json`
- `ready-to-publish.json`

A post is shown as `PASS` only when:

- approval is `approved`
- summary and approval card are `delivered` with receipt
- Facebook plan status is `publishable_dry_run`

Use `publish-safe --check-only` or `publish-safe` for the final selected post after reviewing the report.
