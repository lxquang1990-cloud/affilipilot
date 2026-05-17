# Telegram Delivery Bridge — Local Outbox

Sprint 0 does not send Telegram messages directly. Instead, AffiliPilot writes a local outbox JSON that can later be consumed by an OpenClaw/Telegram sender.

## Queue approval batch

```bash
PYTHONPATH=. python3 -m affilipilot queue-telegram \
  --db data/affilipilot.db \
  --batch-key demo-day \
  --outbox data/outbox/telegram.json
```

## Preview pending outbox

```bash
PYTHONPATH=. python3 -m affilipilot outbox \
  --outbox data/outbox/telegram.json
```

## Mark message status

```bash
PYTHONPATH=. python3 -m affilipilot mark-outbox \
  --outbox data/outbox/telegram.json \
  --message-id demo-day:summary \
  --status sent
```

## Why local outbox first

- Avoid accidental Telegram spam.
- Keep delivery retry state explicit.
- Allow manual inspection before real sending.
- Separate business workflow from channel transport.

## Later real sending

A future OpenClaw delivery bridge may read pending outbox messages and send them through the configured Telegram channel. It must not expose secrets and must respect rate limits.
