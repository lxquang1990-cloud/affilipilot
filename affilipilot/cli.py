from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from affilipilot.accesstrade.client import check_accesstrade_config
from affilipilot.analytics.digest import build_daily_digest
from affilipilot.budget import record_spend
from affilipilot.config import load_config, render_config_status
from affilipilot.publishing.facebook import check_facebook_config, publish_photo_post, publish_post
from affilipilot.publishing.facebook_plan import plan_facebook_batch, render_facebook_plan
from affilipilot.publishing.facebook_token import check_facebook_token, render_facebook_token_report
from affilipilot.publishing.facebook_token_manager import derive_page_token, exchange_short_token, inspect_current_page_token, refresh_from_user_token, render_token_manager_result
from affilipilot.publishing.ready_package import build_ready_to_post_package
from affilipilot.readiness import build_readiness_report, render_readiness_report
from affilipilot.security import write_secret_template
from affilipilot.telegram.adapter import AdapterConfig, handle_text_message
from affilipilot.telegram.delivery import build_openclaw_telegram_plan, deliver_outbox_dry_run, queue_approval_batch, render_delivery_report, render_openclaw_telegram_plan, render_outbox_preview
from affilipilot.telegram.outbox import Outbox
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input
from affilipilot.workflows.affiliate_ready import render_affiliate_ready_validation, validate_affiliate_ready_input
from affilipilot.workflows.approval import create_approval_batch, decide_post, render_status
from affilipilot.workflows.batch_status import build_batch_status, render_batch_status
from affilipilot.workflows.daily_batch import build_batch
from affilipilot.workflows.run_day import run_day
from affilipilot.workflows.scan_to_draft import draft_from_scan, run_product_scan


def cmd_scan_products(args: argparse.Namespace) -> int:
    result = run_product_scan(args.url, args.out, source=args.source, category=args.category, campaign_key=args.campaign_key, limit=args.limit, timeout=args.timeout)
    print(f"AffiliPilot scan-products: {result['total']} items")
    print(f"Source: {args.source} URL: {args.url}")
    if result.get("errors"):
        print("Errors: " + "; ".join(result["errors"]))
    print(f"Output JSON: {result['scan_path']}")
    for item in result.get("items", [])[:5]:
        print(f"- {item.get('title') or '(no title)'} | {item.get('price_vnd') or 'price?'} | {item.get('url')}")
    return 0 if result["total"] else 2


def cmd_scan_draft(args: argparse.Namespace) -> int:
    summary = draft_from_scan(
        args.scan,
        work_dir=args.work_dir,
        db_path=args.db,
        batch_key=args.batch_key,
        outbox_path=args.outbox,
        limit=args.limit,
        convert_affiliate=args.convert_affiliate,
        real_accesstrade=args.real_accesstrade,
        campaign_key=args.campaign_key,
    )
    print(f"AffiliPilot scan-draft complete: {summary['batch_key']}")
    print(f"Products: {summary['total_products']} considered, {summary['selected']} selected")
    print(f"Drafts: {summary['drafts_dir']}")
    print(f"Outbox: {summary['outbox_path']} ({summary['outbox_messages']} messages queued)")
    if summary.get("conversion"):
        conv = summary["conversion"]
        print(f"Accesstrade conversion: ok={conv['ok_count']} failed={conv['failed_count']} dry_run={conv['dry_run']}")
    return 0 if summary["selected"] else 2


def cmd_batch_preview(args: argparse.Namespace) -> int:
    manifest = build_batch(args.input, args.out_dir, limit=args.limit)
    print(f"AffiliPilot batch preview created: {manifest['selected']}/{manifest['total_products']} selected")
    print(f"Output: {manifest['out_dir']}")
    print(f"Preview: {Path(manifest['out_dir']) / 'approval_batch_preview.txt'}")
    return 0


