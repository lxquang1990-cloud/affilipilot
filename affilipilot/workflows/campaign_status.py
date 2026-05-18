from __future__ import annotations

from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.workflows.doctor import build_doctor_report
from affilipilot.workflows.next_action import recommend_next_action


def _resolve_batch_key(db_path: str | Path, batch_key: str = "") -> str:
    if batch_key:
        return batch_key
    db = AffiliPilotDB(db_path)
    db.init()
    with db.connect() as conn:
        row = conn.execute("SELECT batch_key FROM batches ORDER BY id DESC LIMIT 1").fetchone()
    return row["batch_key"] if row else ""


def build_campaign_status(
    *,
    db_path: str | Path = "data/affilipilot.db",
    batch_key: str = "",
    outbox_path: str | Path = "data/outbox/telegram.json",
    out_dir: str | Path = "data/publish/campaign-status",
    secret_path: str | Path | None = None,
    build_ready: bool = True,
) -> dict[str, Any]:
    """Build one operator dashboard. No publish and no external API calls."""
    db_path = Path(db_path)
    outbox_path = Path(outbox_path)
    out_dir = Path(out_dir)
    resolved_batch = _resolve_batch_key(db_path, batch_key) if db_path.exists() else batch_key

    doctor = build_doctor_report(db_path=db_path, outbox_path=outbox_path, batch_key=resolved_batch, secret_path=secret_path)
    ready_report: dict[str, Any] | None = None
    plan_path: Path | None = None
    if build_ready and resolved_batch and doctor.get("batch", {}).get("exists"):
        ready_report = build_ready_to_publish_report(db_path=db_path, batch_key=resolved_batch, outbox_path=outbox_path, out_dir=out_dir)
        plan_path = Path(ready_report["plan_path"])
    else:
        plan_path = out_dir / "facebook-plan.json"

    next_action = recommend_next_action(db_path=db_path, batch_key=resolved_batch or None, outbox_path=outbox_path, plan_path=plan_path)
    return {
        "batch_key": resolved_batch,
        "db_path": str(db_path),
        "outbox_path": str(outbox_path),
        "out_dir": str(out_dir),
        "doctor": doctor,
        "next_action": next_action,
        "ready_to_publish": ready_report,
    }


def render_campaign_status(status: dict[str, Any]) -> str:
    doctor = status["doctor"]
    next_action = status["next_action"]
    ready = status.get("ready_to_publish")
    lines = [
        "🐌 AffiliPilot campaign status",
        f"Batch: {status.get('batch_key') or '(none)'}",
        f"System: {'OK' if doctor['ok_for_local_workflow'] else 'BLOCKED'} | publish config: {'OK' if doctor['ok_for_publish_config'] else 'BLOCKED'} | warnings={doctor['warn_count']}",
        f"Next: {next_action['status']} → {next_action['action']}",
        f"Reason: {next_action['reason']}",
        "",
        "Next command:",
        next_action["command"],
        "",
    ]
    if ready:
        lines.extend([
            "Ready-to-publish:",
            f"- Ready package: {ready['ready_count']} ready / {ready['held_count']} held",
            f"- Facebook plan: {ready['plan_publishable_count']} publishable / {ready['plan_blocked_count']} blocked",
            f"- Publish-safe: {ready['publish_safe_pass_count']} PASS / {ready['publish_safe_block_count']} BLOCK",
            f"- Report: {ready['report_path']}",
            "",
        ])
    batch = doctor["batch"]
    outbox = doctor["outbox"]
    lines.extend([
        "State:",
        f"- Batch: exists={batch['exists']} posts={batch['posts']} approvals={batch['approvals']}",
        f"- Outbox: exists={outbox['exists']} messages={outbox['messages']} statuses={outbox['statuses']}",
        "",
        "Posts:",
    ])
    posts = next_action.get("posts") or []
    if posts:
        for post in posts:
            status_text = "PASS" if post["publish_safe_ok"] else "BLOCK"
            lines.append(f"- {post['post_id']}: approval={post['approval']} delivery={post['summary_delivery']}/{post['card_delivery']} publish_safe={status_text}")
            if post.get("reasons"):
                lines.append("  reasons=" + ", ".join(post["reasons"]))
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Note: campaign-status is read-only except for writing local ready/plan/report files; it never publishes.")
    return "\n".join(lines)
