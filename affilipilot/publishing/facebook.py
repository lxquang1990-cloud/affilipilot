from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file
from affilipilot.links.shortlink import is_short_link
from affilipilot.security import redact_for_audit


@dataclass
class FacebookConfig:
    page_id: str = ""
    page_access_token: str = ""
    page_name: str = ""

    @classmethod
    def from_env(cls) -> "FacebookConfig":
        env_file = load_env_file(DEFAULT_SECRET_PATH)
        return cls(
            page_id=os.environ.get("FACEBOOK_PAGE_ID", "") or env_file.get("FACEBOOK_PAGE_ID", ""),
            page_access_token=os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "") or env_file.get("FACEBOOK_PAGE_ACCESS_TOKEN", ""),
            page_name=os.environ.get("FACEBOOK_PAGE_NAME", "") or env_file.get("FACEBOOK_PAGE_NAME", ""),
        )


@dataclass
class FacebookHealth:
    verified: bool
    reasons: list[str]


def check_facebook_config(config: FacebookConfig | None = None) -> FacebookHealth:
    config = config or FacebookConfig.from_env()
    reasons = []
    if not config.page_id:
        reasons.append("missing_FACEBOOK_PAGE_ID")
    if not config.page_access_token:
        reasons.append("missing_FACEBOOK_PAGE_ACCESS_TOKEN")
    return FacebookHealth(verified=not reasons, reasons=reasons)


def dry_run_publish(post_text: str, config: FacebookConfig | None = None) -> dict:
    health = check_facebook_config(config)
    return {
        "dry_run": True,
        "would_publish": health.verified and bool(post_text.strip()),
        "facebook_verified": health.verified,
        "reasons": health.reasons + ([] if post_text.strip() else ["empty_post_text"]),
        "text_length": len(post_text),
    }


def publish_post(*, post_text: str, link: str = "", config: FacebookConfig | None = None, timeout: int = 30) -> dict[str, Any]:
    """Publish one post to Facebook Page feed.

    Caller must enforce approval and publish gate before invoking this function.
    This function never logs or returns the access token.
    """
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    if not post_text.strip():
        raise RuntimeError("Refusing to publish empty post text")
    endpoint = f"https://graph.facebook.com/v19.0/{config.page_id}/feed"
    payload = {
        "message": post_text,
        "access_token": config.page_access_token,
    }
    if link:
        payload["link"] = link
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "response": redact_for_audit(parsed),
                "endpoint": f"/{config.page_id}/feed",
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        return {
            "ok": False,
            "status": exc.code,
            "response": redact_for_audit(parsed),
            "endpoint": f"/{config.page_id}/feed",
        }


def _caption_link(link: str) -> str:
    """Return the exact click-safe URL to place in Facebook captions.

    Never use cosmetic ellipsis/truncated URLs here: Facebook auto-links visible
    URLs, so a shortened display string such as ``https://go.isclix.com/deep_link/...``
    becomes a real broken link.
    """
    cleaned = link.strip()
    if not cleaned:
        return ""
    if not is_short_link(cleaned):
        raise RuntimeError("Refusing to publish raw affiliate URL in caption; provision product.short_url first")
    return cleaned


def _multipart_post(endpoint: str, *, fields: dict[str, str], files: list[tuple[str, Path]], timeout: int = 60) -> dict[str, Any]:
    boundary = "----AffiliPilotBoundary7MA4YWxkTrZu0gW"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")
    for name, path in files:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode())
        parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        parts.append(path.read_bytes())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(endpoint, data=b"".join(parts), method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "response": redact_for_audit(parsed)}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        return {"ok": False, "status": exc.code, "response": redact_for_audit(parsed)}


def publish_photo_post(*, caption: str, image_path: str, link: str = "", config: FacebookConfig | None = None, timeout: int = 60) -> dict[str, Any]:
    """Publish one local image to Facebook Page photos.

    Caller must enforce approval/media/affiliate gates before invoking this function.
    Uses multipart/form-data and never returns/logs the token.
    """
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    path = Path(image_path)
    if not path.exists():
        raise RuntimeError("Refusing to publish missing image file")
    if not caption.strip():
        raise RuntimeError("Refusing to publish empty caption")

    endpoint = f"https://graph.facebook.com/v19.0/{config.page_id}/photos"
    caption_link = _caption_link(link)
    caption_text = caption + (f"\n\nLink sản phẩm: {caption_link}" if caption_link else "")
    result = _multipart_post(endpoint, fields={"caption": caption_text, "access_token": config.page_access_token}, files=[("source", path)], timeout=timeout)
    return {**result, "endpoint": f"/{config.page_id}/photos"}


