from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FACEBOOK_PHOTO_POST = "photo_post"
FACEBOOK_VIDEO_POST = "video_post"
FACEBOOK_REEL = "reel"
FACEBOOK_LINK_POST = "link_post"
FACEBOOK_TEXT_POST = "text_post"

@dataclass(frozen=True)
class PublishStrategy:
    platform: str
    publish_type: str
    metrics_profile: str
    reason: str
    endpoint_hint: str = ""

def _media_files(post: dict[str, Any]) -> tuple[list[str], str]:
    files = post.get("files", {}) or {}
    images = [str(path) for path in files.get("images", []) if path]
    image = str(files.get("image", "") or "")
    if image and image not in images:
        images.insert(0, image)
    video_path = str(files.get("video", "") or post.get("product", {}).get("video_path", "") or "")
    return images, video_path

def _is_probably_reel(video_path: str, product: dict[str, Any]) -> bool:
    # Conservative foundation: only select reel when metadata explicitly says so.
    # Real orientation/duration probing can be added later without changing callers.
    hints = " ".join(str(product.get(key, "")) for key in ("video_kind", "media_kind", "notes", "tags")).lower()
    name = Path(video_path).name.lower()
    return any(token in hints for token in ("reel", "vertical", "short_video")) or "reel" in name

def select_facebook_publish_strategy(post: dict[str, Any]) -> PublishStrategy:
    product = post.get("product", {}) or {}
    images, video_path = _media_files(post)
    link = product.get("tracking_url") or product.get("affiliate_url") or product.get("url") or ""
    if video_path:
        if _is_probably_reel(video_path, product):
            return PublishStrategy("facebook_page", FACEBOOK_REEL, "reel", "vertical_or_reel_video", endpoint_hint="reels")
        return PublishStrategy("facebook_page", FACEBOOK_VIDEO_POST, "feed_video", "product_video_ready", endpoint_hint="videos")
    if images:
        return PublishStrategy("facebook_page", FACEBOOK_PHOTO_POST, "feed_post", "product_images_ready", endpoint_hint="photos")
    if link:
        return PublishStrategy("facebook_page", FACEBOOK_LINK_POST, "feed_post", "link_only_fallback", endpoint_hint="feed")
    return PublishStrategy("facebook_page", FACEBOOK_TEXT_POST, "feed_post", "text_only_fallback", endpoint_hint="feed")

def strategy_as_dict(strategy: PublishStrategy) -> dict[str, Any]:
    return asdict(strategy)
