from __future__ import annotations

import re
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from affilipilot.accesstrade.catalog import _sale_price, fetch_datafeeds
from affilipilot.models import ProductCandidate
from affilipilot.scanner.core import resolve_http_url


def _host_domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _lazada_ids(url: str) -> tuple[str, str]:
    path = urlparse(url or "").path
    m = re.search(r"-i(\d+)-s(\d+)", path)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"pdp-i(\d+)", path)
    if m:
        return m.group(1), ""
    return "", ""


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _title_score(a: str, b: str) -> float:
    at = {t for t in re.split(r"\W+", _norm_text(a)) if len(t) >= 3}
    bt = {t for t in re.split(r"\W+", _norm_text(b)) if len(t) >= 3}
    if not at or not bt:
        return 0.0
    return len(at & bt) / max(len(at), len(bt))


def _match_score(product: ProductCandidate, item: dict[str, Any], resolved_url: str) -> int:
    score = 0
    item_url = str(item.get("url") or "")
    if item_url and item_url.split("?", 1)[0] == resolved_url.split("?", 1)[0]:
        score += 100
    p_item, s_item = _lazada_ids(item_url)
    p_in, s_in = _lazada_ids(resolved_url)
    if p_item and p_in and p_item == p_in:
        score += 80
    if s_item and s_in and s_item == s_in:
        score += 30
    title_ratio = _title_score(product.title, str(item.get("name") or item.get("title") or ""))
    if title_ratio >= 0.65:
        score += int(40 * title_ratio)
    return score


def _apply_item(product: ProductCandidate, item: dict[str, Any], *, resolved_url: str, score: int) -> ProductCandidate:
    price = _sale_price(item)
    price_vnd = price if price is not None else product.price_vnd
    notes = product.notes or ""
    add = ["accesstrade_enriched", f"accesstrade_match_score={score}"]
    if item.get("merchant"):
        add.append(f"merchant={item.get('merchant')}")
    if item.get("product_id") or item.get("sku"):
        add.append(f"product_id={item.get('product_id') or item.get('sku')}")
    notes = (notes + ";" if notes else "") + ";".join(add)
    return replace(
        product,
        url=str(item.get("url") or resolved_url or product.url),
        title=str(item.get("name") or item.get("title") or product.title),
        category=str(item.get("cate") or item.get("category_name") or item.get("product_category") or product.category or "unknown"),
        price_vnd=price_vnd,
        image_url=str(item.get("image") or item.get("image_url") or product.image_url),
        affiliate_url=str(item.get("aff_link") or product.affiliate_url),
        tracking_url=str(item.get("aff_link") or product.tracking_url),
        original_url=str(item.get("url") or resolved_url or product.original_url or product.url),
        media_source="accesstrade_api" if (item.get("image") or item.get("image_url")) else product.media_source,
        media_confidence="official" if (item.get("image") or item.get("image_url")) else product.media_confidence,
        notes=notes,
    )


def enrich_product_from_accesstrade(product: ProductCandidate, *, min_score: int = 80, limit: int = 200, pages: int = 5, resolve_redirects: bool = True) -> ProductCandidate:
    """Prefer Accesstrade product metadata for price/title/image when a reliable match exists.

    This is intentionally conservative: no guessed price is applied unless the datafeed item
    matches by exact URL/Lazada item id or strong title overlap.
    """
    source_url = product.original_url or product.url
    if not source_url:
        return product
    resolved_url = source_url
    if resolve_redirects and _host_domain(source_url) in {"shorten.asia", "s.shopee.vn"}:
        try:
            resolved_url = resolve_http_url(source_url, timeout=15)
        except Exception:  # noqa: BLE001
            resolved_url = source_url
    domain = _host_domain(resolved_url)
    if not domain or domain in {"go.isclix.com", "shorten.asia"}:
        return product
    best: tuple[int, dict[str, Any]] | None = None
    max_pages = max(1, min(int(pages or 1), 10))
    for page in range(1, max_pages + 1):
        try:
            data = fetch_datafeeds(domain=domain, limit=limit, page=page, timeout=30)
        except Exception:  # noqa: BLE001
            break
        raw_items = data.get("raw_redacted", {}).get("data", []) or []
        if not raw_items:
            break
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            score = _match_score(product, item, resolved_url)
            if best is None or score > best[0]:
                best = (score, item)
            if score >= 100:
                return _apply_item(product, item, resolved_url=resolved_url, score=score)
    if not best or best[0] < min_score:
        return product
    return _apply_item(product, best[1], resolved_url=resolved_url, score=best[0])
