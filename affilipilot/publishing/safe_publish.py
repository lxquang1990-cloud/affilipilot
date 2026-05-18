from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.quality import evaluate_quality_gate
from affilipilot.telegram.outbox import Outbox


def validate_publish_safe(
    *,
    db_path: str | Path,
    batch_key: str,
    post_id: str,
    plan_path: str | Path,
    outbox_path: str | Path,
) -> dict[str, Any]:
    """Validate all preconditions required before a real Facebook publish.

    This function performs no network calls and no publish side effects.
    """
    reasons: list[str] = []
    db = AffiliPilotDB(db_path)
    approvals = {row["post_id"]: row for row in db.get_approvals(batch_key)}
    approval = approvals.get(post_id)
    batch = db.get_batch(batch_key)
    post = None
    post_text = ""
    if not batch:
        reasons.append("batch_not_found")
    else:
        matches = [item for item in batch.get("manifest", {}).get("posts", []) if item.get("post_id") == post_id]
        if not matches:
            reasons.append("batch_post_not_found")
        else:
            post = matches[0]
            post_file = Path(post.get("files", {}).get("post_text", ""))
            post_text = post_file.read_text(encoding="utf-8", errors="ignore") if post_file.exists() else ""
            quality = evaluate_quality_gate(post)
            if not quality.passed:
                reasons.extend(f"quality:{reason}" for reason in quality.reasons)
            market_fit = evaluate_market_fit(post.get("product", {}), post_text)
            if not market_fit.passed:
                reasons.extend(f"market_fit:{reason}" for reason in market_fit.reasons)
            offer_url = post.get("product", {}).get("tracking_url") or post.get("product", {}).get("affiliate_url") or post.get("product", {}).get("url", "")
            offer = validate_offer(offer_url, expected_title=post.get("product", {}).get("title", ""), network=False)
            if not offer.passed:
                reasons.extend(f"offer:{reason}" for reason in offer.reasons)
    if not approval:
        reasons.append("approval_not_found")
    elif approval.get("status") != "approved":
        reasons.append(f"approval_not_approved:{approval.get('status')}")

    outbox = Outbox(outbox_path)
    outbox_messages = {m.id: m for m in outbox.load()}
    expected_ids = [f"{batch_key}:summary", f"{batch_key}:{post_id}"]
    delivery: dict[str, dict[str, str]] = {}
    for message_id in expected_ids:
        message = outbox_messages.get(message_id)
        if not message:
            reasons.append(f"delivery_missing:{message_id}")
            continue
        delivery[message_id] = {
            "status": message.status,
            "receipt": message.receipt,
            "delivered_at": message.delivered_at,
        }
        if message.status != "delivered":
            reasons.append(f"delivery_not_delivered:{message_id}:{message.status}")
        if not message.receipt:
            reasons.append(f"delivery_missing_receipt:{message_id}")

    plan_file = Path(plan_path)
    if not plan_file.exists():
        reasons.append("plan_file_missing")
        plan_item = None
    else:
        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
        matches = [p for p in plan_data.get("plans", []) if p.get("post_id") == post_id]
        if not matches:
            reasons.append("plan_post_not_found")
            plan_item = None
        else:
            plan_item = matches[0]
            if plan_item.get("status") != "publishable_dry_run":
                reasons.append(f"plan_not_publishable:{plan_item.get('status')}")

    return {
        "ok": not reasons,
        "batch_key": batch_key,
        "post_id": post_id,
        "reasons": reasons,
        "approval": approval or {},
        "delivery": delivery,
        "plan_item": plan_item or {},
    }


def render_publish_safe_validation(result: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot publish-safe validation",
        f"Batch: {result['batch_key']}",
        f"Post: {result['post_id']}",
        f"Status: {'PASS' if result['ok'] else 'BLOCK'}",
        "",
    ]
    approval = result.get("approval") or {}
    lines.append(f"Approval: {approval.get('status', 'missing')}")
    for message_id, delivery in (result.get("delivery") or {}).items():
        receipt = delivery.get("receipt") or "missing_receipt"
        lines.append(f"Delivery: {message_id} -> {delivery.get('status')} ({receipt})")
    plan_item = result.get("plan_item") or {}
    if plan_item:
        lines.append(f"Plan: {plan_item.get('status')}")
    if result.get("reasons"):
        lines.append("")
        lines.append("Block reasons:")
        for reason in result["reasons"]:
            lines.append(f"- {reason}")
    return "\n".join(lines)
