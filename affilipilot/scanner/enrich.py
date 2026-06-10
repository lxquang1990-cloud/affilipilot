from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

from affilipilot.media import fetch_image, prepare_product_media_gallery
from affilipilot.video_media import prepare_product_video
from affilipilot.marketplaces.shopee_public_api import get_product_detail, parse_shopee_ids
from affilipilot.scanner.core import fetch_html, parse_products_from_html

IMAGE_EXT_RE = re.compile(r'https?://[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'\s<>]*)?', re.I)
PRODUCT_URL_RE = re.compile(r'https?://(?:www\.)?lazada\.vn/products/[^"\'\s<>]+', re.I)
SHOPEE_PRODUCT_RE = re.compile(r"-i\.(\d+)\.(\d+)", re.I)
SHOPEE_IMAGE_ID_RE = re.compile(r"vn-[a-z0-9-]{20,}", re.I)
BAD_IMAGE_HINTS = ("logo", "sprite", "icon", "app-store", "google-play", "avatar", "feedback", "domino", "/g/tps/", "/ims-web/", "/us/domino/")


def _score_image_url(url: str, title: str = "") -> int:
    low = url.lower()
    score = 0
    if any(h in low for h in BAD_IMAGE_HINTS):
        score -= 50
    if any(h in low for h in ("/cache/750x750/", "/750x750/", "_720x720", "_800x800")):
        score += 80
    if any(h in low for h in ("/cache/100x100/", "/100x100/", "/cache/200x280/", "/200x280/", "/cache/280x280/", "/280x280/")):
        score -= 80
    if "media/catalog/product" in low or "/product/" in low:
        score += 40
    if "lazcdn.com" in low or "tikicdn.com" in low or "cellphones.com.vn" in low:
        score += 15
    if any(ext in low for ext in (".jpg", ".jpeg", ".png", ".webp")):
        score += 5
    for token in re.findall(r"[a-z0-9]{4,}", title.lower()):
        if token in low:
            score += 3
    return score


def harvest_image_urls(html_text: str, *, title: str = "", limit: int = 10) -> list[str]:
    urls = []
    for match in IMAGE_EXT_RE.findall(html_text):
        clean = match.replace("\\/", "/")
        clean = clean.rstrip("\\")
        urls.append(clean)
    seen = set()
    unique = []
    for url in urls:
        key = urllib.parse.urldefrag(url)[0]
        if key in seen:
            continue
        seen.add(key)
        unique.append(url)
    unique = [url for url in unique if _score_image_url(url, title) > 0]
    unique.sort(key=lambda u: _score_image_url(u, title), reverse=True)
    return unique[:limit]


def _is_shopee_product_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "shopee." in host and bool(parse_shopee_ids(url) or SHOPEE_PRODUCT_RE.search(urlparse(url).path))

def _shopee_image_url(image_id: str) -> str:
    return f"https://down-vn.img.susercontent.com/file/{image_id}"

def extract_shopee_product_media(html_text: str, *, limit: int = 12) -> dict[str, Any]:
    """Extract real Shopee PDP gallery media from embedded SSR data/meta tags.

    Shopee product pages include many static app assets (icons/splash screens). This
    helper only accepts CDN image IDs from product-shaped SSR fields or og:image,
    not arbitrary .png/.js assets from the shell page.
    """
    image_ids: list[str] = []

    def add(image_id: str) -> None:
        image_id = (image_id or "").strip()
        if image_id and image_id not in image_ids and SHOPEE_IMAGE_ID_RE.fullmatch(image_id):
            image_ids.append(image_id)

    og = re.search(r'property=["\']og:image["\']\s+content=["\']https?://[^"\']+/file/([^"\']+)["\']', html_text, re.I)
    if og:
        add(og.group(1))
    for match in re.finditer(r'"images"\s*:\s*\[([^\]]{1,3000})\]', html_text):
        for image_id in re.findall(r'"(vn-[a-z0-9-]{20,})"', match.group(1), re.I):
            add(image_id)
            if len(image_ids) >= limit:
                break
        if len(image_ids) >= limit:
            break
    video_urls = []
    for match in re.finditer(r'"(?:url|video_url)"\s*:\s*"(https?://[^"\\]+?\.mp4[^"\\]*)"', html_text):
        url = match.group(1).replace("\\/", "/")
        if url not in video_urls:
            video_urls.append(url)
    for match in re.finditer(r'"default_format"\s*:\s*\{[^{}]{0,1000}"url"\s*:\s*"(https?://[^"\\]+?\.mp4[^"\\]*)"', html_text):
        url = match.group(1).replace("\\/", "/")
        if url not in video_urls:
            video_urls.append(url)
    return {
        "image_urls": [_shopee_image_url(image_id) for image_id in image_ids[:limit]],
        "video_urls": video_urls[:3],
    }


