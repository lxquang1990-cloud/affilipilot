from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.facebook import FacebookConfig, check_facebook_config
from affilipilot.publishing.gate import evaluate_publish_gate


@dataclass
class FacebookPostPlan:
    post_id: str
    status: str
    reasons: list[str] = field(default_factory=list)
    endpoint: str = ""
    payload_preview: dict[str, Any] = field(default_factory=dict)
    dry_run_only: bool = True


@dataclass
class FacebookBatchPlan:
    batch_key: str
    plans: list[FacebookPostPlan]
    publishable_count: int
    blocked_count: int
    dry_run_only: bool = True


def build_graph_payload(*, page_id: str, message: str, link: str = "", image_path: str = "") -> dict[str, Any]:
    payload = {"message": message}
    if link:
        payload["link"] = link
    endpoint = f"/{page_id}/feed"
    if image_path:
        endpoint = f"/{page_id}/photos"
        payload = {"caption": message, "url": link, "local_image_path": image_path}
    return {
        "endpoint": endpoint,
        "payload": payload,
    }


def _post_link(post: dict[str, Any]) -> str:
    product = post.get("product", {})
    return product.get("url", "")


def plan_facebook_batch(db_path: str | Path, *, batch_key: str, out_path: str | Path, config: FacebookConfig | None = None) -> FacebookBatchPlan:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        raise KeyError(f"Batch not found: {batch_key}")
    approvals = {row["post_id"]: row for row in db.get_approvals(batch_key)}
    manifest = batch["manifest"]
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)

    plans: list[FacebookPostPlan] = []
    seen_texts: set[str] = set()
    for post in manifest.get("posts", []):
        post_id = post["post_id"]
        approval = approvals.get(post_id, {})
        approved = approval.get("status") == "approved"
        post_file = Path(post.get("files", {}).get("post_text", ""))
        text = post_file.read_text(encoding="utf-8", errors="ignore").strip() if post_file.exists() else ""
        gate = evaluate_publish_gate(
            post,
            approved=approved,
            facebook_verified=health.verified,
            dry_run_passed=bool(text),
        )
        reasons = list(gate.reasons)
        if text in seen_texts and text:
            reasons.append("duplicate_text")
        seen_texts.add(text)

        if gate.allowed and "duplicate_text" not in reasons:
            graph = build_graph_payload(page_id=config.page_id, message=text, link=_post_link(post), image_path=post.get("files", {}).get("image", ""))
            plans.append(FacebookPostPlan(
                post_id=post_id,
                status="publishable_dry_run",
                endpoint=graph["endpoint"],
                payload_preview=graph["payload"],
            ))
        else:
            plans.append(FacebookPostPlan(
                post_id=post_id,
                status="blocked",
                reasons=reasons or ["not_publishable"],
            ))

    result = FacebookBatchPlan(
        batch_key=batch_key,
        plans=plans,
        publishable_count=sum(1 for p in plans if p.status == "publishable_dry_run"),
        blocked_count=sum(1 for p in plans if p.status != "publishable_dry_run"),
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def render_facebook_plan(plan: FacebookBatchPlan) -> str:
    lines = [
        f"🐌 Facebook dry-run plan — {plan.batch_key}",
        f"Publishable dry-run: {plan.publishable_count}",
        f"Blocked: {plan.blocked_count}",
        "Real POST: disabled",
        "",
    ]
    for item in plan.plans:
        if item.status == "publishable_dry_run":
            text = item.payload_preview.get('message') or item.payload_preview.get('caption') or ''
            lines.append(f"✅ {item.post_id}: would POST {item.endpoint} ({len(text)} chars)")
        else:
            lines.append(f"○ {item.post_id}: blocked — {', '.join(item.reasons)}")
    return "\n".join(lines)
