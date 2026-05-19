from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

GENERIC_BAD_PHRASES = (
    "đừng chỉ nhìn giá",
    "nhu cầu, ngân sách và bối cảnh",
    "sản phẩm này phù hợp hơn khi nhu cầu",
    "lý do mình cần sản phẩm này",
    "tùy nhu cầu",
    "tùy ngân sách",
)
INTERNAL_HASHTAGS = ("#tiepthilienket", "#cellphonesaffiliate", "#lazadaaffiliate", "#shopeeaffiliate")
TECH_TERMS = ("cấu hình", "ram", "chip", "camera", "pin", "bảo hành")
BABY_CARE_TERMS = ("mềm", "cotton", "muslin", "sợi tre", "thấm", "bụi vải", "giặt", "da bé", "lau", "sơ sinh")
HOME_APPLIANCE_TERMS = ("công suất", "kích thước", "bảo hành", "đổi trả", "review", "đánh giá", "sinh hoạt", "trong nhà")
ELECTRONICS_TERMS = ("pin", "bộ nhớ", "cấu hình", "bảo hành", "camera", "dung lượng", "làm việc", "học tập")
RISKY_CLAIM_TERMS = ("điều trị", "chữa", "trị dứt điểm", "tăng đề kháng", "giảm cân", "đường huyết", "tiểu đường", "tăng chiều cao")

@dataclass
class ProductContentResult:
    passed: bool
    score: int
    category: str
    reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def _product_text(product: dict[str, Any], text: str) -> str:
    return " ".join([str(product.get("title", "")), str(product.get("category", "")), text]).lower()


def evaluate_product_content(product: dict[str, Any], text: str) -> ProductContentResult:
    category = str(product.get("category", "")).lower()
    title = str(product.get("title", "")).lower()
    lower = text.lower()
    combined = _product_text(product, text)
    reasons: list[str] = []
    recommendations: list[str] = []
    score = 100

    for phrase in GENERIC_BAD_PHRASES:
        if phrase in lower:
            reasons.append("generic_ai_affiliate_copy")
            recommendations.append("Rewrite with product-specific use case and concrete benefit.")
            score -= 35
            break

    if any(tag in lower for tag in INTERNAL_HASHTAGS):
        reasons.append("internal_affiliate_hashtag")
        recommendations.append("Use audience/search hashtags; keep affiliate disclosure in prose.")
        score -= 25

    if category == "baby_care" or any(term in title for term in ("khăn", "khan", "sữa", "sua")):
        if not any(term in combined for term in BABY_CARE_TERMS):
            reasons.append("missing_product_specific_baby_care_benefit")
            recommendations.append("Mention softness, material, absorbency, washing, low lint, or baby-skin fit.")
            score -= 35
        wrong_terms = [term for term in TECH_TERMS if term in lower and term not in {"bảo hành"}]
        if wrong_terms:
            reasons.append("wrong_category_language:baby_care_tech_terms")
            recommendations.append("Remove tech-shopping words like cấu hình/camera/pin from baby-care captions.")
            score -= 40
        if "khăn" in title and not any(term in lower for term in ("lau", "mềm", "giặt", "thấm", "da bé", "bụi vải")):
            reasons.append("missing_khan_sua_usage_context")
            recommendations.append("Explain concrete usage: lau mặt, lau sữa, lót vai, mang ra ngoài, giặt xoay vòng.")
            score -= 25

    if category in {"electronics", "phone", "smartphone", "laptop", "computer", "phone_accessory", "office_productivity"} or any(term in title for term in ("điện thoại", "iphone", "samsung", "galaxy", "xiaomi")):
        if not any(term in lower for term in ELECTRONICS_TERMS):
            reasons.append("missing_electronics_purchase_rationale")
            recommendations.append("Mention camera, battery, storage, configuration, warranty, work/study, or practical usage rationale.")
            score -= 35

    if category in {"home_appliance", "home_living", "storage"}:
        if not any(term in lower for term in HOME_APPLIANCE_TERMS):
            reasons.append("missing_home_appliance_purchase_rationale")
            recommendations.append("Mention size, power/capacity, warranty, home use case, review photos, or return policy.")
            score -= 30

    if any(term in combined for term in RISKY_CLAIM_TERMS):
        reasons.append("risky_health_or_body_claim")
        recommendations.append("Remove medical/health/body-change claims from affiliate copy.")
        score -= 60

    if len(lower.strip()) < 180:
        reasons.append("content_too_thin")
        recommendations.append("Add a concrete use case, buying checklist, and clear CTA.")
        score -= 15

    score = max(0, min(100, score))
    hard_blocks = {
        "generic_ai_affiliate_copy",
        "internal_affiliate_hashtag",
        "wrong_category_language:baby_care_tech_terms",
        "risky_health_or_body_claim",
    }
    passed = score >= 75 and not any(reason in hard_blocks for reason in reasons)
    return ProductContentResult(passed=passed, score=score, category=category, reasons=reasons, recommendations=recommendations)
