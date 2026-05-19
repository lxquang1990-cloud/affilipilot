from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

from affilipilot.media import fetch_image
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
    if "media/catalog/product" in low or "/product/" in low:
        score += 40
    if "lazcdn.com" in low or "cellphones.com.vn" in low:
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
    return "shopee." in host and bool(SHOPEE_PRODUCT_RE.search(urlparse(url).path))

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
    for match in re.finditer(r'"url"\s*:\s*"(https?://[^"\\]+?\.mp4[^"\\]*)"', html_text):
        url = match.group(1).replace("\\/", "/")
        if url not in video_urls:
            video_urls.append(url)
    return {
        "image_urls": [_shopee_image_url(image_id) for image_id in image_ids[:limit]],
        "video_urls": video_urls[:3],
    }

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
    if _is_shopee_product_url(url):
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
        if media.get("image_urls"):
            product["image_url"] = media["image_urls"][0]
            product["image_urls"] = media["image_urls"]
            product.setdefault("raw", {})["shopee_media"] = media
            product["notes"] = (product.get("notes", "") + ";shopee_product_media").strip(";")
        if media.get("video_urls"):
            product["video_urls"] = media["video_urls"]
    if not product.get("image_url"):
        images = harvest_image_urls(html, title=title or product.get("title", ""), limit=5)
        if images:
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
        if prod.get("image_path") or post.get("files", {}).get("image") or post.get("media", {}).get("ok"):
            results.append({"post_id": post_id, "status": "already_has_media"})
            continue
        image_url = prod.get("image_url", "")
        if not image_url:
            try:
                enriched = enrich_product_from_url(prod.get("original_url") or prod.get("url", ""), title=prod.get("title", ""), category=prod.get("category", "unknown"), source="AUTO")
                image_url = enriched.get("image_url", "")
                if image_url:
                    prod["image_url"] = image_url
            except Exception as exc:
                results.append({"post_id": post_id, "status": "enrich_failed", "reason": type(exc).__name__})
        media_dir = out_dir / "media" / post_id
        media = fetch_image(image_url, media_dir, name_hint=prod.get("title") or post_id) if image_url else None
        if media and media.ok:
            prod["image_path"] = media.local_path
            post.setdefault("files", {})["image"] = media.local_path
            post["media"] = {"ok": True, "local_path": media.local_path, "media_type": media.media_type, "reasons": []}
            updated += 1
            results.append({"post_id": post_id, "status": "media_ready", "image_url": image_url, "local_path": media.local_path})
        else:
            failed += 1
            results.append({"post_id": post_id, "status": "media_missing", "reasons": media.reasons if media else ["missing_image_url"]})
    con.execute("update batches set manifest_json=? where batch_key=?", (json.dumps(manifest, ensure_ascii=False), batch_key))
    con.commit(); con.close()
    summary = {"batch_key": batch_key, "updated": updated, "failed": failed, "results": results}
    (out_dir / "media-enrich-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
