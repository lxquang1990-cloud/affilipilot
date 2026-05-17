from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB


def build_batch_status(db_path: str | Path, *, batch_key: str, facebook_plan: str | Path | None = None) -> dict[str, Any]:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        raise KeyError(f"Batch not found: {batch_key}")

    approvals = db.get_approvals(batch_key)
    approval_by_post = {row["post_id"]: row for row in approvals}
    approval_counts = Counter(row["status"] for row in approvals)
    posts = batch["manifest"].get("posts", [])

    plan_by_post: dict[str, dict[str, Any]] = {}
    if facebook_plan:
        plan_path = Path(facebook_plan)
        if plan_path.exists():
            data = json.loads(plan_path.read_text(encoding="utf-8"))
            plan_by_post = {item["post_id"]: item for item in data.get("plans", [])}

    post_rows = []
    for post in posts:
        post_id = post["post_id"]
        approval = approval_by_post.get(post_id, {"status": "unknown", "reason": ""})
        plan = plan_by_post.get(post_id, {})
        post_rows.append({
            "post_id": post_id,
            "title": post.get("product", {}).get("title") or post.get("product", {}).get("url", ""),
            "score": post.get("score"),
            "compliance": post.get("compliance", {}).get("status"),
            "approval": approval.get("status"),
            "approval_reason": approval.get("reason", ""),
            "facebook_plan": plan.get("status", "not_planned"),
            "facebook_reasons": plan.get("reasons", []),
        })

    plan_counts = Counter(row["facebook_plan"] for row in post_rows)
    return {
        "batch_key": batch_key,
        "batch_status": batch.get("status"),
        "total_posts": len(posts),
        "approval_counts": dict(approval_counts),
        "facebook_plan_counts": dict(plan_counts),
        "posts": post_rows,
    }


def render_batch_status(status: dict[str, Any]) -> str:
    lines = [
        f"🐌 AffiliPilot batch status — {status['batch_key']}",
        f"Batch state: {status.get('batch_status')}",
        f"Posts: {status['total_posts']}",
        "",
        "Approvals:",
    ]
    approval_counts = status.get("approval_counts", {})
    if approval_counts:
        for key in sorted(approval_counts):
            lines.append(f"- {key}: {approval_counts[key]}")
    else:
        lines.append("- none")

    lines.extend(["", "Facebook plan:"])
    plan_counts = status.get("facebook_plan_counts", {})
    if plan_counts:
        for key in sorted(plan_counts):
            lines.append(f"- {key}: {plan_counts[key]}")
    else:
        lines.append("- none")

    lines.extend(["", "Posts:"])
    for row in status.get("posts", []):
        suffix = ""
        if row.get("facebook_reasons"):
            suffix = " — " + ", ".join(row["facebook_reasons"])
        lines.append(
            f"- {row['post_id']}: score={row['score']} compliance={row['compliance']} "
            f"approval={row['approval']} plan={row['facebook_plan']}{suffix}"
        )
    return "\n".join(lines)
