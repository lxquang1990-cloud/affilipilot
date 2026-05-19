from __future__ import annotations

from collections import defaultdict
from typing import Any

CATEGORY_QUOTA = {
    "home_appliance": 2,
    "home_living": 2,
    "storage": 1,
    "electronics": 1,
    "phone_accessory": 1,
    "office_productivity": 1,
    "baby_care": 1,
    "mother_baby": 1,
    "toy": 1,
}

PREFERRED_ORDER = (
    "home_appliance",
    "home_living",
    "storage",
    "office_productivity",
    "electronics",
    "phone_accessory",
    "baby_care",
    "mother_baby",
    "toy",
)

LOW_FIT_CATEGORY_CAP = {
    "unknown": 0,
    "bike_accessory": 0,
    "bike_part": 0,
    "replacement_part": 0,
    "beauty": 1,
}

MIN_SCORE_FOR_LOW_FIT_EXCEPTION = 90


def _category(item: dict[str, Any]) -> str:
    product = item.get("product")
    return str(getattr(product, "category", "") or "unknown").lower()


def _rank_key(item: dict[str, Any]) -> tuple[int, int]:
    category = _category(item)
    preferred = 1 if category in PREFERRED_ORDER else 0
    return (preferred, int(item.get("score", 0)))


def select_portfolio(ranked: list[dict[str, Any]], *, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select a category-diverse approval portfolio.

    Returns (selected, blocked). Items should already be sorted by score desc.
    Low-fit categories are blocked unless explicitly allowed by cap and high score.
    """
    selected: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)

    # First pass: preferred categories in explicit portfolio order.
    for category in PREFERRED_ORDER:
        quota = CATEGORY_QUOTA.get(category, 1)
        for item in ranked:
            if len(selected) >= limit:
                break
            if item in selected or _category(item) != category:
                continue
            if counts[category] >= quota:
                continue
            selected.append(item)
            counts[category] += 1
        if len(selected) >= limit:
            break

    # Second pass: remaining high-score non-low-fit items.
    for item in sorted(ranked, key=_rank_key, reverse=True):
        if len(selected) >= limit:
            break
        if item in selected:
            continue
        category = _category(item)
        low_cap = LOW_FIT_CATEGORY_CAP.get(category)
        if low_cap is not None:
            if counts[category] >= low_cap or int(item.get("score", 0)) < MIN_SCORE_FOR_LOW_FIT_EXCEPTION:
                blocked.append({**item, "portfolio_block_reason": f"low_fit_category_cap:{category}"})
                continue
        selected.append(item)
        counts[category] += 1

    selected_ids = {id(item) for item in selected}
    blocked_ids = {id(item) for item in blocked}
    for item in ranked:
        if id(item) not in selected_ids and id(item) not in blocked_ids:
            category = _category(item)
            reason = "portfolio_limit"
            if counts[category] >= CATEGORY_QUOTA.get(category, 1):
                reason = f"category_quota_full:{category}"
            blocked.append({**item, "portfolio_block_reason": reason})

    return selected, blocked
