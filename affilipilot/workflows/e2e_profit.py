from __future__ import annotations

import hashlib
import json
import re
import urllib.error
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.campaigns import write_campaign_registry
from affilipilot.accesstrade.catalog import fetch_datafeeds, fetch_top_products, write_products_input
from affilipilot.accesstrade.shopee_sheets import fetch_shopee_sheet_products
from affilipilot.content.early_filter import evaluate_early_product_filter
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.content.product_taste import evaluate_product_taste
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.quality import evaluate_quality_gate
from affilipilot.scoring.portfolio import select_portfolio
from affilipilot.scanner.enrich import enrich_product_from_url
from affilipilot.scoring.product_score import score_product
from affilipilot.sources.manual_input import parse_link_lines
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input
from affilipilot.workflows.approval import create_approval_batch
from affilipilot.scanner.enrich import enrich_batch_media
from affilipilot.snailbot_integration import AffiliPilotRunState, append_event, write_run_state

# Accesstrade docs notes used here:
# - Datafeed does not document category filtering; `target_category` is internal only.
# - Some datafeeds include promotion details per product; prefer status_discount feeds.
# - API rate limit is 30 requests/minute, so keep default source count small.
DEFAULT_SOURCE_CACHE_DIR = Path("data/cache/accesstrade/sources")
DEFAULT_SOURCE_CURSOR_PATH = Path("data/source-cursors.json")

DEFAULT_PROFIT_SOURCES = [
    # Primary flow: official Accesstrade/Shopee support sheets. Rotate offsets
    # per sheet so scheduled/manual E2E explores deeper rows instead of always
    # re-reading only the top of each sheet.
    {"kind": "shopee_sheet", "name": "shopee_best_sellers_sheet", "sheet_key": "shopee_best_sellers", "limit": 80, "campaign_key": "SHOPEE"},
    {"kind": "shopee_sheet", "name": "shopee_major_programs_sheet", "sheet_key": "shopee_major_programs", "limit": 80, "campaign_key": "SHOPEE"},
    {"kind": "shopee_sheet", "name": "shopee_brand_bonus_sheet", "sheet_key": "shopee_brand_bonus", "limit": 80, "campaign_key": "SHOPEE"},
    # Secondary fallback sources.
    {"kind": "datafeed", "name": "lazada_home_appliance", "domain": "lazada.vn", "target_category": "home_appliance", "status_discount": "1", "limit": 30, "campaign_key": "LAZADA"},
    {"kind": "datafeed", "name": "lazada_electronics", "domain": "lazada.vn", "target_category": "electronics", "status_discount": "1", "limit": 30, "campaign_key": "LAZADA"},
    {"kind": "datafeed", "name": "lazada_computing", "domain": "lazada.vn", "target_category": "computing", "status_discount": "1", "limit": 30, "campaign_key": "LAZADA"},
    {"kind": "datafeed", "name": "lazada_home_midprice", "domain": "lazada.vn", "target_category": "home_living", "price_from": "80000", "price_to": "1500000", "limit": 30, "campaign_key": "LAZADA"},
    {"kind": "datafeed", "name": "lazada_appliance_midprice", "domain": "lazada.vn", "target_category": "home_appliance", "price_from": "80000", "price_to": "2000000", "limit": 30, "campaign_key": "LAZADA"},
    {"kind": "datafeed", "name": "shopee_mid_price", "domain": "shopee.vn", "price_from": "100000", "price_to": "1500000", "limit": 30, "campaign_key": "SHOPEE"},
    {"kind": "datafeed", "name": "shopee_general", "domain": "shopee.vn", "limit": 30, "campaign_key": "SHOPEE"},
    {"kind": "top_products", "name": "lazada_top", "merchant": "lazada", "limit": 50, "campaign_key": "LAZADA"},
    {"kind": "top_products", "name": "shopee_top", "merchant": "shopee", "limit": 50, "campaign_key": "SHOPEE"},
]

def _post_text(post: dict[str, Any]) -> str:
    path = Path(post.get("files", {}).get("post_text", ""))
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""

def _norm_url(url: str) -> str:
    value = (url or "").strip().lower()
    if not value:
        return ""
    if value.startswith("shopee."):
        value = "https://" + value
    value = value.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    match = re.search(r"shopee\.(?:vn|com)/(?:product/)?([0-9]+)/([0-9]+)", value)
    if not match:
        match = re.search(r"(?:^|-)i\.([0-9]+)\.([0-9]+)(?:$|[./-])", value)
    if match:
        return f"shopee:{match.group(1)}:{match.group(2)}"
    return value


def _norm_alias(value: str) -> str:
    return (value or "").strip().lower().removeprefix("www.")


