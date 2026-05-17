# HEARTBEAT — AffiliPilot Lite

## Status
Local MVP complete: approval-gated draft → outbox → approve → ready package → Facebook dry-run plan pipeline deployed.

## Objective
Build a safe, money-first affiliate assistant for Accesstrade/Shopee content on the Facebook Page `Nâng Niu Trái Ngọt Tình Yêu`.

## Current scope
- [x] Blueprint and build proposal
- [x] Mother/baby compliance policy
- [x] Tracking/sub_id strategy
- [x] Input format for product links
- [x] Product scoring skeleton
- [x] Compliance checker skeleton
- [x] Telegram approval model skeleton
- [x] Batch preview CLI (`python -m affilipilot batch-preview`)
- [x] Ready-to-post preview package output
- [x] SQLite approval state repository
- [x] CLI create-batch/status/decide
- [x] Telegram command parser/mock adapter
- [x] CLI handle-text for Telegram-like local simulation
- [x] Publish gate + ready-to-post fallback
- [x] Facebook dry-run/config stub; real publish disabled
- [x] Facebook dry-run publish planner
- [x] Affiliate Link Gate
- [x] Media Gate
- [x] Media fetch/validation pipeline
- [x] Facebook photo dry-run planner
- [x] Manual affiliate-ready input validator/workflow
- [x] Accesstrade link creator dry-run/real API wrapper
- [x] Converted input writer
- [x] Guarded Facebook photo publish function wired to one-post publish command
- [x] Accesstrade config/payload skeleton; real API disabled
- [x] Config/env status loader
- [x] Secret env template/helper
- [x] Integration readiness report
- [x] Budget tracker skeleton
- [x] Daily digest generator
- [x] Markdown day report generator
- [x] Run-day local end-to-end simulation command
- [x] Telegram local outbox delivery bridge
- [x] Compliance-aware approval card buttons
- [x] Quickstart documentation
- [x] Realistic mother/baby sample batch
- [x] Blacklist state skeleton
- [x] Verification script/tests
- [x] One-shot draft workflow (`draft-links`)
- [x] Approval → ready package → Facebook dry-run command (`approve-ready`)
- [x] Full batch status command (`batch-status`)
- [x] Happy-path smoke command/script (`demo-happy-path`, `scripts/smoke_affilipilot.sh`)
- [x] Operator documentation (`docs/operations.md`)

## Not yet enabled
- Accesstrade token/API calls
- Facebook auto-publish
- TikTok/YouTube/video
- Auto-approve
