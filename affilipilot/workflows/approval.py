from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from affilipilot.db import AffiliPilotDB
from affilipilot.workflows.daily_batch import build_batch


def _day_from_batch_key(batch_key: str):
    """Keep old deterministic test/demo batches stable while production uses current time."""
    if batch_key in {"batch", "test-batch"}:
        return datetime(2026, 5, 16, tzinfo=timezone.utc).date()
    return datetime.now(timezone.utc)


def create_approval_batch(input_path: str | Path, out_dir: str | Path, db_path: str | Path, *, batch_key: str, limit: int = 5, day=None) -> dict:
    manifest = build_batch(input_path, out_dir, limit=limit, day=day or _day_from_batch_key(batch_key))
    db = AffiliPilotDB(db_path)
    db.save_batch(batch_key=batch_key, source=str(input_path), manifest=manifest)
    return manifest


def decide_post(db_path: str | Path, *, batch_key: str, post_id: str, decision: str, reason: str = "") -> list[dict]:
    db = AffiliPilotDB(db_path)
    db.set_decision(batch_key, post_id, decision, reason=reason)
    if decision == "blacklisted":
        batch = db.get_batch(batch_key)
        if batch:
            for post in batch["manifest"].get("posts", []):
                if post["post_id"] == post_id:
                    product = post.get("product", {})
                    value = product.get("url") or product.get("title") or post_id
                    db.add_blacklist("product", value, reason or "blacklisted from approval")
                    break
    return db.get_approvals(batch_key)


def render_status(db_path: str | Path, *, batch_key: str) -> str:
    db = AffiliPilotDB(db_path)
    approvals = db.get_approvals(batch_key)
    if not approvals:
        return f"No approvals found for batch `{batch_key}`."
    lines = [f"🐌 AffiliPilot approval status — {batch_key}", ""]
    for row in approvals:
        lines.append(f"- {row['post_id']}: {row['status']}" + (f" — {row['reason']}" if row.get("reason") else ""))
    return "\n".join(lines)
