from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file


@dataclass
class AccesstradeConfig:
    token: str = ""
    campaign_id: str = ""
    base_url: str = "https://api.accesstrade.vn"

    @classmethod
    def from_env(cls) -> "AccesstradeConfig":
        env_file = load_env_file(DEFAULT_SECRET_PATH)
        return cls(
            token=os.environ.get("ACCESSTRADE_TOKEN", "") or env_file.get("ACCESSTRADE_TOKEN", ""),
            campaign_id=os.environ.get("ACCESSTRADE_SHOPEE_CAMPAIGN_ID", "") or env_file.get("ACCESSTRADE_SHOPEE_CAMPAIGN_ID", ""),
        )


@dataclass
class AccesstradeHealth:
    configured: bool
    reasons: list[str]

@dataclass
class AccesstradeLinkResult:
    ok: bool
    original_url: str
    affiliate_url: str = ""
    payload: dict[str, Any] | None = None
    status: int | None = None
    error: str = ""
    dry_run: bool = True


def check_accesstrade_config(config: AccesstradeConfig | None = None) -> AccesstradeHealth:
    config = config or AccesstradeConfig.from_env()
    reasons = []
    if not config.token:
        reasons.append("missing_ACCESSTRADE_TOKEN")
    if not config.campaign_id:
        reasons.append("missing_or_pending_ACCESSTRADE_SHOPEE_CAMPAIGN_ID")
    return AccesstradeHealth(configured=not reasons, reasons=reasons)


def build_tracking_payload(*, campaign_id: str, urls: list[str], utm: dict[str, str]) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "urls": urls,
        "url_enc": True,
        "utm_source": utm.get("utm_source", ""),
        "utm_medium": utm.get("utm_medium", ""),
        "utm_campaign": utm.get("utm_campaign", ""),
        "utm_content": utm.get("utm_content", ""),
        "sub1": utm.get("sub1", ""),
        "sub2": utm.get("sub2", ""),
        "sub3": utm.get("sub3", ""),
        "sub4": utm.get("sub4", ""),
    }


def create_tracking_link(*, url: str, utm: dict[str, str], config: AccesstradeConfig | None = None, dry_run: bool = True, timeout: int = 30) -> AccesstradeLinkResult:
    config = config or AccesstradeConfig.from_env()
    health = check_accesstrade_config(config)
    payload = build_tracking_payload(campaign_id=config.campaign_id, urls=[url], utm=utm)
    if not health.configured:
        return AccesstradeLinkResult(ok=False, original_url=url, payload=payload, error=",".join(health.reasons), dry_run=dry_run)
    if dry_run:
        return AccesstradeLinkResult(ok=True, original_url=url, affiliate_url=url, payload=payload, dry_run=True)

    endpoint = f"{config.base_url.rstrip('/')}/v1/product_link/create"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {config.token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            affiliate_url = extract_affiliate_url(parsed)
            return AccesstradeLinkResult(ok=bool(affiliate_url), original_url=url, affiliate_url=affiliate_url, payload=payload, status=resp.status, error="" if affiliate_url else "affiliate_url_not_found", dry_run=False)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
            message = parsed.get("message") or parsed.get("error") or body[:300]
        except json.JSONDecodeError:
            message = body[:300]
        return AccesstradeLinkResult(ok=False, original_url=url, payload=payload, status=exc.code, error=str(message), dry_run=False)


def extract_affiliate_url(response: dict[str, Any]) -> str:
    candidates: list[Any] = []
    for key in ("data", "result", "results"):
        value = response.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, dict):
            candidates.append(value)
    candidates.append(response)
    for item in candidates:
        if not isinstance(item, dict):
            continue
        for key in ("short_link", "link", "affiliate_url", "tracking_url", "url"):
            value = item.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    return ""
