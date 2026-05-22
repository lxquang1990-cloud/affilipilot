from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.media_quality import evaluate_media_quality
from affilipilot.publishing.restrictions import PlatformRestriction
from affilipilot.publishing.strategy import FACEBOOK_LINK_POST, FACEBOOK_PHOTO_POST, FACEBOOK_REEL, FACEBOOK_TEXT_POST, FACEBOOK_VIDEO_POST, PublishStrategy
from affilipilot.video_media import validate_video_path
from affilipilot.video_probe import probe_video

@dataclass
class PublishMediaGateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

def _images(post: dict[str, Any]) -> list[str]:
    files = post.get("files", {}) or {}
    images = [str(path) for path in files.get("images", []) if path]
    image = str(files.get("image", "") or post.get("media", {}).get("local_path", "") or post.get("product", {}).get("image_path", "") or "")
    if image and image not in images:
        images.insert(0, image)
    return images

def _video_path(post: dict[str, Any]) -> str:
    files = post.get("files", {}) or {}
    product = post.get("product", {}) or {}
    return str(files.get("video", "") or product.get("video_path", "") or "")

def evaluate_publish_media_gate(post: dict[str, Any], *, strategy: PublishStrategy, restriction: PlatformRestriction) -> PublishMediaGateResult:
    reasons: list[str] = []
    warnings: list[str] = []
    images = _images(post)
    video_path = _video_path(post)

    if strategy.publish_type == FACEBOOK_PHOTO_POST:
        if len(images) < restriction.image_min_count:
            reasons.append("photo_post_requires_image")
        if restriction.image_max_count and len(images) > restriction.image_max_count:
            reasons.append("photo_post_too_many_images")
        media_result = evaluate_media_quality({**post, "files": {**(post.get("files", {}) or {}), "image": images[0] if images else ""}})
        if not media_result.passed:
            reasons.extend(media_result.reasons)
        warnings.extend(media_result.warnings)

    elif strategy.publish_type in {FACEBOOK_VIDEO_POST, FACEBOOK_REEL}:
        if restriction.video_required and not video_path:
            reasons.append(f"{strategy.publish_type}_requires_video")
        if video_path:
            valid = validate_video_path(video_path)
            if not valid.ok:
                reasons.extend(valid.reasons)
            probe = probe_video(video_path)
            if probe.ok:
                min_seconds, max_seconds = restriction.video_duration_seconds
                if min_seconds and probe.duration_seconds < min_seconds:
                    reasons.append(f"video_too_short:{probe.duration_seconds:.1f}s")
                if max_seconds and probe.duration_seconds > max_seconds:
                    reasons.append(f"video_too_long:{probe.duration_seconds:.1f}s")
                if strategy.publish_type == FACEBOOK_REEL and not probe.is_vertical:
                    reasons.append("reel_requires_vertical_video")
            else:
                warnings.extend(probe.reasons)

    elif strategy.publish_type == FACEBOOK_LINK_POST:
        product = post.get("product", {}) or {}
        if not (product.get("tracking_url") or product.get("affiliate_url") or product.get("url")):
            reasons.append("link_post_requires_link")
        warnings.append("link_post_media_weak_fallback")

    elif strategy.publish_type == FACEBOOK_TEXT_POST:
        reasons.append("text_post_not_publishable_for_affiliate")

    return PublishMediaGateResult(passed=not reasons, reasons=list(dict.fromkeys(reasons)), warnings=list(dict.fromkeys(warnings)))
