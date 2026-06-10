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
    If `/video_reels` is rejected as an unknown/unsupported path, safely fall
    back to the official Page `/videos` upload with the same approved
    video/caption/link payload.
    """
    strategy = payload.get("strategy", "")
    if strategy in {"reel_primary", "reel_primary_with_image_comment", "video_primary", "video_primary_with_image_comment"}:
        publisher = publish_reel_post if strategy in {"reel_primary", "reel_primary_with_image_comment"} else publish_video_post
        result = publisher(
            description=payload.get("description", ""),
            video_path=payload.get("local_video_path", ""),
            link=payload.get("url", ""),
        )
        error = result.get("response", {}).get("error", {}) if isinstance(result.get("response"), dict) else {}
        reels_fallback_needed = (
            strategy in {"reel_primary", "reel_primary_with_image_comment"}
            and not result.get("ok")
            and result.get("status") == 400
            and (
                (error.get("code") == 2500 and "Unknown path components" in str(error.get("message", "")))
                or (error.get("code") == 100 and "upload_phase" in str(error.get("message", "")).lower())
            )
        )
        if reels_fallback_needed:
            fallback = publish_video_post(
                description=payload.get("description", ""),
                video_path=payload.get("local_video_path", ""),
                link=payload.get("url", ""),
            )
            result = {**fallback, "fallback_from": "video_reels", "fallback_reason": "facebook_reels_upload_flow_unavailable", "original_result": result}
        if result.get("ok") and strategy in {"video_primary_with_image_comment", "reel_primary_with_image_comment"} and payload.get("local_image_paths"):
            target_id = result.get("response", {}).get("post_id") or result.get("response", {}).get("id", "")
            comments = publish_gallery_comment(
                object_id=target_id,
                image_paths=payload.get("local_image_paths", []),
                message="Ảnh thật sản phẩm",
            )
            # The primary video/reel is already published. Missing comment
            # permissions should be visible to operators but must not turn a
            # successful publish into a false full failure.
            result = {**result, "image_comments": comments}
            if not comments.get("ok"):
                result["status_detail"] = "published_with_image_comment_warning"
                result["warnings"] = [*result.get("warnings", []), "image_comment_failed"]
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
