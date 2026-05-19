from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class NicheStrategy:
    primary_lane: str
    secondary_lanes: list[str] = field(default_factory=list)
    blocked_lanes: list[str] = field(default_factory=list)
    daily_post_limit: int = 2
    rules: list[str] = field(default_factory=list)

def default_strategy(*, audience: str = "profit_first") -> NicheStrategy:
    if audience in {"profit_first", "diverse", "general", "multi_niche"}:
        return NicheStrategy(
            primary_lane="profit_first_multi_category",
            secondary_lanes=["high_commission", "strong_discount", "high_ticket_with_clear_rationale", "seasonal_deals"],
            blocked_lanes=["unsafe_health_claims", "adult_gambling", "unknown_offer", "raw_affiliate_links", "low_quality_generic_copy"],
            daily_post_limit=3,
            rules=[
                "Do not lock discovery to one niche; prioritize commission, discount strength, merchant trust, and offer validity.",
                "Every approval card must explain the commercial reason: commission, deal, price band, warranty, or urgency.",
                "High-ticket products need concrete buying rationale before approval/publish.",
                "Do not publish if offer validation, media provenance, shortlink, approval, or content quality gates fail.",
            ],
        )
    if audience == "mother_baby":
        return NicheStrategy(
            primary_lane="mother_baby_core",
            secondary_lanes=["family_lifestyle", "family_tech_with_explicit_angle"],
            blocked_lanes=["generic_flagship_tech", "unrelated_high_price_items", "tag_page_scrapes"],
            daily_post_limit=2,
            rules=[
                "Prefer products solving a concrete parent/family pain point.",
                "Electronics require a family angle: camera, battery, storage, warranty, travel, or child safety.",
                "Every post needs a specific hook, 2+ benefits, clear CTA, and interest hashtags.",
                "Do not publish if offer validation, media provenance, or market-fit score fails.",
            ],
        )
    return NicheStrategy(primary_lane="generic_affiliate", secondary_lanes=["deal_review"], blocked_lanes=["unknown_offer"], daily_post_limit=3, rules=["Validate offer, audience, and content angle before publish."])

def render_strategy(strategy: NicheStrategy) -> str:
    lines = ["🐌 AffiliPilot monetization strategy", f"Primary lane: {strategy.primary_lane}", f"Secondary lanes: {', '.join(strategy.secondary_lanes) or '(none)'}", f"Blocked lanes: {', '.join(strategy.blocked_lanes) or '(none)'}", f"Daily post limit: {strategy.daily_post_limit}", "Rules:"]
    lines.extend(f"- {rule}" for rule in strategy.rules)
    return "\n".join(lines)
