from __future__ import annotations

from pathlib import Path
from typing import Any

from affilipilot.analytics.data_cube import fetch_facebook_post_metric, latest_social_metrics, render_social_metrics, save_social_metric
from affilipilot.publishing.lifecycle import latest_publish_tasks
from affilipilot.telegram.outbox import Outbox, OutboxMessage


def sync_published_facebook_insights(db_path: str | Path, *, batch_key: str = "", limit: int = 25) -> dict[str, Any]:
    tasks = [row for row in latest_publish_tasks(db_path, batch_key=batch_key) if row.get("state") == "published" and row.get("provider_post_id")]
    synced = 0
    failed = 0
    errors: list[str] = []
    for row in tasks[:limit]:
        metric = fetch_facebook_post_metric(row["provider_post_id"], post_id=row["post_id"])
        raw = metric.raw or {}
        raw.setdefault("publish_type", row.get("publish_type") or "photo_post")
        raw.setdefault("metrics_profile", row.get("metrics_profile") or "feed_post")
        metric.raw = raw
        save_social_metric(db_path, metric)
        if raw.get("ok") is False:
            failed += 1
            errors.append(f"{row['post_id']}:{raw.get('status')}")
        else:
            synced += 1
    return {"synced": synced, "failed": failed, "total_candidates": len(tasks), "errors": errors, "batch_key": batch_key}


def render_insights_sync(summary: dict[str, Any], db_path: str | Path) -> str:
    lines = [
        "🐌 AffiliPilot Facebook insights sync",
        f"Candidates: {summary.get('total_candidates', 0)}",
        f"Synced: {summary.get('synced', 0)}",
        f"Failed: {summary.get('failed', 0)}",
    ]
    if summary.get("errors"):
        lines.append("Errors: " + ", ".join(summary["errors"][:5]))
    rows = latest_social_metrics(db_path)
    if rows:
        lines.extend(["", render_social_metrics(rows[:5])])
    return "\n".join(lines)


def queue_insights_sync_digest(db_path: str | Path, *, outbox_path: str | Path, summary: dict[str, Any]) -> dict[str, Any]:
    outbox = Outbox(outbox_path)
    msg_id = "facebook-insights-sync" + (f"-{summary.get('batch_key')}" if summary.get("batch_key") else "")
    outbox.add(OutboxMessage(id=msg_id, kind="alert", text=render_insights_sync(summary, db_path)))
    return {"queued": 1, "outbox": str(outbox_path), "message_id": msg_id}
