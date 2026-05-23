from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

MOTHER_BABY_CATEGORIES = {"baby_care", "feeding", "toy", "baby_play", "mother_baby", "home_safety"}
SMART_SHOPPING_CATEGORIES = {
    "home_consumable", "home_organization", "kitchen", "cleaning", "home_appliance", "home_living",
    "storage", "office_productivity", "electronics_small", "phone_accessory", "personal_care",
    "baby_care", "feeding", "toy", "baby_play", "mother_baby",
}
TECH_CATEGORIES = {"electronics", "phone", "smartphone", "laptop", "software"}
MOTHER_BABY_PAGE_NAMES = {
    "nâng niu trái ngọt tình yêu",
}
PAGE_AUDIENCE_BY_PAGE_NAME = {
    "itnews vietnam": "tech",
    "itnews": "tech",
}

@dataclass
class PageAudienceFitResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)

def configured_page_audience() -> str:
    return os.environ.get("AFFILIPILOT_PAGE_AUDIENCE", os.environ.get("AFFILIPILOT_PAGE_PROFILE", "multi_niche")).strip().lower() or "multi_niche"

def audience_from_page_name(page_name: str) -> str:
    """Map explicit page names only when the operator has configured a page.

    The default AffiliPilot path must stay money-first / multi-niche. Legacy
    mother/baby behavior is enabled only for explicit page/campaign config, not
    because an old page name lives in memory.
    """
    normalized = " ".join((page_name or "").strip().lower().split())
    if not normalized:
        return ""
    if normalized in MOTHER_BABY_PAGE_NAMES:
        return "mother_baby"
    return PAGE_AUDIENCE_BY_PAGE_NAME.get(normalized, "")

def evaluate_page_audience_fit(product: dict[str, Any], *, page_audience: str | None = None, page_name: str = "") -> PageAudienceFitResult:
    audience = (page_audience or audience_from_page_name(page_name) or configured_page_audience()).strip().lower()
    category = str(product.get("category", "unknown")).strip().lower()
    title = str(product.get("title", "")).lower()
    reasons: list[str] = []

    if audience in {"smart_shopping", "mua_sam_thong_minh", "profit_first", "diverse", "general", "multi_niche"}:
        if category not in SMART_SHOPPING_CATEGORIES and category not in {"unknown", "electronics", "phone", "smartphone", "laptop", "computer"}:
            reasons.append("page_audience_smart_shopping_product_low_fit")
    elif audience in {"mother_baby", "mom_baby", "me_va_be"}:
        if category in TECH_CATEGORIES:
            reasons.append("page_audience_mother_baby_product_tech")
        elif category not in MOTHER_BABY_CATEGORIES and not any(term in title for term in ("bé", "me", "mẹ", "baby", "trẻ em", "đồ chơi", "khăn sữa")):
            reasons.append("page_audience_mother_baby_product_unknown")
    elif audience in {"tech", "it", "itnews", "technology"}:
        if category in MOTHER_BABY_CATEGORIES:
            reasons.append("page_audience_tech_product_mother_baby")
    elif not audience:
        reasons.append("missing_page_audience")

    return PageAudienceFitResult(passed=not reasons, reasons=reasons)
