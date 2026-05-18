# OpenClaw Telegram Bridge

AffiliPilot does not handle Telegram bot tokens. Delivery goes through OpenClaw's configured channel path so provider secrets stay inside OpenClaw config/runtime.

There are two bridge modes:

1. `openclaw-telegram-plan` — review commands only, no send.
2. `openclaw-telegram-send` — execute OpenClaw CLI delivery for pending outbox messages.

## Plan-only mode

```bash
python3 -m affilipilot openclaw-telegram-plan \
  --outbox data/outbox/manual-001.json \
  --reply-to 640968010 \
  --limit 1
```

This prints reviewable `openclaw agent --deliver` commands.

## Send mode

```bash
python3 -m affilipilot openclaw-telegram-send \
  --outbox data/outbox/manual-001.json \
  --reply-to 640968010 \
  --limit 1
```

Safety defaults:

- `--limit` defaults to `1`.
- Message is marked `sent` only after OpenClaw exits with code `0`.
- Message is marked `delivered` only when OpenClaw output contains JSON with one of:
  - `receipt`
  - `message_id`
  - `id`
- If no receipt/message id exists, publish gate remains blocked because `sent` is not enough.
- On CLI error, message is marked `failed`.
- Tokens and provider config are never printed.

Expected receipt format after message id capture:

```text
telegram:<chat_id>:<message_id>
```

## Publish gate reminder

Real Facebook publish still requires `publish-safe` to pass:

- operator approval is `approved`
- summary + selected approval card are `delivered`
- both delivered messages have receipts
- Facebook dry-run plan says `publishable_dry_run`

`openclaw-telegram-send` alone never publishes to Facebook.
