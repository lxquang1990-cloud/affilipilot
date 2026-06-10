from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from affilipilot.models import ProductCandidate
from affilipilot.provider_failures import ProviderBlockedError, classify_provider_failure

SHOPEE_VN_BASE = "https://shopee.vn"
PRODUCT_PATTERNS = (
    re.compile(r"-i\.(\d+)\.(\d+)", re.I),
    re.compile(r"/product/(\d+)/(\d+)", re.I),
)


@dataclass
class ShopeeApiProduct:
    shop_id: int
    item_id: int
    title: str
    url: str
    price_vnd: int | None = None
    image_url: str = ""
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    rating: float | None = None
    sold: int | None = None
    historical_sold: int | None = None
    liked_count: int | None = None
    review_count: int | None = None
    shop_location: str = ""
    is_official_shop: bool = False
    shopee_verified: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_candidate(self, *, category: str = "unknown", keyword: str = "") -> ProductCandidate:
        notes = [
            f"shop_id={self.shop_id}",
            f"item_id={self.item_id}",
            "source=shopee_public_api",
        ]
        if keyword:
            notes.append(f"seed_keyword={keyword}")
        if self.rating is not None:
            notes.append(f"rating={self.rating:.2f}")
        if self.sold is not None:
            notes.append(f"sold={self.sold}")
        if self.historical_sold is not None:
            notes.append(f"historical_sold={self.historical_sold}")
        if self.review_count is not None:
            notes.append(f"review_count={self.review_count}")
        if self.is_official_shop:
            notes.append("official_shop")
        if self.shopee_verified:
            notes.append("shopee_verified")
        return ProductCandidate(
            url=self.url,
            title=self.title,
            category=category,
            price_vnd=self.price_vnd,
            image_url=self.image_url,
            image_urls=self.image_urls,
            video_urls=self.video_urls,
            notes=";".join(notes),
            media_source="shopee_public_api",
            media_confidence="official",
            original_url=self.url,
        )


def parse_shopee_ids(url: str) -> tuple[int, int] | None:
    path = urllib.parse.urlparse(url).path
    for pattern in PRODUCT_PATTERNS:
        match = pattern.search(path)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def image_url(image_id: str) -> str:
    return f"https://down-vn.img.susercontent.com/file/{image_id}"


def _request_json(url: str, *, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://shopee.vn/",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        failure = classify_provider_failure("shopee", status_code=exc.code, body=body)
        if failure.state.value == "provider_blocked":
            raise ProviderBlockedError(failure) from exc
        raise


def _price_vnd(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        raw = int(value)
        return raw // 100000 if raw > 10_000_000 else raw
    except (TypeError, ValueError):
        return None


def _video_urls(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for video in item.get("video_info_list") or []:
        if not isinstance(video, dict):
            continue
        for key in ("url", "default_format", "video_url"):
            value = video.get(key)
            if isinstance(value, str) and value.startswith("http") and value not in urls:
                urls.append(value)
        for version in video.get("video_quality_url") or []:
            if isinstance(version, dict):
                value = version.get("url")
                if isinstance(value, str) and value.startswith("http") and value not in urls:
                    urls.append(value)
    return urls


def product_from_item(item: dict[str, Any], *, base_url: str = SHOPEE_VN_BASE) -> ShopeeApiProduct | None:
    try:
        shop_id = int(item.get("shopid"))
        item_id = int(item.get("itemid"))
    except (TypeError, ValueError):
        return None
    title = str(item.get("name") or "").strip()
    if not title:
        return None
    slug = urllib.parse.quote(re.sub(r"\s+", "-", title).strip("-"), safe="")
    url = f"{base_url.rstrip('/')}/{slug}-i.{shop_id}.{item_id}"
    images = [str(x) for x in (item.get("images") or []) if isinstance(x, str)]
    primary = str(item.get("image") or (images[0] if images else ""))
    if primary and primary not in images:
        images.insert(0, primary)
    rating_obj = item.get("item_rating") or {}
    rating_count = rating_obj.get("rating_count") if isinstance(rating_obj, dict) else None
    review_count = rating_count[0] if isinstance(rating_count, list) and rating_count else item.get("cmt_count")
    return ShopeeApiProduct(
        shop_id=shop_id,
        item_id=item_id,
        title=title,
        url=url,
        price_vnd=_price_vnd(item.get("price_min") or item.get("price")),
        image_url=image_url(images[0]) if images else "",
        image_urls=[image_url(img) for img in images[:12]],
        video_urls=_video_urls(item),
        rating=float(rating_obj.get("rating_star")) if isinstance(rating_obj, dict) and rating_obj.get("rating_star") is not None else None,
        sold=item.get("sold"),
        historical_sold=item.get("historical_sold"),
        liked_count=item.get("liked_count"),
        review_count=review_count,
        shop_location=str(item.get("shop_location") or ""),
        is_official_shop=bool(item.get("is_official_shop") or item.get("show_official_shop_label")),
        shopee_verified=bool(item.get("shopee_verified") or item.get("show_shopee_verified_label")),
        raw=item,
    )


def get_product_detail(shop_id: int, item_id: int, *, timeout: int = 30) -> ShopeeApiProduct | None:
    url = f"{SHOPEE_VN_BASE}/api/v4/item/get?shopid={shop_id}&itemid={item_id}"
    response = _request_json(url, timeout=timeout)
    item = response.get("data") or response.get("item")
    if not isinstance(item, dict):
        return None
    return product_from_item(item)


def search_products(keyword: str, *, limit: int = 20, newest: int = 0, timeout: int = 30) -> list[ShopeeApiProduct]:
    params = urllib.parse.urlencode({"by": "relevancy", "keyword": keyword, "limit": limit, "newest": newest, "order": "desc", "page_type": "search", "scenario": "PAGE_GLOBAL_SEARCH", "version": 2})
    url = f"{SHOPEE_VN_BASE}/api/v4/search/search_items?{params}"
    response = _request_json(url, timeout=timeout)
    items = []
    for row in response.get("items") or []:
        item = row.get("item_basic") if isinstance(row, dict) else None
        if isinstance(item, dict):
            product = product_from_item(item)
            if product:
                items.append(product)
    return items