def enrich_shopee_public_api_media(url: str, *, timeout: int = 8) -> dict[str, Any]:
    """Best-effort live Shopee detail enrichment for gallery/video.

    Shopee sometimes blocks this endpoint from server IPs; callers should treat
    failures as non-fatal and fall back to PDP HTML/Accesstrade media.
    """
    ids = parse_shopee_ids(url)
    if not ids:
        return {"image_urls": [], "video_urls": [], "price_vnd": None, "error": "missing_shopee_ids"}
    try:
        product = get_product_detail(ids[0], ids[1], timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"image_urls": [], "video_urls": [], "price_vnd": None, "error": type(exc).__name__}
    if not product:
        return {"image_urls": [], "video_urls": [], "price_vnd": None, "error": "not_found"}
    return {
        "image_urls": product.image_urls,
        "video_urls": product.video_urls,
        "price_vnd": product.price_vnd,
        "media_source": "shopee_public_api",
        "media_confidence": "official",
    }

def _normalize_lazada_media_url(url: str) -> str:
    url = (url or "").replace("\\/", "/").strip()
    if url.startswith("//"):
        url = "https:" + url
    return url

def extract_lazada_product_media(html_text: str, *, limit: int = 12) -> dict[str, Any]:
    """Extract Lazada PDP gallery images/video from SEO gallery and skuGalleries.

    Lazada exposes real product media in noscript SEO Gallery and embedded
    `skuGalleries`. Generic HTML harvesting often finds only one `og:image` or
    shell assets, so keep this source-specific and restrict to product CDN paths.
    """
    image_urls: list[str] = []
    video_urls: list[str] = []

    def add_image(url: str) -> None:
        clean = _normalize_lazada_media_url(url)
        low = clean.lower()
        if not clean.startswith("http"):
            return
        if not any(host in low for host in ("lazcdn.com", "slatic.net", "filebroker-cdn.lazada.vn")):
            return
        if any(hint in low for hint in BAD_IMAGE_HINTS):
            return
        if not re.search(r"\.(?:jpg|jpeg|png|webp)(?:_|\?|$)", low):
            return
        if clean not in image_urls:
            image_urls.append(clean)

    def add_video(url: str) -> None:
        clean = _normalize_lazada_media_url(url)
        if clean.startswith("http") and ".mp4" in clean.lower() and clean not in video_urls:
            video_urls.append(clean)

    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*itemprop=["\']contentUrl["\']', html_text, re.I):
        add_image(match.group(1))
    for match in re.finditer(r'itemprop=["\']contentUrl["\'][^>]+src=["\']([^"\']+)["\']', html_text, re.I):
        add_image(match.group(1))
    gallery_pos = html_text.find('"skuGalleries"')
    if gallery_pos >= 0:
        snippet = html_text[gallery_pos:gallery_pos + 25000]
        for match in re.finditer(r'"(?:src|poster)"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', snippet):
            value = bytes(match.group(1), "utf-8").decode("unicode_escape", errors="ignore")
            if ".mp4" in value.lower() or "cloud.video.lazada.com" in value.lower():
                add_video(value)
            else:
                add_image(value)
    for match in re.finditer(r'"contentUrl"\s*:\s*"(https?://[^"\\]+?\.mp4[^"\\]*)"', html_text, re.I):
        add_video(match.group(1))
    return {"image_urls": image_urls[:limit], "video_urls": video_urls[:3]}

