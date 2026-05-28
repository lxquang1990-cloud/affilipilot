from __future__ import annotations

from affilipilot.publishing.facebook import (
    publish_gallery_comment,
    publish_multi_photo_post,
    publish_photo_post,
    publish_post,
    publish_reel_post,
    publish_video_post,
)


def dispatch_publish_strategy(item: dict, payload: dict) -> dict:
    """Publish a planned Facebook item using its selected strategy.

    Facebook Page Reels support is not universal across Graph API versions/pages.
    If `/reels` is rejected as an unknown path, safely fall back to the official
    Page `/videos` upload with the same approved video/caption/link payload.
    """
    strategy = payload.get("strategy", "")
    if strategy in {"reel_primary", "video_primary", "video_primary_with_image_comment"}:
        publisher = publish_reel_post if strategy == "reel_primary" else publish_video_post
        result = publisher(
            description=payload.get("description", ""),
            video_path=payload.get("local_video_path", ""),
            link=payload.get("url", ""),
        )
        error = result.get("response", {}).get("error", {}) if isinstance(result.get("response"), dict) else {}
        if strategy == "reel_primary" and not result.get("ok") and result.get("status") == 400 and error.get("code") == 2500 and "Unknown path components" in str(error.get("message", "")):
            fallback = publish_video_post(
                description=payload.get("description", ""),
                video_path=payload.get("local_video_path", ""),
                link=payload.get("url", ""),
            )
            result = {**fallback, "fallback_from": "reels", "fallback_reason": "facebook_reels_endpoint_unsupported", "original_result": result}
        if result.get("ok") and strategy == "video_primary_with_image_comment" and payload.get("local_image_paths"):
            target_id = result.get("response", {}).get("post_id") or result.get("response", {}).get("id", "")
            comments = publish_gallery_comment(
                object_id=target_id,
                image_paths=payload.get("local_image_paths", []),
                message="Ảnh thật sản phẩm",
            )
            result = {**result, "image_comments": comments, "ok": bool(result.get("ok")) and bool(comments.get("ok"))}
        return result
    if strategy == "multi_photo":
        return publish_multi_photo_post(
            message=payload.get("message", ""),
            image_paths=payload.get("local_image_paths", []),
            link=payload.get("url", ""),
        )
    if item.get("endpoint", "").endswith("/photos"):
        return publish_photo_post(
            caption=payload.get("caption", ""),
            image_path=payload.get("local_image_path", ""),
            link=payload.get("url", ""),
        )
    return publish_post(post_text=payload.get("message", ""), link=payload.get("link", ""))
