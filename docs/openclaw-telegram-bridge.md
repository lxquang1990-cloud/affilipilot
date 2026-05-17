# OpenClaw Telegram Bridge

AffiliPilot does not call Telegram Bot API directly. Real delivery should go through OpenClaw's channel delivery path so provider secrets stay inside OpenClaw config/runtime.

The safe bridge is currently **plan-only**: AffiliPilot renders reviewable `openclaw agent --deliver` commands from the local outbox. Operators can inspect and run one command at a time.

## Why plan-only

- Avoid accidental Telegram spam.
- Avoid putting bot tokens in command history, logs, or chat.
- Preserve idempotency: outbox messages are not marked `sent` until the operator decides.
- Keep AffiliPilot independent from OpenClaw internal provider config details.

## Build a delivery plan

```bash
python3 -m affilipilot openclaw-telegram-plan \
  --outbox data/outbox/manual-001.json \
  --reply-to 640968010 \
  --limit 1
```

The command prints one or more shell commands like:

```bash
openclaw agent --message '<approval card text>' --deliver --reply-channel telegram --reply-to 640968010
```

Review each command before running it.

## After manual delivery

Once the operator confirms a message was delivered, mark it locally:

```bash
python3 -m affilipilot mark-outbox \
  --outbox data/outbox/manual-001.json \
  --message-id '<batch-key>:summary' \
  --status sent
```

## Future direct bridge requirements

Before implementing automatic execution, add all of these safeguards:

- explicit `--send` flag, default off
- `--limit` required or default to 1
- OpenClaw CLI availability check
- delivery result capture as JSON under `data/outbox/results/`
- retry policy with backoff and no duplicate sends
- mark `sent` only after OpenClaw confirms delivery
- never print provider tokens or raw OpenClaw config
- tests with mocked subprocess, no real Telegram send

Until then, `openclaw-telegram-plan` remains a reviewable handoff, not a sender.
