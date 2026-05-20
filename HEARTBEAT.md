# HEARTBEAT — AffiliPilot Lite

## Status
Production-hardened automation-first MVP. The pipeline can discover/ingest candidate products, filter and score them, convert affiliate links, generate gated Vietnamese captions, enrich media, queue only vetted approval cards, build publish-safe previews, and publish to Facebook only through explicit guarded commands.

Latest verification: `PYTHONPATH=. pytest` → 217 passed.

## Objective
Build a safe, money-first affiliate assistant for Accesstrade/Shopee/Tiki-style content on the Facebook Page `Nâng Niu Trái Ngọt Tình Yêu`, with low operator friction and strong publish guardrails.

## Current scope
- [x] Blueprint, compliance policy, and tracking/sub_id strategy
- [x] Manual product input, scoring, Vietnamese caption generation, and Telegram-style approval model
- [x] Accesstrade conversion/shortlink flow and docs-correct broad datafeed handling
- [x] Tiki campaign fallback mapping for conversion
- [x] Profit-first E2E workflow and Auto Source Hunter workflow
- [x] Seed Hunter / Seed Auto fallback path
- [x] Product risk, taste, market-fit, and content quality gates
- [x] PMO-style content Gate A/B/C plus bounded regeneration
- [x] Product archetype generator with shortened affiliate disclosure
- [x] PDP media enrichment for galleries/video URLs and local media validation
- [x] Facebook publish planner with single-photo, multi-photo, and video-first strategies
- [x] SQLite approval state, delivery-proof gates, ready package builder, and publish-safe validator
- [x] Guarded real Facebook publish command
- [x] Event log, circuit breaker, kill switch, and time-boxed test auto-publish controls
- [x] Tests/regressions for content, source, media, publish safety, and Accesstrade behavior

## Not enabled by default
- Arbitrary Facebook auto-publish outside explicit guarded test windows
- Publish without delivery proof, approval, and publish-safe PASS
- Anti-bot bypass for Shopee/Lazada
- Direct Telegram Bot API sending outside the OpenClaw bridge
- TikTok/YouTube/Reels publishing

## Next
- [ ] Improve PDP media enrichment pass rate while keeping wrong-media blocks strict
- [ ] Auto-record publish lifecycle event after successful `facebook-publish-one`
- [ ] Add optional browser discovery when the runtime is available
- [ ] Strengthen ROI feedback loop for source/product selection
