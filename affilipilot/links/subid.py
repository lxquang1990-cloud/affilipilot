from __future__ import annotations

import re
from datetime import date, datetime

from affilipilot.models import TrackingIdentity

def slugify(value: str, max_len: int = 48) -> str:
    value = value.lower().strip()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9\u00C0-\u1EF9]+", "-", value, flags=re.IGNORECASE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:max_len] or "product"

def make_post_id(day: date | datetime, index: int, *, slug: str = "") -> str:
    """Build a batch-safe post id for approval/publish tracking."""
    if isinstance(day, datetime):
        stamp = day.strftime("%Y%m%d_%H%M")
        suffix = f"_{slugify(slug, max_len=24)}" if slug else ""
    else:
        # Date-only mode is kept deterministic/backward-compatible for tests and demos.
        stamp = day.strftime("%Y%m%d")
        suffix = ""
    return f"post_{stamp}{suffix}_{index:03d}"

def make_tracking_identity(product_title: str, index: int, *, channel: str = "facebook", property_name: str = "smartshopping", day: date | datetime | None = None) -> TrackingIdentity:
    day = day or datetime.now()
    return TrackingIdentity(
        channel=channel,
        property_name=property_name,
        post_id=make_post_id(day, index, slug=product_title),
        product_id=slugify(product_title),
    )

def build_utm(identity: TrackingIdentity) -> dict[str, str]:
    month = identity.post_id.split("_")[1][:6] if "_" in identity.post_id else "unknown"
    return {
        "utm_source": identity.channel,
        "utm_medium": "page_post" if identity.channel == "facebook" else "social_affiliate",
        "utm_campaign": f"affilipilot_smart_shopping_{month}",
        "utm_content": identity.post_id,
        "sub1": identity.sub1,
        "sub2": identity.sub2,
        "sub3": identity.sub3,
        "sub4": identity.sub4,
    }
