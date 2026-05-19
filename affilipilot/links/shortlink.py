from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse


def configured_short_base() -> str:
    return os.environ.get("AFFILIPILOT_SHORT_BASE_URL", "").strip().rstrip("/")


def is_short_link(url: str) -> bool:
    if not url:
        return False
    base = configured_short_base()
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if base and url.startswith(base + "/go/"):
        return True
    if host == "shorten.asia" and parsed.path.strip("/"):
        return True
    return parsed.path.startswith("/go/") and len(parsed.path.strip("/").split("/")) >= 2


def build_short_link(slug: str, *, base_url: str | None = None) -> str:
    base = (base_url if base_url is not None else configured_short_base()).strip().rstrip("/")
    if not base:
        return ""
    safe_slug = quote(slug.strip().strip("/"), safe="-_.~")
    return f"{base}/go/{safe_slug}" if safe_slug else ""


def visible_link_for_post(product: dict[str, Any]) -> str:
    """Return the URL allowed to appear in Facebook captions.

    Production captions must not expose raw Accesstrade/isclix URLs. The short
    URL is expected to be a real internal redirect, stored on the product as
    ``short_url`` after provisioning.
    """
    return str(product.get("short_url") or "").strip()
