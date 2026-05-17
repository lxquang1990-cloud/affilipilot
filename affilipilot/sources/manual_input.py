from __future__ import annotations

import csv
from pathlib import Path

from affilipilot.models import ProductCandidate


def parse_link_lines(text: str) -> list[ProductCandidate]:
    products: list[ProductCandidate] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        url, *meta_parts = [part.strip() for part in line.split("|")]
        meta: dict[str, str] = {}
        for part in meta_parts:
            if "=" in part:
                key, value = part.split("=", 1)
                meta[key.strip()] = value.strip()
        products.append(ProductCandidate(
            url=url,
            title=meta.get("title", ""),
            category=meta.get("category", "unknown"),
            price_vnd=int(meta["price"]) if meta.get("price", "").isdigit() else None,
            image_url=meta.get("image_url", ""),
            image_path=meta.get("image_path", ""),
            video_url=meta.get("video_url", ""),
            video_path=meta.get("video_path", ""),
            affiliate_url=meta.get("affiliate_url", ""),
            tracking_url=meta.get("tracking_url", ""),
            notes=meta.get("notes", ""),
            media_source=meta.get("media_source", ""),
            media_confidence=meta.get("media_confidence", ""),
            original_url=meta.get("original_url", ""),
        ))
    return products


def parse_products_csv(path: str | Path) -> list[ProductCandidate]:
    products: list[ProductCandidate] = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(ProductCandidate(
                url=row.get("url", "").strip(),
                title=row.get("title", "").strip(),
                category=row.get("category", "unknown").strip() or "unknown",
                price_vnd=int(row["price_vnd"]) if row.get("price_vnd", "").isdigit() else None,
                commission_rate=float(row["commission_rate"]) if row.get("commission_rate") else None,
                image_url=row.get("image_url", "").strip(),
                image_path=row.get("image_path", "").strip(),
                video_url=row.get("video_url", "").strip(),
                video_path=row.get("video_path", "").strip(),
                affiliate_url=row.get("affiliate_url", "").strip(),
                tracking_url=row.get("tracking_url", "").strip(),
                notes=row.get("notes", "").strip(),
                media_source=row.get("media_source", "").strip(),
                media_confidence=row.get("media_confidence", "").strip(),
                original_url=row.get("original_url", "").strip(),
            ))
    return products
