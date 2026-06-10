# AffiliPilot Lite

Smart-shopping, approval-gated Accesstrade/Shopee/Tiki affiliate assistant for SnailBot. AffiliPilot helps find, filter, draft, approve, and publish useful Vietnamese shopping posts without being tied to one niche or one Facebook Page.

AffiliPilot turns product links into scored Vietnamese drafts for “mua sắm thông minh”: practical household items, daily consumables, small tech, home organization, kitchen/cleaning tools, personal care, and mother/baby items when relevant. It runs compliance/product-quality gates, creates Telegram-style approval cards, tracks approval state, validates media/shortlinks/publish safety, and can publish to Facebook only through guarded workflows.

## Current status

Production-hardened MVP. Safe by default, with an explicitly time-boxed test auto-publish mode available on this Pi.

Implemented:

- manual link/CSV input
- Accesstrade campaign registry, conversion/shortlink flow, and report/order helpers
- profit-first E2E workflow: discovery -> filtering -> scoring -> conversion -> draft -> content gates/regeneration -> approval outbox -> ready/publish-safe preview
- official shortlink enforcement; raw Accesstrade/isclix URLs are blocked from Facebook captions
- product risk, taste, market-fit, PMO-style content Gate A/B/C, and portfolio/category-diversity gates
- automatic source hunting with Accesstrade broad-source fallback, Tiki campaign support, curated seed fallback, and local quality filtering
- real PDP media enrichment for Shopee/Tiki/Lazada candidates, including gallery images and video URLs
- local media/video validation and cache support
- Facebook strategies: `single_photo`, `multi_photo`, `video_primary`, `video_primary_with_image_comment`, `reel_primary`, and `reel_primary_with_image_comment` with safe video-post fallback when the Page Reels upload flow is unavailable
- video-first and multi-photo publish planning when valid product media is available
- SQLite approval state and local conversion/ROI table
- Telegram command parser/mock adapter, local outbox, OpenClaw Telegram delivery bridge, and delivery-proof gates
- ready-to-publish package builder and publish-safe validator
- guarded one-post Facebook publish command
- 7-day guarded auto-publish scheduler for a Facebook test window (`scripts/auto_publish_e2e.py`)
- structured JSONL event log, circuit breaker, and `/tmp/affilipilot.KILL` kill switch
- confidence scoring and tier classification (`auto`, `soft_gate`, `manual`, `blocked`)
- Seed Hunter with curated keyword config, Shopee public API adapter, Shopee Accesstrade sheet sources, per-source cursor rotation, seed-file fallback, and seed-to-auto E2E workflow
- readiness/doctor/campaign-status dashboards
- budget tracker and daily digest/report skeletons

Not enabled by default:

- arbitrary Facebook auto-publish outside an explicit state/TTL window
- unsafe publish bypasses
- Telegram Bot API direct send outside the OpenClaw bridge
- third-party marketplace scraper APIs without explicit API key/config
- anti-bot bypass for Shopee/Lazada
- TikTok/YouTube publishing


## Latest release notes — June 2026

This version focuses on making scheduled profit E2E more reliable, broader, and publish-safe:

- Scheduled E2E now queues up to 3 candidates per run (`--limit 3`) while retaining approval-first publishing.
- Shopee Accesstrade sheet sourcing now includes best-sellers, major-programs, and brand-bonus mappings with per-source cursor rotation so deeper rows are explored across runs.
- Google Sheet fetch falls back from `/export?format=csv` to `/gviz/tq?tqx=out:csv` when Google rejects direct export.
- Manual E2E batches use the same recent-selected duplicate filter as scheduled batches, reducing repeated candidate selection.
- Shopee PDP media enrichment probes galleries when source media is thin and strips Shopee app/UI assets from persisted product media.
- Telegram approval publish artifacts are batch-scoped to avoid stale cross-batch Facebook plan reuse.
- Reels publish plans fall back to Page video posts when Graph requires the multi-step `upload_phase` flow; image comments remain best-effort after primary publish.

Previous May 2026 focus:

