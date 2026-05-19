from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.client import AccesstradeConfig, redact_for_audit

@dataclass
class AccesstradeDeal:
    id: str = ""
    name: str = ""
    content: str = ""
    merchant: str = ""
    domain: str = ""
    link: str = ""
    prod_link: str = ""
    image: str = ""
    start_time: str = ""
    end_time: str = ""
    discount_value: str = ""
    discount_percentage: str = ""
    coin_cap: str = ""
    coin_percentage: str = ""
    percentage_used: str = ""
    categories: list[Any] | None = None
    coupons: Any = None

    @property
    def active_hint(self) -> bool:
        if not self.end_time:
            return True
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(self.end_time[:19], fmt) >= datetime.now()
            except ValueError:
                continue
        return True

def _request_json(url: str, *, token: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET", headers={"Content-Type": "application/json", "Authorization": f"Token {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}

def _data_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("coupons", "offers", "data", "items"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []

def fetch_offer_merchants(*, config: AccesstradeConfig | None = None, timeout: int = 30) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "merchants": []}
    url = f"{config.base_url.rstrip('/')}/v1/offers_informations/merchant_list"
    response = _request_json(url, token=config.token, timeout=timeout)
    return {"ok": True, "merchants": _data_list(response), "raw_redacted": redact_for_audit(response)}

def fetch_offer_keywords(*, config: AccesstradeConfig | None = None, timeout: int = 30) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "keywords": []}
    url = f"{config.base_url.rstrip('/')}/v1/offers_informations/keyword_list"
    response = _request_json(url, token=config.token, timeout=timeout)
    return {"ok": True, "keywords": _data_list(response), "raw_redacted": redact_for_audit(response)}

def fetch_coupons(*, config: AccesstradeConfig | None = None, merchant: str = "", keyword: str = "", is_next_day_coupon: bool | None = None, limit: int = 50, page: int = 1, timeout: int = 30) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "deals": []}
    params: dict[str, str] = {"limit": str(limit), "page": str(page)}
    if merchant:
        params["merchant"] = merchant
    if keyword:
        params["keyword"] = keyword
    if is_next_day_coupon is not None:
        params["is_next_day_coupon"] = "true" if is_next_day_coupon else "false"
    url = f"{config.base_url.rstrip('/')}/v1/offers_informations/coupon?{urllib.parse.urlencode(params)}"
    response = _request_json(url, token=config.token, timeout=timeout)
    deals = []
    for item in _data_list(response):
        deal = AccesstradeDeal(
            id=str(item.get("id") or ""),
            name=str(item.get("name") or ""),
            content=str(item.get("content") or ""),
            merchant=str(item.get("merchant") or ""),
            domain=str(item.get("domain") or ""),
            link=str(item.get("link") or ""),
            prod_link=str(item.get("prod_link") or ""),
            image=str(item.get("image") or ""),
            start_time=str(item.get("start_time") or ""),
            end_time=str(item.get("end_time") or ""),
            discount_value=str(item.get("discount_value") or ""),
            discount_percentage=str(item.get("discount_percentage") or ""),
            coin_cap=str(item.get("coin_cap") or ""),
            coin_percentage=str(item.get("coin_percentage") or ""),
            percentage_used=str(item.get("percentage_used") or ""),
            categories=item.get("categories") if isinstance(item.get("categories"), list) else None,
            coupons=item.get("coupons"),
        )
        deals.append(deal)
    return {"ok": True, "source_url": url, "deals": [asdict(d) | {"active_hint": d.active_hint} for d in deals], "raw_redacted": redact_for_audit(response)}

def match_deals_for_product(product: dict[str, Any], deals: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    merchant = (product.get("merchant") or product.get("campaign_key") or "").lower()
    url = (product.get("url") or product.get("original_url") or "").lower()
    category = (product.get("category") or "").lower()
    scored = []
    for deal in deals:
        if not deal.get("active_hint", True):
            continue
        score = 0
        if merchant and merchant in str(deal.get("merchant", "")).lower():
            score += 20
        if deal.get("domain") and str(deal["domain"]).lower() in url:
            score += 20
        if category and category != "unknown" and category in json.dumps(deal.get("categories") or [], ensure_ascii=False).lower():
            score += 10
        if deal.get("discount_value") or deal.get("discount_percentage") or deal.get("coin_cap") or deal.get("coin_percentage"):
            score += 5
        if score >= 20:
            scored.append((score, deal))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:limit]]

def write_deals(out_path: str | Path, data: dict[str, Any]) -> Path:
    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
