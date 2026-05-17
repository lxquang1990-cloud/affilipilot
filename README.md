# AffiliPilot Lite

Money-first, approval-gated Accesstrade/Shopee affiliate assistant for SnailBot and the Facebook Page `Nâng Niu Trái Ngọt Tình Yêu`.

AffiliPilot turns product links into scored Vietnamese Facebook drafts, runs mother/baby compliance checks, creates Telegram-style approval cards, tracks approval state, builds ready-to-post packages, and generates Facebook Graph API dry-run plans.

## Current status

Local MVP is usable and production-safe by default.

Implemented:

- manual link/CSV input
- product scoring
- deterministic Vietnamese caption generation
- mother/baby compliance checker
- affiliate disclosure guard
- affiliate link gate
- media gate
- SQLite approval state
- Telegram command parser/mock adapter
- local Telegram outbox and delivery dry-run
- ready-to-post package
- Facebook publish gate
- Facebook dry-run planner
- guarded one-post Facebook publish command
- Accesstrade link conversion wrapper, dry-run by default
- readiness report
- budget tracker skeleton
- daily digest/report skeleton
- end-to-end happy-path smoke command

Not enabled by default:

- Accesstrade real API calls
- Telegram Bot API direct send
- Facebook auto-publish
- auto-approve
- TikTok/YouTube/video automation

## Quick start

```bash
cd /home/snail/.openclaw/workspace/affilipilot
scripts/verify_all.sh
```

Run deterministic local smoke:

```bash
python3 -m affilipilot demo-happy-path
```

Create drafts from product links:

```bash
python3 -m affilipilot draft-links \
  --input examples/mom_baby_links.txt \
  --work-dir data/runs/manual \
  --db data/affilipilot.db \
  --batch-key manual-001 \
  --limit 5 \
  --outbox data/outbox/manual-001.json \
  --show-preview
```

Review status:

```bash
python3 -m affilipilot batch-status \
  --db data/affilipilot.db \
  --batch-key manual-001
```

Full operator guide: [`docs/operations.md`](docs/operations.md)

## Main commands

```text
readiness          Show integration readiness gates
draft-links        Links -> drafts -> approval batch -> local outbox
handle-text        Simulate Telegram text input
outbox             Render local pending outbox messages
deliver-telegram   Dry-run local delivery / mark sent
status             Approval-only status
decide             Approve/reject/edit/blacklist a post
approve-ready      Ready package + Facebook dry-run plan
batch-status       Full batch summary with optional Facebook plan
demo-happy-path    Deterministic end-to-end local smoke
facebook-plan      Build Facebook dry-run plan
facebook-token-check Check Facebook token/scopes without printing secrets
facebook-publish-one Guarded real publish for exactly one dry-run publishable post
accesstrade-convert Convert links to Accesstrade tracking links; dry-run by default
```

## Safety guarantees

- `draft-links`, `handle-text`, `deliver-telegram`, `approve-ready`, `batch-status`, and `demo-happy-path` do not publish to Facebook.
- `deliver-telegram` does not call Telegram APIs; it renders/marks local outbox only.
- Real Accesstrade conversion requires `accesstrade-convert --real`.
- Real Facebook publish is only through `facebook-publish-one`, and it refuses plans that are not `publishable_dry_run`.
- Secrets should live outside chat/history, e.g. `/home/snail/.openclaw/workspace/secrets/affilipilot.env` with chmod `600`.

## Verification

```bash
scripts/verify_all.sh
```

Current verification includes:

- Python compileall
- pytest suite
- happy-path smoke
- obvious secret scan

## Docs

- [`docs/operations.md`](docs/operations.md) — operator workflow
- [`docs/quickstart.md`](docs/quickstart.md) — quick local start
- [`docs/compliance-policy-mom-baby.md`](docs/compliance-policy-mom-baby.md)
- [`docs/tracking-strategy.md`](docs/tracking-strategy.md)
- [`docs/publish-gate.md`](docs/publish-gate.md)
- [`docs/facebook-dry-run-plan.md`](docs/facebook-dry-run-plan.md)
- [`docs/accesstrade-link-creator.md`](docs/accesstrade-link-creator.md)
- [`docs/telegram-delivery.md`](docs/telegram-delivery.md)

- [`docs/first-real-publish-checklist.md`](docs/first-real-publish-checklist.md) — mandatory checklist before first real Facebook publish

- [`docs/openclaw-telegram-bridge.md`](docs/openclaw-telegram-bridge.md) — safe plan-only OpenClaw Telegram delivery handoff

- [`docs/facebook-token-manager.md`](docs/facebook-token-manager.md) — safe Facebook token exchange/refresh flow

- [`docs/product-scanner.md`](docs/product-scanner.md) — scan category/deal pages into product drafts and approval batches
