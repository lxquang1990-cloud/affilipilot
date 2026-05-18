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

`sent` means the local transport handoff happened. It is **not enough** for production publish.

```bash
PYTHONPATH=. python3 -m affilipilot mark-outbox \
  --outbox data/outbox/telegram.json \
  --message-id demo-day:summary \
  --status sent
```

`delivered` means the operator has real Telegram/provider delivery proof. This is the status required by the Facebook production publish gate.

For production, prefer marking the whole publish pair — batch summary + selected approval card — in one command:

```bash
PYTHONPATH=. python3 -m affilipilot mark-batch-delivered \
  --outbox data/outbox/telegram.json \
  --batch-key demo-day \
  --post-id post_20260516_001 \
  --receipt telegram:640968010:7532
```

For low-level testing only, you can mark pending outbox messages directly:

```bash
PYTHONPATH=. python3 -m affilipilot deliver-telegram \
  --outbox data/outbox/telegram.json \
  --mark-delivered \
  --receipt telegram:640968010:7532
```

## Why local outbox first

- Avoid accidental Telegram spam.
- Keep delivery retry state explicit.
- Allow manual inspection before real sending.
- Separate business workflow from channel transport.

## Later real sending

A future OpenClaw delivery bridge may read pending outbox messages and send them through the configured Telegram channel. It must not expose secrets and must respect rate limits.

Production Facebook publish must remain blocked until both the batch summary and the selected approval card have status `delivered` in the outbox.
