from __future__ import annotations

import re
from dataclasses import dataclass, field

from affilipilot.models import ProductCandidate

BLOCKED_CATEGORY_TOKENS = {
    "medicine",
    "supplement",
    "vitamin",
    "medical",
    "health_and_beauty",
    "weight_loss",
    "adult",
    "gambling",
}

BLOCKED_TEXT_PATTERNS = {
    "medicine_claim": ("thuốc", "dược", "điều trị", "trị ", "chữa", "kháng sinh"),
    "supplement_claim": ("vitamin", "k2d3", "omega", "dha", "canxi", "collagen", "tăng đề kháng", "sức đề kháng", "bổ sung"),
    "medical_device": ("đường huyết", "tiểu đường", "huyết áp", "nhiệt kế", "máy đo", "test nhanh", "hồng ngoại", "dầu cù là", "giảm đau", "khám răng", "nha sĩ", "nha khoa", "bác sĩ", "bac sĩ"),
    "weight_loss_claim": ("giảm cân", "đốt mỡ", "tan mỡ", "eo thon"),
    "adult_or_gambling": ("sinh lý", "bao cao su", "quần lót", "đồ lót", "nội y", "casino", "cá cược", "betting"),
    "child_growth_claim": ("tăng chiều cao", "phát triển trí não", "thông minh hơn", "ăn ngon", "ngủ ngon"),
    "sensitive_pregnancy_or_bodycare": ("bầu", "sau sinh", "dầu lăn", "dầu xoa", "nhân sâm", "green herb", "cù là"),
}

SAFE_CATEGORY_ALLOWLIST = {
    "home_appliance",
    "electronics",
    "phone",
    "smartphone",
    "laptop",
    "computer",
    "phone_accessory",
    "home_living",
    "home_consumable",
    "home_organization",
    "kitchen",
    "cleaning",
    "electronics_small",
    "personal_care",
    "mother_baby",
    "baby_care",
    "toy",
    "storage",
    "feeding",
    "beauty",
    "office_productivity",
    "unknown",
}

@dataclass
class EarlyFilterResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    normalized_category: str = "unknown"


def normalize_category(product: ProductCandidate) -> str:
    raw = f"{product.category} {product.title} {product.notes}".lower()
    category = (product.category or "unknown").strip().lower().replace(" ", "_") or "unknown"
    if any(token in category for token in ("laptop", "computer", "máy_tính", "may_tinh")):
        return "laptop"
    if any(token in category for token in ("phone", "điện_thoại", "dien_thoai", "smartphone")):
        return "phone"
    if any(token in category for token in ("appliance", "gia_dung", "gia-dung")):
        return "home_appliance"
    if any(term in raw for term in ("máy hút bụi", "hút bụi", "máy xay", "nồi chiên", "máy ép", "bếp điện", "bếp từ", "máy lọc", "quạt điện", "quạt tích điện")):
        return "home_appliance"
    if any(term in raw for term in ("khăn giấy", "giấy ăn", "giấy rút", "nước giặt", "nước rửa chén", "khăn lau", "đồ dùng tiêu hao")):
        return "home_consumable"
    if any(term in raw for term in ("làm bánh", "bánh cuốn", "hộp cơm", "bình giữ nhiệt", "nắp nồi", "bảo quản thực phẩm", "khăn lau bếp", "nhà bếp", "khuôn làm bánh")):
        return "kitchen"
    if any(term in raw for term in ("hộp đựng", "kệ để", "giá treo", "tủ đựng", "lưu trữ", "sắp xếp", "gầm giường")):
        return "home_organization"
    if any(token in category for token in ("home", "house", "nha_cua", "đời_sống", "doi_song")):
        return "home_living"
    if any(token in category for token in ("baby", "mother", "me_be", "mẹ_bé", "me-va-be")):
        return "mother_baby"
    if any(token in category for token in ("health", "medical", "medicine", "vitamin", "supplement")):
        return "medical"
    if "nhiệt kế" in raw or "duong huyet" in raw or "đường huyết" in raw:
        return "medical"
    if any(term in raw for term in ("xe đạp", "xe dap", "ghi đông", "ghi dong", "sừng trâu", "sung trau", "shimano", "xích sên", "củ đề", "sang đề")):
        return "bike_accessory"
    if any(term in raw for term in ("điều khiển tivi", "remote", "smart tv", "tivi", "lcd", "led")):
        return "electronics"
    if any(term in raw for term in ("sách ", "sach ", "book", "tiếng anh", "ngoại ngữ", "tiểu thuyết", "truyện tranh")):
        return "book"
    if any(term in raw for term in ("đồ chơi", "toy", "mc queen", "tàu thomas")):
        return "toy"
    return category if category in SAFE_CATEGORY_ALLOWLIST else category


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def evaluate_early_product_filter(product: ProductCandidate) -> EarlyFilterResult:
    normalized = normalize_category(product)
    text = f"{product.title} {product.category} {product.notes} {product.url}".lower()
    text = re.sub(r"\s+", " ", text)
    reasons: list[str] = []
    flags: list[str] = []

    if normalized in BLOCKED_CATEGORY_TOKENS or any(token in normalized for token in BLOCKED_CATEGORY_TOKENS):
        reasons.append(f"blocked_category:{normalized}")
        flags.append("unsafe_category")

    for flag, patterns in BLOCKED_TEXT_PATTERNS.items():
        if _contains_any(text, patterns):
            reasons.append(flag)
            flags.append(flag)

    if not product.url.startswith(("http://", "https://")):
        reasons.append("invalid_product_url")
        flags.append("invalid_url")

    if not product.title.strip():
        reasons.append("missing_title")
        flags.append("insufficient_product_data")

    if product.price_vnd is not None and product.price_vnd < 1_000:
        reasons.append("invalid_or_fake_price:<1000vnd")
        flags.append("invalid_price")

    return EarlyFilterResult(passed=not reasons, reasons=reasons, risk_flags=sorted(set(flags)), normalized_category=normalized)
