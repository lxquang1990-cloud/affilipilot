from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.content.content_gate import evaluate_content_gates
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.telegram.outbox import OutboxMessage
from affilipilot.workflows.approval import create_approval_batch
from affilipilot.workflows.discover_convert import run_discover_convert
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.quality import evaluate_quality_gate


def _post_text(post: dict[str, Any]) -> str:
    path = Path(post.get("files", {}).get("post_text", ""))
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def run_channel_to_approval(
    *,
    url: str,
    batch_key: str,
    work_dir: str | Path,
    db_path: str | Path,
    outbox_path: str | Path,
    source: str = "AUTO",
    category: str = "unknown",
    campaign_key: str = "",
    limit: int = 3,
    dry_run: bool = True,
    timeout_ms: int = 45000,
    wait_ms: int = 3000,
    headless: bool = True,
    queue_telegram: bool = True,
    queue_only_vetted: bool = True,
) -> dict[str, Any]:
    """One-command channel/listing URL to local approval batch.

    Approval-only mode: by default, only posts passing quality, market-fit, and
    offline offer validation are queued to the operator. Filtered items stay in
    the report for audit but are not sent as approval cards.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    discover_dir = work_dir / "discover-convert"
    drafts_dir = work_dir / "drafts"
    publish_dir = work_dir / "publish-preview"

    discover = run_discover_convert(
        url=url,
        work_dir=discover_dir,
        source=source,
        category=category,
        campaign_key=campaign_key,
        limit=limit,
        dry_run=dry_run,
        timeout_ms=timeout_ms,
        wait_ms=wait_ms,
        headless=headless,
    )
    converted_input = Path(discover["converted_input"])
    if discover.get("conversion", {}).get("ok_count", 0) <= 0 or not converted_input.exists() or converted_input.stat().st_size == 0:
        summary = {
            "ok": False,
            "stage": "discover_convert",
            "reason": "no_converted_products",
            "batch_key": batch_key,
            "work_dir": str(work_dir),
            "discover": discover,
            "queued_messages": 0,
            "gates": [],
            "vetted_count": 0,
            "filtered_count": 0,
        }
        (work_dir / "channel-to-approval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    manifest = create_approval_batch(converted_input, drafts_dir, db_path, batch_key=batch_key, limit=limit)
    original_posts = list(manifest.get("posts", []))
    vetted_posts = []
    gate_results = []
    failed_gate_count = 0

    for post in original_posts:
        product = post.get("product", {})
        text = _post_text(post)
        quality_result = evaluate_quality_gate(post)
        product_content_result = evaluate_product_content(product, text)
        content_gate_result = evaluate_content_gates(product, text)
        manifest_content_gate = post.get("content_gate", {})
        market_result = evaluate_market_fit(product, text)
        offer_url = product.get("affiliate_url") or product.get("tracking_url") or product.get("url", "")
        offer_result = validate_offer(offer_url, expected_title=product.get("title", ""), expected_image=product.get("image_url", ""), network=False)
        passed = quality_result.passed and content_gate_result.passed and product_content_result.passed and market_result.passed and offer_result.passed
        if passed:
            vetted_posts.append(post)
        else:
            failed_gate_count += 1
        gate_results.append({
            "post_id": post.get("post_id"),
            "passed": passed,
            "quality": {"passed": quality_result.passed, "score": quality_result.score, "reasons": quality_result.reasons},
            "product_content": {"passed": product_content_result.passed, "score": product_content_result.score, "reasons": product_content_result.reasons, "recommendations": product_content_result.recommendations},
            "content_gates": {
                "passed": content_gate_result.passed,
                "score": content_gate_result.score,
                "reasons": content_gate_result.reasons,
                "layers": [{"layer": layer.layer, "passed": layer.passed, "score": layer.score} for layer in content_gate_result.layers],
                "regenerated_count": manifest_content_gate.get("regenerated_count", 0),
                "attempts": manifest_content_gate.get("attempts", []),
            },
            "market_fit": {"passed": market_result.passed, "score": market_result.score, "reasons": market_result.reasons},
            "offer": {"passed": offer_result.passed, "score": offer_result.score, "reasons": offer_result.reasons},
        })

    if queue_only_vetted:
        manifest["posts"] = vetted_posts
        manifest["selected"] = len(vetted_posts)
        manifest["filtered_posts"] = [post.get("post_id") for post in original_posts if post not in vetted_posts]
        AffiliPilotDB(db_path).save_batch(batch_key=batch_key, source=str(converted_input), manifest=manifest)

    messages: list[OutboxMessage] = []
    if queue_telegram and manifest.get("selected", 0) > 0:
        messages = queue_approval_batch(db_path, batch_key=batch_key, outbox_path=outbox_path)

    ready_report = build_ready_to_publish_report(db_path=db_path, batch_key=batch_key, outbox_path=outbox_path, out_dir=publish_dir)
    summary = {
        "ok": manifest.get("selected", 0) > 0,
        "stage": "approval_batch",
        "reason": "ready_for_delivery" if manifest.get("selected", 0) > 0 else "no_vetted_posts",
        "batch_key": batch_key,
        "work_dir": str(work_dir),
        "db_path": str(db_path),
        "outbox_path": str(outbox_path),
        "discover": discover,
        "manifest": {
            "total_products": manifest.get("total_products", 0),
            "selected": manifest.get("selected", 0),
            "out_dir": manifest.get("out_dir", ""),
        },
        "gates": gate_results,
        "vetted_count": len(vetted_posts),
        "filtered_count": len(original_posts) - len(vetted_posts),
        "gate_failed_count": failed_gate_count,
        "queue_only_vetted": queue_only_vetted,
        "queued_messages": len(messages),
        "ready_to_publish": {
            "ready_count": ready_report.get("ready_count", 0),
            "held_count": ready_report.get("held_count", 0),
            "plan_publishable_count": ready_report.get("plan_publishable_count", 0),
            "plan_blocked_count": ready_report.get("plan_blocked_count", 0),
            "publish_safe_pass_count": ready_report.get("publish_safe_pass_count", 0),
            "publish_safe_block_count": ready_report.get("publish_safe_block_count", 0),
            "report_path": ready_report.get("report_path", ""),
        },
    }
    (work_dir / "channel-to-approval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def render_channel_to_approval(summary: dict[str, Any]) -> str:
    discover = summary.get("discover", {})
    conversion = discover.get("conversion", {})
    manifest = summary.get("manifest", {})
    ready = summary.get("ready_to_publish", {})
    lines = [
        "🐌 AffiliPilot channel-to-approval",
        f"Batch: {summary.get('batch_key')}",
        f"Status: {'OK' if summary.get('ok') else 'BLOCK'} ({summary.get('reason')})",
        f"Work dir: {summary.get('work_dir')}",
        "",
        f"Discovery: {'OK' if discover.get('discovery', {}).get('ok') else 'BLOCK'} total={discover.get('discovery', {}).get('total', 0)}",
        f"Conversion: ok={conversion.get('ok_count', 0)} failed={conversion.get('failed_count', 0)} total={conversion.get('total', 0)}",
    ]
    if manifest:
        lines.extend([
            f"Drafts: queued={manifest.get('selected', 0)} / products={manifest.get('total_products', 0)}",
            f"Vetted: pass={summary.get('vetted_count', 0)} filtered={summary.get('filtered_count', 0)}",
            f"Outbox queued: {summary.get('queued_messages', 0)}",
            f"Ready preview: ready={ready.get('ready_count', 0)} held={ready.get('held_count', 0)} publish-safe-pass={ready.get('publish_safe_pass_count', 0)}",
        ])
    lines.extend([
        "",
        "Operator UX:",
        "- Backend filters weak/unsafe items automatically.",
        "- Operator receives only vetted approval cards.",
        "",
        "Next safe steps:",
        f"1) Review outbox: python -m affilipilot outbox --outbox {summary.get('outbox_path', '<outbox>')}",
        "2) Deliver approval cards: python -m affilipilot openclaw-telegram-send --outbox <outbox> --reply-to 640968010 --account default --limit 2",
        "3) Approve/reject: /aff_approve <post_id> or /aff_reject <post_id>",
        "4) Then campaign-status + publish-safe --check-only before any real publish.",
    ])
    return "\n".join(lines)
