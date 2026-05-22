from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

POSITIONING = "Mua sắm thông minh — món nhỏ, tiện, đáng tiền, dễ kiểm chứng."

CORE_CATEGORIES = {
    "home_consumable": 28,
    "home_organization": 28,
    "kitchen": 26,
    "cleaning": 26,
    "home_appliance": 24,
    "home_living": 24,
    "storage": 24,
    "office_productivity": 16,
}

CONDITIONAL_CATEGORIES = {
    "electronics_small": 16,
    "phone_accessory": 14,
    "personal_care": 10,
    "baby_care": 8,
    "mother_baby": 8,
    "feeding": 8,
    "electronics": 8,
    "toy": 6,
    "beauty": 4,
    "unknown": 0,
}

BLOCKED_CATEGORIES = {
    "medicine",
    "medical",
    "supplement",
    "vitamin",
    "weight_loss",
    "adult",
    "gambling",
    "bike_accessory",
    "bike_part",
    "auto_part",
    "book",
}

CORE_USE_TERMS = (
    "gia đình", "nhà", "bếp", "nhà bếp", "phòng tắm", "nhà tắm", "vệ sinh", "lau", "khăn giấy", "giấy ăn", "nước giặt",
    "hút bụi", "máy hút bụi", "máy xay", "nồi chiên", "bình giữ nhiệt", "hộp cơm", "hộp đựng",
    "kệ", "giá treo", "sắp xếp", "lưu trữ", "gọn", "tiện", "ổ cắm", "đèn ngủ", "đèn bàn",
    "bảo quản", "làm bánh", "du lịch", "văn phòng", "làm việc", "học tập",
)

VALUE_PROOF_TERMS = (
    "bảo hành", "chính hãng", "công suất", "dung tích", "kích thước", "combo", "tiết kiệm", "giảm", "voucher", "brand bonus", "commission",
    "sale", "chịu lực", "chống nước", "an toàn", "inox", "silicone", "pin", "điện áp", "công suất",
)

LOW_FIT_TERMS = (
    "xe đạp", "ghi đông", "shimano", "phụ tùng", "linh kiện", "mô hình", "figure", "anime", "truyện tranh",
    "tiểu thuyết", "ngoại ngữ", "remote", "điều khiển", "ngẫu nhiên", "quần áo", "thời trang", "áo chống nắng",
    "nha khoa", "khám răng", "nha sĩ", "vitamin", "dha", "canxi", "giảm cân", "sinh lý",
)

@dataclass
class NicheFitResult:
    passed: bool
    score: int
    positioning: str = POSITIONING
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    category: str = "unknown"


def _product_text(product: Any) -> str:
    if isinstance(product, dict):
        return f"{product.get('title', '')} {product.get('category', '')} {product.get('notes', '')}".lower()
    return f"{getattr(product, 'title', '')} {getattr(product, 'category', '')} {getattr(product, 'notes', '')}".lower()


def _category(product: Any) -> str:
    if isinstance(product, dict):
        return str(product.get("category") or "unknown").strip().lower() or "unknown"
    return str(getattr(product, "category", "unknown") or "unknown").strip().lower() or "unknown"


def _price(product: Any) -> int:
    if isinstance(product, dict):
        return int(product.get("price_vnd") or product.get("price") or 0)
    return int(getattr(product, "price_vnd", 0) or 0)


def _has_media(product: Any) -> bool:
    if isinstance(product, dict):
        return bool(product.get("image_url") or product.get("image_urls") or product.get("image_path") or product.get("media"))
    return bool(getattr(product, "image_url", "") or getattr(product, "image_urls", []) or getattr(product, "image_path", ""))


def evaluate_niche_fit(product: Any, *, min_score: int = 58) -> NicheFitResult:
    category = _category(product)
    text = _product_text(product)
    price = _price(product)
    score = 45
    reasons: list[str] = []
    penalties: list[str] = []

    if category in CORE_CATEGORIES:
        bonus = CORE_CATEGORIES[category]
        score += bonus
        reasons.append(f"core_smart_shopping_category:{category}+{bonus}")
    elif category in CONDITIONAL_CATEGORIES:
        bonus = CONDITIONAL_CATEGORIES[category]
        score += bonus
        reasons.append(f"conditional_smart_shopping_category:{category}+{bonus}")
    elif category in BLOCKED_CATEGORIES:
        score -= 70
        penalties.append(f"blocked_smart_shopping_category:{category}-70")
    else:
        score -= 10
        penalties.append(f"unclear_smart_shopping_category:{category}-10")

    core_hits = [term for term in CORE_USE_TERMS if term in text]
    if len(core_hits) >= 2:
        score += 22
        reasons.append("clear_household_use_case+22")
    elif core_hits:
        score += 12
        reasons.append("some_household_use_case+12")
    else:
        score -= 16
        penalties.append("missing_household_use_case-16")

    proof_hits = [term for term in VALUE_PROOF_TERMS if term in text]
    if len(proof_hits) >= 2:
        score += 14
        reasons.append("concrete_value_proof+14")
    elif proof_hits:
        score += 7
        reasons.append("some_value_proof+7")
    else:
        score -= 8
        penalties.append("weak_value_proof-8")

    low_hits = [term for term in LOW_FIT_TERMS if term in text]
    if low_hits:
        score -= 45
        penalties.append("low_niche_fit_terms-45")

    if price:
        if 80_000 <= price <= 1_500_000:
            score += 10
            reasons.append("niche_price_band+10")
        elif price < 40_000:
            score -= 8
            penalties.append("too_low_ticket_for_effort-8")
        elif price > 5_000_000:
            score -= 8
            penalties.append("high_ticket_needs_manual_review-8")

    if _has_media(product):
        score += 5
        reasons.append("has_media+5")
    else:
        score -= 10
        penalties.append("missing_media-10")

    score = max(0, min(100, score))
    hard_blocked = any(p.startswith("blocked_smart_shopping_category") or p.startswith("blocked_niche_category") or p.startswith("low_niche_fit_terms") for p in penalties)
    return NicheFitResult(passed=score >= min_score and not hard_blocked, score=score, reasons=reasons, penalties=penalties, category=category)
