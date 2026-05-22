from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from affilipilot.media_quality import upgrade_lazada_image_url
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


def _normalize_product_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl().rstrip("/")


def _item_score(item: ProductScanItem) -> int:
    gallery_bonus = min(len(item.raw.get("image_urls", []) or []), 3) * 5
    video_bonus = 5 if item.raw.get("video_urls") else 0
    return (30 if item.title else 0) + (20 if item.image_url else 0) + (10 if item.price_vnd else 0) + gallery_bonus + video_bonus


def _extract_media_urls(fragment: str, base_url: str) -> tuple[list[str], list[str]]:
    images: list[str] = []
    videos: list[str] = []
    for attr in ("src", "data-src", "data-lazy-src", "data-original"):
        for value in re.findall(rf'<img[^>]+{attr}=["\']([^"\']+)["\']', fragment, flags=re.I):
            url = _abs_url(value, base_url)
            if not url.lower().startswith("data:"):
                upgraded = upgrade_lazada_image_url(url)
                if upgraded not in images:
                    images.append(upgraded)
    for pattern in (r'<video[^>]+src=["\']([^"\']+)["\']', r'<source[^>]+src=["\']([^"\']+)["\']'):
        for value in re.findall(pattern, fragment, flags=re.I):
            url = _abs_url(value, base_url)
            if url not in videos:
                videos.append(url)
    return images, videos


def _dedupe_discovered_items(items: list[ProductScanItem], *, limit: int | None = None) -> list[ProductScanItem]:
    best: dict[str, ProductScanItem] = {}
    order: list[str] = []
    for item in items:
        key = _normalize_product_url(item.url)
        if key not in best:
            best[key] = item
            order.append(key)
            continue
        if _item_score(item) > _item_score(best[key]):
            best[key] = item
    out = [best[key] for key in order]
    return out[:limit] if limit else out


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
        image_urls, video_urls = _extract_media_urls(body, base_url)
        image = image_urls[0] if image_urls else ""
        price = None
        price_match = re.search(r'([0-9][0-9\.]{3,}\s*đ)', body, flags=re.I)
        if price_match:
            price = parse_price_vnd(price_match.group(1))
        items.append(ProductScanItem(
            url=_normalize_product_url(url),
            title=text[:180],
            category=category,
            price_vnd=price,
            image_url=image,
            source=source,
            notes="product_card_discovery",
            raw={"parser": "product_card_discovery", "media_source": "product_card_image" if image else "", "media_confidence": "high" if image else "", "image_urls": image_urls, "video_urls": video_urls},
        ))
    return _dedupe_discovered_items(items, limit=limit)



def _shopee_image_url(image_id: str) -> str:
    image_id = str(image_id or "").strip()
    if not image_id:
        return ""
    if image_id.startswith("http"):
        return image_id
    return f"https://down-vn.img.susercontent.com/file/{image_id}"

def _shopee_video_url(video: dict[str, Any]) -> str:
    video_id = str(video.get("video_id") or "").strip()
    if video_id.startswith("http"):
        return video_id
    if video_id:
        return f"https://down-vn.img.susercontent.com/file/{video_id}"
    formats = video.get("formats") if isinstance(video.get("formats"), list) else []
    for fmt in formats:
        if isinstance(fmt, dict) and fmt.get("path"):
            path = str(fmt["path"])
            if path.startswith("http"):
                return path
            return f"https://down-vn.img.susercontent.com/file/{path}"
    return ""

def _price_from_shopee(value: Any) -> int | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    # Shopee API prices are commonly scaled by 100000.
    if value >= 100000:
        return int(round(value / 100000))
    return int(value)

def _shopee_pdp_initial_items(html_text: str, *, page_url: str, source: str, category: str, limit: int | None = None) -> list[ProductScanItem]:
    if "shopee." not in urlparse(page_url).netloc.lower() and "shopee." not in page_url.lower():
        return []
    items: list[ProductScanItem] = []
    scripts = re.finditer(r'<script[^>]+type=["\']text/mfe-initial-data["\'][^>]*>(.*?)</script>', html_text, flags=re.I | re.S)
    for match in scripts:
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        cached = (((data.get("initialState") or {}).get("DOMAIN_PDP") or {}).get("data") or {}).get("PDP_BFF_DATA", {}).get("cachedMap", {})
        if not isinstance(cached, dict):
            continue
        for key, entry in cached.items():
            item = entry.get("item") if isinstance(entry, dict) else None
            if not isinstance(item, dict):
                continue
            shop_id = item.get("shop_id") or item.get("shopid")
            item_id = item.get("item_id") or item.get("itemid")
            if not shop_id or not item_id:
                if "/" in str(key):
                    shop_id, item_id = str(key).split("/", 1)
            if not shop_id or not item_id:
                continue
            images = [_shopee_image_url(img) for img in (item.get("images") or [])]
            images = [url for url in images if url]
            image = _shopee_image_url(item.get("image")) or (images[0] if images else "")
            if image and image not in images:
                images.insert(0, image)
            videos = [_shopee_video_url(v) for v in (item.get("video_info_list") or []) if isinstance(v, dict)]
            videos = [url for url in videos if url]
            price = _price_from_shopee(item.get("price") or item.get("price_min"))
            if price is None:
                for model in item.get("models") or []:
                    if isinstance(model, dict):
                        price = _price_from_shopee(model.get("price"))
                        if price is not None:
                            break
            title = _clean_text(str(item.get("title") or item.get("name") or ""))
            items.append(ProductScanItem(
                url=f"https://shopee.vn/product/{shop_id}/{item_id}",
                title=title,
                category=category,
                price_vnd=price,
                image_url=image,
                source=source,
                notes="shopee_pdp_initial_data",
                raw={
                    "parser": "shopee_pdp_initial_data",
                    "media_source": "shopee_pdp" if image else "",
                    "media_confidence": "high" if image else "",
                    "image_urls": images,
                    "video_urls": videos,
                    "rating_star": (item.get("item_rating") or {}).get("rating_star") if isinstance(item.get("item_rating"), dict) else None,
                    "shop_location": item.get("shop_location", ""),
                    "brand": item.get("brand", ""),
                },
            ))
            if limit and len(items) >= limit:
                return _dedupe_discovered_items(items, limit=limit)
    return _dedupe_discovered_items(items, limit=limit)

def discover_product_details_from_html(html_text: str, *, page_url: str, source: str = "AUTO", category: str = "unknown", limit: int = 10) -> DiscoveryResult:
    source = (source or "AUTO").upper()
    items = _shopee_pdp_initial_items(html_text, page_url=page_url, source=source, category=category, limit=limit)
    if not items:
        items = _card_product_items(html_text, base_url=page_url, source=source, category=category, limit=limit)
    seen = {_normalize_product_url(item.url) for item in items}
    if len(items) < limit:
        for url in _lazada_product_links_from_text(html_text, page_url):
            normalized = _normalize_product_url(url)
            if normalized in seen or not is_product_detail_url(normalized):
                continue
            items.append(ProductScanItem(url=normalized, title="", category=category, source=source, notes="product_url_discovery", raw={"parser": "product_url_discovery"}))
            seen.add(normalized)
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