- Auto Source Hunter can collect broad Accesstrade inputs, prefer cleaner Tiki/Shopee-style candidates when available, convert links, draft captions, gate content, and queue only vetted approval cards.
- Accesstrade `/v1/datafeeds` is treated as a broad/fallback source only; undocumented category request filters are not sent. Intended category lives as local `target_category` metadata.
- Tiki CPS campaign fallback is supported for link conversion.
- Content generation now uses product archetypes plus bounded regeneration before approval. Generic template phrases are blocked; caption hints are product-specific.
- Affiliate disclosure is intentionally retained for transparency/compliance, but shortened to a less intrusive sentence.
- PDP media enrichment preserves galleries/video URLs before Facebook planning, so valid posts can use `multi_photo` or video-first strategies instead of silently falling back to one image.
- Publish remains guarded by delivery proof, explicit approval, and `publish-safe` PASS. In normal Telegram UX, one approval can trigger immediate publish; if any gate fails, publish is blocked and reported.

## Quick start

Install the package (editable install recommended during development):

```bash
git clone https://github.com/lxquang1990-cloud/affilipilot.git
cd affilipilot
pip install -e .            # or: pip install -e ".[dev,browser]" for full tooling
```

Verify the install:

```bash
affilipilot demo-happy-path
```

Or, without installing, run as a module:

```bash
PYTHONPATH=. python3 -m affilipilot demo-happy-path
```

On Snail's Pi the legacy `/home/snail/.openclaw/workspace/affilipilot` layout is
still supported — both invocation styles work side by side.

Run deterministic local smoke:

```bash
affilipilot demo-happy-path
```

Run the standard profit-first E2E without publishing:

```bash
python3 -m affilipilot profit-e2e \
  --batch-key test-profit \
  --work-dir data/runs/test-profit \
  --db data/affilipilot.db \
  --outbox data/outbox/test-profit.json \
  --sources config/profit-scan-broader.json \
  --discover-limit 40 \
  --limit 1 \
  --real-accesstrade
```

Review status:

```bash
python3 -m affilipilot campaign-status \
  --db data/affilipilot.db \
  --batch-key test-profit \
  --outbox data/outbox/test-profit.json
```

Full operator guide: [`docs/operations.md`](docs/operations.md)

## Automation-first controls

### Event log

```bash
python3 -m affilipilot event-log --limit 30
```

Default path:

```text
data/logs/affilipilot-events.jsonl
```

Important events include:

```text
auto_publish_started
auto_publish_no_publishable_batch
auto_publish_succeeded
auto_publish_failed
auto_publish_done
auto_publish_blocked
kill_switch_changed
draft_classified
```

### Circuit breaker and kill switch

```bash
python3 -m affilipilot circuit-status
python3 -m affilipilot kill-switch on --reason "operator pause"
python3 -m affilipilot kill-switch off
```

The scheduler blocks when:

- `/tmp/affilipilot.KILL` exists
- `data/auto_publish_state.json` has `enabled=false`
- the state TTL has expired
- 3 consecutive publish failures are observed in the event log

### Confidence score and tier classification

```bash
python3 -m affilipilot score-tier \
  --input data/runs/seed-hunter/seed-hunter.input.txt \
  --config config/tier-config.json
```

Default tiers:

```text
auto       score >= 0.85 and compliance ok
soft_gate  score >= 0.70
manual     score >= 0.50
blocked    compliance fail or weak score
```

Emergency override:

```bash
AFFILIPILOT_FORCE_MANUAL=1 python3 -m affilipilot score-tier --input <file>
```

### Conversion/ROI tracking

```bash
python3 -m affilipilot conversion-record \
  --sub-id ap_b001_d001_20260519 \
  --order-id order-001 \
  --status approved \
  --commission-vnd 12000 \
  --order-value-vnd 200000

python3 -m affilipilot conversion-summary
```

The local conversion table is intentionally idempotent by `(sub_id, order_id)`.

## Seed Hunter

Seed Hunter tries to find or validate product seeds before E2E.

```bash
python3 scripts/seed_hunter.py \
  --source shopee_api \
  --out-dir data/runs/seed-hunter \
  --limit 10
```

Current caveat: Shopee public API from this Pi may return anti-bot `403 / 90309999`. The code records this as `blocked_by_shopee_403` and does **not** attempt bypass.

Fallback with curated PDP seed file:

```bash
python3 scripts/seed_hunter.py \
  --source seed_file \
  --seed-file data/manual-seeds.input.txt \
  --out-dir data/runs/seed-hunter-manual \
  --limit 10
```

Then feed the generated input into the normal conversion/E2E workflow, or use the one-shot curated seed workflow:

```bash
python3 scripts/seed_to_auto_e2e.py \
  --seed-file data/manual-seeds.input.txt \
  --batch-key seed-auto-smoke \
  --work-dir data/runs/seed-auto/seed-auto-smoke \
  --limit 1 \
  --campaign-key shopee
```

