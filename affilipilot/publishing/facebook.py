from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file


@dataclass
class FacebookConfig:
    page_id: str = ""
    page_access_token: str = ""

    @classmethod
    def from_env(cls) -> "FacebookConfig":
        env_file = load_env_file(DEFAULT_SECRET_PATH)
        return cls(
            page_id=os.environ.get("FACEBOOK_PAGE_ID", "") or env_file.get("FACEBOOK_PAGE_ID", ""),
            page_access_token=os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "") or env_file.get("FACEBOOK_PAGE_ACCESS_TOKEN", ""),
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
                "response": parsed,
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
            "response": parsed,
            "endpoint": f"/{config.page_id}/feed",
        }


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
    boundary = "----AffiliPilotBoundary7MA4YWxkTrZu0gW"
    caption_text = caption + (f"\n\n{link}" if link else "")
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    add_field("caption", caption_text)
    add_field("access_token", config.page_access_token)
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="source"; filename="{path.name}"\r\n'.encode())
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(path.read_bytes())
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    data = b"".join(parts)
    req = urllib.request.Request(endpoint, data=data, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "response": parsed, "endpoint": f"/{config.page_id}/photos"}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        return {"ok": False, "status": exc.code, "response": parsed, "endpoint": f"/{config.page_id}/photos"}
