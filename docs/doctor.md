# Doctor

`doctor` is a read-only audit for AffiliPilot operations.

It checks local configuration and workflow state without calling Facebook, Telegram, or Accesstrade APIs. It never prints secret values.

## Command

```bash
PYTHONPATH=. python3 -m affilipilot doctor \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --outbox data/outbox/telegram.json
```

Optional:

```bash
--secret-path /home/snail/.openclaw/workspace/secrets/affilipilot.env
```

## Checks

- secret file exists and has safe permissions
- SQLite DB exists
- Telegram outbox exists
- Facebook config presence, without token value
- Accesstrade config presence, without token value
- direct Telegram bot config presence
- local manual workflow readiness
- latest/specified batch summary
- approval status counts
- outbox message status counts

## Exit code

- `0` when the local workflow is not blocked by required config presence.
- `2` when a blocker is detected.

`doctor` is intended before campaign work or when the pipeline state is unclear. Use `next-action` after `doctor` to get the exact next command.
