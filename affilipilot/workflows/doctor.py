from __future__ import annotations

from pathlib import Path
from typing import Any

from affilipilot.config import load_config
from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.facebook import check_facebook_config
from affilipilot.readiness import build_readiness_report
from affilipilot.telegram.outbox import Outbox
from affilipilot.accesstrade.client import check_accesstrade_config
from affilipilot.security import check_secret_file_permissions


def _check(status: str, name: str, detail: str = "", *, severity: str = "info") -> dict[str, str]:
    return {"status": status, "name": name, "detail": detail, "severity": severity}


def _latest_batch_key(db_path: str | Path) -> str:
    db = AffiliPilotDB(db_path)
    db.init()
    with db.connect() as conn:
        row = conn.execute("SELECT batch_key FROM batches ORDER BY id DESC LIMIT 1").fetchone()
    return row["batch_key"] if row else ""


def build_doctor_report(
    *,
    db_path: str | Path = "data/affilipilot.db",
    outbox_path: str | Path = "data/outbox/telegram.json",
    batch_key: str = "",
    secret_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read-only AffiliPilot operational audit. No external API calls."""
    db_path = Path(db_path)
    outbox_path = Path(outbox_path)
    cfg = load_config(secret_path) if secret_path else load_config()
    secret = check_secret_file_permissions(cfg.secret_path)
    readiness = build_readiness_report()
    fb = check_facebook_config()
    at = check_accesstrade_config()

    checks: list[dict[str, str]] = []
    checks.append(_check("pass" if secret["exists"] and secret["secure"] else "warn", "secret_file", str(secret), severity="warn"))
    checks.append(_check("pass" if db_path.exists() else "warn", "sqlite_db", str(db_path), severity="warn"))
    checks.append(_check("pass" if outbox_path.exists() else "warn", "telegram_outbox", str(outbox_path), severity="warn"))
    checks.append(_check("pass" if fb.verified else "missing", "facebook_config", ",".join(fb.reasons) if fb.reasons else "present", severity="blocker"))
    checks.append(_check("pass" if at.configured else "missing", "accesstrade_config", ",".join(at.reasons) if at.reasons else "present", severity="warn"))
    checks.append(_check("pass" if cfg.telegram_config_present else "optional", "telegram_bot_config", "direct bot delivery optional; OpenClaw route can be used", severity="info"))
    checks.append(_check("pass" if readiness.ready_for_local_manual else "warn", "local_manual_workflow", "sprint0/readiness local flow", severity="warn"))

    resolved_batch = batch_key or (_latest_batch_key(db_path) if db_path.exists() else "")
    batch_summary: dict[str, Any] = {"batch_key": resolved_batch, "exists": False, "posts": 0, "approvals": {}}
    if resolved_batch:
        db = AffiliPilotDB(db_path)
        batch = db.get_batch(resolved_batch)
        if batch:
            approvals = db.get_approvals(resolved_batch)
            counts: dict[str, int] = {}
            for row in approvals:
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            batch_summary = {
                "batch_key": resolved_batch,
                "exists": True,
                "posts": len(batch.get("manifest", {}).get("posts", [])),
                "approvals": counts,
            }
            checks.append(_check("pass", "batch", f"{resolved_batch}: {batch_summary['posts']} posts", severity="info"))
        else:
            checks.append(_check("warn", "batch", f"not found: {resolved_batch}", severity="warn"))
    else:
        checks.append(_check("warn", "batch", "no batch found", severity="warn"))

    outbox_summary = {"exists": outbox_path.exists(), "messages": 0, "statuses": {}}
    if outbox_path.exists():
        messages = Outbox(outbox_path).load()
        statuses: dict[str, int] = {}
        for message in messages:
            statuses[message.status] = statuses.get(message.status, 0) + 1
        outbox_summary = {"exists": True, "messages": len(messages), "statuses": statuses}
        checks.append(_check("pass" if messages else "warn", "outbox_messages", f"{len(messages)} messages {statuses}", severity="warn"))

    blocker_count = sum(1 for c in checks if c["status"] in {"missing", "fail"} and c["severity"] == "blocker")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    return {
        "ok_for_local_workflow": blocker_count == 0,
        "ok_for_publish_config": fb.verified,
        "blocker_count": blocker_count,
        "warn_count": warn_count,
        "db_path": str(db_path),
        "outbox_path": str(outbox_path),
        "secret_path": str(cfg.secret_path),
        "batch": batch_summary,
        "outbox": outbox_summary,
        "checks": checks,
    }


def render_doctor_report(report: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot doctor",
        f"Local workflow: {'OK' if report['ok_for_local_workflow'] else 'BLOCKED'}",
        f"Publish config-present: {'OK' if report['ok_for_publish_config'] else 'BLOCKED'}",
        f"Blockers: {report['blocker_count']} | Warnings: {report['warn_count']}",
        f"DB: {report['db_path']}",
        f"Outbox: {report['outbox_path']}",
        f"Secret path: {report['secret_path']}",
        "",
        "Checks:",
    ]
    for check in report["checks"]:
        icon = "✅" if check["status"] == "pass" else "⚠️" if check["status"] == "warn" else "○" if check["status"] == "optional" else "✖"
        lines.append(f"{icon} {check['name']}: {check['status']} — {check['detail']}")
    batch = report["batch"]
    lines.extend(["", f"Batch: {batch.get('batch_key') or '(none)'} exists={batch['exists']} posts={batch['posts']} approvals={batch['approvals']}"])
    outbox = report["outbox"]
    lines.append(f"Outbox: exists={outbox['exists']} messages={outbox['messages']} statuses={outbox['statuses']}")
    lines.append("")
    lines.append("Note: doctor is read-only and does not call Facebook/Telegram/Accesstrade APIs.")
    return "\n".join(lines)
