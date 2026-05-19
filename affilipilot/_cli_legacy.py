from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from affilipilot.accesstrade.client import check_accesstrade_config
from affilipilot.accesstrade.campaigns import write_campaign_registry
from affilipilot.accesstrade.catalog import fetch_datafeeds, fetch_top_products, write_products_input
from affilipilot.accesstrade.deals import fetch_coupons, fetch_offer_keywords, fetch_offer_merchants, write_deals
from affilipilot.accesstrade.reports import fetch_order_list, render_order_summary, save_orders, summarize_orders, write_json as write_report_json
from affilipilot.analytics.digest import build_daily_digest
from affilipilot.analytics.performance import PostPerformance, record_performance, render_performance_summary, summarize_performance
from affilipilot.budget import record_spend
from affilipilot.config import load_config, render_config_status
from affilipilot.content.market_fit import evaluate_market_fit, render_market_fit
from affilipilot.content.variants import generate_content_variants
from affilipilot.marketplaces import classify_url, discovery_advice
from affilipilot.offer import render_offer_validation, validate_offer
from affilipilot.observability.circuit_breaker import check_circuit, render_circuit_status, set_kill_switch
from affilipilot.observability.event_log import EventLog, read_events, render_events
from affilipilot.scoring.confidence import compute_confidence
from affilipilot.scoring.tier import classify_tier, load_tier_config, render_tier_result
from affilipilot.analytics.conversions import render_conversion_summary, summarize_conversions, upsert_conversion
from affilipilot.publishing.facebook import check_facebook_config, publish_gallery_comment, publish_multi_photo_post, publish_photo_post, publish_post, publish_video_post
from affilipilot.publishing.facebook_plan import plan_facebook_batch, render_facebook_plan
from affilipilot.publishing.facebook_token import check_facebook_token, render_facebook_token_report
from affilipilot.publishing.facebook_token_manager import derive_page_token, exchange_short_token, inspect_current_page_token, refresh_from_user_token, render_token_manager_result
from affilipilot.publishing.ready_package import build_ready_to_post_package
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report, render_ready_to_publish_report
from affilipilot.publishing.lifecycle import record_publish_event, render_publish_status
from affilipilot.publishing.safe_publish import render_publish_safe_validation, validate_publish_safe
from affilipilot.readiness import build_readiness_report, render_readiness_report
from affilipilot.security import write_secret_template
from affilipilot.telegram.adapter import AdapterConfig, handle_text_message
from affilipilot.telegram.delivery import build_openclaw_telegram_plan, deliver_outbox_dry_run, mark_batch_delivered, queue_approval_batch, render_batch_delivery_report, render_delivery_report, render_openclaw_telegram_plan, render_openclaw_telegram_send_report, render_outbox_preview, send_openclaw_telegram_outbox
from affilipilot.telegram.outbox import Outbox
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input
from affilipilot.workflows.discover_convert import run_discover_convert, render_discover_convert_summary
from affilipilot.workflows.e2e_profit import render_profit_first_e2e, run_profit_first_e2e
from affilipilot.workflows.channel_approval import run_channel_to_approval, render_channel_to_approval
from affilipilot.workflows.affiliate_ready import render_affiliate_ready_validation, validate_affiliate_ready_input
from affilipilot.workflows.approval import create_approval_batch, decide_post, render_status
from affilipilot.workflows.batch_status import build_batch_status, render_batch_status
from affilipilot.workflows.daily_batch import build_batch
from affilipilot.workflows.run_day import run_day
from affilipilot.workflows.multi_source import load_source_config, render_multi_source_summary, run_multi_source_discovery
from affilipilot.workflows.multi_source_approval import render_multi_source_approval, run_multi_source_approval
from affilipilot.workflows.next_action import recommend_next_action, render_next_action
from affilipilot.workflows.doctor import build_doctor_report, render_doctor_report
from affilipilot.workflows.campaign_status import build_campaign_status, render_campaign_status
from affilipilot.workflows.scan_to_draft import draft_from_scan, run_product_scan
from affilipilot.scanner.enrich import enrich_batch_media, enrich_product_from_url
from affilipilot.scanner.browser_plan import build_browser_scan_plan, render_browser_scan_plan
from affilipilot.scanner.discovery import discover_product_details, write_discovery_result
from affilipilot.scanner.browser_exec import browser_render_discover
from affilipilot.quality import evaluate_quality_gate
from affilipilot.sources.manual_input import parse_link_lines
from affilipilot.strategy import default_strategy, render_strategy


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


def cmd_discover_products(args: argparse.Namespace) -> int:
    result = discover_product_details(args.url, source=args.source, category=args.category, limit=args.limit, timeout=args.timeout, enrich=args.enrich)
    path = write_discovery_result(result, args.out)
    print(f"AffiliPilot discover-products: {len(result.items)} items")
    print(f"Source: {args.source} URL: {args.url}")
    if result.errors:
        print("Errors: " + "; ".join(result.errors))
    print(f"Output JSON: {path}")
    for item in result.items[:5]:
        print(f"- {item.title or '(needs enrichment)'} | {item.price_vnd or 'price?'} | {item.url}")
    return 0 if result.items else 2


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


def cmd_enrich_url(args: argparse.Namespace) -> int:
    data = enrich_product_from_url(args.url, title=args.title, category=args.category, source=args.source, timeout=args.timeout)
    print(f"AffiliPilot enrich-url: {data.get('title') or args.title or args.url}")
    print(f"URL: {data.get('url')}")
    print(f"Image: {data.get('image_url') or '(none)'}")
    print(f"Product URLs found: {len(data.get('product_urls') or [])}")
    for url in (data.get('product_urls') or [])[:5]:
        print(f"- {url}")
    return 0 if data.get('image_url') or data.get('product_urls') else 2


