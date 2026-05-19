from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from affilipilot.content.early_filter import evaluate_early_product_filter
from affilipilot.content.product_taste import evaluate_product_taste
from affilipilot.models import ProductCandidate
from affilipilot.scoring.product_score import score_product


@dataclass
class ConfidenceSignals:
    price_signal: float
    media_signal: float
    title_signal: float
    compliance_signal: float
    merchant_signal: float
    historical_signal: float
    novelty_signal: float


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _note_number(notes: str, key: str) -> float | None:
    marker = key + "="
    if marker not in notes:
        return None
    try:
        return float(notes.split(marker, 1)[1].split(";", 1)[0])
    except ValueError:
        return None


def compute_confidence(product: ProductCandidate, history: dict[str, Any] | None = None) -> tuple[float, dict[str, Any]]:
    early = evaluate_early_product_filter(product)
    taste = evaluate_product_taste(product)
    base = score_product(product)
    notes = product.notes.lower()

    price = product.price_vnd or 0
    price_signal = 0.6
    if price:
        price_signal = 1.0 if 80_000 <= price <= 1_500_000 else 0.55 if price <= 5_000_000 else 0.35

    media_count = len(product.image_urls or []) + (1 if product.image_url or product.image_path else 0)
    video_bonus = 0.2 if (product.video_url or product.video_urls or product.video_path) else 0.0
    media_signal = _clamp(0.25 + min(media_count, 4) * 0.15 + video_bonus)

    title = product.title.strip()
    spam_terms = ("siêu rẻ", "hot hit", "cam kết khỏi", "trị", "giảm cân", "sinh lý")
    title_signal = 0.2 if not title else 0.85
    if len(title.split()) > 28:
        title_signal -= 0.2
    if any(term in title.lower() for term in spam_terms):
        title_signal -= 0.35
    if re.search(r"\d", title):
        title_signal += 0.05
    title_signal = _clamp(title_signal)

    compliance_signal = 1.0 if early.passed else 0.0
    if not taste.passed:
        compliance_signal = min(compliance_signal, 0.45)

    merchant_signal = 0.5
    if any(term in notes for term in ("official_shop", "shopee_verified", "trusted_merchant", "lazada", "shopee")):
        merchant_signal = 0.85
    rating = _note_number(notes, "rating")
    sold = _note_number(notes, "sold")
    if rating and rating >= 4.7:
        merchant_signal += 0.08
    if sold and sold >= 100:
        merchant_signal += 0.07
    merchant_signal = _clamp(merchant_signal)

    historical_signal = float((history or {}).get("historical_signal", 0.5))
    novelty_signal = float((history or {}).get("novelty_signal", 0.7))

    signals = ConfidenceSignals(price_signal, media_signal, title_signal, compliance_signal, merchant_signal, _clamp(historical_signal), _clamp(novelty_signal))
    weights = {
        "compliance_signal": 0.30,
        "media_signal": 0.20,
        "historical_signal": 0.15,
        "price_signal": 0.10,
        "title_signal": 0.10,
        "merchant_signal": 0.10,
        "novelty_signal": 0.05,
    }
    score = sum(getattr(signals, key) * weight for key, weight in weights.items())
    score = min(score, 0.40) if signals.compliance_signal < 0.5 else score
    breakdown = asdict(signals)
    breakdown.update({"base_score": base["score"], "base_reasons": base["reasons"], "taste_score": taste.score, "taste_reasons": taste.reasons + taste.penalties})
    return round(_clamp(score), 4), breakdown
