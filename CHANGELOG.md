# CHANGELOG

## 0.4.0 — Revenue loop, publish types, Reels, and engagement ops (May 2026)

### Added
- Shopee shortlink support and canonicalization for links such as `s.shopee.vn`, including rendered PDP data extraction fallback.
- Minimal AI-first caption policy: one AI-generated benefit sentence, fixed price/link CTA, and hashtags; no deterministic long repair fallback for approval captions.
- Tracking identity preservation from Accesstrade conversion through draft/publish IDs (`tracking_post_id`, `tracking_product_id`, `tracking_sub1..4`) so ROI attribution can join on `utm_content/post_id`.
- ROI digest MVP joining published post mappings with Accesstrade orders/conversions; supports `roi-digest`, `--sync`, `--dry-run`, and `--queue` without auto-publish.
- Publish lifecycle model and task table with states from draft creation through approval, planning, publish, hidden/deleted/failed/held.
- Platform restriction registry for Facebook Page publish types: `photo_post`, `video_post`, `reel`, `link_post`, and `text_post`.
- Social metrics/data cube foundation with `publish_type` and `metrics_profile` separation for feed posts, videos, and Reels.
- Engagement/comment workflow: comment capture, AI reply suggestion, Telegram review queue, and operator-approved `/aff_reply` / `/aff_ignore` command handling.
- Facebook publish strategy selector with video probing via `ffprobe`; vertical short local videos can plan as Reels, other videos as video posts.
- Publish-type-aware caption guidance so AI prompt knows whether the plan is photo/video/Reel/link/text while preserving the minimal rendered caption format.
- Publish-type media/restriction gate: photo requires image, video requires local video, Reel requires valid vertical short video, link post is weak-media fallback, text post blocks affiliate publishing.
- Production Reel dispatch path (`reel_primary -> /{page_id}/reels`) behind existing Telegram delivery proof, approval, dry-run, media gate, and publish-safe validation.
- Scheduled Facebook insights sync foundation (`facebook-insights-sync-scheduled` and `scripts/scheduled_facebook_insights_sync.sh`) with Telegram digest queueing.
- Durable operating model documentation in `docs/OPERATING_MODEL.md`.

### Changed
- Scheduled AffiliPilot cron wrapper always notifies Telegram: approval card if posts are ready, digest/status if zero posts are publish-ready.
- Caption safety rules now act as AI prompt feedback/guardrails instead of bypassing AI with deterministic templates.
- Facebook planning now records and renders `publish_type` / `metrics_profile` through approval cards, lifecycle, dry-run payload, and data cube.
- Comment reply workflow remains approval-first: AI may suggest, but only explicit operator command sends a reply.

### Fixed
- Cron PATH issue that prevented scheduled Telegram delivery from finding `openclaw` under minimal cron environment.
- Shopee product/media extraction false positives and shortlink flows that previously required full product URLs.
- Warning/checklist caption phrases for baby/play products that conflicted with the concise caption policy.

### Verification
- Focused compile, pytest, smoke, doctor, and diff-check passes across the new release branches.
- Latest pushed feature commits included: `8f87fd4`, `4d8f3ec`, `8247bde`, `4e36f90`, `ff4a0fa`, `20b9cd9`, `06a66f7`, `0c7df49`, `3556a92`.

## 0.3.0 — Automation-first content/media pipeline (May 2026)

### Added
- Approval-triggered publish path: one operator approval can now save approval, verify delivery proof, rebuild Facebook plan, run `publish-safe`, publish to the Page if PASS, and record lifecycle state.
- Auto Source Hunter workflow for low-touch product input discovery, local quality filtering, link conversion, content drafting, media enrichment, approval-card queueing, and publish-safe preview.
- Seed Auto workflow and seed hunter updates that avoid undocumented Accesstrade category filters.
- PMO-style content Gate A/B/C and bounded regeneration before approval cards are queued.
- Product archetype caption generation for baby care towels, feeding items, home storage, cleaning appliances, and kitchen appliances.
- PDP media enrichment preservation for product galleries/video URLs, plus filename collision protection for CDN URLs with query params.
- Regression tests for auto-source quality, media enrichment, content gates, content regeneration, generator archetypes, and Accesstrade docs-correct behavior.

### Changed
- Accesstrade `/v1/datafeeds` is now treated as broad/fallback input only; undocumented `cat` request filtering was removed. Use local `target_category` metadata for reporting/filtering.
- Added Tiki CPS fallback campaign mapping for conversion.
- Approval workflow now blocks non-publish-ready cards earlier when content/media/link metadata are insufficient.
- Caption copy no longer emits generic checklist dumps such as “Khi xem sản phẩm, nên check kỹ…”. It uses shorter product-specific hints instead.
- Affiliate disclosure remains required for transparency/compliance, but the default wording is shorter and less intrusive.
- Facebook planning can now receive enriched multi-image/video metadata upstream and emit richer strategies when media gates pass.

