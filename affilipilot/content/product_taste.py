from __future__ import annotations

from dataclasses import dataclass, field

from affilipilot.models import ProductCandidate

PREFERRED_CATEGORIES = {
    "home_appliance": 22,
    "home_living": 18,
    "electronics": 18,
    "phone_accessory": 14,
    "office_productivity": 14,
    "baby_care": 12,
    "mother_baby": 10,
    "toy": 10,
    "storage": 12,
}

LOW_FIT_CATEGORIES = {
    "bike_part": 28,
    "bike_accessory": 20,
    "auto_part": 28,
    "replacement_part": 24,
    "unknown": 18,
    "beauty": 8,
}

BLOCKED_TEST_URL_TERMS = ("example.com", "localhost", "127.0.0.1")

HARD_BLOCK_TITLE_TERMS = (
    "điều khiển tivi",
    "điều khiển tv",
    "mô hình",
    "figure",
    "anime",
    "demon slayer",
    "kimetsu",
    "ben10",
    "mc queen",
    "tàu thomas",
    "shop gửi ngẫu nhiên",
)

LOW_FIT_TITLE_TERMS = (
    "shimano",
    "groupset",
    "derailleur",
    "cassette",
    "xích xe đạp",
    "lip xe đạp",
    "củ đề",
    "sang đề",
    "phụ tùng",
    "linh kiện thay thế",
    "remote",
    "bo mạch",
    "mainboard",
    "adapter thay thế",
    "nhập mã",
)

BROAD_USE_TERMS = (
    "gia đình",
    "nhà",
    "bếp",
    "vệ sinh",
    "lưu trữ",
    "sắp xếp",
    "học tập",
    "làm việc",
    "du lịch",
    "tiện lợi",
    "bảo hành",
    "chính hãng",
    "trẻ em",
    "đồ chơi",
)

@dataclass
class ProductTasteResult:
    score: int
    passed: bool
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)


def evaluate_product_taste(product: ProductCandidate) -> ProductTasteResult:
    category = (product.category or "unknown").strip().lower() or "unknown"
    text = f"{product.title} {product.category} {product.notes}".lower()
    score = 50
    reasons: list[str] = []
    penalties: list[str] = []

    preferred = PREFERRED_CATEGORIES.get(category, 0)
    if preferred:
        score += preferred
        reasons.append(f"preferred_category:{category}+{preferred}")

    low_fit = LOW_FIT_CATEGORIES.get(category, 0)
    if low_fit:
        score -= low_fit
        penalties.append(f"low_fit_category:{category}-{low_fit}")

    if any(term in (product.url or "").lower() for term in BLOCKED_TEST_URL_TERMS):
        score -= 60
        penalties.append("test_or_placeholder_url-60")

    hard_blocked = False
    if any(term in text for term in HARD_BLOCK_TITLE_TERMS):
        score -= 60
        hard_blocked = True
        penalties.append("hard_block_low_approval_fit-60")

    if any(term in text for term in LOW_FIT_TITLE_TERMS):
        score -= 25
        penalties.append("niche_or_replacement_part-25")

    broad_terms = [term for term in BROAD_USE_TERMS if term in text]
    if len(broad_terms) >= 2:
        score += 16
        reasons.append("broad_household_use_case+16")
    elif broad_terms:
        score += 8
        reasons.append("some_use_case_clarity+8")

    if product.price_vnd:
        if 80_000 <= product.price_vnd <= 1_200_000:
            score += 10
            reasons.append("comfortable_approval_price_band+10")
        elif product.price_vnd > 5_000_000:
            score -= 10
            penalties.append("high_ticket_needs_manual_rationale-10")

    if not (product.image_url or product.image_urls or product.image_path):
        score -= 15
        penalties.append("weak_visual_for_facebook-15")

    if len(product.title.split()) > 28:
        score -= 8
        penalties.append("marketplace_title_too_noisy-8")

    score = max(0, min(100, score))
    return ProductTasteResult(score=score, passed=(score >= 50 and not hard_blocked), reasons=reasons, penalties=penalties)
