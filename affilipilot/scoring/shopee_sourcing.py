from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import re
from urllib.parse import urlparse

from affilipilot.models import ProductCandidate


@dataclass(frozen=True)
class ShopeeSourcingScore:
    score: int = 0
    reasons: list[str] = field(default_factory=list)


def _note_value(notes: str, key: str) -> str:
    for part in re.split(r"[;|]", notes):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip().lower() == key.lower():
            return v.strip()
    return ""


def _parse_percent(raw: str) -> float | None:
    raw = raw.strip().replace("%", "")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value / 100 if value > 1 else value


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _is_shopee(product: ProductCandidate) -> bool:
    text = f"{product.url} {product.affiliate_url} {product.tracking_url} {product.notes}".lower()
    host = urlparse(product.url).netloc.lower()
    return "shopee" in text or "shopee" in host


def score_shopee_sourcing(product: ProductCandidate, *, today: date | None = None) -> ShopeeSourcingScore:
    if not _is_shopee(product):
        return ShopeeSourcingScore()
    today = today or date.today()
    notes = product.notes.lower()
    score = 0
    reasons: list[str] = []

    score += 4
    reasons.append("shopee_source+4")

    commission = _parse_percent(_note_value(notes, "brand_commission") or _note_value(notes, "brand_commission_pct"))
    start = _parse_date(_note_value(notes, "brand_bonus_start") or _note_value(notes, "start_date"))
    end = _parse_date(_note_value(notes, "brand_bonus_end") or _note_value(notes, "end_date"))
    has_brand_bonus = any(term in notes for term in ("brand_bonus", "commission_xtra", "hoa_hong_xtra", "hoa hồng xtra")) or commission is not None
    active_window = (start is None or start <= today) and (end is None or today <= end)
    if has_brand_bonus and active_window:
        score += 16
        reasons.append("brand_bonus_active+16")
        if commission is not None:
            pct = round(commission * 100, 2)
            if commission >= 0.10:
                score += 14
                reasons.append(f"brand_commission_excellent:{pct}%+14")
            elif commission >= 0.06:
                score += 9
                reasons.append(f"brand_commission_good:{pct}%+9")
            elif commission >= 0.03:
                score += 5
                reasons.append(f"brand_commission_ok:{pct}%+5")
    elif has_brand_bonus and not active_window:
        score -= 8
        reasons.append("brand_bonus_expired_or_not_started-8")

    apply_to = _note_value(notes, "apply_to").lower()
    if apply_to in {"whole_shop", "all_shop", "shop", "toan_shop", "toàn_shop"}:
        score += 5
        reasons.append("brand_bonus_apply_whole_shop+5")
    elif apply_to in {"specific_products", "product", "sku"}:
        score += 2
        reasons.append("brand_bonus_apply_specific_products+2")

    campaign = _note_value(notes, "campaign_window") or _note_value(notes, "campaign")
    if campaign:
        c = campaign.lower()
        if any(term in c for term in ("spike", "15", "25", "payday", "mid_month", "monthly_sale")):
            score += 8
            reasons.append(f"campaign_window:{campaign}+8")

    source_tags = f"{_note_value(notes, 'source_tag')} {notes}"
    tag_boosts = {
        "hot_sku": 8,
        "hot_deal": 8,
        "hot_collection": 6,
        "shopee_choice": 6,
        "mall_vcx": 6,
        "voucher_xtra": 5,
        "freeship": 4,
        "livestream": 3,
        "video": 3,
    }
    for tag, boost in tag_boosts.items():
        if tag in source_tags:
            score += boost
            reasons.append(f"source_tag:{tag}+{boost}")

    return ShopeeSourcingScore(score=score, reasons=reasons)