def cmd_enrich_media(args: argparse.Namespace) -> int:
    summary = enrich_batch_media(args.db, batch_key=args.batch_key, out_dir=args.out_dir, limit=args.limit)
    print(f"AffiliPilot enrich-media: {summary['batch_key']}")
    print(f"Media updated: {summary['updated']}")
    print(f"Media failed: {summary['failed']}")
    for item in summary['results']:
        print(f"- {item['post_id']}: {item['status']}")
    return 0 if summary['failed'] == 0 else 2


def cmd_browser_scan_plan(args: argparse.Namespace) -> int:
    plan = build_browser_scan_plan(args.url, source=args.source, category=args.category, out_path=args.out)
    print(render_browser_scan_plan(plan))
    if args.out:
        print(f"Plan JSON: {args.out}")
    return 0



def cmd_discover_convert(args: argparse.Namespace) -> int:
    summary = run_discover_convert(
        url=args.url,
        work_dir=args.work_dir,
        source=args.source,
        category=args.category,
        campaign_key=args.campaign_key,
        limit=args.limit,
        dry_run=args.dry_run,
        timeout_ms=args.timeout_ms,
        wait_ms=args.wait_ms,
        headless=not args.headed,
    )
    print(render_discover_convert_summary(summary))
    return 0 if summary.get("conversion", {}).get("ok_count", 0) > 0 else 2


def cmd_profit_e2e(args: argparse.Namespace) -> int:
    summary = run_profit_first_e2e(
        batch_key=args.batch_key,
        work_dir=args.work_dir,
        db_path=args.db,
        outbox_path=args.outbox,
        sources_path=args.sources or None,
        discover_limit=args.discover_limit,
        select_limit=args.limit,
        real_accesstrade=args.real_accesstrade,
        queue_telegram=not args.no_queue,
        cache_dir=args.cache_dir,
    )
    print(render_profit_first_e2e(summary))
    return 0 if summary.get("ok") else 2

def cmd_multi_source_scan(args: argparse.Namespace) -> int:
    sources = load_source_config(args.sources)
    summary = run_multi_source_discovery(
        sources=sources,
        work_dir=args.work_dir,
        per_source_limit=args.per_source_limit,
        final_limit=args.limit,
        dry_run=args.dry_run,
        timeout_ms=args.timeout_ms,
        wait_ms=args.wait_ms,
        headless=not args.headed,
    )
    print(render_multi_source_summary(summary))
    return 0 if summary.get("selected_count", 0) else 2


def cmd_multi_source_approval(args: argparse.Namespace) -> int:
    sources = load_source_config(args.sources)
    summary = run_multi_source_approval(
        sources=sources,
        batch_key=args.batch_key,
        work_dir=args.work_dir,
        db_path=args.db,
        outbox_path=args.outbox,
        per_source_limit=args.per_source_limit,
        limit=args.limit,
        dry_run=args.dry_run,
        timeout_ms=args.timeout_ms,
        wait_ms=args.wait_ms,
        headless=not args.headed,
        queue_telegram=not args.no_queue,
    )
    print(render_multi_source_approval(summary))
    return 0 if summary.get("ok") else 2


def cmd_channel_approval(args: argparse.Namespace) -> int:
    summary = run_channel_to_approval(
        url=args.url,
        batch_key=args.batch_key,
        work_dir=args.work_dir,
        db_path=args.db,
        outbox_path=args.outbox,
        source=args.source,
        category=args.category,
        campaign_key=args.campaign_key,
        limit=args.limit,
        dry_run=args.dry_run,
        timeout_ms=args.timeout_ms,
        wait_ms=args.wait_ms,
        headless=not args.headed,
        queue_telegram=not args.no_queue,
    )
    print(render_channel_to_approval(summary))
    return 0 if summary.get("ok") else 2

def cmd_browser_discover(args: argparse.Namespace) -> int:
    result = browser_render_discover(args.url, out_path=args.out, source=args.source, category=args.category, limit=args.limit, timeout_ms=args.timeout_ms, wait_ms=args.wait_ms, headless=not args.headed)
    print(f"AffiliPilot browser-discover: ok={result.ok} total={result.total}")
    if result.scan_path:
        print(f"Output JSON: {result.scan_path}")
    if result.error:
        print(f"Error: {result.error}")
    for note in result.notes:
        print(f"Note: {note}")
    return 0 if result.ok else 2


def cmd_quality_gate(args: argparse.Namespace) -> int:
    from affilipilot.db import AffiliPilotDB
    db = AffiliPilotDB(args.db)
    batch = db.get_batch(args.batch_key)
    if not batch:
        raise KeyError(f"Batch not found: {args.batch_key}")
    failed = 0
    print(f"🐌 AffiliPilot quality gate — {args.batch_key}")
    for post in batch["manifest"].get("posts", []):
        result = evaluate_quality_gate(post)
        status = "PASS" if result.passed else "BLOCK"
        if not result.passed:
            failed += 1
        print(f"- {post['post_id']}: {status} score={result.score} media={result.media_score} caption={result.caption_score}" + (f" — {', '.join(result.reasons)}" if result.reasons else ""))
    return 0 if failed == 0 else 2


def cmd_marketplace_classify(args: argparse.Namespace) -> int:
    classification = classify_url(args.url)
    advice = discovery_advice(args.url)
    print("🐌 AffiliPilot marketplace classify")
    print(f"URL: {args.url}")
    print(f"Marketplace: {classification.marketplace}")
    print(f"Kind: {classification.kind}")
    print(f"Normalized: {classification.normalized_url}")
    if classification.reasons:
        print("Reasons:")
        for reason in classification.reasons:
            print(f"- {reason}")
    print(f"Action: {advice.action}")
    print(f"OK: {advice.ok}")
    print(f"Advice: {advice.reason}")
    if advice.command_hint:
        print("Command hint:")
        print(advice.command_hint.replace("<url>", args.url))
    return 0 if advice.ok or args.allow_needs_discovery else 2