def harvest_lazada_product_urls(html_text: str, *, limit: int = 20) -> list[str]:
    urls = []
    for match in PRODUCT_URL_RE.findall(html_text):
        urls.append(match.replace("\\/", "/"))
    seen = set()
    out = []
    for url in urls:
        key = urllib.parse.urldefrag(url)[0].split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def enrich_product_from_url(url: str, *, title: str = "", category: str = "unknown", source: str = "AUTO", timeout: int = 30) -> dict[str, Any]:
    shopee_api_media: dict[str, Any] = {}
    if _is_shopee_product_url(url):
        shopee_api_media = enrich_shopee_public_api_media(url, timeout=min(timeout, 8))
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read().decode(charset, errors="replace")
    else:
        html = fetch_html(url, timeout=timeout)
    items = parse_products_from_html(html, page_url=url, source=source, category=category, limit=1)
    product = items[0].__dict__ if items else {"url": url, "title": title, "category": category, "source": source, "image_url": ""}
    if _is_shopee_product_url(url):
        media = extract_shopee_product_media(html, limit=12)
        image_urls = shopee_api_media.get("image_urls") or media.get("image_urls")
        video_urls = shopee_api_media.get("video_urls") or media.get("video_urls")
        if shopee_api_media.get("price_vnd"):
            product["price_vnd"] = shopee_api_media["price_vnd"]
        if image_urls:
            product["image_url"] = image_urls[0]
            product["image_urls"] = image_urls
            product.setdefault("raw", {})["shopee_media"] = {"pdp": media, "api": shopee_api_media}
            product["media_source"] = shopee_api_media.get("media_source") or "shopee_pdp"
            product["media_confidence"] = shopee_api_media.get("media_confidence") or "official"
            product["notes"] = (product.get("notes", "") + ";shopee_product_media").strip(";")
        if video_urls:
            product["video_urls"] = video_urls
            product["video_url"] = video_urls[0]
            product["notes"] = (product.get("notes", "") + ";shopee_product_video").strip(";")
    elif "lazada." in urlparse(url).netloc.lower():
        media = extract_lazada_product_media(html, limit=12)
        if media.get("image_urls"):
            product["image_url"] = media["image_urls"][0]
            product["image_urls"] = media["image_urls"]
            product.setdefault("raw", {})["lazada_media"] = media
            product["media_source"] = "lazada_pdp"
            product["media_confidence"] = "official"
            product["notes"] = (product.get("notes", "") + ";lazada_product_media").strip(";")
        if media.get("video_urls"):
            product["video_urls"] = media["video_urls"]
    images = [] if _is_shopee_product_url(url) else harvest_image_urls(html, title=title or product.get("title", ""), limit=8)
    if images and not product.get("image_urls"):
        product["image_urls"] = images
    if not product.get("image_url") and images:
        product["image_url"] = images[0]
        product.setdefault("raw", {})["image_candidates"] = images
        product["notes"] = (product.get("notes", "") + ";image_harvest").strip(";")
    product["product_urls"] = harvest_lazada_product_urls(html, limit=10)
    return product


