from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from affilipilot.models import ProductCandidate
from affilipilot.quality import is_product_detail_url

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AffiliPilot/1.0; +https://github.com/lxquang1990-cloud/affilipilot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

@dataclass
class ScanSource:
    url: str
    source: str = "AUTO"
    category: str = "unknown"
    campaign_key: str = ""

@dataclass
class ProductScanItem:
    url: str
    title: str = ""
    category: str = "unknown"
    price_vnd: int | None = None
    image_url: str = ""
    source: str = "AUTO"
    notes: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_candidate(self) -> ProductCandidate:
        return ProductCandidate(
            url=self.url,
            title=self.title,
            category=self.category or "unknown",
            price_vnd=self.price_vnd,
            image_url=self.image_url,
            notes=self.notes,
        )

@dataclass
class ScanResult:
    source: ScanSource
    fetched_at: str
    items: list[ProductScanItem]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": asdict(self.source),
            "fetched_at": self.fetched_at,
            "total": len(self.items),
            "errors": self.errors,
            "items": [asdict(item) for item in self.items],
        }




def resolve_http_url(url: str, *, timeout: int = 20) -> str:
    """Resolve redirects with browser-like headers; return final URL without fetching twice downstream."""
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl()

def fetch_html(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _abs_url(value: str, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(value.strip()))


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_price_vnd(value: str) -> int | None:
    if not value:
        return None
    text = html.unescape(str(value)).lower()
    if "liên hệ" in text or "contact" in text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None
    price = int(digits)
    if price < 1_000:
        return None
    return price


def _jsonld_products(html_text: str, *, base_url: str, source: str, category: str) -> list[ProductScanItem]:
    items: list[ProductScanItem] = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_text, flags=re.I | re.S):
        raw = html.unescape(match.group(1)).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        stack = list(nodes)
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                node_type = node.get("@type")
                if isinstance(node_type, list):
                    is_product = "Product" in node_type
                else:
                    is_product = node_type == "Product"
                if is_product:
                    offers = node.get("offers") if isinstance(node.get("offers"), dict) else {}
                    url = node.get("url") or offers.get("url") or base_url
                    image = node.get("image", "")
                    if isinstance(image, list):
                        image = image[0] if image else ""
                    items.append(ProductScanItem(
                        url=_abs_url(str(url), base_url),
                        title=_clean_text(str(node.get("name", ""))),
                        category=category,
                        price_vnd=parse_price_vnd(str(offers.get("price", ""))),
                        image_url=_abs_url(str(image), base_url) if image else "",
                        source=source,
                        notes="jsonld",
                        raw={"parser": "jsonld", "media_source": "jsonld_product_image" if image else "", "media_confidence": "high" if image else ""},
                    ))
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)
    return items


def _meta_fallback_product(html_text: str, *, base_url: str, source: str, category: str) -> list[ProductScanItem]:
    title = ""
    image_url = ""
    for prop in ("og:title", "twitter:title"):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']', html_text, flags=re.I)
        if m:
            title = _clean_text(m.group(1))
            break
    for prop in ("og:image", "twitter:image"):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']', html_text, flags=re.I)
        if m:
            image_url = _abs_url(m.group(1), base_url)
            break
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.I | re.S)
        title = _clean_text(m.group(1)) if m else ""
    if title:
        return [ProductScanItem(url=base_url, title=title, category=category, image_url=image_url, source=source, notes="meta_fallback", raw={"parser": "meta", "media_source": "product_detail_og_image" if image_url else "", "media_confidence": "high" if image_url else ""})]
    return []


def _cellphones_product_cards(html_text: str, *, base_url: str, source: str, category: str) -> list[ProductScanItem]:
    items: list[ProductScanItem] = []
    card_pattern = re.compile(r'<div class="product-info">(.*?)</div>\s*<div class="bottom-div">', flags=re.I | re.S)
    for card in card_pattern.findall(html_text):
        href = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', card, flags=re.I)
        title = re.search(r'<div class="product__name">\s*<h3>(.*?)</h3>', card, flags=re.I | re.S)
        price = re.search(r'<p class="product__price--show">(.*?)</p>', card, flags=re.I | re.S)
        image = re.search(r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\'][^>]+class="product__img"', card, flags=re.I | re.S)
        if not href or not title:
            continue
        name = _clean_text(title.group(1))
        if not name or name.lower() in {"xem tất cả", "cellphones logo"}:
            continue
        items.append(ProductScanItem(
            url=_abs_url(href.group(1), base_url),
            title=name,
            category=category,
            price_vnd=parse_price_vnd(price.group(1) if price else ""),
            image_url=_abs_url(image.group(1), base_url) if image else "",
            source=source,
            notes="cellphones_product_card",
            raw={"parser": "cellphones_product_card", "media_source": "product_card_image" if image else "", "media_confidence": "high" if image else ""},
        ))
    return items