### Fixed
- Root cause of single-image Facebook posts: upstream sources only passed one image and skipped PDP gallery enrichment before planning.
- Media enrichment scoring now prefers larger Tiki/Lazada/Shopee product images and down-ranks thumbnails/static app assets.
- Shopee/Lazada/Tiki discovery fallbacks are safer: blocked/unstable sources are reported and locally gated instead of bypassed.

### Verification
- `PYTHONPATH=. pytest` → 217 passed.

## 0.2.0 — Optimization pass (May 2026)

### Fixed
- `scanner/browser_exec.py`: contract violation when Playwright is installed but the page returns no items — `BrowserExecutionResult` now always populates `error` when `ok=False` so callers can log a reason. Fixes `test_browser_exec.py::test_browser_render_discover_gracefully_handles_missing_runtime`.
- `accesstrade/client.py`: `create_tracking_link(dry_run=True)` no longer requires a configured token to succeed. Dry-run is intended for pipeline validation; config gating is the job of `check_accesstrade_config`. Fixes `test_accesstrade_links.py::test_convert_and_write_input` and `test_discover_convert.py::test_discover_convert_dry_run`.
- `publishing/facebook.py`, `facebook_token_manager.py`: added explicit `import urllib.error` (was relying on implicit re-export via `urllib.request`).

### Security
- New `affilipilot/security.py` module exports `redact_for_audit` and `redact_response`. Centralizes the redaction logic previously duplicated in `accesstrade/client.py`.
- `publishing/facebook.py` now redacts every Graph API response before returning it, including HTTP error bodies. The publish result written by `facebook-publish-one` to disk is also passed through `redact_response` defense-in-depth.
- Redaction patterns extended to catch inline `access_token=...`, `Bearer ...`, and `EAA...` Facebook token prefixes inside free-form strings, not just dict keys.

### Performance
- `config.py:load_env_file` now caches by `(path, mtime_ns)` via `lru_cache`. The dotenv secret file used to be re-parsed dozens of times per E2E run.
- `db.py:AffiliPilotDB.init` skips `executescript(SCHEMA)` after the first call within a process. Reduces SQLite write traffic in long workflows.

### Portability
- `config.DEFAULT_SECRET_PATH` is now resolved at import time with fallback: `AFFILIPILOT_SECRETS` env var → legacy Pi path → XDG `~/.config/affilipilot/secrets.env`. Previously hard-coded to the Pi-specific path.

### Packaging
- New `pyproject.toml` with PEP 517 build, `affilipilot` console entry point, optional extras `[browser]` (Playwright) and `[dev]` (pytest/ruff/mypy/coverage).
- New Makefile targets: `install`, `install-dev`, `test-cov`, `lint`, `format`, `type-check`.

### Refactor
- `cli.py` (1367 lines) split into `cli/` package with registry pattern:
  - `cli/_registry.py`: `@register` decorator and `build_parser`/`main` entry points.
  - `cli/observability.py`: `event-log`, `circuit-status`, `kill-switch`, `score-tier`, `conversion-record`, `conversion-summary` (6 commands).
  - `cli/facebook.py`: `facebook-plan`, `facebook-publish-one`, `facebook-token-check`, `facebook-token-manager` (4 commands).
  - `cli/accesstrade.py`: 7 `accesstrade-*` commands.
  - `cli/_legacy_bridge.py`: automatically bridges the remaining 52 commands still in `_cli_legacy.py` (renamed from `cli.py`). Migration is incremental; bridge auto-skips commands that have moved.
- 17/69 commands migrated (25%). Remaining roadmap documented in `MIGRATION_GUIDE.md`.

### Tests
- 191/191 tests pass (was 188/191). All three previously failing tests are fixed at the code level rather than by adjusting assertions:
  - `test_accesstrade_links.py::test_convert_and_write_input`
  - `test_browser_exec.py::test_browser_render_discover_gracefully_handles_missing_runtime`
  - `test_discover_convert.py::test_discover_convert_dry_run`
- Two existing tests (`test_create_tracking_link_dry_run_*`) updated to reflect the new dry-run contract (synthesizes isclix URLs instead of failing on missing config). The semantic change is documented inline.
- `test_publish_requires_telegram.py` patch targets expanded to cover both the legacy and the new CLI module bindings of `publish_post`.

## 0.1.0 — Initial Sprint 0 scaffold (unreleased)
- Initialize AffiliPilot Lite Sprint 0 scaffold.
- Add one-shot `draft-links` workflow for links → scored drafts → approval batch → local Telegram outbox.
- Add Telegram mock adapter outbox queueing and local `deliver-telegram` dry-run/mark-sent command.
- Add `approve-ready` command for approved-post ready package + Facebook dry-run plan.
- Add `batch-status` command for approvals/compliance/Facebook plan state.
- Add deterministic `demo-happy-path` smoke command and `scripts/smoke_affilipilot.sh`.
- Update README, quickstart, and operations documentation.
- Verification suite now includes compile, pytest, smoke, and secret scan.
