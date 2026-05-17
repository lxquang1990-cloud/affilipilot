from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file

DEFAULT_CAMPAIGN_ALIASES = {
    "shopee.vn": "SHOPEE",
    "shopee.com": "SHOPEE",
    "lazada.vn": "LAZADA",
    "lazada.com": "LAZADA",
    "tiki.vn": "TIKI",
}

@dataclass
class AccesstradeCampaign:
    key: str
    campaign_id: str
    channel_id: str = ""
    domains: tuple[str, ...] = ()

@dataclass
class AccesstradeConfig:
    token: str = ""
    campaign_id: str = ""
    base_url: str = "https://api.accesstrade.vn"
    channel_id: str = ""
    campaigns: dict[str, AccesstradeCampaign] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "AccesstradeConfig":
        env_file = load_env_file(DEFAULT_SECRET_PATH)

        def value(name: str) -> str:
            return os.environ.get(name, "") or env_file.get(name, "")

        default_campaign = value("ACCESSTRADE_CAMPAIGN_ID") or value("ACCESSTRADE_SHOPEE_CAMPAIGN_ID")
        default_channel = value("ACCESSTRADE_CHANNEL_ID")
        campaigns = load_campaigns_from_values({**env_file, **os.environ})
        return cls(
            token=value("ACCESSTRADE_TOKEN"),
            campaign_id=default_campaign,
            channel_id=default_channel,
            campaigns=campaigns,
        )

    def resolve_campaign(self, url: str = "", campaign_key: str = "") -> AccesstradeCampaign:
        key = normalize_campaign_key(campaign_key)
        if key and key in self.campaigns:
            return self.campaigns[key]
        detected = detect_campaign_key(url, self.campaigns)
        if detected and detected in self.campaigns:
            return self.campaigns[detected]
        if key and not self.campaign_id:
            return AccesstradeCampaign(key=key, campaign_id="")
        return AccesstradeCampaign(key=key or detected or "default", campaign_id=self.campaign_id, channel_id=self.channel_id)

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
    campaign_key: str = ""

def normalize_campaign_key(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.strip().upper()).strip("_")

def load_campaigns_from_values(values: dict[str, str]) -> dict[str, AccesstradeCampaign]:
    campaigns: dict[str, AccesstradeCampaign] = {}
    for name, campaign_id in values.items():
        if not name.startswith("ACCESSTRADE_CAMPAIGN_") or not campaign_id:
            continue
        suffix = name.removeprefix("ACCESSTRADE_CAMPAIGN_")
        if suffix.endswith("_CHANNEL_ID") or suffix.endswith("_DOMAINS"):
            continue
        key = normalize_campaign_key(suffix)
        channel_id = values.get(f"ACCESSTRADE_CAMPAIGN_{key}_CHANNEL_ID", "")
        domains_raw = values.get(f"ACCESSTRADE_CAMPAIGN_{key}_DOMAINS", "")
        domains = tuple(d.strip().lower() for d in domains_raw.split(",") if d.strip())
        campaigns[key] = AccesstradeCampaign(key=key, campaign_id=campaign_id, channel_id=channel_id, domains=domains)

    # Backward compatibility with the original single Shopee variable.
    legacy_shopee = values.get("ACCESSTRADE_SHOPEE_CAMPAIGN_ID", "")
    if legacy_shopee and "SHOPEE" not in campaigns:
        campaigns["SHOPEE"] = AccesstradeCampaign(key="SHOPEE", campaign_id=legacy_shopee, domains=("shopee.vn", "shopee.com"))

    return campaigns

def detect_campaign_key(url: str, campaigns: dict[str, AccesstradeCampaign] | None = None) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    for campaign_key, campaign in (campaigns or {}).items():
        if any(host.endswith(domain) for domain in campaign.domains):
            return campaign_key
    for domain, key in DEFAULT_CAMPAIGN_ALIASES.items():
        if host.endswith(domain):
            return key
    return ""

def check_accesstrade_config(config: AccesstradeConfig | None = None, *, url: str = "", campaign_key: str = "") -> AccesstradeHealth:
    config = config or AccesstradeConfig.from_env()
    selected = config.resolve_campaign(url=url, campaign_key=campaign_key)
    reasons = []
    if not config.token:
        reasons.append("missing_ACCESSTRADE_TOKEN")
    if not selected.campaign_id:
        if campaign_key:
            reasons.append(f"missing_ACCESSTRADE_CAMPAIGN_{normalize_campaign_key(campaign_key)}")
        else:
            reasons.append("missing_ACCESSTRADE_CAMPAIGN_ID")
    return AccesstradeHealth(configured=not reasons, reasons=reasons)

def build_isclix_deep_link(*, url: str, campaign_id: str, channel_id: str, utm: dict[str, str] | None = None) -> str:
    params: dict[str, str] = {"url_enc": __import__("base64").b64encode(url.encode("utf-8")).decode("ascii")}
    for key, value in (utm or {}).items():
        if key.startswith("sub") and value:
            params[key] = value
    return f"https://go.isclix.com/deep_link/v5/{campaign_id}/{channel_id}?{urllib.parse.urlencode(params)}"


def build_tracking_payload(*, campaign_id: str, urls: list[str], utm: dict[str, str], channel_id: str = "") -> dict[str, Any]:
    payload = {
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
    if channel_id:
        payload["channel_id"] = channel_id
    return payload

def create_tracking_link(*, url: str, utm: dict[str, str], config: AccesstradeConfig | None = None, dry_run: bool = True, timeout: int = 30, campaign_key: str = "") -> AccesstradeLinkResult:
    config = config or AccesstradeConfig.from_env()
    selected = config.resolve_campaign(url=url, campaign_key=campaign_key)
    health = check_accesstrade_config(config, url=url, campaign_key=campaign_key)
    payload = build_tracking_payload(campaign_id=selected.campaign_id, urls=[url], utm=utm, channel_id=selected.channel_id)
    if not health.configured:
        return AccesstradeLinkResult(ok=False, original_url=url, payload=payload, error=",".join(health.reasons), dry_run=dry_run, campaign_key=selected.key)
    if dry_run:
        fallback_url = build_isclix_deep_link(url=url, campaign_id=selected.campaign_id, channel_id=selected.channel_id, utm=utm) if selected.campaign_id and selected.channel_id else url
        return AccesstradeLinkResult(ok=True, original_url=url, affiliate_url=fallback_url, payload=payload, dry_run=True, campaign_key=selected.key)

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
            if not affiliate_url and selected.campaign_id and selected.channel_id and str(parsed.get("status_code")) == "03":
                affiliate_url = build_isclix_deep_link(url=url, campaign_id=selected.campaign_id, channel_id=selected.channel_id, utm=utm)
            return AccesstradeLinkResult(ok=bool(affiliate_url), original_url=url, affiliate_url=affiliate_url, payload=payload, status=resp.status, error="" if affiliate_url else "affiliate_url_not_found", dry_run=False, campaign_key=selected.key)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
            message = parsed.get("message") or parsed.get("error") or body[:300]
        except json.JSONDecodeError:
            message = body[:300]
        return AccesstradeLinkResult(ok=False, original_url=url, payload=payload, status=exc.code, error=str(message), dry_run=False, campaign_key=selected.key)

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
