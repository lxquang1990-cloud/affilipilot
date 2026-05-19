from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.client import AccesstradeConfig, redact_for_audit

@dataclass
class CampaignInfo:
    campaign_id: str
    name: str = ""
    merchant: str = ""
    approval: str = ""
    status: str = ""
    category: str = ""
    sub_category: str = ""
    url: str = ""
    end_date: str = ""
    min_commission: float | None = None
    max_commission: float | None = None
    commission_type: str = ""
    cookie_expire: int | None = None
    source: str = ""
    aliases: list[str] | None = None

    @property
    def approved(self) -> bool:
        return self.approval.lower() == "successful"

    @property
    def running(self) -> bool:
        return str(self.status) in {"1", "running", "active", ""}

def _request_json(url: str, *, token: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}

def _campaigns_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        campaigns = data.get("campaigns")
        if isinstance(campaigns, list):
            return [item for item in campaigns if isinstance(item, dict)]
    return []

def _campaign_aliases(item: dict[str, Any]) -> list[str]:
    aliases: set[str] = set()
    for key in ("merchant", "adv_code", "name"):
        value = str(item.get(key) or "").strip().lower()
        if value:
            aliases.add(value)
    url = str(item.get("url") or "")
    host = urllib.parse.urlparse(url).netloc.lower()
    if host:
        aliases.add(host.removeprefix("www."))
    return sorted(aliases)


def _to_campaign_info(item: dict[str, Any], *, source: str = "") -> CampaignInfo:
    return CampaignInfo(
        campaign_id=str(item.get("campaign_id") or item.get("id") or ""),
        name=str(item.get("name") or ""),
        merchant=str(item.get("merchant") or ""),
        approval=str(item.get("approval") or ""),
        status=str(item.get("status") or ""),
        category=str(item.get("category_name") or item.get("category") or ""),
        sub_category=str(item.get("sub_category") or ""),
        url=str(item.get("url") or ""),
        end_date=str(item.get("end_date") or item.get("end_time") or ""),
        min_commission=item.get("min_commission"),
        max_commission=item.get("max_commission"),
        commission_type=str(item.get("commission_type") or ""),
        cookie_expire=item.get("cookie_expire") or item.get("cookie_duration"),
        source=source,
        aliases=_campaign_aliases(item),
    )


def _merge_campaigns(existing: CampaignInfo, incoming: CampaignInfo) -> CampaignInfo:
    merged = asdict(existing)
    incoming_data = asdict(incoming)
    for key, value in incoming_data.items():
        if key == "aliases":
            merged[key] = sorted(set(merged.get(key) or []) | set(value or []))
        elif key == "source":
            merged[key] = ",".join(sorted(set(filter(None, str(merged.get(key) or "").split(",") + str(value or "").split(",")))))
        elif value not in (None, "", []):
            merged[key] = value
    return CampaignInfo(**merged)


def _fetch_campaigns_url(url: str, *, token: str, timeout: int) -> tuple[list[CampaignInfo], dict[str, Any]]:
    response = _request_json(url, token=token, timeout=timeout)
    source = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    return [_to_campaign_info(item, source=source) for item in _campaigns_from_response(response)], response


def fetch_campaign_registry(*, config: AccesstradeConfig | None = None, approval: str = "successful", page_size: int = 100, timeout: int = 30, include_legacy: bool = True) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "campaigns": [], "raw_redacted": {}}
    params = {"page": "1", "page_size": str(page_size)}
    if approval:
        params["approval"] = approval
    base = config.base_url.rstrip("/")
    urls = [f"{base}/v1/cashback/campaigns?{urllib.parse.urlencode(params)}"]
    if include_legacy:
        legacy_params = {"limit": str(min(page_size, 50)), "page": "1"}
        if approval:
            legacy_params["approval"] = approval
        urls.append(f"{base}/v1/campaigns?{urllib.parse.urlencode(legacy_params)}")

    by_id: dict[str, CampaignInfo] = {}
    raw_redacted: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for url in urls:
        try:
            campaigns, response = _fetch_campaigns_url(url, token=config.token, timeout=timeout)
        except Exception as exc:  # pragma: no cover - network defensive path
            errors[url] = f"{type(exc).__name__}: {exc}"
            continue
        raw_redacted[url] = redact_for_audit(response)
        for campaign in campaigns:
            if not campaign.campaign_id:
                continue
            by_id[campaign.campaign_id] = _merge_campaigns(by_id[campaign.campaign_id], campaign) if campaign.campaign_id in by_id else campaign
    return {
        "ok": bool(by_id),
        "source_urls": urls,
        "campaigns": [asdict(item) for item in by_id.values()],
        "raw_redacted": raw_redacted,
        "errors": errors,
    }

def write_campaign_registry(out_path: str | Path, *, config: AccesstradeConfig | None = None, approval: str = "successful") -> dict[str, Any]:
    registry = fetch_campaign_registry(config=config, approval=approval)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return registry

def load_campaign_registry(path: str | Path) -> dict[str, CampaignInfo]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    result: dict[str, CampaignInfo] = {}
    for item in data.get("campaigns", []):
        info = CampaignInfo(**{key: item.get(key) for key in CampaignInfo.__dataclass_fields__})
        if info.campaign_id:
            result[info.campaign_id] = info
    return result

def campaign_block_reasons(campaign_id: str, registry_path: str | Path = "data/accesstrade-campaigns.json") -> list[str]:
    if not campaign_id:
        return ["missing_campaign_id"]
    registry = load_campaign_registry(registry_path)
    if not registry:
        return []
    info = registry.get(str(campaign_id))
    if not info:
        return ["campaign_not_in_approved_registry"]
    reasons: list[str] = []
    if not info.approved:
        reasons.append("campaign_not_approved")
    if not info.running:
        reasons.append("campaign_not_running")
    if info.end_date:
        # Keep expiry parsing conservative; exact formats vary in docs/API.
        pass
    return reasons
