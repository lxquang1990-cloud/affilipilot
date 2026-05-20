"""Facebook Page publishing CLI commands.

Commands:
    facebook-plan            Build Graph API dry-run plan for approved posts
    facebook-publish-one     Publish exactly one already-planned post (guarded)
    facebook-token-check     Check token validity/scopes without leaking secrets
    facebook-token-manager   Inspect/exchange/refresh user/page tokens

Safety contract:
    All publishing requires Telegram delivery proof via --outbox + --batch-key
    unless --unsafe-skip-telegram-gate is explicitly set (test-only). Real
    publish output never contains the access token because every response
    passes through ``affilipilot.security.redact_for_audit``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from affilipilot.cli._registry import register
from affilipilot.publishing.facebook import publish_post  # backward-compatible test patch target
from affilipilot.publishing.facebook_plan import plan_facebook_batch, render_facebook_plan
from affilipilot.publishing.facebook_token import check_facebook_token, render_facebook_token_report
from affilipilot.publishing.facebook_token_manager import (
    derive_page_token,
    exchange_short_token,
    inspect_current_page_token,
    refresh_from_user_token,
    render_token_manager_result,
)
from affilipilot.publishing.dispatch import dispatch_publish_strategy
from affilipilot.publishing.safe_publish import validate_publish_safe
from affilipilot.security import redact_response

DEFAULT_DB = "data/affilipilot.db"
DEFAULT_PLAN_OUT = "data/publish/facebook-plan.json"
DEFAULT_RESULT_OUT = "data/publish/facebook-result.json"


def _configure_facebook_plan(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--batch-key", required=True)
    p.add_argument("--out", default=DEFAULT_PLAN_OUT)


@register(
    "facebook-plan",
    help="Build Facebook Graph API dry-run plan for approved posts; no POST",
    configure=_configure_facebook_plan,
)
def cmd_facebook_plan(args: argparse.Namespace) -> int:
    plan = plan_facebook_batch(args.db, batch_key=args.batch_key, out_path=args.out)
    print(render_facebook_plan(plan))
    print(f"Plan JSON: {args.out}")
    return 0 if plan.publishable_count else 2


def _configure_facebook_publish_one(p: argparse.ArgumentParser) -> None:
    p.add_argument("--plan", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--out", default=DEFAULT_RESULT_OUT)
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite DB path for approval validation")
    p.add_argument("--outbox", default="", help="Outbox JSON containing Telegram delivery proof")
    p.add_argument("--batch-key", default="", help="Batch key for Telegram delivery proof")
    p.add_argument(
        "--require-telegram-sent",
        action="store_true",
        help="Deprecated compatibility flag; delivery proof is required by default and must be marked delivered",
    )
    p.add_argument(
        "--unsafe-skip-telegram-gate",
        action="store_true",
        help="Explicit test-only bypass for Telegram delivery proof; never use for production",
    )



@register(
    "facebook-publish-one",
    help="Publish exactly one already-planned publishable post to Facebook",
    configure=_configure_facebook_publish_one,
)
def cmd_facebook_publish_one(args: argparse.Namespace) -> int:
    if not args.unsafe_skip_telegram_gate:
        if not args.outbox or not args.batch_key:
            raise SystemExit(
                "Refusing publish: production publish needs --outbox and --batch-key for Telegram delivery proof"
            )
        gate = validate_publish_safe(
            db_path=args.db,
            batch_key=args.batch_key,
            post_id=args.post_id,
            plan_path=args.plan,
            outbox_path=args.outbox,
        )
        if not gate["ok"]:
            raise SystemExit("Refusing publish; publish-safe validation failed: " + ", ".join(gate["reasons"]))

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    matches = [p for p in plan.get("plans", []) if p.get("post_id") == args.post_id]
    if not matches:
        raise SystemExit(f"Post not found in plan: {args.post_id}")
    item = matches[0]
    if item.get("status") != "publishable_dry_run":
        raise SystemExit(f"Refusing publish; plan status is {item.get('status')}: {item.get('reasons')}")

    payload = item.get("payload_preview", {})
    result = dispatch_publish_strategy(item, payload)

    # Defense-in-depth: even though publish_post/photo/video already redact,
    # apply one more pass before writing to disk in case a strategy returns
    # a wrapped result with nested response objects.
    safe_result = redact_response(result)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(safe_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Facebook publish result: ok={safe_result.get('ok')} status={safe_result.get('status')}")
    print(f"Result JSON: {out}")
    response = safe_result.get("response", {}) if isinstance(safe_result.get("response"), dict) else {}
    if response.get("id"):
        print(f"Facebook post id: {response['id']}")
    return 0 if safe_result.get("ok") else 2


@register("facebook-token-check", help="Check Facebook token validity/scopes without printing secrets")
def cmd_facebook_token_check(args: argparse.Namespace) -> int:
    report = check_facebook_token()
    print(render_facebook_token_report(report))
    return 0 if report.valid and not report.missing_scopes and report.page_probe_ok else 2


def _configure_facebook_token_manager(p: argparse.ArgumentParser) -> None:
    p.add_argument("--action", required=True, choices=["inspect", "exchange", "page-token", "refresh"])
    p.add_argument(
        "--short-token",
        default="",
        help="Short-lived User Token for --action exchange. Prefer env/file input over chat.",
    )
    p.add_argument("--auto", action="store_true", help="For refresh: skip when user token is not near expiry")
    p.add_argument("--threshold-days", type=int, default=15, help="Refresh threshold for --auto")
    p.add_argument("--no-write", action="store_true", help="Dry-run API flow without updating secrets file")


@register(
    "facebook-token-manager",
    help="Inspect/exchange/refresh Facebook user/page tokens without printing secrets",
    configure=_configure_facebook_token_manager,
)
def cmd_facebook_token_manager(args: argparse.Namespace) -> int:
    action_map = {
        "inspect": lambda: inspect_current_page_token(),
        "exchange": lambda: exchange_short_token(args.short_token or "", write=not args.no_write),
        "page-token": lambda: derive_page_token(write=not args.no_write),
        "refresh": lambda: refresh_from_user_token(
            auto=args.auto, threshold_days=args.threshold_days, write=not args.no_write
        ),
    }
    runner = action_map.get(args.action)
    if runner is None:
        raise SystemExit(f"Unknown token manager action: {args.action}")
    result = runner()
    print(render_token_manager_result(result))
    return 0 if result.ok else 2
