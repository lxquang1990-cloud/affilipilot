from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from affilipilot.media_quality import evaluate_media_quality

AFFILIATE_HOST_HINTS = (
    "accesstrade.vn",
    "go.isclix.com",
    "pub.accesstrade.vn",
    "shorten.asia",
    "s.shopee.vn",
)
DEMO_HOST_OR_PATH_HINTS = ("example", "demo", "localhost", "test-safe", "/test", "test-")
UNTRUSTED_MEDIA_HINTS = (
    "/g/tps/",
    "/ims-web/",
    "/us/domino/",
    "app-store",
    "google-play",
    "logo",
    "sprite",
    "icon",
    "feedback",
)


@dataclass
class RequirementCheck:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def is_affiliate_link(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if any(hint in lowered for hint in DEMO_HOST_OR_PATH_HINTS):
        return False
    if any(host in lowered for host in AFFILIATE_HOST_HINTS):
        return True
    # Accept explicit tracking markers if user already has converted URL.
    if any(marker in lowered for marker in ("aff", "utm_source=affiliate", "sub_id", "sub1=", "sub3=")):
        return True
    return False


def check_affiliate_link(post: dict[str, Any]) -> RequirementCheck:
    product = post.get("product", {})
    link = product.get("affiliate_url") or product.get("tracking_url") or product.get("url", "")
    reasons: list[str] = []
    if not link:
        reasons.append("missing_product_link")
    elif not is_affiliate_link(link):
        reasons.append("link_not_affiliate_tracking")
    return RequirementCheck(passed=not reasons, reasons=reasons)


def check_media(post: dict[str, Any]) -> RequirementCheck:
    product = post.get("product", {})
    files = post.get("files", {})
    media = post.get("media", {})
    remote_candidates = [
        product.get("image_url", ""),
        product.get("video_url", ""),
    ]
    local_candidates = [
        product.get("image_path", ""),
        product.get("video_path", ""),
        files.get("image", ""),
        files.get("video", ""),
        media.get("local_path", ""),
    ]
    reasons: list[str] = []
    all_candidates = remote_candidates + local_candidates
    if not any(str(item).strip() for item in all_candidates):
        reasons.append("missing_product_media")
    for item in all_candidates:
        lowered = str(item).lower()
        if lowered and any(hint in lowered for hint in UNTRUSTED_MEDIA_HINTS):
            reasons.append("untrusted_product_media")
            break

    existing_local = [str(item) for item in local_candidates if str(item).strip() and Path(str(item)).exists()]
    if not existing_local:
        if any(str(item).strip() for item in remote_candidates):
            reasons.append("media_not_downloaded")
        else:
            reasons.append("missing_local_media")
    for key in ("image_path", "video_path"):
        value = product.get(key) or files.get(key.replace("_path", ""), "")
        if value and not Path(value).exists():
            reasons.append(f"media_path_not_found:{key}")
    media_quality = evaluate_media_quality(post)
    reasons.extend(reason for reason in media_quality.reasons if reason not in reasons)
    return RequirementCheck(passed=not reasons, reasons=reasons)
