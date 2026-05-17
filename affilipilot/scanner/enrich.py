from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from affilipilot.media import fetch_image
from affilipilot.scanner.core import fetch_html, parse_products_from_html

IMAGE_EXT_RE = re.compile(r'https?://[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'\s<>]*)?', re.I)
PRODUCT_URL_RE = re.compile(r'https?://(?:www\.)?lazada\.vn/products/[^"\'\s<>]+', re.I)
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
    html = fetch_html(url, timeout=timeout)
    items = parse_products_from_html(html, page_url=url, source=source, category=category, limit=1)
    product = items[0].__dict__ if items else {"url": url, "title": title, "category": category, "source": source, "image_url": ""}
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