See [`docs/seed-source-upgrade.md`](docs/seed-source-upgrade.md).

## Main commands

```text
event-log            Render structured automation/audit events
circuit-status       Show auto-publish circuit breaker status
kill-switch          Toggle /tmp/affilipilot.KILL
score-tier           Confidence score + auto/soft/manual/blocked classification
conversion-record    Insert/update one conversion row
conversion-summary   Summarize local conversion/ROI table
readiness            Show integration readiness gates
profit-e2e           Profit-first E2E; no direct Facebook publish
draft-links          Links -> drafts -> approval batch -> local outbox
handle-text          Simulate Telegram text input
outbox               Render local pending outbox messages
openclaw-telegram-send Send pending outbox via OpenClaw CLI; delivered only with receipt
status               Approval-only status
decide               Approve/reject/edit/blacklist a post
batch-status         Full batch summary with optional Facebook plan
facebook-plan        Build Facebook dry-run plan
facebook-token-check Check Facebook token/scopes without printing secrets
facebook-publish-one Guarded real publish for exactly one planned post
publish-safe         Validate approval + delivery proof + plan before optional publish
ready-to-publish     Ready package + Facebook plan + publish-safe status; no publish
next-action          Recommend exact next operator step; no publish
doctor               Read-only audit; no external API calls
campaign-status      One-screen dashboard
accesstrade-convert  Convert links to Accesstrade tracking links; dry-run by default
accesstrade-orders   Fetch/summarize Accesstrade orders
```

## Safety guarantees

- Most commands are read-only or plan-only; `profit-e2e`, `ready-to-publish`, `facebook-plan`, `doctor`, and `campaign-status` do not publish directly.
- Real Accesstrade conversion requires explicit `--real`/`--real-accesstrade` flags where applicable.
- Real Facebook publish goes through guarded publish commands and publish-safe validation.
- Production publish requires approval and delivery proof unless an explicit time-boxed test state permits scheduler auto-approval.
- The auto scheduler checks circuit breaker state before doing work and logs structured events.
- Raw affiliate/deep links are blocked from captions; official/trusted shortlinks are required.
- If valid product video exists, video-first planning is preferred; image-only fallback is not silent.
- Secrets should live outside chat/history, e.g. `~/.config/affilipilot/secrets.env` with chmod `600` (or `/home/snail/.openclaw/workspace/secrets/affilipilot.env` on Snail's Pi). Override path via `AFFILIPILOT_SECRETS=/custom/path/.env`.

## Verification

```bash
PYTHONPATH=. pytest -q
scripts/verify_all.sh
```

Current verification includes:

- Python compileall
- pytest suite
- happy-path smoke
- obvious secret scan

Latest local regression at README update time:

```text
191 passed
```

## Docs

- [`docs/operations.md`](docs/operations.md) — operator workflow
- [`docs/quickstart.md`](docs/quickstart.md) — quick local start
- [`docs/automation-first.md`](docs/automation-first.md) — event log, circuit breaker, tier scoring, seed/ROI automation
- [`docs/seed-source-upgrade.md`](docs/seed-source-upgrade.md) — curated seed file to validated/optional publish workflow
- [`docs/compliance-policy-mom-baby.md`](docs/compliance-policy-mom-baby.md)
- [`docs/tracking-strategy.md`](docs/tracking-strategy.md)
- [`docs/publish-gate.md`](docs/publish-gate.md)
- [`docs/publish-safe.md`](docs/publish-safe.md)
- [`docs/ready-to-publish.md`](docs/ready-to-publish.md)
- [`docs/next-action.md`](docs/next-action.md)
- [`docs/doctor.md`](docs/doctor.md)
- [`docs/campaign-status.md`](docs/campaign-status.md)
- [`docs/facebook-dry-run-plan.md`](docs/facebook-dry-run-plan.md)
- [`docs/accesstrade-link-creator.md`](docs/accesstrade-link-creator.md)
- [`docs/telegram-delivery.md`](docs/telegram-delivery.md)
- [`docs/telegram-commands.md`](docs/telegram-commands.md)
- [`docs/first-real-publish-checklist.md`](docs/first-real-publish-checklist.md)
- [`docs/openclaw-telegram-bridge.md`](docs/openclaw-telegram-bridge.md)
- [`docs/facebook-token-manager.md`](docs/facebook-token-manager.md)
- [`docs/product-scanner.md`](docs/product-scanner.md)
