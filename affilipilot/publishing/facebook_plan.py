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
from affilipilot.publishing.lifecycle import record_publish_event
from affilipilot.publishing.restrictions import get_platform_restriction
from affilipilot.publishing.strategy import PublishStrategy, select_facebook_publish_strategy, strategy_as_dict
from affilipilot.quality import evaluate_quality_gate


@dataclass
class FacebookPostPlan:
    post_id: str
    status: str
    reasons: list[str] = field(default_factory=list)
    endpoint: str = ""
    payload_preview: dict[str, Any] = field(default_factory=dict)
    publish_type: str = "photo_post"
    metrics_profile: str = "feed_post"
    dry_run_only: bool = True


@dataclass
class FacebookBatchPlan:
    batch_key: str
    plans: list[FacebookPostPlan]
    publishable_count: int
    blocked_count: int
    dry_run_only: bool = True


def build_graph_payload(*, page_id: str, message: str, link: str = "", image_path: str = "", image_paths: list[str] | None = None, video_path: str = "", publish_type: str = "") -> dict[str, Any]:
    image_paths = [path for path in (image_paths or []) if path]
    payload = {"message": message}
    if link:
        payload["link"] = link
    endpoint = f"/{page_id}/feed"
    strategy = "feed"
    if video_path:
        endpoint = f"/{page_id}/reels" if publish_type == "reel" else f"/{page_id}/videos"
        payload = {"description": message, "url": link, "local_video_path": video_path, "local_image_paths": image_paths[:4]}
        strategy = "reel_primary" if publish_type == "reel" else ("video_primary_with_image_comment" if image_paths else "video_primary")
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



def _publish_text(post: dict[str, Any]) -> str:
    post_file = Path(post.get("files", {}).get("post_text", ""))
    artifact_text = post_file.read_text(encoding="utf-8", errors="ignore").strip() if post_file.exists() else ""
    manifest_text = str(post.get("caption") or "").strip()
    # Prefer the current manifest caption over a draft artifact. Manual edits and
    # regenerated copy update the manifest first; stale `.post.txt` files must not
    # leak old captions into Facebook payloads. Fall back to the artifact for
    # legacy batches that do not carry `post.caption`.
    return manifest_text or artifact_text

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
        text = _publish_text(post)
        gate = evaluate_publish_gate(
            post,
            approved=approved,
            facebook_verified=health.verified,
            dry_run_passed=bool(text),
        )
        quality = evaluate_quality_gate(post)
        market_fit = evaluate_market_fit(post.get("product", {}), text)
        page_fit = evaluate_page_audience_fit(post.get("product", {}), page_name=config.page_name)
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

        files = post.get("files", {})
        strategy = select_facebook_publish_strategy(post)
        restrictions = get_platform_restriction(strategy.platform, publish_type=strategy.publish_type)
        if len(text) > restrictions.caption_max_chars:
            reasons.append("caption_too_long_for_facebook")
        if text in seen_texts and text:
            reasons.append("duplicate_text")
        seen_texts.add(text)
        video_available = bool(product.get("video_url") or product.get("video_urls"))
        video_path = files.get("video", "") or product.get("video_path", "")
        if video_available and not video_path:
            reasons.append("video_available_but_not_publish_ready")
        if video_path and not Path(video_path).exists():
            reasons.append("video_path_not_found")

        if gate.allowed and quality.passed and market_fit.passed and page_fit.passed and offer.passed and "duplicate_text" not in reasons and "caption_too_long_for_facebook" not in reasons and "missing_real_short_link" not in reasons and "video_available_but_not_publish_ready" not in reasons and "video_path_not_found" not in reasons:
            graph = build_graph_payload(page_id=config.page_id, message=text, link=_post_link(post), image_path=files.get("image", ""), image_paths=files.get("images", [])[:restrictions.image_max_count], video_path=video_path, publish_type=strategy.publish_type)
            plans.append(FacebookPostPlan(
                post_id=post_id,
                status="publishable_dry_run",
                endpoint=graph["endpoint"],
                payload_preview={**graph["payload"], "strategy": graph["strategy"], "publish_type": strategy.publish_type, "metrics_profile": strategy.metrics_profile},
                publish_type=strategy.publish_type,
                metrics_profile=strategy.metrics_profile,
            ))
            record_publish_event(db_path, batch_key=batch_key, post_id=post_id, state="planned", reason="facebook_dry_run_plan", payload={"endpoint": graph["endpoint"], "strategy": graph["strategy"], **strategy_as_dict(strategy)})
        else:
            plans.append(FacebookPostPlan(
                post_id=post_id,
                status="blocked",
                reasons=reasons or ["not_publishable"],
                publish_type=strategy.publish_type,
                metrics_profile=strategy.metrics_profile,
            ))
            record_publish_event(db_path, batch_key=batch_key, post_id=post_id, state="held", reason=",".join(reasons or ["not_publishable"]), payload={"reasons": reasons or ["not_publishable"], **strategy_as_dict(strategy)})

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
            # Feed/photo payloads use `message`/`caption`; Facebook video uploads
            # use `description`. Render the same public text field that will be
            # posted so operators do not see a false "0 chars" for video plans.
            text = item.payload_preview.get('message') or item.payload_preview.get('caption') or item.payload_preview.get('description') or ''
            publish_type = getattr(item, "publish_type", item.payload_preview.get("publish_type", "photo_post"))
            metrics_profile = getattr(item, "metrics_profile", item.payload_preview.get("metrics_profile", "feed_post"))
            lines.append(f"✅ {item.post_id}: would POST {item.endpoint} [{publish_type}/{metrics_profile}] ({len(text)} chars)")
        else:
            publish_type = getattr(item, "publish_type", "photo_post")
            metrics_profile = getattr(item, "metrics_profile", "feed_post")
            lines.append(f"○ {item.post_id}: blocked [{publish_type}/{metrics_profile}] — {', '.join(item.reasons)}")
    return "\n".join(lines)
