from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from affilipilot.content.niche_policy import evaluate_niche_fit
from affilipilot.media_quality import evaluate_media_quality
from affilipilot.models import ContentDraft
from affilipilot.scoring.product_score import score_product

@dataclass
class ApprovalContext:
    money_score: int
    niche_score: int
    niche_passed: bool
    content_score: float = 0.0
    content_passed: bool = False
    media_status: str = "UNKNOWN"
    media_warnings: list[str] = field(default_factory=list)
    media_reasons: list[str] = field(default_factory=list)
    top_reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    caption_source: str = "unknown"
    ai_reason: str = ""
    ai_provider: str = ""
    caption_quality_passed: bool = False
    caption_quality_score: int = 0
    caption_quality_source: str = ""
    caption_quality_reasons: list[str] = field(default_factory=list)
    publish_type: str = "photo_post"
    metrics_profile: str = "feed_post"


def _top_score_reasons(reasons: list[str], limit: int = 4) -> list[str]:
    preferred_prefixes = (
        "niche_fit:",
        "core_niche_category:",
        "clear_household_use_case",
        "concrete_value_proof",
        "trusted_merchant:",
        "profitable_price_band",
        "discount_",
        "has_product_media",
    )
    picked = [r for r in reasons if any(str(r).startswith(prefix) for prefix in preferred_prefixes)]
    if len(picked) < limit:
        picked.extend(r for r in reasons if r not in picked)
    return [str(r) for r in picked[:limit]]


def build_approval_context(draft: ContentDraft, *, post: dict[str, Any] | None = None, content_gate: dict[str, Any] | None = None) -> ApprovalContext:
    score_info = score_product(draft.product)
    niche = evaluate_niche_fit(draft.product)
    gate = content_gate or {}
    media_warnings: list[str] = []
    media_reasons: list[str] = []
    media_status = "UNKNOWN"
    if post:
        media_result = evaluate_media_quality(post)
        media_warnings = list(media_result.warnings)
        media_reasons = list(media_result.reasons)
        media_status = "PASS_WITH_WARNING" if media_result.passed and media_result.warnings else ("PASS" if media_result.passed else "BLOCK")
    blockers: list[str] = []
    if not niche.passed:
        blockers.append(f"niche_score:{niche.score}")
    if gate and not gate.get("passed", False):
        blockers.extend(str(reason) for reason in gate.get("reasons", [])[:4])
    if media_reasons:
        blockers.extend(media_reasons[:4])
    return ApprovalContext(
        money_score=int(score_info["score"]),
        niche_score=niche.score,
        niche_passed=niche.passed,
        content_score=float(gate.get("score", 0.0) or 0.0),
        content_passed=bool(gate.get("passed", False)) if gate else False,
        media_status=media_status,
        media_warnings=media_warnings,
        media_reasons=media_reasons,
        top_reasons=_top_score_reasons(list(score_info.get("reasons", []))),
        blockers=blockers,
        caption_source=str(gate.get("caption_source") or draft.metadata.get("caption_source") or "unknown"),
        ai_reason=str(gate.get("ai_reason") or draft.metadata.get("ai_reason") or ""),
        ai_provider=str(gate.get("ai_provider") or draft.metadata.get("ai_provider") or ""),
        caption_quality_passed=bool(gate.get("caption_quality_passed", draft.metadata.get("caption_quality_passed", False))),
        caption_quality_score=int(gate.get("caption_quality_score", draft.metadata.get("caption_quality_score", 0)) or 0),
        caption_quality_source=str(gate.get("caption_quality_source") or draft.metadata.get("caption_quality_source") or ""),
        caption_quality_reasons=[str(item) for item in (gate.get("caption_quality_reasons") or draft.metadata.get("caption_quality_reasons") or [])],
        publish_type=str(gate.get("publish_type") or draft.metadata.get("publish_type") or "photo_post"),
        metrics_profile=str(gate.get("metrics_profile") or draft.metadata.get("metrics_profile") or "feed_post"),
    )
