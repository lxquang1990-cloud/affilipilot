from __future__ import annotations

from urllib.parse import urlparse

from affilipilot.models import ProductCandidate

PROFIT_CATEGORY_BONUS = {
    "electronics": 12,
    "phone": 12,
    "smartphone": 12,
    "laptop": 10,
    "computer": 10,
    "phone_accessory": 8,
    "home_appliance": 12,
    "home_living": 9,
    "beauty": 6,
    "mother_baby": 6,
    "baby_care": 6,
    "toy": 5,
    "storage": 7,
    "feeding": 5,
    "office_productivity": 8,
    "bike_accessory": 4,
    "unknown": -6,
}

RISKY_CATEGORY_PENALTY = {
    "medicine": 90,
    "supplement": 80,
    "vitamin": 80,
    "medical": 90,
    "health_and_beauty": 45,
    "weight_loss": 80,
    "adult": 95,
    "gambling": 100,
}

TRUSTED_MERCHANT_HINTS = {
    "lazada_kol": 10,
    "lazada": 8,
    "shopee": 8,
    "tiki": 8,
    "cellphones": 10,
    "fpt": 10,
    "dienmayxanh": 10,
    "thegioididong": 10,
}

SPAM_TITLE_TERMS = ("siêu rẻ", "hot hit", "cam kết khỏi", "trị dứt điểm", "tăng đề kháng", "giảm cân", "sinh lý")
FACT_TERMS = ("bảo hành", "chính hãng", "discount_rate=", "discount_vnd=", "giảm", "sale", "combo", "dung tích", "kích thước", "công suất", "pin", "bộ nhớ")
COMMERCIAL_TERMS = ("giảm", "sale", "deal", "bảo hành", "chính hãng", "trả góp", "tiện", "gọn", "combo")


def _discount_rate(product: ProductCandidate) -> float | None:
    text = f"{product.notes}".lower()
    if "discount_rate=" not in text:
        return None
    try:
        raw = text.split("discount_rate=", 1)[1].split(";", 1)[0].split(" ", 1)[0]
        rate = float(raw)
        return rate / 100 if rate > 1 else rate
    except ValueError:
        return None


def _merchant_score(product: ProductCandidate) -> tuple[int, str]:
    text = f"{product.notes} {product.url} {product.affiliate_url}".lower()
    host = urlparse(product.url).netloc.lower()
    for hint, score in TRUSTED_MERCHANT_HINTS.items():
        if hint in text or hint in host:
            return score, f"trusted_merchant:{hint}+{score}"
    return 0, ""


def _content_fact_score(product: ProductCandidate) -> tuple[int, list[str]]:
    text = f"{product.title} {product.category} {product.notes}".lower()
    found = [term for term in FACT_TERMS if term in text]
    reasons: list[str] = []
    score = 0
    if len(found) >= 2:
        score += 10
        reasons.append("enough_facts_for_caption+10")
    elif found:
        score += 5
        reasons.append("some_facts_for_caption+5")
    if len(product.title) > 120:
        score -= 8
        reasons.append("title_too_long_marketplace_spam-8")
    if any(term in text for term in SPAM_TITLE_TERMS):
        score -= 18
        reasons.append("spam_or_claimy_title-18")
    return score, reasons


def score_product(product: ProductCandidate) -> dict[str, int | list[str]]:
    score = 35
    reasons: list[str] = []
    category = product.category.lower().strip() or "unknown"

    bonus = PROFIT_CATEGORY_BONUS.get(category, 0)
    if bonus:
        score += bonus
        reasons.append(f"profit_category_bonus:{category}+{bonus}")

    penalty = RISKY_CATEGORY_PENALTY.get(category, 0)
    if penalty:
        score -= penalty
        reasons.append(f"risky_category_penalty:{category}-{penalty}")

    if product.price_vnd:
        if 100_000 <= product.price_vnd <= 1_500_000:
            score += 14
            reasons.append("profitable_price_band+14")
        elif 1_500_000 < product.price_vnd <= 8_000_000:
            score += 9
            reasons.append("considered_high_ticket+9")
        elif product.price_vnd > 8_000_000:
            score += 2
            reasons.append("high_ticket_needs_strong_rationale+2")
        elif product.price_vnd < 30_000:
            score -= 12
            reasons.append("low_ticket_item-12")

    if product.commission_rate:
        if product.commission_rate >= 0.10:
            score += 22
            reasons.append("commission_excellent+22")
        elif product.commission_rate >= 0.06:
            score += 14
            reasons.append("commission_good+14")
        elif product.commission_rate >= 0.03:
            score += 7
            reasons.append("commission_ok+7")

    discount = _discount_rate(product)
    if discount is not None:
        if discount >= 0.40:
            score += 16
            reasons.append("discount_excellent+16")
        elif discount >= 0.20:
            score += 10
            reasons.append("discount_strong+10")
        elif discount >= 0.10:
            score += 5
            reasons.append("discount_ok+5")

    merchant_score, merchant_reason = _merchant_score(product)
    if merchant_score:
        score += merchant_score
        reasons.append(merchant_reason)

    text = f"{product.title} {product.notes}".lower()
    if any(word in text for word in COMMERCIAL_TERMS):
        score += 8
        reasons.append("commercial_angle+8")

    fact_score, fact_reasons = _content_fact_score(product)
    score += fact_score
    reasons.extend(fact_reasons)

    if product.image_url or product.image_urls or product.image_path:
        score += 5
        reasons.append("has_product_media+5")
    else:
        score -= 10
        reasons.append("missing_product_media-10")

    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons}
