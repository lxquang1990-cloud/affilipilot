from __future__ import annotations

from pathlib import Path

from affilipilot.analytics.digest import build_daily_digest
from affilipilot.db import AffiliPilotDB


def write_day_report(db_path: str | Path, *, batch_key: str, out_path: str | Path) -> Path:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        raise KeyError(f"Batch not found: {batch_key}")
    digest = build_daily_digest(db_path, batch_key=batch_key)
    approvals = db.get_approvals(batch_key)
    approval_map = {a["post_id"]: a for a in approvals}
    manifest = batch["manifest"]

    lines = [
        f"# AffiliPilot Day Report — {batch_key}",
        "",
        "## Digest",
        "",
        "```text",
        digest,
        "```",
        "",
        "## Drafts",
        "",
    ]
    for post in manifest.get("posts", []):
        product = post.get("product", {})
        approval = approval_map.get(post["post_id"], {})
        lines.extend([
            f"### {post['post_id']} — {product.get('title') or product.get('url')}",
            "",
            f"- Score: `{post.get('score')}`",
            f"- Compliance: `{post.get('compliance', {}).get('status')}`",
            f"- Approval: `{approval.get('status', 'unknown')}`",
            f"- Tracking: `{post.get('tracking', {}).get('sub3', post['post_id'])}`",
            f"- Post file: `{post.get('files', {}).get('post_text')}`",
            "",
        ])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