def publish_photo_comment(*, object_id: str, image_path: str, message: str = "", config: FacebookConfig | None = None, timeout: int = 90) -> dict[str, Any]:
    """Comment on a Facebook object with one local image attachment."""
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    if not object_id.strip():
        raise RuntimeError("Refusing to comment without target object id")
    path = Path(image_path)
    if not path.exists():
        raise RuntimeError("Refusing to comment missing image file")
    endpoint = f"https://graph.facebook.com/v19.0/{object_id}/comments"
    fields = {"access_token": config.page_access_token}
    if message.strip():
        fields["message"] = message.strip()
    result = _multipart_post(endpoint, fields=fields, files=[("source", path)], timeout=timeout)
    return {**result, "endpoint": f"/{object_id}/comments"}


def publish_gallery_comment(*, object_id: str, image_paths: list[str], message: str = "Ảnh thật sản phẩm", config: FacebookConfig | None = None, timeout: int = 90) -> dict[str, Any]:
    """Post one image comment per gallery image and return aggregate status."""
    results = []
    for index, image_path in enumerate([path for path in image_paths if path][:4], 1):
        text = message if index == 1 else ""
        result = publish_photo_comment(object_id=object_id, image_path=image_path, message=text, config=config, timeout=timeout)
        results.append({"image_path": image_path, **result})
        if not result.get("ok"):
            return {"ok": False, "status": result.get("status"), "stage": "image_comment", "results": results}
    return {"ok": all(item.get("ok") for item in results), "status": 200 if results else 0, "stage": "image_comments", "results": results}


def publish_video_post(*, description: str, video_path: str, link: str = "", config: FacebookConfig | None = None, timeout: int = 180) -> dict[str, Any]:
    """Publish one local video to Facebook Page videos."""
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    path = Path(video_path)
    if not path.exists():
        raise RuntimeError("Refusing to publish missing video file")
    if not description.strip():
        raise RuntimeError("Refusing to publish empty video description")
    endpoint = f"https://graph.facebook.com/v19.0/{config.page_id}/videos"
    caption_link = _caption_link(link)
    description_text = description + (f"\n\nLink sản phẩm: {caption_link}" if caption_link else "")
    result = _multipart_post(endpoint, fields={"description": description_text, "access_token": config.page_access_token}, files=[("source", path)], timeout=timeout)
    return {**result, "endpoint": f"/{config.page_id}/videos"}


def publish_multi_photo_post(*, message: str, image_paths: list[str], link: str = "", config: FacebookConfig | None = None, timeout: int = 90) -> dict[str, Any]:
    """Publish a Facebook feed post with multiple attached photos.

    Uploads photos unpublished first, then creates one feed post with attached_media.
    """
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    paths = [Path(path) for path in image_paths if path]
    if len(paths) < 2:
        raise RuntimeError("multi-photo publish requires at least 2 images")
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"Refusing to publish missing image file: {path}")
    upload_ids: list[str] = []
    for path in paths[:4]:
        endpoint = f"https://graph.facebook.com/v19.0/{config.page_id}/photos"
        upload = _multipart_post(endpoint, fields={"published": "false", "access_token": config.page_access_token}, files=[("source", path)], timeout=timeout)
        if not upload.get("ok"):
            return {**upload, "endpoint": f"/{config.page_id}/photos", "stage": "upload_unpublished_photo", "uploaded_media_ids": upload_ids}
        media_id = upload.get("response", {}).get("id")
        if media_id:
            upload_ids.append(media_id)
    caption_link = _caption_link(link)
    message_text = message + (f"\n\nLink sản phẩm: {caption_link}" if caption_link else "")
    payload = {"message": message_text, "access_token": config.page_access_token}
    for index, media_id in enumerate(upload_ids):
        payload[f"attached_media[{index}]"] = json.dumps({"media_fbid": media_id})
    data = urllib.parse.urlencode(payload).encode("utf-8")
    endpoint = f"https://graph.facebook.com/v19.0/{config.page_id}/feed"
    req = urllib.request.Request(endpoint, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "response": parsed, "endpoint": f"/{config.page_id}/feed", "stage": "feed_multi_photo", "uploaded_media_ids": upload_ids}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        return {"ok": False, "status": exc.code, "response": parsed, "endpoint": f"/{config.page_id}/feed", "stage": "feed_multi_photo", "uploaded_media_ids": upload_ids}
