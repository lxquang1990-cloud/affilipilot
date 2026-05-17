from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from affilipilot.publishing.requirements import check_affiliate_link, check_media

PRODUCT_DETAIL_HINTS = (
    "/products/",
    "-i",  # Lazada product slug often contains -i<item>-s<sku>
    ".html",
)
TAG_OR_SEARCH_HINTS = (
    "/tag/",
    "/catalog/",
    "/search",
    "?q=",
    "keyword=",
)
TRUSTED_MEDIA_SOURCES = {
    "product_detail_og_image",
    "jsonld_product_image",
    "product_card_image",
    "user_uploaded_image",
    "brand_api_product_image",
}

@dataclass
class QualityGateResult:
    passed: bool
    score: int
    media_score: int
    caption_score: int
    reasons: list[str] = field(default_factory=list)


def _text_for_post(post: dict[str, Any]) -> str:
    path = post.get("files", {}).get("post_text", "")
    if path and Path(path).exists():
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    return str(post.get("post_text", ""))


def is_product_detail_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    lower = url.lower()
    if any(hint in lower for hint in TAG_OR_SEARCH_HINTS):
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "lazada." in host:
        return "/products/" in path or ("-i" in path and "-s" in path and path.endswith(".html"))
    if "cellphones.com.vn" in host:
        return path.endswith(".html") and len(path.strip("/")) > 8
    if "shopee." in host:
        return "-i." in path or bool(path.strip("/"))
    return any(hint in lower for hint in PRODUCT_DETAIL_HINTS)


def evaluate_quality_gate(post: dict[str, Any]) -> QualityGateResult:
    reasons: list[str] = []
    product = post.get("product", {})
    source_url = product.get("original_url") or product.get("source_url") or product.get("canonical_url") or ""
    media = post.get("media", {})
    media_source = media.get("source") or product.get("media_source", "")
    media_confidence = media.get("confidence") or product.get("media_confidence", "")
    text = _text_for_post(post)

    affiliate = check_affiliate_link(post)
    if not affiliate.passed:
        reasons.extend(affiliate.reasons)

    media_check = check_media(post)
    if not media_check.passed:
        reasons.extend(media_check.reasons)

    if source_url and not is_product_detail_url(source_url):
        reasons.append("source_not_product_detail")
    if media_source and media_source not in TRUSTED_MEDIA_SOURCES:
        reasons.append(f"untrusted_media_source:{media_source}")
    if media_confidence and str(media_confidence).lower() not in {"high", "trusted"}:
        reasons.append(f"low_media_confidence:{media_confidence}")
    has_local_user_media = bool(product.get("image_path") or product.get("video_path"))
    has_legacy_safe_remote_media = bool(product.get("image_url")) and not source_url
    if not media_source and not (has_local_user_media or has_legacy_safe_remote_media):
        reasons.append("missing_media_source")
    if not media_confidence and not (has_local_user_media or has_legacy_safe_remote_media):
        reasons.append("missing_media_confidence")

    if "#shopeeaffiliate" in text.lower() and "lazada" in (source_url + " " + product.get("notes", "") + " " + product.get("url", "")).lower():
        reasons.append("wrong_campaign_hashtag")
    if "tiếp thị liên kết" not in text.lower() and "hoa hồng" not in text.lower():
        reasons.append("missing_affiliate_disclosure")
    if len(text.strip()) < 120:
        reasons.append("caption_too_short")

    media_score = 100
    if any(r.startswith("missing_product_media") or r.startswith("untrusted_product_media") for r in reasons):
        media_score = 0
    elif any(r.startswith("missing_media") or r.startswith("low_media") or r.startswith("untrusted_media") for r in reasons):
        media_score = 50

    caption_score = 100
    if "wrong_campaign_hashtag" in reasons:
        caption_score -= 50
    if "missing_affiliate_disclosure" in reasons:
        caption_score -= 50
    if "caption_too_short" in reasons:
        caption_score -= 20
    caption_score = max(0, caption_score)

    score = min(media_score, caption_score, 100 if not reasons else max(0, 100 - 15 * len(reasons)))
    return QualityGateResult(passed=not reasons and score >= 80 and media_score >= 90, score=score, media_score=media_score, caption_score=caption_score, reasons=reasons)
