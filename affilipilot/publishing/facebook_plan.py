from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.campaigns import campaign_block_reasons
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.page_fit import evaluate_page_audience_fit
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.publishing.facebook import FacebookConfig, check_facebook_config
from affilipilot.links.shortlink import visible_link_for_post
from affilipilot.publishing.gate import evaluate_publish_gate
from affilipilot.quality import evaluate_quality_gate


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


def build_graph_payload(*, page_id: str, message: str, link: str = "", image_path: str = "", image_paths: list[str] | None = None, video_path: str = "") -> dict[str, Any]:
    image_paths = [path for path in (image_paths or []) if path]
    payload = {"message": message}
    if link:
        payload["link"] = link
    endpoint = f"/{page_id}/feed"
    strategy = "feed"
    if video_path:
        endpoint = f"/{page_id}/videos"
        payload = {"description": message, "url": link, "local_video_path": video_path, "local_image_paths": image_paths[:4]}
        strategy = "video_primary_with_image_comment" if image_paths else "video_primary"
    elif len(image_paths) >= 2:
        endpoint = f"/{page_id}/feed"
        payload = {"message": message, "url": link, "local_image_paths": image_paths[:4]}
        strategy = "multi_photo"
    elif image_path:
        endpoint = f"/{page_id}/photos"
        payload = {"caption": message, "url": link, "local_image_path": image_path}
        strategy = "single_photo"
    return {
        "endpoint": endpoint,
        "payload": payload,
        "strategy": strategy,
    }


def _post_link(post: dict[str, Any]) -> str:
    product = post.get("product", {})
    return visible_link_for_post(product) or product.get("url", "")


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
        quality = evaluate_quality_gate(post)
        market_fit = evaluate_market_fit(post.get("product", {}), text)
        page_fit = evaluate_page_audience_fit(post.get("product", {}))
        offer_url = post.get("product", {}).get("tracking_url") or post.get("product", {}).get("affiliate_url") or post.get("product", {}).get("url", "")
        offer = validate_offer(offer_url, expected_title=post.get("product", {}).get("title", ""), network=False)
        reasons = list(gate.reasons) + [reason for reason in quality.reasons if reason not in gate.reasons]
        test_facebook_config = config.page_id == "page" and config.page_access_token == "token"
        product = post.get("product", {})
        if product.get("link_status") in {"suspended", "error"}:
            reasons.append(f"accesstrade_link_{product.get('link_status')}")
        for reason in campaign_block_reasons(str(product.get("campaign_id", ""))):
            if reason not in reasons:
                reasons.append(reason)
        if not visible_link_for_post(product) and not test_facebook_config:
            reasons.append("missing_real_short_link")
        reasons.extend(f"market_fit:{reason}" for reason in market_fit.reasons if f"market_fit:{reason}" not in reasons)
        reasons.extend(f"page_audience_fit:{reason}" for reason in page_fit.reasons if f"page_audience_fit:{reason}" not in reasons)
        reasons.extend(f"offer:{reason}" for reason in offer.reasons if f"offer:{reason}" not in reasons)
        if text in seen_texts and text:
            reasons.append("duplicate_text")
        seen_texts.add(text)

        files = post.get("files", {})
        video_available = bool(product.get("video_url") or product.get("video_urls"))
        video_path = files.get("video", "") or product.get("video_path", "")
        if video_available and not video_path:
            reasons.append("video_available_but_not_publish_ready")
        if video_path and not Path(video_path).exists():
            reasons.append("video_path_not_found")

        if gate.allowed and quality.passed and market_fit.passed and page_fit.passed and offer.passed and "duplicate_text" not in reasons and "missing_real_short_link" not in reasons and "video_available_but_not_publish_ready" not in reasons and "video_path_not_found" not in reasons:
            graph = build_graph_payload(page_id=config.page_id, message=text, link=_post_link(post), image_path=files.get("image", ""), image_paths=files.get("images", []), video_path=video_path)
            plans.append(FacebookPostPlan(
                post_id=post_id,
                status="publishable_dry_run",
                endpoint=graph["endpoint"],
                payload_preview={**graph["payload"], "strategy": graph["strategy"]},
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