def _campaign_lookup(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for campaign in registry.get("campaigns", []):
        if str(campaign.get("approval", "")).lower() != "successful":
            continue
        if str(campaign.get("status", "")) not in {"1", "running", "active", ""}:
            continue
        for alias in campaign.get("aliases") or []:
            if alias:
                lookup[_norm_alias(alias)] = campaign
        url = campaign.get("url", "")
        if url:
            host = __import__("urllib.parse").parse.urlparse(url).netloc
            if host:
                lookup[_norm_alias(host)] = campaign
    return lookup


def _source_campaign_id(source: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> str:
    for value in (source.get("merchant", ""), source.get("campaign", ""), source.get("domain", "")):
        campaign = lookup.get(_norm_alias(str(value)))
        if campaign and campaign.get("campaign_id"):
            return str(campaign["campaign_id"])
    return ""

def _line_for_product(product) -> str:
    parts = [product.url]
    for key, value in {
        "title": product.title,
        "category": product.category,
        "price": product.price_vnd,
        "commission_rate": product.commission_rate,
        "image_url": product.image_url,
        "image_urls": ",".join(product.image_urls or []),
        "affiliate_url": product.affiliate_url,
        "tracking_url": product.tracking_url,
        "notes": product.notes,
        "media_source": product.media_source,
        "media_confidence": product.media_confidence,
        "original_url": product.original_url,
        "campaign_id": product.campaign_id,
        "campaign_key": product.campaign_key,
    }.items():
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return " | ".join(str(part) for part in parts)



def _commission_rate_from_campaign(campaign: dict[str, Any] | None) -> tuple[float | None, list[str]]:
    if not campaign:
        return None, ["commission_policy:missing_campaign_match"]
    raw = campaign.get("max_commission") or campaign.get("min_commission")
    if raw in (None, ""):
        return None, ["commission_policy:missing_rate"]
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        return None, ["commission_policy:invalid_rate"]
    # Accesstrade campaign APIs may return either 8.0 or 0.08. Normalize to ratio.
    if rate > 1:
        rate = rate / 100
    return max(0.0, rate), [f"commission_policy:campaign_rate={rate:.4f}"]

def _campaign_for_source(source: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for value in (source.get("merchant", ""), source.get("campaign", ""), source.get("domain", "")):
        campaign = lookup.get(_norm_alias(str(value)))
        if campaign:
            return campaign
    return None

def _conversion_likelihood(product, *, base_score: int, taste_score: int) -> tuple[float, list[str]]:
    likelihood = 0.02 + (max(0, min(100, base_score)) / 100) * 0.06 + (max(0, min(100, taste_score)) / 100) * 0.04
    reasons = [f"conversion_likelihood_base={likelihood:.4f}"]
    notes = (product.notes or "").lower()
    if "discount_rate=" in notes:
        try:
            rate = float(notes.split("discount_rate=", 1)[1].split(";", 1)[0].split(" ", 1)[0])
            if rate > 1:
                rate = rate / 100
            if rate >= 0.30:
                likelihood += 0.015
                reasons.append("conversion_likelihood_discount>=30%+0.015")
            elif rate >= 0.15:
                likelihood += 0.008
                reasons.append("conversion_likelihood_discount>=15%+0.008")
        except ValueError:
            pass
    if product.image_url or product.image_urls or product.image_path:
        likelihood += 0.005
        reasons.append("conversion_likelihood_media+0.005")
    likelihood = max(0.005, min(0.20, likelihood))
    reasons.append(f"conversion_likelihood_final={likelihood:.4f}")
    return likelihood, reasons

def _expected_profit_score(product, *, base_score: int, taste_score: int, commission_rate: float | None, commission_reasons: list[str]) -> tuple[int, dict[str, Any], list[str]]:
    price = int(product.price_vnd or 0)
    rate = float(commission_rate or product.commission_rate or 0)
    if rate and not product.commission_rate:
        product.commission_rate = rate
    likelihood, likelihood_reasons = _conversion_likelihood(product, base_score=base_score, taste_score=taste_score)
    expected_commission_vnd = price * rate
    expected_profit_vnd = expected_commission_vnd * likelihood
    # Profit-first, but not blind: combine monetization with quality/taste.
    profit_points = min(70, int(expected_profit_vnd / 250))
    quality_points = int(max(0, min(100, base_score)) * 0.20) + int(max(0, min(100, taste_score)) * 0.10)
    final = max(0, min(100, profit_points + quality_points))
    metrics = {
        "sale_price_vnd": price,
        "commission_rate": rate,
        "expected_commission_vnd": round(expected_commission_vnd, 2),
        "conversion_likelihood": round(likelihood, 4),
        "expected_profit_vnd": round(expected_profit_vnd, 2),
        "profit_points": profit_points,
        "quality_points": quality_points,
    }
    reasons = [
        "score_model:expected_profit",
        f"sale_price_vnd={price}",
        f"commission_rate={rate:.4f}",
        f"expected_commission_vnd={expected_commission_vnd:.0f}",
        f"expected_profit_vnd={expected_profit_vnd:.0f}",
        f"profit_points={profit_points}",
        f"quality_points={quality_points}",
    ] + commission_reasons + likelihood_reasons
    if not price:
        reasons.append("expected_profit_missing_price")
    if not rate:
        reasons.append("expected_profit_missing_commission_rate")
    return final, metrics, reasons

def _load_sources(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return DEFAULT_PROFIT_SOURCES
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("sources", data) if isinstance(data, dict) else data

def _is_placeholder_product(product: dict[str, Any]) -> bool:
    text = " ".join(str(product.get(key, "")) for key in ("url", "image_url", "affiliate_url", "tracking_url")).lower()
    placeholder_terms = (
        "example.com",
        "localhost",
        "127.0.0.1",
        "lazada.vn/products/safe",
        "lazada.vn/s.jpg",
        "/products/safe",
        "/safe.jpg",
        "/s.jpg",
        "test-safe",
        "fixture",
        "lazada.vn/products/risky",
        "lazada.vn/r.jpg",
        "/products/risky",
        "/r.jpg",
    )
    fixture_titles = (
        "vitamin k2d3 tăng đề kháng cho bé",
        "máy lọc không khí chính hãng bảo hành 12 tháng",
    )
    title = str(product.get("title", "")).lower()
    return any(term in text for term in placeholder_terms) or any(term in title for term in fixture_titles)


def _load_cached_source(out: Path) -> dict[str, Any] | None:
    if not out.exists():
        return None
    try:
        cached = json.loads(out.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    products = [p for p in cached.get("products", []) if isinstance(p, dict) and not _is_placeholder_product(p)]
    if products:
        cached["products"] = products
        cached["ok"] = True
        cached["source_mode"] = "cached_fallback"
        return cached
    return None


def _source_filter_note(source: dict[str, Any]) -> str:
    if source.get("target_category"):
        return "category_filter_not_supported_by_accesstrade:datafeed_broad_fetch_internal_target_category_only"
    return ""

def _load_source_cursors(path: str | Path = DEFAULT_SOURCE_CURSOR_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_source_cursors(cursors: dict[str, Any], path: str | Path = DEFAULT_SOURCE_CURSOR_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cursors, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_offset(source: dict[str, Any], *, cursor_path: str | Path = DEFAULT_SOURCE_CURSOR_PATH) -> int:
    if source.get("offset") not in (None, ""):
        try:
            return max(0, int(source.get("offset")))
        except (TypeError, ValueError):
            return 0
    cursors = _load_source_cursors(cursor_path)
    key = str(source.get("name") or source.get("sheet_key") or source.get("kind", "source"))
    try:
        return max(0, int(cursors.get(key, {}).get("offset", 0)))
    except (TypeError, ValueError, AttributeError):
        return 0


def _advance_source_cursor(source: dict[str, Any], report: dict[str, Any], *, cursor_path: str | Path = DEFAULT_SOURCE_CURSOR_PATH) -> None:
    if source.get("kind") != "shopee_sheet" or not report.get("ok"):
        return
    key = str(source.get("name") or source.get("sheet_key") or source.get("kind", "source"))
    limit = int(report.get("limit") or source.get("limit") or 0)
    offset = int(report.get("offset") or 0)
    total_available = int(report.get("total_available") or 0)
    if limit <= 0:
        return
    next_offset = offset + limit
    if total_available and next_offset >= total_available:
        next_offset = 0
    cursors = _load_source_cursors(cursor_path)
    cursors[key] = {"offset": next_offset, "last_offset": offset, "limit": limit, "total_available": total_available}
    _save_source_cursors(cursors, cursor_path)


def _source_page(source: dict[str, Any], *, batch_key: str = "") -> int:
    """Return a deterministic rotating page for scheduled discovery.

    Accesstrade datafeeds default to page=1. Running every cron slot against
    page=1 makes reports look identical and keeps re-scanning the same products.
    Use a stable hash of batch+source so retries are reproducible while later
    slots naturally explore different pages. Explicit source page still wins.
    """
    explicit = source.get("page")
    if explicit not in (None, ""):
        try:
            return max(1, int(explicit))
        except (TypeError, ValueError):
            return 1
    if not batch_key:
        return 1
    seed = f"{batch_key}:{source.get('name') or source.get('kind', 'source')}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return 1 + (int(digest[:8], 16) % 10)

def _fetch_source(source: dict[str, Any], out_dir: Path, *, cache_dir: str | Path = DEFAULT_SOURCE_CACHE_DIR, batch_key: str = "", cursor_path: str | Path = DEFAULT_SOURCE_CURSOR_PATH) -> dict[str, Any]:
    name = source.get("name") or source.get("kind", "source")
    out = out_dir / f"{name}.json"
    run_cache_out = out_dir / "cache" / f"{name}.json"
    global_cache_out = Path(cache_dir) / f"{name}.json"
    run_cache_out.parent.mkdir(parents=True, exist_ok=True)
    global_cache_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.get("kind") == "top_products":
            data = fetch_top_products(merchant=source.get("merchant", ""), date_from=source.get("date_from", ""), date_to=source.get("date_to", ""))
        elif source.get("kind") == "shopee_sheet":
            from affilipilot.accesstrade.shopee_sheets import DEFAULT_SHOPEE_SHEETS
            sheet_id = str(source.get("sheet_id") or "")
            gid = str(source.get("gid") or "")
            if not sheet_id:
                sheet_id, gid = DEFAULT_SHOPEE_SHEETS.get(str(source.get("sheet_key") or "shopee_best_sellers"), DEFAULT_SHOPEE_SHEETS["shopee_best_sellers"])
            data = fetch_shopee_sheet_products(sheet_id=sheet_id, gid=gid, limit=int(source.get("limit", 100)), offset=_source_offset(source, cursor_path=cursor_path), source_name=name)
        else:
            data = fetch_datafeeds(
                campaign=source.get("campaign", ""),
                domain=source.get("domain", ""),
                status_discount=source.get("status_discount", ""),
                discount_rate_from=source.get("discount_rate_from", ""),
                price_from=source.get("price_from", ""),
                price_to=source.get("price_to", ""),
                page=_source_page(source, batch_key=batch_key),
                limit=int(source.get("limit", 50)),
            )
    except urllib.error.HTTPError as exc:
        cached = _load_cached_source(global_cache_out) or _load_cached_source(run_cache_out)
        data = cached or {"ok": False, "error": f"http_error:{exc.code}", "products": [], "source": source.get("kind", "datafeed")}
        if cached:
            data["fallback_error"] = f"http_error:{exc.code}"
    except Exception as exc:
        cached = _load_cached_source(global_cache_out) or _load_cached_source(run_cache_out)
        data = cached or {"ok": False, "error": f"source_fetch_error:{type(exc).__name__}", "products": [], "source": source.get("kind", "datafeed")}
        if cached:
            data["fallback_error"] = f"source_fetch_error:{type(exc).__name__}"
    filter_note = _source_filter_note(source)
    data["requested_page"] = _source_page(source, batch_key=batch_key) if source.get("kind") not in {"top_products", "shopee_sheet"} else None
    if filter_note:
        data["source_filter_note"] = filter_note
        data["target_category"] = source.get("target_category", "")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if data.get("ok") and data.get("products") and data.get("source_mode") != "cached_fallback":
        clean_products = [p for p in data.get("products", []) if isinstance(p, dict) and not _is_placeholder_product(p)]
        if clean_products:
            cache_data = {**data, "products": clean_products}
            run_cache_out.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            global_cache_out.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    data["name"] = name
    data["campaign_key"] = source.get("campaign_key", "")
    data["json_path"] = str(out)
    _advance_source_cursor(source, data, cursor_path=cursor_path)
    return data


def _top_reasons(blocked: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in blocked:
        for reason in item.get("reasons", []):
            counts[reason] = counts.get(reason, 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _top_taste_reasons(blocked: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in blocked:
        for reason in item.get("penalties", []) + item.get("reasons", []):
            counts[reason] = counts.get(reason, 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _top_portfolio_reasons(blocked: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in blocked:
        reason = str(item.get("portfolio_block_reason") or "portfolio_blocked")
        counts[reason] = counts.get(reason, 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _serialize_portfolio_blocked(blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in blocked:
        product = item.get("product")
        result.append({
            "url": getattr(product, "url", ""),
            "title": getattr(product, "title", ""),
            "category": getattr(product, "category", ""),
            "score": item.get("score"),
            "reason": item.get("portfolio_block_reason", ""),
        })
    return result


def _uses_recent_duplicate_filter(batch_key: str) -> bool:
    return str(batch_key or "").startswith(("auto-source-", "scheduled-", "profit-first-", "manual-e2e-"))


def _recent_selected_urls(db_path: str | Path, *, limit_batches: int = 96, auto_only: bool = False) -> set[str]:
    """Return recently selected product URLs from saved batch manifests.

    Source sheets/APIs often return overlapping candidate sets across runs, so
    in-run dedup is not enough. Suppress products that already reached an
    approval batch recently. Shopee product URLs are normalized by shop/item id
    so product/product-page/deep-link query variants still dedup together.
    """
    db = AffiliPilotDB(db_path)
    db.init()
    urls: set[str] = set()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT batch_key, manifest_json FROM batches ORDER BY id DESC LIMIT ?",
            (max(0, int(limit_batches)),),
        ).fetchall()
    for row in rows:
        batch_key = str(row["batch_key"])
        if auto_only and not batch_key.startswith("auto-source-"):
            continue
        try:
            manifest = json.loads(row["manifest_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        for post in manifest.get("posts", []):
            product = post.get("product", {}) if isinstance(post, dict) else {}
            for value in (product.get("original_url"), product.get("url")):
                norm = _norm_url(str(value or ""))
                if norm:
                    urls.add(norm)
    return urls


def _filter_recently_selected(ranked: list[dict[str, Any]], recent_urls: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fresh: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in ranked:
        product = item.get("product")
        keys = {_norm_url(getattr(product, "url", "")), _norm_url(getattr(product, "original_url", ""))}
        keys.discard("")
        if keys & recent_urls:
            blocked.append({**item, "portfolio_block_reason": "recently_selected_product"})
        else:
            fresh.append(item)
    return fresh, blocked

def _enrich_selected_media(selected: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    metrics = {"attempted": 0, "updated": 0, "failed": 0, "skipped": 0}
    enriched: list[dict[str, Any]] = []
    for item in selected:
        product = item.get("product")
        if not product:
            enriched.append(item)
            continue
        if product.image_url or product.image_urls or product.image_path or product.video_url or product.video_urls or product.video_path:
            metrics["skipped"] += 1
            enriched.append(item)
            continue
        detail_url = product.original_url or product.url
        if not detail_url:
            metrics["skipped"] += 1
            enriched.append(item)
            continue
        metrics["attempted"] += 1
        try:
            media = enrich_product_from_url(detail_url, title=product.title, category=product.category, source=product.campaign_key or item.get("campaign_key", "AUTO"), timeout=25)
        except Exception as exc:  # noqa: BLE001 - keep source candidate and report enrichment failure
            product.notes = (product.notes + ";" if product.notes else "") + f"media_enrich_failed={type(exc).__name__}"
            metrics["failed"] += 1
            enriched.append(item)
            continue
        image_urls = media.get("image_urls") or []
        video_urls = media.get("video_urls") or []
        if image_urls:
            product.image_url = image_urls[0]
            product.image_urls = image_urls
            product.media_source = media.get("media_source") or ("shopee_pdp" if "shopee." in detail_url.lower() else "pdp_image")
            product.media_confidence = media.get("media_confidence") or "official"
            product.notes = (product.notes + ";" if product.notes else "") + "pdp_media_enriched"
            metrics["updated"] += 1
        if video_urls:
            product.video_url = video_urls[0]
            product.video_urls = video_urls
            if not image_urls:
                metrics["updated"] += 1
        if not image_urls and not video_urls:
            metrics["failed"] += 1
        enriched.append(item)
    return enriched, metrics

def run_profit_first_e2e(
    *,
    batch_key: str,
    work_dir: str | Path,
    db_path: str | Path,
    outbox_path: str | Path,
    sources_path: str | Path | None = None,
    discover_limit: int = 50,
    select_limit: int = 5,
    real_accesstrade: bool = False,
    queue_telegram: bool = True,
    cache_dir: str | Path = DEFAULT_SOURCE_CACHE_DIR,
) -> dict[str, Any]:
    work_dir = Path(work_dir)
    source_dir = work_dir / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    merged_input = work_dir / "profit-first.candidates.txt"
    selected_input = work_dir / "profit-first.selected.txt"
    converted_json = work_dir / "profit-first.converted.json"
    converted_input = work_dir / "profit-first.converted.txt"
    campaign_registry_path = work_dir / "campaign-registry.json"
    drafts_dir = work_dir / "drafts"
    publish_dir = work_dir / "publish-preview"
    state_path = work_dir / "snailbot-state.json"
    events_path = work_dir / "snailbot-events.jsonl"

    def record(stage: str, message: str, data: dict[str, Any] | None = None, *, status: str = "running") -> None:
        append_event(events_path, run_id=batch_key, kind="workflow.stage", message=message, data={"stage": stage, **(data or {})})
        write_run_state(
            state_path,
            AffiliPilotRunState(
                batch_key=batch_key,
                stage=stage,
                status=status,
                artifacts=[str(events_path)],
                metrics=data or {},
            ),
        )

    record("started", "Profit-first E2E started", {"work_dir": str(work_dir), "real_accesstrade": real_accesstrade, "queue_telegram": queue_telegram})

    sources = _load_sources(sources_path)
    campaign_registry = write_campaign_registry(campaign_registry_path) if real_accesstrade else {"ok": False, "campaigns": []}
    record("campaign_registry", "Campaign registry loaded", {"ok": campaign_registry.get("ok"), "campaign_count": len(campaign_registry.get("campaigns", []))})
    campaign_lookup = _campaign_lookup(campaign_registry)
    source_reports = []
    candidates_by_url: dict[str, dict[str, Any]] = {}
    early_blocked: list[dict[str, Any]] = []
    taste_blocked: list[dict[str, Any]] = []
    for source in sources:
        report = _fetch_source(source, source_dir, cache_dir=cache_dir, batch_key=batch_key)
        campaign = _campaign_for_source(source, campaign_lookup)
        campaign_id = str(campaign.get("campaign_id", "")) if campaign else _source_campaign_id(source, campaign_lookup)
        commission_rate, commission_reasons = _commission_rate_from_campaign(campaign)
        report["campaign_id"] = campaign_id
        report["commission_rate"] = commission_rate
        report["commission_reasons"] = commission_reasons
        source_reports.append({k: v for k, v in report.items() if k != "raw_redacted"})
        temp_input = source_dir / f"{report['name']}.input.txt"
        write_products_input(report.get("products", [])[:discover_limit], temp_input)
        for product in parse_link_lines(temp_input.read_text(encoding="utf-8")):
            early = evaluate_early_product_filter(product)
            if not early.passed:
                early_blocked.append({"source": report["name"], "url": product.url, "title": product.title, "category": product.category, "normalized_category": early.normalized_category, "reasons": early.reasons, "risk_flags": early.risk_flags})
                continue
            product.category = early.normalized_category
            product.campaign_id = campaign_id or product.campaign_id
            product.campaign_key = report.get("campaign_key", "") or product.campaign_key
            score = score_product(product)
            taste = evaluate_product_taste(product)
            if not taste.passed:
                taste_blocked.append({"source": report["name"], "url": product.url, "title": product.title, "category": product.category, "taste_score": taste.score, "reasons": taste.reasons, "penalties": taste.penalties})
                continue
            final_score, profit_metrics, profit_reasons = _expected_profit_score(
                product,
                base_score=int(score["score"]),
                taste_score=int(taste.score),
                commission_rate=commission_rate,
                commission_reasons=commission_reasons,
            )
            key = _norm_url(product.url or product.original_url)
            item = {"product": product, "score": final_score, "score_reasons": profit_reasons + list(score.get("reasons", [])) + [f"taste_score:{taste.score}"] + taste.reasons + taste.penalties, "source": report["name"], "campaign_key": report.get("campaign_key", ""), "campaign_id": campaign_id, "taste_score": taste.score, "profit_metrics": profit_metrics}
            if key and (key not in candidates_by_url or item["score"] > candidates_by_url[key]["score"]):
                candidates_by_url[key] = item

    ranked = sorted(candidates_by_url.values(), key=lambda item: item["score"], reverse=True)
    recent_urls = _recent_selected_urls(db_path) if _uses_recent_duplicate_filter(batch_key) else set()
    fresh_ranked, recent_blocked = _filter_recently_selected(ranked, recent_urls)
    selected, portfolio_blocked = select_portfolio(fresh_ranked, limit=select_limit)
    selected, selected_media_enrichment = _enrich_selected_media(selected)
    portfolio_blocked = recent_blocked + portfolio_blocked
    record(
        "candidates_ranked",
        "Candidates ranked and portfolio selected",
        {
            "candidate_count": len(ranked),
            "fresh_candidate_count": len(fresh_ranked),
            "recent_duplicate_blocked_count": len(recent_blocked),
            "early_blocked_count": len(early_blocked),
            "taste_blocked_count": len(taste_blocked),
            "portfolio_blocked_count": len(portfolio_blocked),
            "selected_count": len(selected),
            "selected_media_enrichment": selected_media_enrichment,
        },
    )
    merged_input.write_text("\n".join(_line_for_product(item["product"]) for item in ranked) + ("\n" if ranked else ""), encoding="utf-8")
    selected_input.write_text("\n".join(_line_for_product(item["product"]) for item in selected) + ("\n" if selected else ""), encoding="utf-8")

    conversion = {"total": 0, "ok_count": 0, "failed_count": 0, "items": []}
    effective_input = selected_input
    if selected:
        campaign_key = selected[0].get("campaign_key", "")
        conversion = convert_input_links(selected_input, converted_json, dry_run=not real_accesstrade, limit=select_limit, campaign_key=campaign_key, allow_channel_urls=False)
        write_converted_input(converted_json, converted_input)
        if converted_input.exists() and converted_input.stat().st_size > 0:
            effective_input = converted_input
    record("conversion", "Selected products converted or prepared", {"selected_count": len(selected), "conversion_ok_count": conversion.get("ok_count", 0), "conversion_failed_count": conversion.get("failed_count", 0), "effective_input": str(effective_input)})

    if not effective_input.exists() or effective_input.stat().st_size == 0:
        summary = {"ok": False, "reason": "no_effective_input", "batch_key": batch_key, "work_dir": str(work_dir), "outbox_path": str(outbox_path), "sources": source_reports, "candidate_count": len(ranked), "fresh_candidate_count": len(fresh_ranked), "recent_duplicate_blocked_count": len(recent_blocked), "early_blocked_count": len(early_blocked), "top_early_block_reasons": _top_reasons(early_blocked), "taste_blocked_count": len(taste_blocked), "top_taste_block_reasons": _top_taste_reasons(taste_blocked), "portfolio_blocked_count": len(portfolio_blocked), "top_portfolio_block_reasons": _top_portfolio_reasons(portfolio_blocked), "selected_count": len(selected), "selected_input": str(selected_input), "effective_input": str(effective_input), "conversion": conversion, "queued_messages": 0}
        if queue_telegram:
            message = OutboxMessage(
                id=f"{batch_key}:no-post-digest",
                kind="digest",
                text=render_profit_first_e2e(summary),
            )
            Outbox(outbox_path).save([message])
            summary["queued_messages"] = 1
            summary["queued_digest"] = True
        else:
            summary["queued_digest"] = False
        record("blocked", "Profit-first E2E blocked before approval batch", {"reason": "no_effective_input", "candidate_count": len(ranked), "selected_count": len(selected), "queued_digest": summary["queued_digest"]}, status="blocked")
        (work_dir / "profit-first-e2e-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    manifest = create_approval_batch(effective_input, drafts_dir, db_path, batch_key=batch_key, limit=select_limit)
    media_enrichment = enrich_batch_media(db_path, batch_key=batch_key, out_dir=drafts_dir, limit=select_limit)
    manifest = AffiliPilotDB(db_path).get_batch(batch_key)["manifest"]
    original_posts = list(manifest.get("posts", []))
    record(
        "approval_batch_created",
        "Approval batch created and media enriched",
        {
            "original_post_count": len(original_posts),
            "effective_input": str(effective_input),
            "media_enrichment_updated": media_enrichment.get("updated", 0),
            "media_enrichment_failed": media_enrichment.get("failed", 0),
        },
    )
    vetted_posts = []
    gates = []
    for post in original_posts:
        product = post.get("product", {})
        text = _post_text(post)
        quality = evaluate_quality_gate(post)
        product_content = evaluate_product_content(product, text)
        market_fit = evaluate_market_fit(product, text)
        offer_url = product.get("affiliate_url") or product.get("tracking_url") or product.get("url", "")
        offer = validate_offer(offer_url, expected_title=product.get("title", ""), expected_image=product.get("image_url", ""), network=False)
        passed = quality.passed and product_content.passed and market_fit.passed and offer.passed
        if passed:
            vetted_posts.append(post)
        gates.append({
            "post_id": post.get("post_id"),
            "passed": passed,
            "score": post.get("score"),
            "score_reasons": post.get("score_reasons", []),
            "quality": {"passed": quality.passed, "score": quality.score, "reasons": quality.reasons},
            "product_content": {"passed": product_content.passed, "score": product_content.score, "reasons": product_content.reasons},
            "market_fit": {"passed": market_fit.passed, "score": market_fit.score, "reasons": market_fit.reasons},
            "offer": {"passed": offer.passed, "score": offer.score, "reasons": offer.reasons},
        })

    manifest["posts"] = vetted_posts
    manifest["selected"] = len(vetted_posts)
    manifest["filtered_posts"] = [p.get("post_id") for p in original_posts if p not in vetted_posts]
    AffiliPilotDB(db_path).save_batch(batch_key=batch_key, source=str(effective_input), manifest=manifest)
    record("gates_evaluated", "Approval batch gates evaluated", {"vetted_count": len(vetted_posts), "filtered_count": len(original_posts) - len(vetted_posts)})

    messages = []
    if queue_telegram and vetted_posts:
        messages = queue_approval_batch(db_path, batch_key=batch_key, outbox_path=outbox_path)
    record("approval_queued", "Telegram approval queue step completed", {"queued_messages": len(messages), "queue_telegram": queue_telegram})

    ready = build_ready_to_publish_report(db_path=db_path, batch_key=batch_key, outbox_path=outbox_path, out_dir=publish_dir)
    summary = {
        "ok": bool(vetted_posts),
        "reason": "ready_for_operator_approval" if vetted_posts else "no_vetted_posts",
        "batch_key": batch_key,
        "work_dir": str(work_dir),
        "db_path": str(db_path),
        "outbox_path": str(outbox_path),
        "source_count": len(sources),
        "candidate_count": len(ranked),
        "fresh_candidate_count": len(fresh_ranked),
        "recent_duplicate_blocked_count": len(recent_blocked),
        "early_blocked_count": len(early_blocked),
        "top_early_block_reasons": _top_reasons(early_blocked),
        "taste_blocked_count": len(taste_blocked),
        "top_taste_block_reasons": _top_taste_reasons(taste_blocked),
        "portfolio_blocked_count": len(portfolio_blocked),
        "top_portfolio_block_reasons": _top_portfolio_reasons(portfolio_blocked),
        "selected_count": len(selected),
        "selected_profit_metrics": [{"title": item["product"].title, "url": item["product"].url, "score": item.get("score"), "profit_metrics": item.get("profit_metrics", {})} for item in selected],
        "merged_input": str(merged_input),
        "selected_input": str(selected_input),
        "effective_input": str(effective_input),
        "conversion": {"total": conversion.get("total", 0), "ok_count": conversion.get("ok_count", 0), "failed_count": conversion.get("failed_count", 0), "dry_run": conversion.get("dry_run")},
        "campaign_registry": {"path": str(campaign_registry_path), "ok": campaign_registry.get("ok"), "count": len(campaign_registry.get("campaigns", []))},
        "vetted_count": len(vetted_posts),
        "filtered_count": len(original_posts) - len(vetted_posts),
        "queued_messages": len(messages),
        "gates": gates,
        "ready_to_publish": {k: ready.get(k) for k in ("ready_count", "held_count", "plan_publishable_count", "plan_blocked_count", "publish_safe_pass_count", "publish_safe_block_count", "report_path")},
        "sources": source_reports,
        "early_blocked": early_blocked[:50],
        "taste_blocked": taste_blocked[:50],
        "portfolio_blocked": _serialize_portfolio_blocked(portfolio_blocked[:50]),
    }
    record("finished", "Profit-first E2E finished", {"ok": summary["ok"], "reason": summary["reason"], "vetted_count": len(vetted_posts), "queued_messages": len(messages)}, status="finished" if summary["ok"] else "blocked")
    (work_dir / "profit-first-e2e-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary

def _source_line(source: dict[str, Any]) -> str:
    status = "OK" if source.get("ok") else "ERR"
    products = len(source.get("products", []))
    mode = source.get("source_mode", "live")
    error = source.get("error") or source.get("fallback_error") or ""
    campaign = source.get("campaign_id") or "-"
    target = source.get("target_category") or "-"
    note = source.get("source_filter_note") or ""
    suffix = f" error={error}" if error else ""
    note_suffix = f" note={note}" if note else ""
    return f"- {source.get('name')}: {status} products={products} mode={mode} campaign={campaign} target={target}{suffix}{note_suffix}"


def _gate_failure_summary(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for gate in gates:
        if gate.get("passed"):
            continue
        for section in ("quality", "product_content", "market_fit", "offer"):
            for reason in gate.get(section, {}).get("reasons", []):
                counts[f"{section}:{reason}"] = counts.get(f"{section}:{reason}", 0) + 1
    return [{"reason": reason, "count": count} for reason, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]]


def _format_top_reason(items: list[dict[str, Any]]) -> str:
    if not items:
        return "-"
    first = items[0]
    return f"{first.get('reason', '-')}: {first.get('count', 0)}"


def render_profit_first_e2e(summary: dict[str, Any], *, verbose: bool = False) -> str:
    conv = summary.get("conversion", {})
    ready = summary.get("ready_to_publish", {})
    source_lines = [_source_line(s) for s in summary.get("sources", [])]
    gate_failures = _gate_failure_summary(summary.get("gates", []))
    no_card_reasons = []
    if summary.get("candidate_count", 0) == 0:
        no_card_reasons.append("Không còn candidate sau source/filter.")
    if summary.get("early_blocked_count", 0):
        no_card_reasons.append(f"Early filter block {summary.get('early_blocked_count')} sản phẩm rủi ro/không hợp lệ.")
    if summary.get("taste_blocked_count", 0):
        no_card_reasons.append(f"Taste layer block {summary.get('taste_blocked_count')} sản phẩm low-fit.")
    if summary.get("portfolio_blocked_count", 0):
        no_card_reasons.append(f"Portfolio giữ lại {summary.get('portfolio_blocked_count')} sản phẩm do quota/fit.")
    if conv.get("failed_count", 0):
        no_card_reasons.append(f"Convert Accesstrade fail {conv.get('failed_count')} sản phẩm.")
    if gate_failures:
        no_card_reasons.append(f"Gate nội dung/chất lượng block: {gate_failures[:3]}")
    if summary.get("vetted_count", 0) > 0 and summary.get("queued_messages", 0) == 0:
        no_card_reasons.append("Có vetted posts nhưng chưa queue/deliver Telegram.")

    status = "OK" if summary.get("ok") else "BLOCK"
    lines = [
        f"🐌 AffiliPilot: {status}",
        f"Batch: {summary.get('batch_key')}",
        f"Kết quả: {summary.get('selected_count', 0)} chọn / {summary.get('queued_messages', 0)} card / {ready.get('ready_count', 0)} ready",
        f"Filter: early {summary.get('early_blocked_count', 0)} | taste {summary.get('taste_blocked_count', 0)} | portfolio {summary.get('portfolio_blocked_count', 0)}",
        f"Lý do chính: {_format_top_reason(summary.get('top_early_block_reasons', []))}; {_format_top_reason(summary.get('top_taste_block_reasons', []))}",
    ]
    if no_card_reasons:
        lines.append(f"Vì sao chưa có card: {no_card_reasons[0]}")
    next_action = "Mở outbox để review nếu cần." if summary.get("queued_messages", 0) else "Không cần approve — batch này không có sản phẩm đạt."
    lines.append(f"Next: {next_action}")

    if not verbose:
        return "\n".join(lines)

    lines.extend([
        "",
        "— Chi tiết —",
        f"Reason: {summary.get('reason')}",
        f"Work dir: {summary.get('work_dir')}",
        "Source health:",
        *(source_lines or ["- no sources recorded"]),
        f"Conversion: ok={conv.get('ok_count', 0)} failed={conv.get('failed_count', 0)} dry_run={conv.get('dry_run')}",
        f"Vetted: pass={summary.get('vetted_count', 0)} filtered={summary.get('filtered_count', 0)}",
        f"Top early: {summary.get('top_early_block_reasons', [])[:5]}",
        f"Top taste: {summary.get('top_taste_block_reasons', [])[:5]}",
        f"Top portfolio: {summary.get('top_portfolio_block_reasons', [])[:5]}",
        f"Top gates: {gate_failures[:5]}",
        f"Outbox: {summary.get('outbox_path')}",
        f"Ready report: {ready.get('report_path')}",
    ])
    return "\n".join(lines)