def enrich_batch_media(db_path: str | Path, *, batch_key: str, out_dir: str | Path, limit: int | None = None) -> dict[str, Any]:
    db_path = Path(db_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    row = con.execute("select manifest_json from batches where batch_key=?", (batch_key,)).fetchone()
    if not row:
        con.close()
        raise KeyError(batch_key)
    manifest = json.loads(row[0])
    updated = 0
    failed = 0
    results = []
    for post in manifest.get("posts", [])[:limit]:
        prod = post.get("product", {})
        post_id = post.get("post_id", "post")
        existing_images = post.get("files", {}).get("images") or []
        has_video_file = bool(prod.get("video_path") or post.get("files", {}).get("video"))
        has_video_url = bool(prod.get("video_url") or prod.get("video_urls"))
        source_url = prod.get("original_url") or prod.get("url", "")
        is_shopee_product = _is_shopee_product_url(source_url)
        needs_video_probe = is_shopee_product and not (has_video_file or has_video_url)
        image_url_count = len(prod.get("image_urls") or []) + (1 if prod.get("image_url") else 0)
        needs_gallery_probe = is_shopee_product and image_url_count < 2
        if (not needs_video_probe) and (not needs_gallery_probe) and (prod.get("image_path") or post.get("files", {}).get("image") or post.get("media", {}).get("ok")) and (existing_images or not prod.get("image_urls")):
            results.append({"post_id": post_id, "status": "already_has_media"})
            continue
        image_url = prod.get("image_url", "")
        try:
            from affilipilot.media_quality import BAD_MEDIA_NAME_HINTS
            prod["image_urls"] = [
                url for url in (prod.get("image_urls") or [])
                if not any(hint in url.lower() for hint in BAD_MEDIA_NAME_HINTS)
            ]
            has_bad_media = any(hint in f"{image_url} {prod.get('image_path', '')}".lower() for hint in BAD_MEDIA_NAME_HINTS)
        except Exception:  # noqa: BLE001
            has_bad_media = False
        if not image_url or has_bad_media or needs_video_probe or needs_gallery_probe:
            try:
                enriched = enrich_product_from_url(source_url, title=prod.get("title", ""), category=prod.get("category", "unknown"), source="AUTO")
                image_url = enriched.get("image_url", "") or image_url
                if image_url:
                    prod["image_url"] = image_url
                    prod["image_urls"] = enriched.get("image_urls") or prod.get("image_urls", [])
                    prod["media_source"] = enriched.get("media_source") or ("shopee_pdp" if "shopee_product_media" in enriched.get("notes", "") else prod.get("media_source", ""))
                    prod["media_confidence"] = enriched.get("media_confidence") or ("official" if prod.get("media_source") == "shopee_pdp" else prod.get("media_confidence", ""))
                if enriched.get("price_vnd"):
                    prod["price_vnd"] = enriched["price_vnd"]
                if enriched.get("video_urls"):
                    prod["video_urls"] = enriched.get("video_urls") or prod.get("video_urls", [])
                    prod["video_url"] = prod["video_urls"][0] if prod["video_urls"] else prod.get("video_url", "")
            except Exception as exc:
                results.append({"post_id": post_id, "status": "enrich_failed", "reason": type(exc).__name__})
        media_dir = out_dir / "media" / post_id
        gallery_results = prepare_product_media_gallery(prod, media_dir) if (prod.get("image_urls") or prod.get("image_url")) else []
        media = gallery_results[0] if gallery_results else (fetch_image(image_url, media_dir, name_hint=prod.get("title") or post_id) if image_url else None)
        video_status = "no_video"
        video_urls = prod.get("video_urls") or ([prod.get("video_url")] if prod.get("video_url") else [])
        if video_urls and not (prod.get("video_path") or post.get("files", {}).get("video")):
            video = prepare_product_video(prod, out_dir / "video" / post_id)
            if video.ok:
                prod["video_path"] = video.local_path
                post.setdefault("files", {})["video"] = video.local_path
                video_status = "video_ready"
            else:
                video_status = "video_missing:" + ",".join(video.reasons[:3])
        if media and media.ok:
            prod["image_path"] = media.local_path
            post.setdefault("files", {})["image"] = media.local_path
            post.setdefault("files", {})["images"] = [item.local_path for item in gallery_results if item.ok]
            post["media"] = {"ok": True, "local_path": media.local_path, "media_type": media.media_type, "reasons": [], "video_status": video_status, "gallery_count": len(post.get("files", {}).get("images", []))}
            updated += 1
            results.append({"post_id": post_id, "status": "media_ready", "image_url": image_url, "local_path": media.local_path, "video_status": video_status})
        else:
            failed += 1
            results.append({"post_id": post_id, "status": "media_missing", "reasons": media.reasons if media else ["missing_image_url"]})
    con.execute("update batches set manifest_json=? where batch_key=?", (json.dumps(manifest, ensure_ascii=False), batch_key))
    con.commit(); con.close()
    summary = {"batch_key": batch_key, "updated": updated, "failed": failed, "results": results}
    (out_dir / "media-enrich-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
