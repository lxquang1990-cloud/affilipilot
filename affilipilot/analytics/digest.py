from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB


def build_daily_digest(db_path: str | Path, *, batch_key: str) -> str:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        return f"🐌 AffiliPilot digest — {batch_key}\nNo batch found."
    approvals = db.get_approvals(batch_key)
    counts = Counter(row["status"] for row in approvals)
    manifest = batch["manifest"]
    posts: list[dict[str, Any]] = manifest.get("posts", [])
    avg_score = round(sum(int(p.get("score", 0)) for p in posts) / len(posts), 1) if posts else 0
    risky = [p for p in posts if p.get("compliance", {}).get("status") != "pass"]

    lines = [
        f"🐌 AffiliPilot daily digest — {batch_key}",
        "",
        f"Products considered: {manifest.get('total_products', 0)}",
        f"Drafts selected: {manifest.get('selected', 0)}",
        f"Average money score: {avg_score}/100",
        f"Pending: {counts.get('pending', 0)}",
        f"Approved: {counts.get('approved', 0)}",
        f"Rejected: {counts.get('rejected', 0)}",
        f"Needs edit: {counts.get('needs_edit', 0)}",
        f"Blacklisted: {counts.get('blacklisted', 0)}",
        f"Compliance non-pass: {len(risky)}",
        "",
        "Top drafts:",
    ]
    for post in posts[:5]:
        product = post.get("product", {})
        lines.append(f"- {post['post_id']} · {post.get('score')}/100 · {post.get('compliance', {}).get('status')} · {product.get('title') or product.get('url')}")
    return "\n".join(lines)
