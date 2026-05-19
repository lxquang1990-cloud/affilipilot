from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

MOTHER_BABY_CATEGORIES = {"baby_care", "feeding", "toy", "baby_play", "mother_baby", "home_safety", "storage"}
TECH_CATEGORIES = {"electronics", "phone", "smartphone", "laptop", "software"}
PAGE_AUDIENCE_BY_PAGE_NAME = {
    "itnews vietnam": "tech",
    "itnews": "tech",
    "nâng niu trái ngọt tình yêu": "mother_baby",
}

@dataclass
class PageAudienceFitResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)

def configured_page_audience() -> str:
    return os.environ.get("AFFILIPILOT_PAGE_AUDIENCE", "profit_first").strip().lower() or "profit_first"

def audience_from_page_name(page_name: str) -> str:
    normalized = " ".join((page_name or "").strip().lower().split())
    return PAGE_AUDIENCE_BY_PAGE_NAME.get(normalized, "")

def evaluate_page_audience_fit(product: dict[str, Any], *, page_audience: str | None = None, page_name: str = "") -> PageAudienceFitResult:
    audience = (page_audience or audience_from_page_name(page_name) or configured_page_audience()).strip().lower()
    category = str(product.get("category", "unknown")).strip().lower()
    title = str(product.get("title", "")).lower()
    reasons: list[str] = []

    if audience in {"profit_first", "diverse", "general", "multi_niche"}:
        # Product breadth is allowed; downstream quality/compliance gates still block bad copy/offers.
        pass
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
