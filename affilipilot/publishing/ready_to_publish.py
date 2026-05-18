from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.facebook_plan import plan_facebook_batch
from affilipilot.publishing.ready_package import build_ready_to_post_package
from affilipilot.publishing.safe_publish import validate_publish_safe


def build_ready_to_publish_report(
    *,
    db_path: str | Path,
    batch_key: str,
    outbox_path: str | Path,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Build ready package + Facebook dry-run plan + publish-safe validations.

    No network calls and no real publish side effects.
    """
    out_dir = Path(out_dir)
    ready_dir = out_dir / "ready"
    plan_path = out_dir / "facebook-plan.json"
    report_path = out_dir / "ready-to-publish.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    ready_package = build_ready_to_post_package(db_path, batch_key=batch_key, out_dir=ready_dir)
    plan = plan_facebook_batch(db_path, batch_key=batch_key, out_path=plan_path)

    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    post_ids = [post["post_id"] for post in (batch or {}).get("manifest", {}).get("posts", [])]
    validations = [
        validate_publish_safe(
            db_path=db_path,
            batch_key=batch_key,
            post_id=post_id,
            plan_path=plan_path,
            outbox_path=outbox_path,
        )
        for post_id in post_ids
    ]
    publishable = [item for item in validations if item["ok"]]
    blocked = [item for item in validations if not item["ok"]]
    report = {
        "batch_key": batch_key,
        "out_dir": str(out_dir),
        "ready_dir": str(ready_dir),
        "plan_path": str(plan_path),
        "report_path": str(report_path),
        "ready_count": ready_package["ready_count"],
        "held_count": ready_package["held_count"],
        "plan_publishable_count": plan.publishable_count,
        "plan_blocked_count": plan.blocked_count,
        "publish_safe_pass_count": len(publishable),
        "publish_safe_block_count": len(blocked),
        "validations": validations,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def render_ready_to_publish_report(report: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot ready-to-publish",
        f"Batch: {report['batch_key']}",
        f"Ready package: {report['ready_count']} ready / {report['held_count']} held",
        f"Facebook plan: {report['plan_publishable_count']} publishable / {report['plan_blocked_count']} blocked",
        f"Publish-safe: {report['publish_safe_pass_count']} PASS / {report['publish_safe_block_count']} BLOCK",
        f"Plan JSON: {report['plan_path']}",
        f"Report JSON: {report['report_path']}",
        "",
    ]
    for item in report["validations"]:
        status = "✅ PASS" if item["ok"] else "○ BLOCK"
        lines.append(f"{status} {item['post_id']}")
        if item.get("reasons"):
            lines.append("  Reasons: " + ", ".join(item["reasons"]))
    return "\n".join(lines)