def cmd_market_fit(args: argparse.Namespace) -> int:
    products = parse_link_lines(Path(args.input).read_text(encoding="utf-8"))
    failed = 0
    for product in products[: args.limit or None]:
        text = ""
        result = evaluate_market_fit(product.__dict__, text, audience=args.audience)
        print(render_market_fit(result))
        print()
        if not result.passed:
            failed += 1
    return 0 if failed == 0 else 2

def cmd_content_variants(args: argparse.Namespace) -> int:
    products = parse_link_lines(Path(args.input).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, product in enumerate(products[: args.limit or None], 1):
        variants = generate_content_variants(product, audience=args.audience)
        path = out_dir / f"product_{idx:02d}_variants.md"
        lines = [f"# Variants for {product.title or product.url}", ""]
        for variant in variants:
            lines.extend([f"## {variant.variant_id} — {variant.angle} — {variant.score}/100 {'PASS' if variant.passed else 'BLOCK'}", "", variant.text, ""])
            if variant.reasons:
                lines.extend(["Reasons:", *(f"- {r}" for r in variant.reasons), ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"{product.title or product.url}: best={variants[0].angle} score={variants[0].score} file={path}")
    return 0

def cmd_offer_validate(args: argparse.Namespace) -> int:
    result = validate_offer(args.url, expected_title=args.expected_title, expected_image=args.expected_image, network=args.network)
    print(render_offer_validation(result))
    return 0 if result.passed else 2

def cmd_performance_record(args: argparse.Namespace) -> int:
    item = PostPerformance(batch_key=args.batch_key, post_id=args.post_id, facebook_post_id=args.facebook_post_id, category=args.category, angle=args.angle, price_vnd=args.price_vnd, visual_type=args.visual_type, clicks=args.clicks, conversions=args.conversions, commission_vnd=args.commission_vnd)
    record_performance(args.path, item)
    print(f"Performance recorded: {args.batch_key}/{args.post_id}")
    return 0

def cmd_performance_summary(args: argparse.Namespace) -> int:
    print(render_performance_summary(summarize_performance(args.path)))
    return 0

def cmd_strategy(args: argparse.Namespace) -> int:
    print(render_strategy(default_strategy(audience=args.audience)))
    return 0


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


def cmd_publish_status(args: argparse.Namespace) -> int:
    print(render_publish_status(args.db, batch_key=args.batch_key))
    return 0


def cmd_record_publish_event(args: argparse.Namespace) -> int:
    record_publish_event(args.db, batch_key=args.batch_key, post_id=args.post_id, state=args.state, facebook_post_id=args.facebook_post_id, reason=args.reason)
    print(f"Publish event recorded: {args.batch_key}/{args.post_id} -> {args.state}")
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
    demo_media_dir = work_dir / "demo-media"
    demo_media_dir.mkdir(parents=True, exist_ok=True)
    demo_images = []
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        image_path = demo_media_dir / name
        image_path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
        demo_images.append(image_path)
    input_path.write_text("\n".join([
        f"https://go.isclix.com/deep_link/product-a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={demo_images[0]}",
        f"https://go.isclix.com/deep_link/product-b | title=Yếm ăn dặm silicone mềm | category=feeding | price=79000 | image_path={demo_images[1]}",
        f"https://go.isclix.com/deep_link/product-c | title=Khăn sữa cotton mềm | category=baby-care | price=59000 | image_path={demo_images[2]}",
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
    result = deliver_outbox_dry_run(args.outbox, mark_sent=args.mark_sent, mark_delivered=args.mark_delivered, receipt=args.receipt, limit=args.limit)
    print(render_delivery_report(result))
    return 0


def cmd_mark_outbox(args: argparse.Namespace) -> int:
    outbox = Outbox(args.outbox)
    outbox.mark(args.message_id, args.status, receipt=args.receipt)
    print(f"Outbox message marked: {args.message_id} -> {args.status}")
    return 0

def cmd_mark_batch_delivered(args: argparse.Namespace) -> int:
    result = mark_batch_delivered(args.outbox, batch_key=args.batch_key, post_id=args.post_id, receipt=args.receipt)
    print(render_batch_delivery_report(result))
    return 0


def cmd_openclaw_telegram_plan(args: argparse.Namespace) -> int:
    plan = build_openclaw_telegram_plan(args.outbox, reply_to=args.reply_to, reply_channel=args.reply_channel, account=args.account, agent=args.agent or None, limit=args.limit)
    print(render_openclaw_telegram_plan(plan))
    return 0

def cmd_openclaw_telegram_send(args: argparse.Namespace) -> int:
    result = send_openclaw_telegram_outbox(args.outbox, reply_to=args.reply_to, reply_channel=args.reply_channel, account=args.account, agent=args.agent or None, to=args.to, session_id=args.session_id, limit=args.limit)
    print(render_openclaw_telegram_send_report(result))
    return 0 if all(item["status"] in {"sent", "delivered"} for item in result["messages"]) else 2


def cmd_facebook_plan(args: argparse.Namespace) -> int:
    plan = plan_facebook_batch(args.db, batch_key=args.batch_key, out_path=args.out)
    print(render_facebook_plan(plan))
    print(f"Plan JSON: {args.out}")
    return 0 if plan.publishable_count else 2


def cmd_facebook_publish_one(args: argparse.Namespace) -> int:
    from pathlib import Path
    import json
    if not args.unsafe_skip_telegram_gate:
        if not args.outbox or not args.batch_key:
            raise SystemExit("Refusing publish: production publish needs --outbox and --batch-key for Telegram delivery proof")
        gate = validate_publish_safe(db_path=args.db, batch_key=args.batch_key, post_id=args.post_id, plan_path=args.plan, outbox_path=args.outbox)
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
    if payload.get("strategy") in {"video_primary", "video_primary_with_image_comment"}:
        result = publish_video_post(description=payload.get("description", ""), video_path=payload.get("local_video_path", ""), link=payload.get("url", ""))
        if result.get("ok") and payload.get("strategy") == "video_primary_with_image_comment" and payload.get("local_image_paths"):
            target_id = result.get("response", {}).get("post_id") or result.get("response", {}).get("id", "")
            comments = publish_gallery_comment(object_id=target_id, image_paths=payload.get("local_image_paths", []), message="Ảnh thật sản phẩm")
            result = {**result, "image_comments": comments, "ok": bool(result.get("ok")) and bool(comments.get("ok"))}
    elif payload.get("strategy") == "multi_photo":
        result = publish_multi_photo_post(message=payload.get("message", ""), image_paths=payload.get("local_image_paths", []), link=payload.get("url", ""))
    elif item.get("endpoint", "").endswith("/photos"):
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


def cmd_publish_safe(args: argparse.Namespace) -> int:
    validation = validate_publish_safe(db_path=args.db, batch_key=args.batch_key, post_id=args.post_id, plan_path=args.plan, outbox_path=args.outbox)
    print(render_publish_safe_validation(validation))
    if args.check_only:
        return 0 if validation["ok"] else 2
    if not validation["ok"]:
        return 2
    return cmd_facebook_publish_one(args)

def cmd_ready_to_publish(args: argparse.Namespace) -> int:
    report = build_ready_to_publish_report(db_path=args.db, batch_key=args.batch_key, outbox_path=args.outbox, out_dir=args.out_dir)
    print(render_ready_to_publish_report(report))
    return 0 if report["publish_safe_pass_count"] else 2

def cmd_next_action(args: argparse.Namespace) -> int:
    result = recommend_next_action(db_path=args.db, batch_key=args.batch_key or None, outbox_path=args.outbox, plan_path=args.plan or None)
    print(render_next_action(result))
    return 0

def cmd_doctor(args: argparse.Namespace) -> int:
    report = build_doctor_report(db_path=args.db, outbox_path=args.outbox, batch_key=args.batch_key, secret_path=args.secret_path or None)
    print(render_doctor_report(report))
    return 0 if report["ok_for_local_workflow"] else 2

def cmd_campaign_status(args: argparse.Namespace) -> int:
    status = build_campaign_status(db_path=args.db, batch_key=args.batch_key, outbox_path=args.outbox, out_dir=args.out_dir, secret_path=args.secret_path or None, build_ready=not args.no_build_ready)
    print(render_campaign_status(status))
    return 0 if status["doctor"]["ok_for_local_workflow"] else 2

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


def cmd_accesstrade_campaigns(args: argparse.Namespace) -> int:
    registry = write_campaign_registry(args.out, approval=args.approval)
    print(f"Accesstrade campaigns: ok={registry.get('ok')} count={len(registry.get('campaigns', []))}")
    if registry.get("error"):
        print(f"Error: {registry['error']}")
    print(f"Output JSON: {args.out}")
    return 0 if registry.get("ok") else 2

def cmd_accesstrade_datafeed(args: argparse.Namespace) -> int:
    data = fetch_datafeeds(campaign=args.campaign, domain=args.domain, cat=args.cat, status_discount=args.status_discount, discount_rate_from=args.discount_rate_from, price_from=args.price_from, price_to=args.price_to, page=args.page, limit=args.limit)
    write_report_json(args.out, data)
    print(f"Accesstrade datafeed: ok={data.get('ok')} products={len(data.get('products', []))}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_products_input(data.get("products", []), args.write_input, category_override=args.category)
        print(f"Input TXT: {path}")
    return 0 if data.get("ok") else 2

def cmd_accesstrade_top_products(args: argparse.Namespace) -> int:
    data = fetch_top_products(merchant=args.merchant, date_from=args.date_from, date_to=args.date_to)
    write_report_json(args.out, data)
    print(f"Accesstrade top-products: ok={data.get('ok')} products={len(data.get('products', []))}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_products_input(data.get("products", []), args.write_input, category_override=args.category)
        print(f"Input TXT: {path}")
    return 0 if data.get("ok") else 2

def cmd_accesstrade_deals(args: argparse.Namespace) -> int:
    if args.kind == "merchants":
        data = fetch_offer_merchants()
    elif args.kind == "keywords":
        data = fetch_offer_keywords()
    else:
        data = fetch_coupons(merchant=args.merchant, keyword=args.keyword, is_next_day_coupon=args.next_day, limit=args.limit, page=args.page)
    write_deals(args.out, data)
    count_key = "deals" if args.kind == "coupons" else args.kind
    print(f"Accesstrade deals {args.kind}: ok={data.get('ok')} count={len(data.get(count_key, []))}")
    print(f"Output JSON: {args.out}")
    return 0 if data.get("ok") else 2

def cmd_accesstrade_orders(args: argparse.Namespace) -> int:
    data = fetch_order_list(since=args.since, until=args.until, merchant=args.merchant, status=args.status, page=args.page, limit=args.limit)
    write_report_json(args.out, data)
    saved = save_orders(args.db, data.get("orders", [])) if data.get("ok") else 0
    summary = summarize_orders(args.db)
    print(f"Accesstrade orders: ok={data.get('ok')} fetched={len(data.get('orders', []))} saved={saved}")
    print(f"Output JSON: {args.out}")
    print(render_order_summary(summary))
    return 0 if data.get("ok") else 2

def cmd_accesstrade_report(args: argparse.Namespace) -> int:
    summary = summarize_orders(args.db)
    print(render_order_summary(summary))
    if args.out:
        write_report_json(args.out, summary)
        print(f"Output JSON: {args.out}")
    return 0

def cmd_accesstrade_convert(args: argparse.Namespace) -> int:
    summary = convert_input_links(args.input, args.out, dry_run=args.dry_run, limit=args.limit, campaign_key=args.campaign_key, allow_channel_urls=args.allow_channel_urls)
    print(f"Accesstrade convert: ok={summary['ok_count']} failed={summary['failed_count']} dry_run={summary['dry_run']}")
    if summary.get("failed_count"):
        for row in summary.get("items", []):
            if not row.get("result", {}).get("ok"):
                preflight = row.get("preflight", {})
                classification = preflight.get("classification", {})
                advice = preflight.get("advice", {})
                print(f"- blocked index={row.get('index')} marketplace={classification.get('marketplace')} kind={classification.get('kind')} error={row.get('result', {}).get('error')}")
                if advice.get("command_hint"):
                    print(f"  hint: {advice.get('command_hint')}")
    print(f"Output JSON: {args.out}")
    if args.write_input:
        path = write_converted_input(args.out, args.write_input)
        print(f"Converted input: {path}")
    return 0 if summary["failed_count"] == 0 else 2

def cmd_event_log(args: argparse.Namespace) -> int:
    print(render_events(read_events(args.path, limit=args.limit)))
    return 0


def cmd_circuit_status(args: argparse.Namespace) -> int:
    status = check_circuit(state_path=args.state, kill_path=args.kill_path, event_log_path=args.event_log)
    print(render_circuit_status(status))
    return 0 if status.allowed else 2


def cmd_kill_switch(args: argparse.Namespace) -> int:
    enabled = args.action == "on"
    status = set_kill_switch(enabled, kill_path=args.kill_path, event_log_path=args.event_log, reason=args.reason)
    print(render_circuit_status(status))
    return 0


def cmd_score_tier(args: argparse.Namespace) -> int:
    products = parse_link_lines(Path(args.input).read_text(encoding="utf-8"))
    cfg = load_tier_config(args.config)
    log = EventLog(args.event_log)
    print(f"AffiliPilot tier scoring: {len(products)} products")
    for product in products[: args.limit]:
        score, signals = compute_confidence(product)
        tier = classify_tier(score, signals, cfg)
        log.event("draft_classified", title=product.title, url=product.url, score=score, tier=tier.value, signals=signals)
        print(f"- {product.title or product.url}: {render_tier_result(score, tier, signals)}")
    return 0


def cmd_conversion_record(args: argparse.Namespace) -> int:
    order = {
        "sub_id": args.sub_id,
        "order_id": args.order_id,
        "order_status": args.status,
        "commission_vnd": args.commission_vnd,
        "order_value_vnd": args.order_value_vnd,
        "draft_id": args.draft_id,
        "post_id": args.post_id,
        "campaign_id": args.campaign_id,
    }
    upsert_conversion(args.db, order)
    print(render_conversion_summary(summarize_conversions(args.db)))
    return 0


def cmd_conversion_summary(args: argparse.Namespace) -> int:
    print(render_conversion_summary(summarize_conversions(args.db)))
    return 0


def cmd_sprint0(args: argparse.Namespace) -> int:
    batch_key = args.batch_key or datetime.now().strftime("sprint0-%Y%m%d-%H%M%S")
    work_dir = Path(args.work_dir) / batch_key
    input_path = Path(args.input) if args.input else work_dir / "input.links.txt"
    if args.links:
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text("\n".join(args.links) + "\n", encoding="utf-8")
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    manifest = create_approval_batch(input_path, work_dir / "drafts", args.db, batch_key=batch_key, limit=args.limit)
    messages = queue_approval_batch(args.db, batch_key=batch_key, outbox_path=args.outbox)

    print(f"AffiliPilot Sprint 0 workflow ready: {batch_key}")
    print(f"Products: {manifest['total_products']} considered, {manifest['selected']} selected")
    print(f"Drafts: {work_dir / 'drafts'}")
    print(f"Telegram approval outbox: {args.outbox} ({len(messages)} messages queued)")
    print("")
    print("Next safe steps:")
    print(f"1) Review: python -m affilipilot outbox --outbox {args.outbox}")
    print("2) Deliver approval cards via Telegram provider/OpenClaw, then mark delivered only after real delivery.")
    print(f"3) Approve from Telegram: /aff_approve <post_id>")
    print(f"4) Build plan: python -m affilipilot approve-ready --db {args.db} --batch-key {batch_key} --out-dir {work_dir / 'approved'}")
    print(f"5) Publish: python -m affilipilot facebook-publish-one --plan {work_dir / 'approved' / 'facebook-plan.json'} --post-id <post_id> --outbox {args.outbox} --batch-key {batch_key}")
    return 0 if manifest["selected"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AffiliPilot Lite CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("event-log", help="Render structured AffiliPilot JSONL events")
    p.add_argument("--path", default="data/logs/affilipilot-events.jsonl")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_event_log)

    p = sub.add_parser("circuit-status", help="Show auto-publish circuit breaker status")
    p.add_argument("--state", default="data/auto_publish_state.json")
    p.add_argument("--kill-path", default="/tmp/affilipilot.KILL")
    p.add_argument("--event-log", default="data/logs/affilipilot-events.jsonl")
    p.set_defaults(func=cmd_circuit_status)

    p = sub.add_parser("kill-switch", help="Toggle auto-publish kill switch")
    p.add_argument("action", choices=["on", "off"])
    p.add_argument("--reason", default="operator")
    p.add_argument("--kill-path", default="/tmp/affilipilot.KILL")
    p.add_argument("--event-log", default="data/logs/affilipilot-events.jsonl")
    p.set_defaults(func=cmd_kill_switch)

    p = sub.add_parser("score-tier", help="Score input products and classify auto/soft/manual/blocked tiers; no publish")
    p.add_argument("--input", required=True)
    p.add_argument("--config", default="config/tier-config.json")
    p.add_argument("--event-log", default="data/logs/affilipilot-events.jsonl")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_score_tier)

    p = sub.add_parser("conversion-record", help="Record one conversion/order row for ROI tracking")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--sub-id", required=True)
    p.add_argument("--order-id", required=True)
    p.add_argument("--status", default="pending")
    p.add_argument("--commission-vnd", type=int, default=0)
    p.add_argument("--order-value-vnd", type=int, default=0)
    p.add_argument("--draft-id", default="")
    p.add_argument("--post-id", default="")
    p.add_argument("--campaign-id", default="")
    p.set_defaults(func=cmd_conversion_record)

    p = sub.add_parser("conversion-summary", help="Summarize local conversion/ROI table")
    p.add_argument("--db", default="data/affilipilot.db")
    p.set_defaults(func=cmd_conversion_summary)

    p = sub.add_parser("scan-products", help="Scan a page URL and extract product candidates into scan JSON")
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="data/scans/products.json")
    p.add_argument("--source", default="AUTO", help="Source label, e.g. CELLPHONES, LAZADA, SHOPEE")
    p.add_argument("--category", default="unknown", help="Default category assigned to scanned products")
    p.add_argument("--campaign-key", default="", help="Optional Accesstrade campaign key for downstream conversion")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=cmd_scan_products)

    p = sub.add_parser("discover-products", help="Discover product-detail URLs from category/search HTML; discovery-only, no publish")
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="data/scans/discovered-products.json")
    p.add_argument("--source", default="AUTO")
    p.add_argument("--category", default="unknown")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--enrich", action="store_true", help="Fetch each discovered product detail URL and enrich metadata/media")
    p.set_defaults(func=cmd_discover_products)

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

    p = sub.add_parser("enrich-url", help="Try multiple strategies to extract product metadata/media from one URL")
    p.add_argument("--url", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--category", default="unknown")
    p.add_argument("--source", default="AUTO")
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=cmd_enrich_url)

    p = sub.add_parser("enrich-media", help="Try to fill missing product media for an existing batch")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_enrich_media)

    p = sub.add_parser("browser-scan-plan", help="Create a safe browser-render extraction plan for dynamic product pages")
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--source", default="AUTO")
    p.add_argument("--category", default="unknown")
    p.set_defaults(func=cmd_browser_scan_plan)


    p = sub.add_parser("profit-e2e", help="Standard profit-first E2E: Accesstrade discovery -> scoring -> conversion -> vetted approval outbox -> ready preview; no publish")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--work-dir", default="data/runs/profit-e2e")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--outbox", default="data/outbox/profit-e2e.json")
    p.add_argument("--sources", default="", help="Optional JSON sources config; defaults to profit-first Accesstrade sources")
    p.add_argument("--discover-limit", type=int, default=50)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--real-accesstrade", action="store_true", help="Call real Accesstrade conversion API; default is dry-run")
    p.add_argument("--no-queue", action="store_true", help="Do not queue Telegram approval cards")
    p.add_argument("--cache-dir", default="data/cache/accesstrade/sources", help="Cross-run source cache directory for Accesstrade source fallback")
    p.set_defaults(func=cmd_profit_e2e)

    p = sub.add_parser("multi-source-scan", help="Run multiple marketplace sources, merge/dedupe/rank candidates, and write one selected input file")
    p.add_argument("--sources", default="config/multi-source.mother-baby.json", help="JSON source config; defaults to mother/baby multi-source config")
    p.add_argument("--work-dir", default="data/runs/multi-source-scan")
    p.add_argument("--per-source-limit", type=int, default=5)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--timeout-ms", type=int, default=45000)
    p.add_argument("--wait-ms", type=int, default=3000)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API for each discovered product")
    p.set_defaults(dry_run=True)
    p.set_defaults(func=cmd_multi_source_scan)

    p = sub.add_parser("multi-source-approval", help="Multi-source scanner to local approval batch; no Telegram delivery and no publish")
    p.add_argument("--sources", default="config/multi-source.mother-baby.json")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--work-dir", default="data/runs/multi-source-approval")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--per-source-limit", type=int, default=5)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--timeout-ms", type=int, default=45000)
    p.add_argument("--wait-ms", type=int, default=3000)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--no-queue", action="store_true")
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API for each discovered product")
    p.set_defaults(dry_run=True)
    p.set_defaults(func=cmd_multi_source_approval)

    p = sub.add_parser("channel-approval", help="One-command channel/listing URL to local approval batch; no Telegram delivery and no publish")
    p.add_argument("--url", required=True)
    p.add_argument("--batch-key", required=True)
    p.add_argument("--work-dir", default="data/runs/channel-approval")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--source", default="AUTO")
    p.add_argument("--category", default="unknown")
    p.add_argument("--campaign-key", default="")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--timeout-ms", type=int, default=45000)
    p.add_argument("--wait-ms", type=int, default=3000)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--no-queue", action="store_true", help="Do not add approval cards to local outbox")
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API after discovery")
    p.set_defaults(dry_run=True)
    p.set_defaults(func=cmd_channel_approval)

    p = sub.add_parser("discover-convert", help="Browser-discover product URLs from a channel/listing page, then Accesstrade-convert discovered product URLs")
    p.add_argument("--url", required=True)
    p.add_argument("--work-dir", default="data/runs/discover-convert")
    p.add_argument("--source", default="AUTO")
    p.add_argument("--category", default="unknown")
    p.add_argument("--campaign-key", default="")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--timeout-ms", type=int, default=45000)
    p.add_argument("--wait-ms", type=int, default=3000)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API after discovery")
    p.set_defaults(dry_run=True)
    p.set_defaults(func=cmd_discover_convert)

    p = sub.add_parser("browser-discover", help="Render a dynamic page with Playwright and discover product-detail URLs; discovery-only")
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="data/scans/browser-discovered-products.json")
    p.add_argument("--source", default="AUTO")
    p.add_argument("--category", default="unknown")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--timeout-ms", type=int, default=45000)
    p.add_argument("--wait-ms", type=int, default=3000)
    p.add_argument("--headed", action="store_true")
    p.set_defaults(func=cmd_browser_discover)

    p = sub.add_parser("quality-gate", help="Evaluate product-detail/media/caption quality before publish")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.set_defaults(func=cmd_quality_gate)


    p = sub.add_parser("marketplace-classify", help="Classify Shopee/Lazada URLs before discovery/conversion")
    p.add_argument("--url", required=True)
    p.add_argument("--allow-needs-discovery", action="store_true", help="Exit 0 for channel/search URLs that need discovery")
    p.set_defaults(func=cmd_marketplace_classify)

    p = sub.add_parser("market-fit", help="Score product/audience fit before content approval")
    p.add_argument("--input", required=True)
    p.add_argument("--audience", default="mother_baby")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_market_fit)

    p = sub.add_parser("content-variants", help="Generate scored content angle variants; no publish")
    p.add_argument("--input", required=True)
    p.add_argument("--out-dir", default="data/content-variants")
    p.add_argument("--audience", default="mother_baby")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_content_variants)

    p = sub.add_parser("offer-validate", help="Validate offer URL; network check only with --network")
    p.add_argument("--url", required=True)
    p.add_argument("--expected-title", default="")
    p.add_argument("--expected-image", default="")
    p.add_argument("--network", action="store_true")
    p.set_defaults(func=cmd_offer_validate)

    p = sub.add_parser("performance-record", help="Record post performance metrics from Facebook/Accesstrade reports")
    p.add_argument("--path", default="data/analytics/performance.json")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--facebook-post-id", default="")
    p.add_argument("--category", default="")
    p.add_argument("--angle", default="")
    p.add_argument("--price-vnd", type=int, default=0)
    p.add_argument("--visual-type", default="catalog")
    p.add_argument("--clicks", type=int, default=0)
    p.add_argument("--conversions", type=int, default=0)
    p.add_argument("--commission-vnd", type=int, default=0)
    p.set_defaults(func=cmd_performance_record)

    p = sub.add_parser("performance-summary", help="Summarize affiliate post performance")
    p.add_argument("--path", default="data/analytics/performance.json")
    p.set_defaults(func=cmd_performance_summary)

    p = sub.add_parser("strategy", help="Render current monetization/niche strategy")
    p.add_argument("--audience", default="mother_baby")
    p.set_defaults(func=cmd_strategy)

    p = sub.add_parser("publish-status", help="Show latest publish lifecycle state for a batch")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.set_defaults(func=cmd_publish_status)

    p = sub.add_parser("record-publish-event", help="Record a publish lifecycle event without calling Facebook")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--state", required=True, choices=["planned", "published", "hidden", "deleted", "failed"])
    p.add_argument("--facebook-post-id", default="")
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_record_publish_event)

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

    p = sub.add_parser("deliver-telegram", help="Dry-run local Telegram delivery from outbox; optionally mark pending messages as sent/delivered")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--mark-sent", action="store_true", help="Mark processed messages as sent/handed off; not enough for production publish")
    p.add_argument("--mark-delivered", action="store_true", help="Mark processed messages as delivered after real Telegram/provider delivery proof")
    p.add_argument("--receipt", default="", help="Required with --mark-delivered, e.g. telegram:chat_id:message_id")
    p.set_defaults(func=cmd_deliver_telegram)

    p = sub.add_parser("mark-outbox", help="Mark outbox message status")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--message-id", required=True)
    p.add_argument("--status", required=True, choices=["pending", "sent", "delivered", "failed", "skipped"])
    p.add_argument("--receipt", default="", help="Required when --status delivered")
    p.set_defaults(func=cmd_mark_outbox)

    p = sub.add_parser("mark-batch-delivered", help="Mark summary + one approval card delivered for a batch/post")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--receipt", required=True, help="Telegram/provider receipt, e.g. telegram:640968010:7555")
    p.set_defaults(func=cmd_mark_batch_delivered)

    p = sub.add_parser("openclaw-telegram-plan", help="Render OpenClaw CLI delivery commands for pending outbox messages; plan-only, no send")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--reply-to", required=True, help="Telegram delivery target, e.g. chat id or @username")
    p.add_argument("--reply-channel", default="telegram")
    p.add_argument("--account", default="", help="Optional OpenClaw channel account id, e.g. secops/default")
    p.add_argument("--agent", default="", help="Deprecated compatibility option; direct message sends do not use agent routing")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_openclaw_telegram_plan)

    p = sub.add_parser("openclaw-telegram-send", help="Send pending outbox messages through OpenClaw CLI; marks delivered only with receipt")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--reply-to", required=True, help="Telegram delivery target, e.g. chat id or @username")
    p.add_argument("--reply-channel", default="telegram")
    p.add_argument("--account", default="", help="Optional OpenClaw channel account id, e.g. secops/default")
    p.add_argument("--agent", default="", help="Deprecated compatibility option; direct message sends do not use agent routing")
    p.add_argument("--to", default="", help="Deprecated compatibility option; direct message sends do not use E.164 routing")
    p.add_argument("--session-id", default="", help="Deprecated compatibility option; direct message sends do not use session routing")
    p.add_argument("--limit", type=int, default=1, help="Safety default: send one message only")
    p.set_defaults(func=cmd_openclaw_telegram_send)

    p = sub.add_parser("facebook-plan", help="Build Facebook Graph API dry-run plan for approved posts; no POST")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--out", default="data/publish/facebook-plan.json")
    p.set_defaults(func=cmd_facebook_plan)

    p = sub.add_parser("facebook-publish-one", help="Publish exactly one already-planned publishable post to Facebook")
    p.add_argument("--plan", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--out", default="data/publish/facebook-result.json")
    p.add_argument("--db", default="data/affilipilot.db", help="SQLite DB path for approval validation")
    p.add_argument("--outbox", default="", help="Outbox JSON containing Telegram delivery proof")
    p.add_argument("--batch-key", default="", help="Batch key for Telegram delivery proof")
    p.add_argument("--require-telegram-sent", action="store_true", help="Deprecated compatibility flag; delivery proof is required by default and must be marked delivered")
    p.add_argument("--unsafe-skip-telegram-gate", action="store_true", help="Explicit test-only bypass for Telegram delivery proof; never use for production")
    p.set_defaults(func=cmd_facebook_publish_one)

    p = sub.add_parser("publish-safe", help="Validate approval + delivery proof + dry-run plan, then optionally publish one post")
    p.add_argument("--plan", required=True)
    p.add_argument("--post-id", required=True)
    p.add_argument("--out", default="data/publish/facebook-result.json")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--outbox", required=True)
    p.add_argument("--batch-key", required=True)
    p.add_argument("--check-only", action="store_true", help="Validate only; do not call Facebook")
    p.add_argument("--unsafe-skip-telegram-gate", action="store_false", default=False, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_publish_safe)

    p = sub.add_parser("ready-to-publish", help="Build ready package + Facebook plan + publish-safe status for every post; no publish")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", required=True)
    p.add_argument("--outbox", required=True)
    p.add_argument("--out-dir", default="data/publish/ready-to-publish")
    p.set_defaults(func=cmd_ready_to_publish)

    p = sub.add_parser("next-action", help="Recommend the exact next operator step for a batch; no publish")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", default="", help="Defaults to latest batch")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--plan", default="", help="Optional existing facebook-plan.json")
    p.set_defaults(func=cmd_next_action)

    p = sub.add_parser("doctor", help="Read-only audit of config, DB, batch, and outbox; no external API calls")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", default="", help="Defaults to latest batch")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--secret-path", default="", help="Optional env file path; values are never printed")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("campaign-status", help="One-screen operator dashboard: doctor + next-action + ready summary; no publish")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", default="", help="Defaults to latest batch")
    p.add_argument("--outbox", default="data/outbox/telegram.json")
    p.add_argument("--out-dir", default="data/publish/campaign-status")
    p.add_argument("--secret-path", default="", help="Optional env file path; values are never printed")
    p.add_argument("--no-build-ready", action="store_true", help="Skip generating local ready/plan/report files")
    p.set_defaults(func=cmd_campaign_status)

    p = sub.add_parser("sprint0", help="Sprint 0 workflow: pasted product links -> scored drafts -> Telegram approval outbox; no publish")
    p.add_argument("--input", default="", help="Path to product_links.txt or products.csv. Optional when --link is used.")
    p.add_argument("--link", dest="links", action="append", default=[], help="Inline product line. Repeat for multiple products; supports `url | title=... | category=... | price=... | image_url=...`.")
    p.add_argument("--work-dir", default="data/runs/sprint0")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--batch-key", default="")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--outbox", default="data/outbox/sprint0.json")
    p.set_defaults(func=cmd_sprint0)

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

    p = sub.add_parser("accesstrade-campaigns", help="Fetch approved Accesstrade campaign registry; no publish")
    p.add_argument("--out", default="data/accesstrade/campaigns.json")
    p.add_argument("--approval", default="successful")
    p.set_defaults(func=cmd_accesstrade_campaigns)

    p = sub.add_parser("accesstrade-datafeed", help="Fetch Accesstrade datafeed products and optionally write AffiliPilot input TXT")
    p.add_argument("--out", default="data/accesstrade/datafeed.json")
    p.add_argument("--write-input", default="")
    p.add_argument("--campaign", default="")
    p.add_argument("--domain", default="")
    p.add_argument("--cat", default="", help="Accesstrade category code, e.g. thiet-bi-gia-dung, cong-nghe, nha-cua-doi-song")
    p.add_argument("--status-discount", default="")
    p.add_argument("--discount-rate-from", default="")
    p.add_argument("--price-from", default="")
    p.add_argument("--price-to", default="")
    p.add_argument("--category", default="")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_accesstrade_datafeed)

    p = sub.add_parser("accesstrade-top-products", help="Fetch Accesstrade top products and optionally write AffiliPilot input TXT")
    p.add_argument("--out", default="data/accesstrade/top-products.json")
    p.add_argument("--write-input", default="")
    p.add_argument("--merchant", default="")
    p.add_argument("--date-from", default="")
    p.add_argument("--date-to", default="")
    p.add_argument("--category", default="")
    p.set_defaults(func=cmd_accesstrade_top_products)

    p = sub.add_parser("accesstrade-deals", help="Fetch Accesstrade offer merchants/keywords/coupons; no publish")
    p.add_argument("--kind", choices=["merchants", "keywords", "coupons"], default="coupons")
    p.add_argument("--out", default="data/accesstrade/deals.json")
    p.add_argument("--merchant", default="")
    p.add_argument("--keyword", default="")
    p.add_argument("--next-day", action="store_true")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_accesstrade_deals)

    p = sub.add_parser("accesstrade-orders", help="Fetch Accesstrade orders into local DB and print performance summary")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--out", default="data/accesstrade/orders.json")
    p.add_argument("--since", required=True)
    p.add_argument("--until", required=True)
    p.add_argument("--merchant", default="")
    p.add_argument("--status", default="")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=300)
    p.set_defaults(func=cmd_accesstrade_orders)

    p = sub.add_parser("accesstrade-report", help="Summarize synced Accesstrade orders from local DB")
    p.add_argument("--db", default="data/affilipilot.db")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_accesstrade_report)

    p = sub.add_parser("accesstrade-convert", help="Convert product URLs to Accesstrade tracking links; dry-run by default")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="data/accesstrade/converted.json")
    p.add_argument("--write-input", default="", help="Optional converted .txt input path")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--campaign-key", default="", help="Optional campaign key, e.g. SHOPEE, LAZADA, TIKI. Auto-detected by domain when configured.")
    p.add_argument("--real", dest="dry_run", action="store_false", help="Call real Accesstrade API")
    p.add_argument("--allow-channel-urls", action="store_true", help="Development escape hatch: allow channel/search URLs past marketplace preflight")
    p.set_defaults(dry_run=True)
    p.set_defaults(func=cmd_accesstrade_convert)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
