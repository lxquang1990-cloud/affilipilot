from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.quality import evaluate_quality_gate
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.workflows.approval import create_approval_batch
from affilipilot.workflows.multi_source import run_multi_source_discovery


def _post_text(post: dict[str, Any]) -> str:
    path = Path(post.get("files", {}).get("post_text", ""))
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def run_multi_source_approval(
    *,
    sources: list[dict[str, Any]],
    batch_key: str,
    work_dir: str | Path,
    db_path: str | Path,
    outbox_path: str | Path,
    per_source_limit: int = 5,
    limit: int = 5,
    dry_run: bool = True,
    timeout_ms: int = 45000,
    wait_ms: int = 3000,
    headless: bool = True,
    queue_telegram: bool = True,
) -> dict[str, Any]:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    scan_dir = work_dir / "multi-source"
    drafts_dir = work_dir / "drafts"
    publish_dir = work_dir / "publish-preview"

    scan = run_multi_source_discovery(
        sources=sources,
        work_dir=scan_dir,
        per_source_limit=per_source_limit,
        final_limit=limit,
        dry_run=dry_run,
        timeout_ms=timeout_ms,
        wait_ms=wait_ms,
        headless=headless,
    )
    merged_input = Path(scan["merged_input"])
    if scan.get("selected_count", 0) <= 0 or not merged_input.exists() or merged_input.stat().st_size == 0:
        summary = {
            "ok": False,
            "stage": "multi_source_scan",
            "reason": "no_selected_candidates",
            "batch_key": batch_key,
            "work_dir": str(work_dir),
            "scan": scan,
            "queued_messages": 0,
            "vetted_count": 0,
            "filtered_count": 0,
        }
        (work_dir / "multi-source-approval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    manifest = create_approval_batch(merged_input, drafts_dir, db_path, batch_key=batch_key, limit=limit)
    original_posts = list(manifest.get("posts", []))
    vetted_posts = []
    gate_results = []
    for post in original_posts:
        product = post.get("product", {})
        text = _post_text(post)
        quality = evaluate_quality_gate(post)
        product_content = evaluate_product_content(product, text)
        market_fit = evaluate_market_fit(product, text)
        offer_url = product.get("affiliate_url") or product.get("tracking_url") or product.get("url", "")
        offer = validate_offer(offer_url, expected_title=product.get("title", ""), expected_image=product.get("image_url", ""), network=False)
        passed = quality.passed and product_content.passed and market_fit.passed and offer.passed
        if passed:
            vetted_posts.append(post)
        gate_results.append({
            "post_id": post.get("post_id"),
            "passed": passed,
            "quality": {"passed": quality.passed, "score": quality.score, "reasons": quality.reasons},
            "product_content": {"passed": product_content.passed, "score": product_content.score, "reasons": product_content.reasons, "recommendations": product_content.recommendations},
            "market_fit": {"passed": market_fit.passed, "score": market_fit.score, "reasons": market_fit.reasons},
            "offer": {"passed": offer.passed, "score": offer.score, "reasons": offer.reasons},
        })

    manifest["posts"] = vetted_posts
    manifest["selected"] = len(vetted_posts)
    manifest["filtered_posts"] = [post.get("post_id") for post in original_posts if post not in vetted_posts]
    AffiliPilotDB(db_path).save_batch(batch_key=batch_key, source=str(merged_input), manifest=manifest)

    messages = []
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
        "scan": scan,
        "manifest": {"total_products": manifest.get("total_products", 0), "selected": manifest.get("selected", 0), "out_dir": manifest.get("out_dir", "")},
        "gates": gate_results,
        "vetted_count": len(vetted_posts),
        "filtered_count": len(original_posts) - len(vetted_posts),
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
    (work_dir / "multi-source-approval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def render_multi_source_approval(summary: dict[str, Any]) -> str:
    scan = summary.get("scan", {})
    manifest = summary.get("manifest", {})
    ready = summary.get("ready_to_publish", {})
    return "\n".join([
        "🐌 AffiliPilot multi-source approval",
        f"Batch: {summary.get('batch_key')}",
        f"Status: {'OK' if summary.get('ok') else 'BLOCK'} ({summary.get('reason')})",
        f"Work dir: {summary.get('work_dir')}",
        f"Sources: {scan.get('source_count', 0)} candidates={scan.get('candidate_count', 0)} selected={scan.get('selected_count', 0)}",
        f"Drafts queued: {manifest.get('selected', 0)} / products={manifest.get('total_products', 0)}",
        f"Vetted: pass={summary.get('vetted_count', 0)} filtered={summary.get('filtered_count', 0)}",
        f"Outbox queued: {summary.get('queued_messages', 0)}",
        f"Ready preview: ready={ready.get('ready_count', 0)} held={ready.get('held_count', 0)} publish-safe-pass={ready.get('publish_safe_pass_count', 0)}",
        "",
        "Next: deliver approval cards, then approve/reject. Real publish still requires publish-safe PASS.",
    ])
