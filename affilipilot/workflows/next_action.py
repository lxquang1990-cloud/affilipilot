from __future__ import annotations

from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.safe_publish import validate_publish_safe
from affilipilot.telegram.outbox import Outbox


def _latest_batch_key(db_path: str | Path) -> str | None:
    db = AffiliPilotDB(db_path)
    db.init()
    with db.connect() as conn:
        row = conn.execute("SELECT batch_key FROM batches ORDER BY id DESC LIMIT 1").fetchone()
    return row["batch_key"] if row else None


def recommend_next_action(
    *,
    db_path: str | Path,
    batch_key: str | None = None,
    outbox_path: str | Path,
    plan_path: str | Path | None = None,
) -> dict[str, Any]:
    batch_key = batch_key or _latest_batch_key(db_path)
    if not batch_key:
        return {
            "batch_key": "",
            "status": "NO_BATCH",
            "action": "create_batch",
            "command": "python -m affilipilot sprint0 --link '<product link | title=... | category=... | price=...>'",
            "reason": "No batch found in SQLite.",
            "posts": [],
        }

    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        return {
            "batch_key": batch_key,
            "status": "NO_BATCH",
            "action": "create_batch",
            "command": "python -m affilipilot sprint0 --link '<product link | title=... | category=... | price=...>'",
            "reason": f"Batch not found: {batch_key}",
            "posts": [],
        }

    outbox = Outbox(outbox_path)
    outbox_messages = {m.id: m for m in outbox.load()}
    approvals = {row["post_id"]: row for row in db.get_approvals(batch_key)}
    post_ids = [post["post_id"] for post in batch.get("manifest", {}).get("posts", [])]
    plan_path = Path(plan_path) if plan_path else Path("data/publish") / batch_key / "facebook-plan.json"

    posts = []
    for post_id in post_ids:
        approval = approvals.get(post_id, {})
        summary = outbox_messages.get(f"{batch_key}:summary")
        card = outbox_messages.get(f"{batch_key}:{post_id}")
        validation = validate_publish_safe(db_path=db_path, batch_key=batch_key, post_id=post_id, plan_path=plan_path, outbox_path=outbox_path)
        posts.append({
            "post_id": post_id,
            "approval": approval.get("status", "missing"),
            "summary_delivery": summary.status if summary else "missing",
            "card_delivery": card.status if card else "missing",
            "publish_safe_ok": validation["ok"],
            "reasons": validation["reasons"],
        })

    if any(post["publish_safe_ok"] for post in posts):
        post_id = next(post["post_id"] for post in posts if post["publish_safe_ok"])
        return {
            "batch_key": batch_key,
            "status": "READY_TO_PUBLISH",
            "action": "publish_safe",
            "post_id": post_id,
            "command": f"python -m affilipilot publish-safe --db {db_path} --batch-key {batch_key} --post-id {post_id} --plan {plan_path} --outbox {outbox_path}",
            "reason": "At least one post passed approval, delivery proof, and Facebook dry-run plan gates.",
            "posts": posts,
        }

    if not outbox_messages:
        return {
            "batch_key": batch_key,
            "status": "NEEDS_OUTBOX",
            "action": "queue_telegram",
            "command": f"python -m affilipilot queue-telegram --db {db_path} --batch-key {batch_key} --outbox {outbox_path}",
            "reason": "No Telegram outbox messages exist for this batch.",
            "posts": posts,
        }

    needs_delivery = [p for p in posts if p["summary_delivery"] != "delivered" or p["card_delivery"] != "delivered"]
    if needs_delivery:
        post_id = needs_delivery[0]["post_id"]
        return {
            "batch_key": batch_key,
            "status": "NEEDS_DELIVERY_PROOF",
            "action": "mark_batch_delivered",
            "post_id": post_id,
            "command": f"python -m affilipilot mark-batch-delivered --outbox {outbox_path} --batch-key {batch_key} --post-id {post_id} --receipt telegram:<chat_id>:<message_id>",
            "reason": "Telegram approval summary/card are not both delivered with receipt.",
            "posts": posts,
        }

    needs_approval = [p for p in posts if p["approval"] != "approved"]
    if needs_approval:
        post_id = needs_approval[0]["post_id"]
        return {
            "batch_key": batch_key,
            "status": "NEEDS_APPROVAL",
            "action": "approve_or_reject",
            "post_id": post_id,
            "command": f"/aff_approve {post_id}  # or /aff_reject {post_id}",
            "reason": "Delivery proof exists, but operator approval is not approved yet.",
            "posts": posts,
        }

    if not plan_path.exists():
        return {
            "batch_key": batch_key,
            "status": "NEEDS_READY_TO_PUBLISH",
            "action": "ready_to_publish",
            "command": f"python -m affilipilot ready-to-publish --db {db_path} --batch-key {batch_key} --outbox {outbox_path} --out-dir {plan_path.parent}",
            "reason": "Approval and delivery are present, but Facebook plan/report is missing.",
            "posts": posts,
        }

    return {
        "batch_key": batch_key,
        "status": "BLOCKED",
        "action": "inspect_ready_to_publish",
        "command": f"python -m affilipilot ready-to-publish --db {db_path} --batch-key {batch_key} --outbox {outbox_path} --out-dir {plan_path.parent}",
        "reason": "No post is publish-safe yet; inspect per-post block reasons.",
        "posts": posts,
    }


def render_next_action(result: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot next action",
        f"Batch: {result.get('batch_key') or '(none)'}",
        f"Status: {result['status']}",
        f"Action: {result['action']}",
        f"Reason: {result['reason']}",
        "",
        "Command:",
        result["command"],
    ]
    posts = result.get("posts") or []
    if posts:
        lines.extend(["", "Posts:"])
        for post in posts:
            lines.append(
                f"- {post['post_id']}: approval={post['approval']} delivery={post['summary_delivery']}/{post['card_delivery']} publish_safe={'PASS' if post['publish_safe_ok'] else 'BLOCK'}"
            )
            if post.get("reasons"):
                lines.append("  reasons=" + ", ".join(post["reasons"]))
    return "\n".join(lines)
