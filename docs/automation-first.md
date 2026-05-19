# Automation-First AffiliPilot

This document describes the current automation-first controls in AffiliPilot. The goal is to increase automation while preserving safety, reversibility, and auditability.

## Core principles

1. **Trust through tiers** — not all posts are equal. High-confidence posts may become auto candidates; medium-confidence posts go to soft/manual gates; weak/risky posts are blocked.
2. **Observability first** — every auto action should leave a structured audit event.
3. **Reversibility** — the operator can stop automation with a kill switch, state toggle, or expired TTL.
4. **No anti-bot bypass** — marketplace discovery uses permitted APIs, existing sources, browser-rendered extraction when available, or curated seed files. AffiliPilot does not attempt to bypass Shopee/Lazada anti-bot controls.

## Structured event log

Default path:

```text
data/logs/affilipilot-events.jsonl
```

Render recent events:

```bash
python3 -m affilipilot.cli event-log --limit 30
```

Common events:

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

## Circuit breaker

Check status:

```bash
python3 -m affilipilot.cli circuit-status
```

The circuit blocks automation when:

- `/tmp/affilipilot.KILL` exists
- `data/auto_publish_state.json` has `enabled=false`
- the state `expires_at` TTL has passed
- the event log shows 3 consecutive publish failures

Toggle kill switch:

```bash
python3 -m affilipilot.cli kill-switch on --reason "operator pause"
python3 -m affilipilot.cli kill-switch off
```

## Tier scoring

Config:

```text
config/tier-config.json
```

Score an input file:

```bash
python3 -m affilipilot.cli score-tier \
  --input data/runs/seed-hunter/seed-hunter.input.txt \
  --config config/tier-config.json
```

Default tiers:

```text
auto       score >= 0.85 and compliance signal ok
soft_gate  score >= 0.70
manual     score >= 0.50
blocked    compliance fail or weak score
```

Emergency manual-only mode:

```bash
AFFILIPILOT_FORCE_MANUAL=1 python3 -m affilipilot.cli score-tier --input <file>
```

## Seed Hunter

Automatic seed search remains the hardest part. Shopee public API can return anti-bot `403 / 90309999` from this Pi, so `shopee_api` source may produce zero seeds. This is expected and should not be bypassed.

Use curated seed files when needed:

```bash
python3 scripts/seed_hunter.py \
  --source seed_file \
  --seed-file data/manual-seeds.input.txt \
  --out-dir data/runs/seed-hunter-manual \
  --limit 10
```

The generated `seed-hunter.input.txt` can then be fed into normal Accesstrade conversion and quality/publish-safe gates.

## Conversion / ROI tracking

Record one conversion/order:

```bash
python3 -m affilipilot.cli conversion-record \
  --sub-id ap_b001_d001_20260519 \
  --order-id order-001 \
  --status approved \
  --commission-vnd 12000 \
  --order-value-vnd 200000
```

Summarize conversions:

```bash
python3 -m affilipilot.cli conversion-summary
```

Rows are idempotent by `(sub_id, order_id)`.

## Auto-publish scheduler

The local scheduler is:

```text
scripts/auto_publish_e2e.py
```

It performs:

```text
profit-e2e
→ synthetic approval/delivery only inside explicit test window
→ ready-to-publish
→ publish-safe
→ guarded publish
→ event log
```

It exits safely without publishing if no product passes gates.

## Current limitation

The broad Accesstrade feed is noisy and often returns medical/supplement/low-fit products. The preferred path for reliable automation is:

```text
curated/manual seed list or permitted marketplace API
→ Seed Hunter validation
→ Accesstrade official shortlink conversion
→ media/video enrichment
→ quality/product gates
→ tier scoring
→ publish-safe
```