def cmd_create_batch(args: argparse.Namespace) -> int:
    manifest = create_approval_batch(args.input, args.out_dir, args.db, batch_key=args.batch_key, limit=args.limit)
    print(f"AffiliPilot approval batch created: {args.batch_key}")
    print(f"Selected: {manifest['selected']}/{manifest['total_products']}")
    print(f"Preview: {Path(manifest['out_dir']) / 'approval_batch_preview.txt'}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    approvals = decide_post(args.db, batch_key=args.batch_key, post_id=args.post_id, decision=args.decision, reason=args.reason)
    print(f"Decision saved: {args.batch_key}/{args.post_id} -> {args.decision}")
    for row in approvals:
        print(f"{row['post_id']}: {row['status']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(render_status(args.db, batch_key=args.batch_key))
    return 0


def cmd_batch_status(args: argparse.Namespace) -> int:
    print(render_batch_status(build_batch_status(args.db, batch_key=args.batch_key, facebook_plan=args.facebook_plan or None)))
    return 0


def cmd_handle_text(args: argparse.Namespace) -> int:
    outbox_path = Path(args.outbox) if args.outbox else None
    result = handle_text_message(args.text, AdapterConfig(db_path=Path(args.db), work_dir=Path(args.work_dir), limit=args.limit, outbox_path=outbox_path))
    print(result.text)
    for attachment in result.attachments:
        print(f"ATTACHMENT:{attachment}")
    return 0


def cmd_ready_package(args: argparse.Namespace) -> int:
    package = build_ready_to_post_package(args.db, batch_key=args.batch_key, out_dir=args.out_dir, facebook_verified=args.facebook_verified, dry_run_passed=args.dry_run_passed)
    print(f"Ready package: {package['ready_count']} ready, {package['held_count']} held")
    print(f"Output: {args.out_dir}")
    return 0

def cmd_approve_ready(args: argparse.Namespace) -> int:
    ready_dir = Path(args.out_dir) / "ready"
    plan_path = Path(args.out_dir) / "facebook-plan.json"
    package = build_ready_to_post_package(args.db, batch_key=args.batch_key, out_dir=ready_dir)
    plan = plan_facebook_batch(args.db, batch_key=args.batch_key, out_path=plan_path)
    print(f"AffiliPilot approve-ready: {args.batch_key}")
    print(f"Ready package: {package['ready_count']} ready, {package['held_count']} held")
    print(render_facebook_plan(plan))
    print(f"Ready dir: {ready_dir}")
    print(f"Facebook plan JSON: {plan_path}")
    return 0 if package["ready_count"] else 2

def cmd_demo_happy_path(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir)
    batch_key = args.batch_key
    input_path = work_dir / "input.links.txt"
    db_path = Path(args.db)
    outbox_path = work_dir / "outbox.json"
    approved_dir = work_dir / "approved"
    plan_path = approved_dir / "facebook-plan.json"

    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("\n".join([
        "https://go.isclix.com/deep_link/product-a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/a.jpg",
        "https://go.isclix.com/deep_link/product-b | title=Yếm ăn dặm silicone mềm | category=feeding | price=79000 | image_url=https://cdn.example/b.jpg",
        "https://go.isclix.com/deep_link/product-c | title=Khăn sữa cotton mềm | category=baby-care | price=59000 | image_url=https://cdn.example/c.jpg",
    ]) + "\n", encoding="utf-8")

    manifest = create_approval_batch(input_path, work_dir / "drafts", db_path, batch_key=batch_key, limit=3)
    messages = queue_approval_batch(db_path, batch_key=batch_key, outbox_path=outbox_path)
    decide_post(db_path, batch_key=batch_key, post_id="post_20260516_001", decision="approved", reason="happy path demo")
    package = build_ready_to_post_package(db_path, batch_key=batch_key, out_dir=approved_dir / "ready")
    plan = plan_facebook_batch(db_path, batch_key=batch_key, out_path=plan_path)
    status = build_batch_status(db_path, batch_key=batch_key, facebook_plan=plan_path)

    print(f"AffiliPilot demo happy path: {batch_key}")
    print(f"Drafts selected: {manifest['selected']}/{manifest['total_products']}")
    print(f"Outbox queued: {len(messages)} messages")
    print(f"Ready package: {package['ready_count']} ready, {package['held_count']} held")
    print(render_facebook_plan(plan))
    print()
    print(render_batch_status(status))
    print(f"Work dir: {work_dir}")
    return 0 if package["ready_count"] and plan.publishable_count else 2


def cmd_health(args: argparse.Namespace) -> int:
    fb = check_facebook_config()
    at = check_accesstrade_config()
    print(render_config_status(load_config()))
    print("Facebook:", "OK" if fb.verified else "NOT CONFIGURED", ",".join(fb.reasons) if fb.reasons else "")
    print("Accesstrade:", "OK" if at.configured else "NOT CONFIGURED", ",".join(at.reasons) if at.reasons else "")
    return 0 if fb.verified and at.configured else 2


def cmd_digest(args: argparse.Namespace) -> int:
    print(build_daily_digest(args.db, batch_key=args.batch_key))
    return 0


def cmd_record_spend(args: argparse.Namespace) -> int:
    status = record_spend(args.path, phase=args.phase, amount_vnd=args.amount, note=args.note, cap_vnd=args.cap)
    print(f"Budget: spent={status.spent_vnd} remaining={status.remaining_vnd} mode={status.mode}")
    return 0 if not status.hard_exceeded else 2


def cmd_init_secrets(args: argparse.Namespace) -> int:
    path = write_secret_template(args.path, overwrite=args.overwrite)
    print(f"Secret template ready: {path}")
    print("Fill values locally. Do not paste tokens into chat. Permissions set to 600 when created/overwritten.")
    return 0


def cmd_readiness(args: argparse.Namespace) -> int:
    report = build_readiness_report()
    print(render_readiness_report(report))
    return 0 if report.ready_for_sprint1_manual else 2


def cmd_run_day(args: argparse.Namespace) -> int:
    result = run_day(args.input, args.work_dir, args.db, batch_key=args.batch_key, limit=args.limit)
    print(f"AffiliPilot run-day complete: {result['batch_key']}")
    print(f"Drafts: {result['drafts_dir']}")
    print(f"Approval preview: {result['approval_preview']}")
    print(f"Ready package: {result['ready_dir']} ({result['ready_count']} ready / {result['held_count']} held)")
    print(f"Report: {result['report']}")
    return 0


def cmd_queue_telegram(args: argparse.Namespace) -> int:
    messages = queue_approval_batch(args.db, batch_key=args.batch_key, outbox_path=args.outbox)
    print(f"Queued {len(messages)} Telegram delivery messages into {args.outbox}")
    return 0


def cmd_draft_links(args: argparse.Namespace) -> int:
    input_path = Path(args.input) if args.input else Path(args.work_dir) / "inline_links.txt"
    if args.links:
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text("\n".join(args.links) + "\n", encoding="utf-8")
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    batch_key = args.batch_key or datetime.now().strftime("draft-%Y%m%d-%H%M%S")
    out_dir = Path(args.work_dir) / batch_key / "drafts"
    manifest = create_approval_batch(input_path, out_dir, args.db, batch_key=batch_key, limit=args.limit)
    messages = queue_approval_batch(args.db, batch_key=batch_key, outbox_path=args.outbox)

    print(f"AffiliPilot draft-links complete: {batch_key}")
    print(f"Products: {manifest['total_products']} considered, {manifest['selected']} selected")
    print(f"Drafts: {out_dir}")
    print(f"Approval preview: {out_dir / 'approval_batch_preview.txt'}")
    print(f"Telegram outbox: {args.outbox} ({len(messages)} messages queued)")
    if args.show_preview:
        print()
        print(render_outbox_preview(args.outbox))
    return 0

def cmd_outbox(args: argparse.Namespace) -> int:
    print(render_outbox_preview(args.outbox))
    return 0


def cmd_deliver_telegram(args: argparse.Namespace) -> int:
    result = deliver_outbox_dry_run(args.outbox, mark_sent=args.mark_sent, limit=args.limit)
    print(render_delivery_report(result))
    return 0


def cmd_mark_outbox(args: argparse.Namespace) -> int:
    outbox = Outbox(args.outbox)
    outbox.mark(args.message_id, args.status)
    print(f"Outbox message marked: {args.message_id} -> {args.status}")
    return 0


def cmd_openclaw_telegram_plan(args: argparse.Namespace) -> int:
    plan = build_openclaw_telegram_plan(args.outbox, reply_to=args.reply_to, reply_channel=args.reply_channel, agent=args.agent or None, limit=args.limit)
    print(render_openclaw_telegram_plan(plan))
    return 0


def cmd_facebook_plan(args: argparse.Namespace) -> int:
    plan = plan_facebook_batch(args.db, batch_key=args.batch_key, out_path=args.out)
    print(render_facebook_plan(plan))
    print(f"Plan JSON: {args.out}")
    return 0 if plan.publishable_count else 2


def cmd_facebook_publish_one(args: argparse.Namespace) -> int:
    from pathlib import Path
    import json
    if args.require_telegram_sent:
        if not args.outbox or not args.batch_key:
            raise SystemExit("Refusing publish: --require-telegram-sent needs --outbox and --batch-key")
        outbox = Outbox(args.outbox)
        expected_ids = {f"{args.batch_key}:summary", f"{args.batch_key}:{args.post_id}"}
        sent_ids = {m.id for m in outbox.load() if m.status == "sent"}
        missing = sorted(expected_ids - sent_ids)
        if missing:
            raise SystemExit("Refusing publish: Telegram approval messages not marked sent: " + ", ".join(missing))
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    matches = [p for p in plan.get("plans", []) if p.get("post_id") == args.post_id]
    if not matches:
        raise SystemExit(f"Post not found in plan: {args.post_id}")
    item = matches[0]
    if item.get("status") != "publishable_dry_run":
        raise SystemExit(f"Refusing publish; plan status is {item.get('status')}: {item.get('reasons')}")
    payload = item.get("payload_preview", {})
    if item.get("endpoint", "").endswith("/photos"):
        result = publish_photo_post(caption=payload.get("caption", ""), image_path=payload.get("local_image_path", ""), link=payload.get("url", ""))
    else:
        result = publish_post(post_text=payload.get("message", ""), link=payload.get("link", ""))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Facebook publish result: ok={result.get('ok')} status={result.get('status')}")
    print(f"Result JSON: {out}")
    if result.get("response", {}).get("id"):
        print(f"Facebook post id: {result['response']['id']}")
    return 0 if result.get("ok") else 2


def cmd_facebook_token_check(args: argparse.Namespace) -> int:
    report = check_facebook_token()
    print(render_facebook_token_report(report))
    return 0 if report.valid and not report.missing_scopes and report.page_probe_ok else 2


def cmd_facebook_token_manager(args: argparse.Namespace) -> int:
    if args.action == "inspect":
        result = inspect_current_page_token()
    elif args.action == "exchange":
        result = exchange_short_token(args.short_token or "", write=not args.no_write)
    elif args.action == "page-token":
        result = derive_page_token(write=not args.no_write)
    elif args.action == "refresh":
        result = refresh_from_user_token(auto=args.auto, threshold_days=args.threshold_days, write=not args.no_write)
    else:
        raise SystemExit(f"Unknown token manager action: {args.action}")
    print(render_token_manager_result(result))
    return 0 if result.ok else 2


def cmd_validate_input(args: argparse.Namespace) -> int:
    validation = validate_affiliate_ready_input(args.input)
    print(render_affiliate_ready_validation(validation))
    return 0 if validation.passed else 2


def cmd_accesstrade_convert(args: argparse.Namespace) -> int:
    summary = convert_input_links(args.input, args.out, dry_run=args.dry_run, limit=args.limit, campaign_key=args.campaign_key)
    print(f"Accesstrade convert: ok={summary['ok_count']} failed={summary['failed_count']} dry_run={summary['dry_run']}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_converted_input(args.out, args.write_input)
        print(f"Converted input: {path}")
    return 0 if summary["failed_count"] == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AffiliPilot Lite CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan-products", help="Scan a page URL and extract product candidates into scan JSON")
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="data/scans/products.json")
    p.add_argument("--source", default="AUTO", help="Source label, e.g. CELLPHONES, LAZADA, SHOPEE")
    p.add_argument("--category", default="unknown", help="Default category assigned to scanned products")
    p.add_argument("--campaign-key", default="", help="Optional Accesstrade campaign key for downstream conversion")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=cmd_scan_products)

    p = sub.add_parser("scan-draft", help="Turn scan JSON into scored drafts and Telegram approval outbox")
    p.add_argument("--scan", required=True, help="Scan JSON from scan-products")
    p.add_argument("--work-dir", default="data/runs/scan-draft")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--outbox", default="data/outbox/scan-draft.json")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--convert-affiliate", action="store_true", help="Convert scanned URLs through Accesstrade before drafting; dry-run unless --real-accesstrade")
    p.add_argument("--real-accesstrade", action="store_true", help="Call real Accesstrade API when --convert-affiliate is set")
    p.add_argument("--campaign-key", default="", help="Optional Accesstrade campaign key override")
    p.set_defaults(func=cmd_scan_draft)

    p = sub.add_parser("batch-preview", help="Build scored draft posts and Telegram approval-card previews from product links/CSV")
    p.add_argument("--input", required=True, help="Path to product_links.txt or products.csv")
    p.add_argument("--out-dir", required=True, help="Output directory for preview package")
    p.add_argument("--limit", type=int, default=5, help="Number of top products to draft")
    p.set_defaults(func=cmd_batch_preview)

    p = sub.add_parser("create-batch", help="Create an approval batch and persist pending approvals in SQLite")
    p.add_argument("--input", required=True, help="Path to product_links.txt or products.csv")
    p.add_argument("--out-dir", required=True, help="Output directory for preview package")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True, help="Unique batch key, e.g. 2026-05-16-am")
    p.add_argument("--limit", type=int, default=5, help="Number of top products to draft")
    p.set_defaults(func=cmd_create_batch)

    p = sub.add_parser("decide", help="Set approval decision for a post")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--decision", required=True, choices=["pending", "approved", "rejected", "needs_edit", "blacklisted"])
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_decide)

    p = sub.add_parser("status", help="Show approval status for a batch")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("batch-status", help="Show full batch state: approvals, compliance, and optional Facebook plan status")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--facebook-plan", default="", help="Optional facebook-plan.json generated by approve-ready/facebook-plan")
    p.set_defaults(func=cmd_batch_status)

    p = sub.add_parser("handle-text", help="Mock Telegram text adapter; parses links or commands and runs local workflow")
    p.add_argument("text", help="Telegram-like message text")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--work-dir", default="data/telegram-mock", help="Work directory for inbound links and drafts")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--outbox", default="", help="Optional local Telegram outbox JSON to queue generated approval messages")
    p.set_defaults(func=cmd_handle_text)

    p = sub.add_parser("ready-package", help="Build ready-to-post fallback package for approved posts")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--facebook-verified", action="store_true")
    p.add_argument("--dry-run-passed", action="store_true")
    p.set_defaults(func=cmd_ready_package)

    p = sub.add_parser("approve-ready", help="Build approved-post ready package and Facebook dry-run plan; no real publish")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--out-dir", required=True)
    p.set_defaults(func=cmd_approve_ready)

    p = sub.add_parser("demo-happy-path", help="Run local end-to-end smoke: draft, queue, approve one post, ready package, Facebook dry-run, batch status")
    p.add_argument("--work-dir", default="data/demo-happy-path")
    p.add_argument("--db", default="data/demo-happy-path.db")
    p.add_argument("--batch-key", default="demo-happy-path")
    p.set_defaults(func=cmd_demo_happy_path)

    p = sub.add_parser("health", help="Check local env configuration presence for Facebook/Accesstrade")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("digest", help="Render daily digest for a batch")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", required=True)
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("record-spend", help="Record LLM/API spend into budget tracker")
    p.add_argument("--path", default="data/budget/today.json")
    p.add_argument("--phase", required=True)
    p.add_argument("--amount", type=int, required=True)
    p.add_argument("--note", default="")
    p.add_argument("--cap", type=int, default=30000)
    p.set_defaults(func=cmd_record_spend)

    p = sub.add_parser("init-secrets", help="Create local secrets env template with chmod 600")
    p.add_argument("--path", default="/home/snail/.openclaw/workspace/secrets/affilipilot.env")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_init_secrets)

    p = sub.add_parser("readiness", help="Show Sprint/API/publish readiness report")
    p.set_defaults(func=cmd_readiness)

    p = sub.add_parser("run-day", help="Run local end-to-end day simulation: batch, drafts, ready package, report")
    p.add_argument("--input", required=True, help="Path to links txt/csv")
    p.add_argument("--work-dir", default="data/runs", help="Work output directory")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", default=None)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_run_day)

    p = sub.add_parser("queue-telegram", help="Queue local Telegram delivery package for a batch into outbox JSON")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.set_defaults(func=cmd_queue_telegram)

    p = sub.add_parser("draft-links", help="One-shot workflow: links -> scored drafts -> persisted approval batch -> Telegram outbox preview")
    p.add_argument("--input", default="", help="Path to product_links.txt or products.csv. Optional when --link is used.")
    p.add_argument("--link", dest="links", action="append", default=[], help="Inline product line. Repeat for multiple products; supports `url | title=... | category=... | price=...`.")
    p.add_argument("--work-dir", default="data/runs", help="Work output directory")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path")
    p.add_argument("--batch-key", default="", help="Unique batch key. Defaults to draft-YYYYMMDD-HHMMSS")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--show-preview", action="store_true", help="Print queued Telegram approval messages after generating them")
    p.set_defaults(func=cmd_draft_links)

    p = sub.add_parser("outbox", help="Render pending local Telegram outbox messages")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.set_defaults(func=cmd_outbox)

    p = sub.add_parser("deliver-telegram", help="Dry-run local Telegram delivery from outbox; optionally mark pending messages as sent")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--mark-sent", action="store_true", help="Mark processed messages as sent without calling external Telegram APIs")
    p.set_defaults(func=cmd_deliver_telegram)

    p = sub.add_parser("mark-outbox", help="Mark outbox message status")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--message-id", required=True)
    p.add_argument("--status", required=True, choices=["pending", "sent", "failed", "skipped"])
    p.set_defaults(func=cmd_mark_outbox)

    p = sub.add_parser("openclaw-telegram-plan", help="Render OpenClaw CLI delivery commands for pending outbox messages; plan-only, no send")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--reply-to", required=True, help="Telegram delivery target, e.g. chat id or @username")
    p.add_argument("--reply-channel", default="telegram")
    p.add_argument("--agent", default="", help="Optional OpenClaw agent id to run the delivery turn")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_openclaw_telegram_plan)

    p = sub.add_parser("facebook-plan", help="Build Facebook Graph API dry-run plan for approved posts; no POST")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--out", default="data/publish/facebook-plan.json")
    p.set_defaults(func=cmd_facebook_plan)

    p = sub.add_parser("facebook-publish-one", help="Publish exactly one already-planned publishable post to Facebook")
    p.add_argument("--plan", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--out", default="data/publish/facebook-result.json")
    p.add_argument("--require-telegram-sent", action="store_true", help="Refuse real publish unless summary and approval card are marked sent in outbox")
    p.add_argument("--outbox", default="", help="Outbox JSON used with --require-telegram-sent")
    p.add_argument("--batch-key", default="", help="Batch key used with --require-telegram-sent")
    p.set_defaults(func=cmd_facebook_publish_one)

    p = sub.add_parser("facebook-token-check", help="Check Facebook token validity/scopes without printing secrets")
    p.set_defaults(func=cmd_facebook_token_check)

    p = sub.add_parser("facebook-token-manager", help="Inspect/exchange/refresh Facebook user/page tokens without printing secrets")
    p.add_argument("--action", required=True, choices=["inspect", "exchange", "page-token", "refresh"])
    p.add_argument("--short-token", default="", help="Short-lived User Token for --action exchange. Prefer env/file input over chat.")
    p.add_argument("--auto", action="store_true", help="For refresh: skip when user token is not near expiry")
    p.add_argument("--threshold-days", type=int, default=15, help="Refresh threshold for --auto")
    p.add_argument("--no-write", action="store_true", help="Dry-run API flow without updating secrets file")
    p.set_defaults(func=cmd_facebook_token_manager)

    p = sub.add_parser("validate-input", help="Validate input has affiliate/tracking link and media before publishing")
    p.add_argument("--input", required=True)
    p.set_defaults(func=cmd_validate_input)

    p = sub.add_parser("accesstrade-convert", help="Convert product URLs to Accesstrade tracking links; dry-run by default")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="data/accesstrade/converted.json")
    p.add_argument("--write-input", default="", help="Optional converted .txt input path")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--campaign-key", default="", help="Optional campaign key, e.g. SHOPEE, LAZADA, TIKI. Auto-detected by domain when configured.")
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API")
    p.set_defaults(dry_run=True)
    p.set_defaults(func=cmd_accesstrade_convert)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
