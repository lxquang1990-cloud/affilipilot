# CHANGELOG

## Unreleased
- Initialize AffiliPilot Lite Sprint 0 scaffold.
- Add one-shot `draft-links` workflow for links → scored drafts → approval batch → local Telegram outbox.
- Add Telegram mock adapter outbox queueing and local `deliver-telegram` dry-run/mark-sent command.
- Add `approve-ready` command for approved-post ready package + Facebook dry-run plan.
- Add `batch-status` command for approvals/compliance/Facebook plan state.
- Add deterministic `demo-happy-path` smoke command and `scripts/smoke_affilipilot.sh`.
- Update README, quickstart, and operations documentation.
- Verification suite now includes compile, pytest, smoke, and secret scan.
