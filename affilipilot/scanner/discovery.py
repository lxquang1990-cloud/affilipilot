from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from affilipilot.quality import is_product_detail_url
from affilipilot.scanner.core import ProductScanItem, ScanResult, ScanSource, _abs_url, _clean_text, parse_price_vnd, scan_url, write_scan_result

@dataclass
class DiscoveryResult:
    source_url: str
    source: str
    category: str
    discovered_at: str
    items: list[ProductScanItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_scan_result(self) -> ScanResult:
        return ScanResult(
            source=ScanSource(url=self.source_url, source=self.source, category=self.category),
            fetched_at=self.discovered_at,
            items=self.items,
            errors=self.errors,
        )

    def to_dict(self) -> dict[str, Any]:
        data = self.to_scan_result().to_dict()
        data["source_url"] = self.source_url
        data["discovered_at"] = self.discovered_at
        return data


def _host_matches(url: str, host_hint: str) -> bool:
    return host_hint in urlparse(url).netloc.lower()


def _lazada_product_links_from_text(text: str, base_url: str) -> list[str]:
    links: set[str] = set()
    patterns = [
        r'https?:\\/\\/www\.lazada\.vn\\/products\\/[^"\\<>\s]+?\.html',
        r'https?://www\.lazada\.vn/products/[^"\'<>\s]+?\.html',
        r'//www\.lazada\.vn/products/[^"\'<>\s]+?\.html',
        r'/products/[^"\'<>\s]+?\.html',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            url = match.replace('\\/', '/')
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = urljoin(base_url, url)
            links.add(url.split('?', 1)[0])
    return sorted(links)


def _card_product_items(html_text: str, *, base_url: str, source: str, category: str, limit: int | None = None) -> list[ProductScanItem]:
    items: list[ProductScanItem] = []
    anchor_pattern = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', flags=re.I | re.S)
    for href, body in anchor_pattern.findall(html_text):
        url = _abs_url(href, base_url)
        if not is_product_detail_url(url):
            continue
        text = _clean_text(body)
        img_alt = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', body, flags=re.I)
        if img_alt and (not text or len(text) < 12):
            text = _clean_text(img_alt.group(1))
        image = ""
        img = re.search(r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']', body, flags=re.I)
        if img:
            image = _abs_url(img.group(1), base_url)
        price = None
        price_match = re.search(r'([0-9][0-9\.]{3,}\s*đ)', body, flags=re.I)
        if price_match:
            price = parse_price_vnd(price_match.group(1))
        items.append(ProductScanItem(
            url=url,
            title=text[:180],
            category=category,
            price_vnd=price,
            image_url=image,
            source=source,
            notes="product_card_discovery",
            raw={"parser": "product_card_discovery", "media_source": "product_card_image" if image else "", "media_confidence": "high" if image else ""},
        ))
        if limit and len(items) >= limit:
            break
    return items


def discover_product_details_from_html(html_text: str, *, page_url: str, source: str = "AUTO", category: str = "unknown", limit: int = 10) -> DiscoveryResult:
    source = (source or "AUTO").upper()
    items = _card_product_items(html_text, base_url=page_url, source=source, category=category, limit=limit)
    seen = {item.url for item in items}
    if len(items) < limit:
        for url in _lazada_product_links_from_text(html_text, page_url):
            if url in seen or not is_product_detail_url(url):
                continue
            items.append(ProductScanItem(url=url, title="", category=category, source=source, notes="product_url_discovery", raw={"parser": "product_url_discovery"}))
            seen.add(url)
            if len(items) >= limit:
                break
    return DiscoveryResult(source_url=page_url, source=source, category=category, discovered_at=datetime.now(timezone.utc).isoformat(), items=items)


def discover_product_details(url: str, *, source: str = "AUTO", category: str = "unknown", limit: int = 10, timeout: int = 30, html_text: str | None = None, enrich: bool = False) -> DiscoveryResult:
    if html_text is None:
        from affilipilot.scanner.core import fetch_html
        html_text = fetch_html(url, timeout=timeout)
    result = discover_product_details_from_html(html_text, page_url=url, source=source, category=category, limit=limit)
    if enrich and result.items:
        enriched: list[ProductScanItem] = []
        errors = list(result.errors)
        for item in result.items[:limit]:
            if item.title and item.image_url:
                enriched.append(item)
                continue
            scan = scan_url(item.url, source=source, category=category, limit=1, timeout=timeout)
            if scan.items:
                enriched_item = scan.items[0]
                enriched_item.raw.setdefault("discovered_from", url)
                enriched.append(enriched_item)
            else:
                errors.extend(scan.errors)
                enriched.append(item)
        result.items = enriched
        result.errors = errors
    return result


def write_discovery_result(result: DiscoveryResult, out_path: str | Path) -> Path:
    return write_scan_result(result.to_scan_result(), out_path)
