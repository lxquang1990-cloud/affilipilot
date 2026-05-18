# Telegram Commands

AffiliPilot's Telegram adapter supports safe operator commands. These commands are local adapter actions; they do not publish to Facebook.

## Status commands

```text
/campaign_status [batch_key]
/next_action [batch_key]
/doctor [batch_key]
```

Aliases:

```text
/campaign-status, /campaign
/next-action, /next
```

If `batch_key` is omitted or set to `latest`, the latest SQLite batch is used.

## Approval commands

```text
/aff_approve <post_id> [reason]
/aff_reject <post_id> [reason]
/aff_edit <post_id> [reason]
/aff_blacklist <post_id> [reason]
```

AffiliPilot intentionally avoids bare `/approve` because OpenClaw uses that command for native approval cards. Approval commands affect the latest batch only.

## Batch creation

Paste product links directly, or use:

```text
/batch
<link 1>
<link 2>
```

The adapter creates drafts, writes the approval preview, and queues local outbox messages when configured.

## Safety

- `/campaign_status`, `/next_action`, and `/doctor` are read-only except that `/campaign_status` may write local ready/plan/report files.
- None of these commands call Facebook, Telegram Bot API, or Accesstrade.
- Real publish remains gated by `publish-safe`.
