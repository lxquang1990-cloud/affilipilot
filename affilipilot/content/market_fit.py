from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MOTHER_BABY_CORE = {"storage", "feeding", "home_safety", "toy", "baby_care", "mother_care"}
ELECTRONICS = {"electronics", "phone", "smartphone"}
INTERNAL_HASHTAGS = ("#cellphonesaffiliate", "#lazadaaffiliate", "#shopeeaffiliate")

@dataclass
class MarketFitResult:
    passed: bool
    score: int
    audience: str
    angle: str
    reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

def infer_angle(product: dict[str, Any], audience: str = "profit_first") -> str:
    category = str(product.get("category", "")).lower()
    title = str(product.get("title", "")).lower()
    if category in ELECTRONICS or any(term in title for term in ("samsung", "galaxy", "iphone", "xiaomi", "điện thoại")):
        if audience == "mother_baby":
            return "family_camera_memory"
        return "tech_review_deal"
    if category == "feeding":
        return "easier_feeding_routine"
    if category == "storage":
        return "tidier_baby_corner"
    if category == "home_safety":
        return "safer_home_for_mobile_baby"
    if category == "toy":
        return "safe_play_and_discovery"
    return "clear_need_before_buying"

def evaluate_market_fit(product: dict[str, Any], text: str = "", *, audience: str = "profit_first") -> MarketFitResult:
    reasons: list[str] = []
    recommendations: list[str] = []
    score = 100
    category = str(product.get("category", "")).lower()
    title = str(product.get("title", "")).lower()
    lower_text = text.lower()
    price = int(product.get("price_vnd") or product.get("price") or 0)
    angle = infer_angle(product, audience=audience)

    is_electronics = category in ELECTRONICS or any(term in title for term in ("samsung", "galaxy", "iphone", "xiaomi", "điện thoại"))
    if audience in {"profit_first", "diverse", "general", "multi_niche"}:
        if price >= 10_000_000 and not any(term in lower_text for term in ("bảo hành", "trả góp", "chính hãng", "so sánh", "camera", "pin", "bộ nhớ")):
            score -= 20
            reasons.append("high_price_without_purchase_rationale")
            recommendations.append("High-value products need concrete buying rationale: warranty, installment, specs, use-case, or comparison.")
    elif audience == "mother_baby" and category and category not in MOTHER_BABY_CORE and not is_electronics:
        score -= 35
        reasons.append("category_not_core_audience")
        recommendations.append("Move this product to a better-matched page or write a very explicit family use-case.")

    if audience == "mother_baby" and is_electronics:
        benefit_terms = ("camera", "chụp", "ảnh", "video", "pin", "bộ nhớ", "bảo hành", "cấu hình", "màu")
        if not any(term in lower_text for term in benefit_terms):
            score -= 45
            reasons.append("missing_family_electronics_angle")
            recommendations.append("Frame electronics around camera for children, family photos/videos, battery, storage, warranty, or travel.")
        if "đồ tiện dùng trong sinh hoạt hằng ngày với bé" in lower_text:
            score -= 40
            reasons.append("generic_mother_baby_template_mismatch")
            recommendations.append("Do not use generic mother/baby wording for a flagship phone.")
        if price >= 10_000_000 and not any(term in lower_text for term in ("so sánh", "bảo hành", "trả góp", "camera", "pin", "bộ nhớ")):
            score -= 20
            reasons.append("high_price_without_purchase_rationale")

    if "đồ tiện dùng trong sinh hoạt hằng ngày với bé" in lower_text and audience in {"profit_first", "diverse", "general", "multi_niche"}:
        score -= 35
        reasons.append("generic_mother_baby_template_mismatch")
        recommendations.append("Do not reuse mother/baby template copy for diverse profit-first products.")

    if any(tag in lower_text for tag in INTERNAL_HASHTAGS):
        score -= 15
        reasons.append("internal_affiliate_hashtag")
        recommendations.append("Use interest/search hashtags; keep affiliate disclosure in prose, not as primary reach hashtag.")

    if text and len(text.strip()) < 180:
        score -= 15
        reasons.append("content_too_thin_for_market_fit")

    score = max(0, min(100, score))
    passed = score >= 70 and not any(r in reasons for r in ("generic_mother_baby_template_mismatch", "missing_family_electronics_angle"))
    return MarketFitResult(passed=passed, score=score, audience=audience, angle=angle, reasons=reasons, recommendations=recommendations)

def render_market_fit(result: MarketFitResult) -> str:
    lines = [
        "🐌 AffiliPilot market-fit gate",
        f"Audience: {result.audience}",
        f"Angle: {result.angle}",
        f"Score: {result.score}/100",
        f"Status: {'PASS' if result.passed else 'BLOCK'}",
    ]
    if result.reasons:
        lines.append("Reasons:")
        lines.extend(f"- {reason}" for reason in result.reasons)
    if result.recommendations:
        lines.append("Recommendations:")
        lines.extend(f"- {rec}" for rec in result.recommendations)
    return "\n".join(lines)
