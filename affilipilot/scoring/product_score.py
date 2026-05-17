from __future__ import annotations

from affilipilot.models import ProductCandidate

SAFE_CATEGORY_BONUS = {
    "storage": 20,
    "feeding": 15,
    "toy": 12,
    "stroller_accessory": 12,
    "baby_room": 10,
    "home_safety": 16,
    "unknown": 0,
}

RISKY_CATEGORY_PENALTY = {
    "milk": 60,
    "formula": 60,
    "medicine": 80,
    "supplement": 70,
    "vitamin": 70,
    "medical": 80,
    "weight_loss": 70,
}


def score_product(product: ProductCandidate) -> dict[str, int | list[str]]:
    score = 40
    reasons: list[str] = []
    category = product.category.lower().strip() or "unknown"

    bonus = SAFE_CATEGORY_BONUS.get(category, 0)
    if bonus:
        score += bonus
        reasons.append(f"safe_category_bonus:{category}+{bonus}")

    penalty = RISKY_CATEGORY_PENALTY.get(category, 0)
    if penalty:
        score -= penalty
        reasons.append(f"risky_category_penalty:{category}-{penalty}")

    if product.price_vnd:
        if 50_000 <= product.price_vnd <= 350_000:
            score += 15
            reasons.append("price_fit+15")
        elif product.price_vnd > 800_000:
            score -= 10
            reasons.append("high_price-10")

    if product.commission_rate:
        if product.commission_rate >= 0.08:
            score += 12
            reasons.append("commission_good+12")
        elif product.commission_rate >= 0.04:
            score += 6
            reasons.append("commission_ok+6")

    text = f"{product.title} {product.notes}".lower()
    if any(word in text for word in ["gọn", "tiện", "sắp xếp", "ăn dặm", "an toàn nhà", "xe đẩy"]):
        score += 10
        reasons.append("content_angle+10")

    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons}
