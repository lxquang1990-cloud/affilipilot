from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.campaigns import write_campaign_registry
from affilipilot.accesstrade.catalog import fetch_datafeeds, fetch_top_products, write_products_input
from affilipilot.content.early_filter import evaluate_early_product_filter
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.content.product_taste import evaluate_product_taste
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.quality import evaluate_quality_gate
from affilipilot.scoring.portfolio import select_portfolio
from affilipilot.scoring.product_score import score_product
from affilipilot.sources.manual_input import parse_link_lines
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input
from affilipilot.workflows.approval import create_approval_batch

# Accesstrade docs notes used here:
# - Datafeed does not document category filtering; `target_category` is internal only.
# - Some datafeeds include promotion details per product; prefer status_discount feeds.
# - API rate limit is 30 requests/minute, so keep default source count small.
DEFAULT_SOURCE_CACHE_DIR = Path("data/cache/accesstrade/sources")

DEFAULT_PROFIT_SOURCES = [
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
    return (url or "").split("?", 1)[0].rstrip("/").lower()


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

def _fetch_source(source: dict[str, Any], out_dir: Path, *, cache_dir: str | Path = DEFAULT_SOURCE_CACHE_DIR) -> dict[str, Any]:
    name = source.get("name") or source.get("kind", "source")
    out = out_dir / f"{name}.json"
    run_cache_out = out_dir / "cache" / f"{name}.json"
    global_cache_out = Path(cache_dir) / f"{name}.json"
    run_cache_out.parent.mkdir(parents=True, exist_ok=True)
    global_cache_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.get("kind") == "top_products":
            data = fetch_top_products(merchant=source.get("merchant", ""), date_from=source.get("date_from", ""), date_to=source.get("date_to", ""))
        else:
            data = fetch_datafeeds(
                campaign=source.get("campaign", ""),
                domain=source.get("domain", ""),
                status_discount=source.get("status_discount", ""),
                discount_rate_from=source.get("discount_rate_from", ""),
                price_from=source.get("price_from", ""),
                price_to=source.get("price_to", ""),
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

    sources = _load_sources(sources_path)
    campaign_registry = write_campaign_registry(campaign_registry_path) if real_accesstrade else {"ok": False, "campaigns": []}
    campaign_lookup = _campaign_lookup(campaign_registry)
    source_reports = []
    candidates_by_url: dict[str, dict[str, Any]] = {}
    early_blocked: list[dict[str, Any]] = []
    taste_blocked: list[dict[str, Any]] = []
    for source in sources:
        report = _fetch_source(source, source_dir, cache_dir=cache_dir)
        campaign_id = _source_campaign_id(source, campaign_lookup)
        report["campaign_id"] = campaign_id
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
            final_score = min(100, int(score["score"]) + max(0, taste.score - 50) // 2)
            key = _norm_url(product.url or product.original_url)
            item = {"product": product, "score": final_score, "score_reasons": list(score.get("reasons", [])) + [f"taste_score:{taste.score}"] + taste.reasons + taste.penalties, "source": report["name"], "campaign_key": report.get("campaign_key", ""), "campaign_id": campaign_id, "taste_score": taste.score}
            if key and (key not in candidates_by_url or item["score"] > candidates_by_url[key]["score"]):
                candidates_by_url[key] = item

    ranked = sorted(candidates_by_url.values(), key=lambda item: item["score"], reverse=True)
    selected, portfolio_blocked = select_portfolio(ranked, limit=select_limit)
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

    if not effective_input.exists() or effective_input.stat().st_size == 0:
        summary = {"ok": False, "reason": "no_effective_input", "batch_key": batch_key, "work_dir": str(work_dir), "sources": source_reports, "candidate_count": len(ranked), "early_blocked_count": len(early_blocked), "top_early_block_reasons": _top_reasons(early_blocked), "taste_blocked_count": len(taste_blocked), "top_taste_block_reasons": _top_taste_reasons(taste_blocked), "portfolio_blocked_count": len(portfolio_blocked), "top_portfolio_block_reasons": _top_portfolio_reasons(portfolio_blocked), "selected_count": len(selected), "conversion": conversion}
        (work_dir / "profit-first-e2e-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    manifest = create_approval_batch(effective_input, drafts_dir, db_path, batch_key=batch_key, limit=select_limit)
    original_posts = list(manifest.get("posts", []))
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

    messages = []
    if queue_telegram and vetted_posts:
        messages = queue_approval_batch(db_path, batch_key=batch_key, outbox_path=outbox_path)

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
        "early_blocked_count": len(early_blocked),
        "top_early_block_reasons": _top_reasons(early_blocked),
        "taste_blocked_count": len(taste_blocked),
        "top_taste_block_reasons": _top_taste_reasons(taste_blocked),
        "portfolio_blocked_count": len(portfolio_blocked),
        "top_portfolio_block_reasons": _top_portfolio_reasons(portfolio_blocked),
        "selected_count": len(selected),
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


def render_profit_first_e2e(summary: dict[str, Any]) -> str:
    conv = summary.get("conversion", {})
    ready = summary.get("ready_to_publish", {})
    source_lines = [_source_line(s) for s in summary.get("sources", [])]
    gate_failures = _gate_failure_summary(summary.get("gates", []))
    no_card_reasons = []
    if summary.get("candidate_count", 0) == 0:
        no_card_reasons.append("No candidates after source fetch and early filtering.")
    if summary.get("early_blocked_count", 0):
        no_card_reasons.append(f"Early filter blocked {summary.get('early_blocked_count')} risky/invalid products.")
    if summary.get("taste_blocked_count", 0):
        no_card_reasons.append(f"Taste layer blocked {summary.get('taste_blocked_count')} low-fit products.")
    if summary.get("portfolio_blocked_count", 0):
        no_card_reasons.append(f"Portfolio selector held back {summary.get('portfolio_blocked_count')} products due category quota/fit.")
    if conv.get("failed_count", 0):
        no_card_reasons.append(f"Accesstrade conversion failed for {conv.get('failed_count')} selected products.")
    if gate_failures:
        no_card_reasons.append(f"Content/quality gates blocked posts: {gate_failures[:3]}")
    if summary.get("vetted_count", 0) > 0 and summary.get("queued_messages", 0) == 0:
        no_card_reasons.append("Vetted posts exist, but Telegram queue/delivery was skipped or disabled for this run.")
    lines = [
        "🐌 AffiliPilot profit-first E2E",
        f"Batch: {summary.get('batch_key')}",
        f"Status: {'OK' if summary.get('ok') else 'BLOCK'} ({summary.get('reason')})",
        f"Work dir: {summary.get('work_dir')}",
        "",
        "Source health:",
        *(source_lines or ["- no sources recorded"]),
        "",
        "Pipeline:",
        f"- discovered candidates: {summary.get('candidate_count', 0)}",
        f"- early blocked: {summary.get('early_blocked_count', 0)}",
        f"- taste blocked: {summary.get('taste_blocked_count', 0)}",
        f"- portfolio held back: {summary.get('portfolio_blocked_count', 0)}",
        f"- selected for conversion/draft: {summary.get('selected_count', 0)}",
        f"- conversion: ok={conv.get('ok_count', 0)} failed={conv.get('failed_count', 0)} dry_run={conv.get('dry_run')}",
        f"- vetted: pass={summary.get('vetted_count', 0)} filtered={summary.get('filtered_count', 0)}",
        f"- outbox queued: {summary.get('queued_messages', 0)}",
        f"- ready preview: ready={ready.get('ready_count', 0)} held={ready.get('held_count', 0)} publish-safe-pass={ready.get('publish_safe_pass_count', 0)}",
        "",
        f"Top early block reasons: {summary.get('top_early_block_reasons', [])[:5]}",
        f"Top taste block reasons: {summary.get('top_taste_block_reasons', [])[:5]}",
        f"Top portfolio block reasons: {summary.get('top_portfolio_block_reasons', [])[:5]}",
        f"Top gate failures: {gate_failures[:5]}",
    ]
    if no_card_reasons:
        heading = "Operator notes:" if summary.get("vetted_count", 0) > 0 else "Why no approval-ready cards:"
        lines.extend(["", heading, *(f"- {reason}" for reason in no_card_reasons)])
    lines.extend([
        "",
        "Artifacts:",
        f"- selected input: {summary.get('selected_input')}",
        f"- effective input: {summary.get('effective_input')}",
        f"- outbox: {summary.get('outbox_path')}",
        f"- ready report: {ready.get('report_path')}",
        "",
        "Next safe steps:",
        f"1) Review outbox: python3 -m affilipilot.cli outbox --outbox {summary.get('outbox_path')}",
        "2) Deliver approval cards to Telegram if queued.",
        "3) Approve/reject cards.",
        "4) Run publish-safe --check-only before any real Facebook publish.",
    ])
    return "\n".join(lines)
