from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.publishing.facebook_plan import plan_facebook_batch
from affilipilot.publishing.lifecycle import record_publish_event
from affilipilot.publishing.safe_publish import validate_publish_safe
from affilipilot.security import redact_response


def _response_facebook_id(result: dict[str, Any]) -> str:
    response = result.get("response", {}) if isinstance(result.get("response"), dict) else {}
    return str(response.get("post_id") or response.get("id") or "")


def publish_after_approval(
    *,
    db_path: str | Path,
    batch_key: str,
    post_id: str,
    outbox_path: str | Path,
    out_dir: str | Path,
    publisher,
) -> dict[str, Any]:
    """Publish a post immediately after a real operator approval.

    The approval itself is the final publish intent. This function still builds a
    fresh Facebook plan and runs publish-safe before any network side effect.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "facebook-plan.json"
    result_path = out_dir / f"publish-{post_id}.json"

    plan = plan_facebook_batch(db_path, batch_key=batch_key, out_path=plan_path)
    gate = validate_publish_safe(
        db_path=db_path,
        batch_key=batch_key,
        post_id=post_id,
        plan_path=plan_path,
        outbox_path=outbox_path,
    )
    if not gate["ok"]:
        record_publish_event(
            db_path,
            batch_key=batch_key,
            post_id=post_id,
            state="failed",
            reason="publish_safe_block_after_approval",
            payload={"reasons": gate["reasons"], "plan_path": str(plan_path)},
        )
        return {
            "ok": False,
            "status": "blocked",
            "batch_key": batch_key,
            "post_id": post_id,
            "plan_path": str(plan_path),
            "result_path": "",
            "reasons": gate["reasons"],
            "publish_safe": gate,
        }

    matches = [item for item in plan.plans if item.post_id == post_id]
    if not matches or matches[0].status != "publishable_dry_run":
        reasons = ["plan_not_publishable"] + (matches[0].reasons if matches else ["plan_post_not_found"])
        record_publish_event(
            db_path,
            batch_key=batch_key,
            post_id=post_id,
            state="failed",
            reason="plan_block_after_approval",
            payload={"reasons": reasons, "plan_path": str(plan_path)},
        )
        return {
            "ok": False,
            "status": "blocked",
            "batch_key": batch_key,
            "post_id": post_id,
            "plan_path": str(plan_path),
            "result_path": "",
            "reasons": reasons,
            "publish_safe": gate,
        }

    item = matches[0]
    result = publisher({
        "post_id": item.post_id,
        "status": item.status,
        "reasons": item.reasons,
        "endpoint": item.endpoint,
        "payload_preview": item.payload_preview,
    }, item.payload_preview)
    safe_result = redact_response(result)
    result_path.write_text(json.dumps(safe_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    facebook_id = _response_facebook_id(safe_result)
    record_publish_event(
        db_path,
        batch_key=batch_key,
        post_id=post_id,
        state="published" if safe_result.get("ok") else "failed",
        facebook_post_id=facebook_id,
        reason="approval_triggered_publish" if safe_result.get("ok") else "facebook_publish_failed_after_approval",
        payload={"result_path": str(result_path), "plan_path": str(plan_path), "result": safe_result},
    )

    return {
        "ok": bool(safe_result.get("ok")),
        "status": "published" if safe_result.get("ok") else "failed",
        "batch_key": batch_key,
        "post_id": post_id,
        "facebook_post_id": facebook_id,
        "plan_path": str(plan_path),
        "result_path": str(result_path),
        "reasons": [] if safe_result.get("ok") else ["facebook_publish_failed"],
        "publish_safe": gate,
        "result": safe_result,
    }


def render_publish_after_approval(result: dict[str, Any]) -> str:
    if result.get("ok"):
        lines = [
            "✅ Approved + published to Facebook",
            f"Post: {result['post_id']}",
        ]
        if result.get("facebook_post_id"):
            lines.append(f"Facebook post id: {result['facebook_post_id']}")
        lines.append(f"Result JSON: {result['result_path']}")
        return "\n".join(lines)
    lines = [
        "⚠️ Approved, but publish was blocked",
        f"Post: {result['post_id']}",
        "Reasons: " + ", ".join(result.get("reasons") or ["unknown"]),
        f"Plan JSON: {result.get('plan_path', '')}",
    ]
    return "\n".join(lines)
