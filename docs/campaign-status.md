# Campaign Status

`campaign-status` is the one-screen operator dashboard for AffiliPilot.

It combines:

- `doctor` summary
- `next-action` recommendation
- `ready-to-publish` summary

It does not publish and does not call external APIs. By default, it writes local ready/plan/report files so the dashboard is based on fresh data.

## Command

```bash
PYTHONPATH=. python3 -m affilipilot campaign-status \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --outbox data/outbox/telegram.json \
  --out-dir data/publish/demo-day
```

Optional:

```bash
--no-build-ready   # skip writing fresh ready/plan/report files
--secret-path /home/snail/.openclaw/workspace/secrets/affilipilot.env
```

## Use

Run this when you want to know, in one glance:

- whether local config/state is healthy
- what command should be run next
- how many posts are ready, held, publishable, or blocked
- per-post publish-safe reasons

If `Next` says `READY_TO_PUBLISH`, review the report, then use `publish-safe --check-only` before the final `publish-safe` command.
