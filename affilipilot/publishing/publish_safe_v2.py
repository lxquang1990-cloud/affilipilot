from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.content.content_gate import evaluate_content_gates
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.niche_policy import evaluate_niche_fit
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.db import AffiliPilotDB
from affilipilot.media_quality import evaluate_media_quality
from affilipilot.offer import validate_offer
from affilipilot.publishing.requirements import check_affiliate_link
from affilipilot.quality import evaluate_quality_gate
from affilipilot.telegram.outbox import Outbox

@dataclass
class SafeCheck:
    name: str
    status: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in {"pass", "pass_with_warning"}


def _resolve_project_path(path: str | Path, *, project_root: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else project_root / candidate


def _normalize_post_paths(post: dict[str, Any], *, project_root: Path) -> dict[str, Any]:
    """Return a shallow-normalized post with local paths resolved to project root.

    Scheduled batches store media/draft paths relative to the AffiliPilot project
    root, while the Telegram/OpenClaw process may run from another CWD. Publish
    safety must inspect the same files used by facebook-plan, not paths resolved
    against process CWD.
    """
    normalized = {**post}
    files = dict(post.get("files", {}))
    for key in ("post_text", "telegram_card", "image", "video"):
        if files.get(key):
            files[key] = str(_resolve_project_path(files[key], project_root=project_root))
    if isinstance(files.get("images"), list):
        files["images"] = [str(_resolve_project_path(path, project_root=project_root)) for path in files["images"] if path]
    normalized["files"] = files
    product = dict(post.get("product", {}))
    for key in ("image_path", "video_path"):
        if product.get(key):
            product[key] = str(_resolve_project_path(product[key], project_root=project_root))
    normalized["product"] = product
    return normalized


def _text_for_post(post: dict[str, Any]) -> str:
    post_file = Path(post.get("files", {}).get("post_text", ""))
    artifact_text = post_file.read_text(encoding="utf-8", errors="ignore") if str(post_file) and post_file.exists() else ""
    manifest_text = str(post.get("caption") or post.get("text") or post.get("message") or post.get("post_text") or "").strip()
    return manifest_text or artifact_text


def _check_batch_post(db_path: str | Path, batch_key: str, post_id: str) -> tuple[SafeCheck, dict[str, Any] | None, dict[str, Any] | None]:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        return SafeCheck("batch_post", "block", ["batch_not_found"]), None, None
    project_root = Path(db_path).expanduser().resolve().parents[1]
    posts = batch.get("manifest", {}).get("posts", [])
    matches = [_normalize_post_paths(item, project_root=project_root) for item in posts if item.get("post_id") == post_id]
    if not matches:
        return SafeCheck("batch_post", "block", ["batch_post_not_found"]), batch, None
    return SafeCheck("batch_post", "pass", details={"batch_status": batch.get("status", "")}), batch, matches[0]


def _check_approval(db_path: str | Path, batch_key: str, post_id: str) -> SafeCheck:
    db = AffiliPilotDB(db_path)
    approvals = {row["post_id"]: row for row in db.get_approvals(batch_key)}
    approval = approvals.get(post_id)
    if not approval:
        return SafeCheck("approval", "block", ["approval_not_found"])
    if approval.get("status") != "approved":
        return SafeCheck("approval", "block", [f"approval_not_approved:{approval.get('status')}"] , details=approval)
    return SafeCheck("approval", "pass", details=approval)


def _check_delivery(outbox_path: str | Path, batch_key: str, post_id: str) -> SafeCheck:
    outbox = Outbox(outbox_path)
    messages = {m.id: m for m in outbox.load()}
    reasons: list[str] = []
    details: dict[str, Any] = {}
    # The approval card is mandatory delivery proof. The batch summary is optional
    # for concise single-card batches.
    for message_id in [f"{batch_key}:{post_id}"]:
        msg = messages.get(message_id)
        if not msg:
            reasons.append(f"delivery_missing:{message_id}")
            continue
        details[message_id] = {"status": msg.status, "receipt": msg.receipt, "delivered_at": msg.delivered_at}
        if msg.status != "delivered":
            reasons.append(f"delivery_not_delivered:{message_id}:{msg.status}")
        if not msg.receipt:
            reasons.append(f"delivery_missing_receipt:{message_id}")
    summary_id = f"{batch_key}:summary"
    summary = messages.get(summary_id)
    if summary:
        details[summary_id] = {"status": summary.status, "receipt": summary.receipt, "delivered_at": summary.delivered_at}
    return SafeCheck("delivery", "block" if reasons else "pass", reasons, details=details)


def _check_content(post: dict[str, Any]) -> SafeCheck:
    text = _text_for_post(post)
    product = post.get("product", {})
    reasons: list[str] = []
    product_content = evaluate_product_content(product, text)
    if not product_content.passed:
        reasons.extend(product_content.reasons)
    gates = evaluate_content_gates(product, text)
    if not gates.passed:
        reasons.extend(gates.reasons)
    market = evaluate_market_fit(product, text)
    if not market.passed:
        reasons.extend(f"market_fit:{reason}" for reason in market.reasons)
    quality = evaluate_quality_gate(post)
    # Keep the legacy gate as the final aggregate sanity check, but de-duplicate.
    if not quality.passed:
        for reason in quality.reasons:
            if reason.startswith("media_") or reason in {"media_not_downloaded", "missing_local_media"}:
                continue
            legacy_reason = f"quality:{reason}"
            if legacy_reason not in reasons:
                reasons.append(legacy_reason)
            if reason not in reasons:
                reasons.append(reason)
    details = {"content_score": gates.score, "quality_score": quality.score, "caption_score": quality.caption_score}
    return SafeCheck("content", "block" if reasons else "pass", reasons, details=details)


def _check_niche(post: dict[str, Any]) -> SafeCheck:
    product = post.get("product", {})
    niche = evaluate_niche_fit(product)
    details = asdict(niche)
    legacy_broad_affiliate = product.get("media_source") == "product_card_image" and "cellphones" in str(product.get("original_url") or product.get("url") or "").lower()
    if not niche.passed and not legacy_broad_affiliate:
        reasons = [f"niche_score:{niche.score}", *niche.penalties]
        return SafeCheck("niche", "block", reasons, details=details)
    if not niche.passed:
        return SafeCheck("niche", "pass_with_warning", [f"niche_score:{niche.score}"], details=details)
    return SafeCheck("niche", "pass", details=details)


def _check_media(post: dict[str, Any]) -> SafeCheck:
    quality = evaluate_media_quality(post)
    status = "block" if quality.reasons else ("pass_with_warning" if quality.warnings else "pass")
    return SafeCheck("media", status, list(quality.reasons), list(quality.warnings), {"width": quality.width, "height": quality.height})


def _check_offer(post: dict[str, Any]) -> SafeCheck:
    product = post.get("product", {})
    affiliate = check_affiliate_link(post)
    reasons: list[str] = []
    if not affiliate.passed:
        reasons.extend(affiliate.reasons)
    offer_url = product.get("tracking_url") or product.get("affiliate_url") or product.get("url", "")
    offer = validate_offer(offer_url, expected_title=product.get("title", ""), network=False)
    if not offer.passed:
        reasons.extend(f"offer:{reason}" for reason in offer.reasons)
    return SafeCheck("offer", "block" if reasons else "pass", reasons)


def _check_plan(plan_path: str | Path, post_id: str) -> SafeCheck:
    path = Path(plan_path)
    if not path.exists():
        return SafeCheck("facebook_plan", "block", ["plan_file_missing"])
    plan = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in plan.get("plans", []) if item.get("post_id") == post_id]
    if not matches:
        return SafeCheck("facebook_plan", "block", ["plan_post_not_found"])
    item = matches[0]
    if item.get("status") != "publishable_dry_run":
        return SafeCheck("facebook_plan", "block", [f"plan_not_publishable:{item.get('status')}"] , details=item)
    payload = item.get("payload_preview", {})
    # Video uploads use Facebook's `description` field; photo/link plans use
    # `caption`/`message`. All are valid public caption text for publish-safe.
    has_caption = bool(payload.get("caption") or payload.get("message") or payload.get("description"))
    if payload and not has_caption:
        return SafeCheck("facebook_plan", "block", ["plan_missing_caption"], details=item)
    has_media = bool(payload.get("local_image_path") or payload.get("local_video_path") or payload.get("image_url") or payload.get("video_url"))
    has_link = bool(payload.get("link") or payload.get("url"))
    if payload and not (has_media or has_link):
        return SafeCheck("facebook_plan", "block", ["plan_missing_media_or_link_payload"], details=item)
    return SafeCheck("facebook_plan", "pass", details=item)


