from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from affilipilot.accesstrade.catalog import _product_from_item
from affilipilot.accesstrade.client import AccesstradeConfig, redact_for_audit


def _request_json(url: str, *, token: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Content-Type": "application/json", "Authorization": f"Token {token}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}


def _payload(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    if isinstance(data, dict):
        return data
    return response if isinstance(response, dict) else {}


def fetch_product_detail(*, merchant: str, product_id: str, config: AccesstradeConfig | None = None, timeout: int = 30) -> dict[str, Any]:
    """Fetch official Accesstrade product detail by merchant + product_id."""
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "product": None}
    params = {"merchant": merchant, "product_id": product_id}
    url = f"{config.base_url.rstrip()}/v1/product_detail?{urllib.parse.urlencode(params)}"
    response = _request_json(url, token=config.token, timeout=timeout)
    item = _payload(response)
    if not item:
        return {"ok": False, "error": "empty_product_detail", "source_url": url, "product": None, "raw_redacted": redact_for_audit(response)}
    normalized = dict(item)
    normalized.setdefault("url", item.get("link") or item.get("url") or "")
    normalized.setdefault("name", item.get("name") or item.get("title") or "")
    normalized.setdefault("cate", item.get("category_name") or item.get("category_id") or "unknown")
    normalized.setdefault("merchant", merchant)
    normalized.setdefault("product_id", product_id)
    product = _product_from_item(normalized, source="accesstrade_product_detail")
    return {"ok": True, "source_url": url, "product": product.__dict__, "raw_redacted": redact_for_audit(response)}
