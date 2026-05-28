from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.client import AccesstradeConfig, redact_for_audit
from affilipilot.models import ProductCandidate

@dataclass
class AccesstradeProduct:
    url: str
    title: str = ""
    category: str = "unknown"
    price_vnd: int | None = None
    discount_vnd: int | None = None
    discount_rate: float | None = None
    image_url: str = ""
    affiliate_url: str = ""
    product_id: str = ""
    merchant: str = ""
    source: str = "accesstrade"
    raw: dict[str, Any] | None = None

    def to_candidate(self) -> ProductCandidate:
        notes = []
        if self.discount_vnd is not None:
            notes.append(f"discount_vnd={self.discount_vnd}")
        if self.discount_rate is not None:
            notes.append(f"discount_rate={self.discount_rate}")
        if self.merchant:
            notes.append(f"merchant={self.merchant}")
        if self.product_id:
            notes.append(f"product_id={self.product_id}")
        return ProductCandidate(
            url=self.url,
            title=self.title,
            category=self.category or "unknown",
            price_vnd=self.discount_vnd or self.price_vnd,
            image_url=self.image_url,
            affiliate_url=self.affiliate_url,
            tracking_url=self.affiliate_url,
            notes=";".join(notes),
            media_source="accesstrade_api",
            media_confidence="official",
            original_url=self.url,
        )

def _request_json(url: str, *, token: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET", headers={"Content-Type": "application/json", "Authorization": f"Token {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}

def _items(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("products", "items", "coupons", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []

def _int_money(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None

def _discount_rate(item: dict[str, Any]) -> float | None:
    value = item.get("discount_rate")
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sale_price(item: dict[str, Any]) -> int | None:
    """Return the actual sale price.

    Official Accesstrade datafeeds define:
    - `price`: original/list price
    - `discount`: sale price after discount
    - `discount_amount`: amount reduced
    - `discount_rate`: percent reduced

    Some observed Shopee rows use `discount=30` while `discount_amount` nearly
    equals `price`, meaning `discount` is effectively a percent. Keep this as a
    compatibility fallback after the official semantics.
    """
    price = _int_money(item.get("price"))
    discount = _int_money(item.get("discount"))
    discount_amount = _int_money(item.get("discount_amount"))
    discount_rate = _discount_rate(item)
    if discount and price:
        if 0 < discount <= 100 and discount_amount and discount_amount >= max(1, price - discount - 1):
            return max(0, int(round(price * (100 - discount) / 100)))
        if discount >= 1_000 or discount < price:
            return discount
        return discount
    if price and discount_rate and 0 < discount_rate <= 100:
        return max(0, int(round(price * (100 - discount_rate) / 100)))
    if price and discount_amount and 0 < discount_amount < price:
        return max(0, price - discount_amount)
    return discount or price

def _product_from_item(item: dict[str, Any], *, source: str) -> AccesstradeProduct:
    price = _int_money(item.get("price"))
    sale_price = _sale_price(item)
    discount = _int_money(item.get("discount"))
    category = str(item.get("category_name") or item.get("cate") or item.get("product_category") or "unknown")
    return AccesstradeProduct(
        url=str(item.get("url") or item.get("link") or ""),
        title=str(item.get("name") or item.get("title") or ""),
        category=category,
        price_vnd=price,
        discount_vnd=sale_price,
        discount_rate=float(item.get("discount_rate")) if item.get("discount_rate") not in (None, "") else None,
        image_url=str(item.get("image") or item.get("image_url") or ""),
        affiliate_url=str(item.get("aff_link") or item.get("prod_link") or ""),
        product_id=str(item.get("product_id") or item.get("sku") or ""),
        merchant=str(item.get("merchant") or item.get("campaign") or item.get("domain") or ""),
        source=source,
        raw=item,
    )

def fetch_datafeeds(*, config: AccesstradeConfig | None = None, campaign: str = "", domain: str = "", status_discount: str = "", discount_rate_from: str = "", discount_rate_to: str = "", discount_amount_from: str = "", discount_amount_to: str = "", discount_from: str = "", discount_to: str = "", price_from: str = "", price_to: str = "", update_from: str = "", update_to: str = "", page: int = 1, limit: int = 50, timeout: int = 30) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "products": []}
    limit = max(1, min(int(limit), 200))
    params = {"page": str(page), "limit": str(limit)}
    for key, value in {"campaign": campaign, "domain": domain, "status_discount": status_discount, "discount_rate_from": discount_rate_from, "discount_rate_to": discount_rate_to, "discount_amount_from": discount_amount_from, "discount_amount_to": discount_amount_to, "discount_from": discount_from, "discount_to": discount_to, "price_from": price_from, "price_to": price_to, "update_from": update_from, "update_to": update_to}.items():
        if value not in (None, ""):
            params[key] = str(value)
    url = f"{config.base_url.rstrip('/')}/v1/datafeeds?{urllib.parse.urlencode(params)}"
    response = _request_json(url, token=config.token, timeout=timeout)
    products = [_product_from_item(item, source="accesstrade_datafeed") for item in _items(response)]
    return {"ok": True, "source": "datafeeds", "source_url": url, "total": response.get("total", len(products)), "products": [asdict(p) for p in products], "raw_redacted": redact_for_audit(response)}

def fetch_top_products(*, config: AccesstradeConfig | None = None, merchant: str = "", date_from: str = "", date_to: str = "", timeout: int = 30) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "products": []}
    params = {k: v for k, v in {"merchant": merchant, "date_from": date_from, "date_to": date_to}.items() if v}
    url = f"{config.base_url.rstrip('/')}/v1/top_products" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    response = _request_json(url, token=config.token, timeout=timeout)
    products = [_product_from_item(item, source="accesstrade_top_products") for item in _items(response)]
    return {"ok": True, "source": "top_products", "source_url": url, "total": response.get("total", len(products)), "products": [asdict(p) for p in products], "raw_redacted": redact_for_audit(response)}

def write_products_input(products: list[dict[str, Any]], out_path: str | Path, *, category_override: str = "") -> Path:
    lines = []
    for p in products:
        cand = AccesstradeProduct(**{k: p.get(k) for k in AccesstradeProduct.__dataclass_fields__}).to_candidate()
        if category_override:
            cand.category = category_override
        parts = [cand.url]
        for key, value in {
            "title": cand.title,
            "category": cand.category,
            "price": cand.price_vnd,
            "image_url": cand.image_url,
            "affiliate_url": cand.affiliate_url,
            "tracking_url": cand.tracking_url,
            "notes": cand.notes,
            "media_source": cand.media_source,
            "media_confidence": cand.media_confidence,
            "original_url": cand.original_url,
        }.items():
            if value not in (None, ""):
                parts.append(f"{key}={value}")
        lines.append(" | ".join(str(x) for x in parts))
    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out
