from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

MIN_IMAGE_WIDTH = 600
MIN_IMAGE_HEIGHT = 600
WARN_IMAGE_WIDTH = 400
WARN_IMAGE_HEIGHT = 400
THUMBNAIL_HINTS = ("_80x80", "_120x120", "_200x200", "_300x300")
BAD_MEDIA_NAME_HINTS = (
    "ios_splash_screen",
    "android_splash",
    "splash_screen",
    "shopee-mobilemall",
    "app-store",
    "google-play",
    "logo",
    "icon",
)
TRUSTED_SMALL_IMAGE_SOURCES = {
    "shopee_pdp",
    "lazada_pdp",
    "product_detail_og_image",
    "jsonld_product_image",
    "product_card_image",
    "user_uploaded_image",
    "brand_api_product_image",
    "accesstrade_api",
}

@dataclass
class MediaQualityResult:
    passed: bool
    width: int = 0
    height: int = 0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

def upgrade_lazada_image_url(url: str, *, size: int = 720, quality: int = 80) -> str:
    """Upgrade Lazada thumbnail URLs like .jpg_200x200q80.jpg to a larger variant."""
    if not url or "lazcdn.com" not in url:
        return url
    parsed = urlparse(url)
    path = parsed.path
    if ".jpg_" in path:
        path = path.split(".jpg_", 1)[0] + f".jpg_{size}x{size}q{quality}.jpg"
    elif ".png_" in path:
        path = path.split(".png_", 1)[0] + f".png_{size}x{size}q{quality}.png"
    return urlunparse(parsed._replace(path=path))

def image_url_has_thumbnail_hint(url: str) -> bool:
    lower = (url or "").lower()
    return any(hint in lower for hint in THUMBNAIL_HINTS)

def _jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1] if i + 1 < len(data) else 0
        i += 2
        if marker in {0xD8, 0xD9}:
            continue
        if i + 2 > len(data):
            break
        length = int.from_bytes(data[i:i+2], "big")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3} and i + 7 < len(data):
            height = int.from_bytes(data[i+3:i+5], "big")
            width = int.from_bytes(data[i+5:i+7], "big")
            return width, height
        i += max(length, 2)
    return 0, 0

def _png_size(data: bytes) -> tuple[int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return 0, 0

def image_dimensions(path: str | Path) -> tuple[int, int]:
    data = Path(path).read_bytes()[:65536]
    if data.startswith(b"\xff\xd8"):
        return _jpeg_size(data)
    if data.startswith(b"\x89PNG"):
        return _png_size(data)
    return 0, 0

def _trusted_small_image(post: dict[str, Any]) -> bool:
    product = post.get("product", {})
    media = post.get("media", {})
    source = (media.get("source") or product.get("media_source") or "").lower()
    confidence = (media.get("confidence") or product.get("media_confidence") or "").lower()
    return source in TRUSTED_SMALL_IMAGE_SOURCES and confidence in {"high", "trusted", "official"}

def evaluate_media_quality(post: dict[str, Any], *, min_width: int = MIN_IMAGE_WIDTH, min_height: int = MIN_IMAGE_HEIGHT) -> MediaQualityResult:
    files = post.get("files", {})
    media = post.get("media", {})
    product = post.get("product", {})
    path = files.get("image") or media.get("local_path") or product.get("image_path", "")
    reasons: list[str] = []
    warnings: list[str] = []
    width = height = 0
    remote = product.get("image_url", "")
    media_text = f"{path} {remote}".lower()
    if any(hint in media_text for hint in BAD_MEDIA_NAME_HINTS):
        reasons.append("media_non_product_asset")
    if not path or not Path(path).exists():
        reasons.append("media_quality_missing_local_image")
    else:
        try:
            width, height = image_dimensions(path)
        except Exception:  # noqa: BLE001
            reasons.append("media_quality_unreadable_image")
        if width and height and (width < min_width or height < min_height):
            if width >= WARN_IMAGE_WIDTH and height >= WARN_IMAGE_HEIGHT and _trusted_small_image(post):
                warnings.append(f"media_image_small_but_trusted:{width}x{height}")
            else:
                reasons.append(f"media_image_too_small:{width}x{height}")
    if image_url_has_thumbnail_hint(remote):
        reasons.append("media_remote_thumbnail_url")
    return MediaQualityResult(passed=not reasons, width=width, height=height, reasons=reasons, warnings=warnings)