def _generic_anchor_cards(html_text: str, *, base_url: str, source: str, category: str, product_detail_only: bool = False) -> list[ProductScanItem]:
    items: list[ProductScanItem] = []
    anchor_pattern = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', flags=re.I | re.S)
    for href, body in anchor_pattern.findall(html_text):
        text = _clean_text(body)
        if len(text) < 8:
            img_alt = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', body, flags=re.I)
            text = _clean_text(img_alt.group(1)) if img_alt else text
        if len(text) < 8:
            continue
        url = _abs_url(href, base_url)
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme.startswith("http"):
            continue
        if product_detail_only and not is_product_detail_url(url):
            continue
        image = ""
        img = re.search(r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']', body, flags=re.I)
        if img:
            image = _abs_url(img.group(1), base_url)
        price = None
        price_match = re.search(r'([0-9][0-9\.]{3,}\s*đ)', body, flags=re.I)
        if price_match:
            price = parse_price_vnd(price_match.group(1))
        items.append(ProductScanItem(url=url, title=text[:180], category=category, price_vnd=price, image_url=image, source=source, notes="anchor_card", raw={"parser": "anchor"}))
    return items


def _dedupe_items(items: list[ProductScanItem], *, limit: int | None = None) -> list[ProductScanItem]:
    seen: set[str] = set()
    out: list[ProductScanItem] = []
    for item in items:
        key = urllib.parse.urldefrag(item.url)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out


def _is_lazada_channel_or_listing_url(page_url: str) -> bool:
    parsed = urllib.parse.urlparse(page_url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    return "lazada.vn" in host and not is_product_detail_url(page_url) and (
        path.startswith("/tag/")
        or path.startswith("/shop/")
        or path.startswith("/catalog/")
        or path in {"/", ""}
        or "lazada.vn" in host
    )


def parse_products_from_html(html_text: str, *, page_url: str, source: str = "AUTO", category: str = "unknown", limit: int | None = None) -> list[ProductScanItem]:
    source = (source or "AUTO").upper()
    items: list[ProductScanItem] = []
    lazada_listing = _is_lazada_channel_or_listing_url(page_url) or source == "LAZADA"
    if source == "CELLPHONES" or "cellphones.com.vn" in page_url:
        items.extend(_cellphones_product_cards(html_text, base_url=page_url, source=source, category=category))
    if len(items) < (limit or 1):
        items.extend(_jsonld_products(html_text, base_url=page_url, source=source, category=category))
    if len(items) < (limit or 1):
        items.extend(_generic_anchor_cards(html_text, base_url=page_url, source=source, category=category, product_detail_only=lazada_listing))
    if not items and not lazada_listing:
        items.extend(_meta_fallback_product(html_text, base_url=page_url, source=source, category=category))
    return _dedupe_items(items, limit=limit)


def scan_url(url: str, *, source: str = "AUTO", category: str = "unknown", campaign_key: str = "", limit: int = 10, timeout: int = 30, html_text: str | None = None) -> ScanResult:
    errors: list[str] = []
    try:
        text = html_text if html_text is not None else fetch_html(url, timeout=timeout)
        items = parse_products_from_html(text, page_url=url, source=source, category=category, limit=limit)
    except Exception as exc:  # caller surfaces error; scanner should not crash workflow
        items = []
        errors.append(str(exc))
    return ScanResult(source=ScanSource(url=url, source=source, category=category, campaign_key=campaign_key), fetched_at=datetime.now(timezone.utc).isoformat(), items=items, errors=errors)


def write_scan_result(result: ScanResult, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def scan_result_to_input_lines(scan_json: str | Path, *, max_items: int | None = None) -> list[str]:
    data = json.loads(Path(scan_json).read_text(encoding="utf-8"))
    lines: list[str] = []
    for item in data.get("items", [])[:max_items]:
        parts = [item.get("url", "")]
        for key in ("title", "category", "price_vnd", "image_url", "notes"):
            value = item.get(key)
            if value not in (None, ""):
                out_key = "price" if key == "price_vnd" else key
                parts.append(f"{out_key}={value}")
        raw = item.get("raw") or {}
        for key in ("media_source", "media_confidence"):
            value = raw.get(key)
            if value:
                parts.append(f"{key}={value}")
        lines.append(" | ".join(parts))
    return lines