def validate_publish_safe_v2(*, db_path: str | Path, batch_key: str, post_id: str, plan_path: str | Path, outbox_path: str | Path) -> dict[str, Any]:
    checks: list[SafeCheck] = []
    batch_check, _batch, post = _check_batch_post(db_path, batch_key, post_id)
    checks.append(batch_check)
    checks.append(_check_approval(db_path, batch_key, post_id))
    checks.append(_check_delivery(outbox_path, batch_key, post_id))
    if post:
        checks.extend([_check_offer(post), _check_niche(post), _check_content(post), _check_media(post)])
    checks.append(_check_plan(plan_path, post_id))
    reasons = [reason for check in checks if check.status == "block" for reason in check.reasons]
    warnings = [warning for check in checks for warning in check.warnings]
    return {
        "version": "publish-safe-v2",
        "ok": not reasons,
        "batch_key": batch_key,
        "post_id": post_id,
        "reasons": reasons,
        "warnings": warnings,
        "checks": [asdict(check) for check in checks],
        "approval": next((check.details for check in checks if check.name == "approval"), {}),
        "delivery": next((check.details for check in checks if check.name == "delivery"), {}),
        "plan_item": next((check.details for check in checks if check.name == "facebook_plan"), {}),
    }


def render_publish_safe_v2(result: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot publish-safe v2",
        f"Batch: {result['batch_key']}",
        f"Post: {result['post_id']}",
        f"Status: {'PASS' if result['ok'] else 'BLOCK'}",
        "",
        "Checks:",
    ]
    for check in result.get("checks", []):
        label = check.get("status", "unknown").upper()
        lines.append(f"- {check.get('name')}: {label}")
        for warning in check.get("warnings", [])[:4]:
            lines.append(f"  warning: {warning}")
        for reason in check.get("reasons", [])[:6]:
            lines.append(f"  reason: {reason}")
    if result.get("warnings"):
        lines.append("")
        lines.append("Warnings:")
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    if result.get("reasons"):
        lines.append("")
        lines.append("Block reasons:")
        for reason in result["reasons"]:
            lines.append(f"- {reason}")
    return "\n".join(lines)
