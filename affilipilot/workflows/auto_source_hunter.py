from __future__ import annotations

import json
import urllib.error
from dataclasses import asdict
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.catalog import AccesstradeProduct, fetch_datafeeds, write_products_input
from affilipilot.content.early_filter import evaluate_early_product_filter
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.content.product_taste import evaluate_product_taste
from affilipilot.db import AffiliPilotDB
from affilipilot.offer import validate_offer
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.quality import evaluate_quality_gate
from affilipilot.scoring.product_score import score_product
from affilipilot.scanner.enrich import enrich_product_from_url
from affilipilot.sources.manual_input import parse_link_lines
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input
from affilipilot.workflows.approval import create_approval_batch

DEFAULT_AUTO_SOURCES = [
    {"name": "shopee_home_low", "domain": "shopee.vn", "campaign_key": "SHOPEE", "status_discount": "1", "price_from": "50000", "price_to": "500000", "pages": 4, "limit": 100, "weight": 8},
    {"name": "shopee_home_mid", "domain": "shopee.vn", "campaign_key": "SHOPEE", "status_discount": "1", "price_from": "500000", "price_to": "1500000", "pages": 4, "limit": 100, "weight": 9},
    {"name": "shopee_appliance_high", "domain": "shopee.vn", "campaign_key": "SHOPEE", "status_discount": "1", "price_from": "1500000", "price_to": "3500000", "pages": 3, "limit": 100, "weight": 7},
    {"name": "tiki_home_mid", "domain": "tiki.vn", "campaign_key": "TIKI", "status_discount": "1", "price_from": "80000", "price_to": "1500000", "pages": 3, "limit": 100, "weight": 7},
    {"name": "tiki_home_high", "domain": "tiki.vn", "campaign_key": "TIKI", "status_discount": "1", "price_from": "1500000", "price_to": "3500000", "pages": 2, "limit": 100, "weight": 6},
    {"name": "lazada_fallback", "domain": "lazada.vn", "campaign_key": "LAZADA", "status_discount": "1", "price_from": "80000", "price_to": "1500000", "pages": 1, "limit": 80, "weight": 1},
]

PREFERRED_TITLE_TERMS = (
    "máy hút bụi", "hút bụi", "đèn ngủ", "cảm biến", "quạt", "ổ cắm", "kệ", "hộp đựng", "gầm giường",
    "bình giữ nhiệt", "hộp cơm", "nắp nồi", "máy xay", "bảo quản", "khăn lau", "ghế ăn", "bình tập uống",
    "khăn sữa", "hộp chia sữa", "túi đựng", "đèn bàn", "nhà tắm", "nhà bếp", "sắp xếp", "lưu trữ",
    "làm bánh", "bánh cuốn", "nhà", "bếp", "gia đình", "du lịch", "tiện lợi",
)

LOW_AUTOMATION_FIT_TERMS = (
    "xe đạp", "ghi đông", "sừng trâu", "shimano", "phụ tùng", "linh kiện", "khám răng", "nha sĩ", "nha khoa",
    "đồ chơi điện thoại", "siêu nhân", "mô hình", "figure", "anime", "gửi ngẫu nhiên", "điều khiển", "remote",
    "áo chống nắng", "thời trang", "quần áo", "sách tiếng anh", "ngoại ngữ", "tiểu thuyết", "truyện tranh",
)

HIGH_INTENT_TERMS = (
    "máy hút bụi", "hút bụi", "máy xay", "nồi chiên", "bình giữ nhiệt", "hộp cơm", "hộp đựng", "kệ để",
    "giá treo", "bảo quản thực phẩm", "khăn lau bếp", "làm bánh", "bánh cuốn", "đèn ngủ", "đèn bàn", "ổ cắm",
)

AUTO_BROAD_ALLOWED_CATEGORIES = {
    "home_appliance",
    "home_living",
    "storage",
    "office_productivity",
    "mother_baby",
    "baby_care",
    "feeding",
}

AUTO_BROAD_CONDITIONAL_CATEGORIES = {"toy", "electronics", "unknown", "book"}


def _candidate_line(product) -> str:
    parts = [product.url]
    for key, value in {
        "title": product.title,
        "category": product.category,
        "price": product.price_vnd,
        "image_url": product.image_url,
        "affiliate_url": product.affiliate_url,
        "tracking_url": product.tracking_url,
        "notes": product.notes,
        "media_source": product.media_source,
        "media_confidence": product.media_confidence,
        "original_url": product.original_url,
        "campaign_key": product.campaign_key,
        "campaign_id": product.campaign_id,
    }.items():
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    for key in ("image_urls", "video_urls"):
        value = getattr(product, key, []) or []
        if value:
            parts.append(f"{key}={','.join(str(item) for item in value if item)}")
    return " | ".join(str(part) for part in parts)


def _enrich_selected_media(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in selected:
        product = item["product"]
        detail_url = product.original_url or product.url
        if not detail_url:
            enriched.append(item)
            continue
        try:
            media = enrich_product_from_url(detail_url, title=product.title, category=product.category, source=product.campaign_key or "AUTO", timeout=25)
        except Exception as exc:  # noqa: BLE001 - record and keep the candidate
            product.notes = (product.notes + ";" if product.notes else "") + f"media_enrich_failed={type(exc).__name__}"
            enriched.append(item)
            continue
        image_urls = media.get("image_urls") or []
        video_urls = media.get("video_urls") or []
        if image_urls:
            product.image_url = image_urls[0]
            product.image_urls = image_urls
            product.media_source = media.get("media_source") or ("shopee_pdp" if "shopee." in detail_url.lower() else "jsonld_product_image")
            product.media_confidence = media.get("media_confidence") or "official"
            product.notes = (product.notes + ";" if product.notes else "") + "pdp_media_enriched"
        if video_urls:
            product.video_url = video_urls[0]
            product.video_urls = video_urls
        enriched.append(item)
    return enriched

def _post_text(post: dict[str, Any]) -> str:
    path = Path(post.get("files", {}).get("post_text", ""))
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _title_adjustment(title: str) -> tuple[int, list[str]]:
    text = title.lower()
    hits = [term for term in PREFERRED_TITLE_TERMS if term in text]
    low_hits = [term for term in LOW_AUTOMATION_FIT_TERMS if term in text]
    score = 0
    reasons: list[str] = []
    if len(hits) >= 2:
        score += 30
        reasons.append("preferred_title_terms>=2+30")
    elif hits:
        score += 18
        reasons.append("preferred_title_terms+18")
    if low_hits:
        score -= 60
        reasons.append("low_automation_fit_title_terms-60")
    return score, reasons


def _auto_broad_fit(product, title_reasons: list[str]) -> tuple[bool, list[str]]:
    category = (product.category or "unknown").lower()
    text = f"{product.title} {product.category} {product.notes}".lower()
    has_preferred_title = any(reason.startswith("preferred_title_terms") for reason in title_reasons)
    has_low_auto_term = any(term in text for term in LOW_AUTOMATION_FIT_TERMS)
    reasons: list[str] = []
    if has_low_auto_term:
        reasons.append("low_automation_fit_title")
        return False, reasons
    has_high_intent = any(term in text for term in HIGH_INTENT_TERMS)
    if category in AUTO_BROAD_ALLOWED_CATEGORIES:
        return True, reasons
    if category in AUTO_BROAD_CONDITIONAL_CATEGORIES and has_preferred_title and has_high_intent:
        return True, ["conditional_category_with_high_intent_title"]
    reasons.append(f"auto_broad_low_fit_category:{category}")
    return False, reasons


def _fetch_source_pages(source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    products: list[dict[str, Any]] = []
    page_reports: list[dict[str, Any]] = []
    pages = int(source.get("pages", 1))
    for page in range(1, pages + 1):
        try:
            data = fetch_datafeeds(
                domain=source.get("domain", ""),
                campaign=source.get("campaign", ""),
                status_discount=source.get("status_discount", ""),
                price_from=source.get("price_from", ""),
                price_to=source.get("price_to", ""),
                page=page,
                limit=int(source.get("limit", 100)),
                timeout=25,
            )
            batch = data.get("products") or []
            products.extend(batch)
            page_reports.append({"page": page, "ok": data.get("ok"), "products": len(batch), "error": data.get("error", ""), "source_url": data.get("source_url", "")})
        except urllib.error.HTTPError as exc:
            page_reports.append({"page": page, "ok": False, "products": 0, "error": f"http_error:{exc.code}"})
        except Exception as exc:  # noqa: BLE001
            page_reports.append({"page": page, "ok": False, "products": 0, "error": f"fetch_error:{type(exc).__name__}"})
    report = {
        "name": source.get("name"),
        "domain": source.get("domain"),
        "campaign_key": source.get("campaign_key", ""),
        "raw_products": len(products),
        "pages": page_reports,
    }
    return products, report


def _products_to_candidates(products: list[dict[str, Any]], source: dict[str, Any], tmp_input: Path) -> list[Any]:
    enriched = []
    for product in products:
        row = dict(product)
        row["merchant"] = row.get("merchant") or source.get("domain", "")
        enriched.append(row)
    write_products_input(enriched, tmp_input)
    candidates = parse_link_lines(tmp_input.read_text(encoding="utf-8"))
    for cand in candidates:
        cand.campaign_key = source.get("campaign_key", "") or cand.campaign_key
        cand.notes = (cand.notes + ";" if cand.notes else "") + f"auto_source={source.get('name')};domain={source.get('domain')}"
    return candidates


def run_auto_source_hunter(
    *,
    batch_key: str,
    work_dir: str | Path,
    db_path: str | Path,
    outbox_path: str | Path,
    source_config: str | Path | None = None,
    collect_limit: int = 500,
    select_limit: int = 5,
    real_accesstrade: bool = True,
    queue_telegram: bool = True,
) -> dict[str, Any]:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    sources = json.loads(Path(source_config).read_text(encoding="utf-8")).get("sources", []) if source_config else DEFAULT_AUTO_SOURCES
    raw_dir = work_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    source_reports = []
    candidates_by_url: dict[str, dict[str, Any]] = {}
    early_blocked: list[dict[str, Any]] = []
    taste_blocked: list[dict[str, Any]] = []

    per_source_limit = max(1, collect_limit // max(1, len(sources)))
    collected = 0
    for source in sources:
        products, report = _fetch_source_pages(source)
        products = products[:per_source_limit]
        collected += len(products)
        tmp_input = raw_dir / f"{source.get('name', 'source')}.input.txt"
        candidates = _products_to_candidates(products, source, tmp_input)
        accepted = 0
        for product in candidates:
            early = evaluate_early_product_filter(product)
            if not early.passed:
                early_blocked.append({"source": source.get("name"), "title": product.title, "category": product.category, "reasons": early.reasons})
                continue
            product.category = early.normalized_category
            taste = evaluate_product_taste(product)
            if not taste.passed:
                taste_blocked.append({"source": source.get("name"), "title": product.title, "category": product.category, "reasons": taste.reasons, "penalties": taste.penalties})
                continue
            scored = score_product(product)
            title_adjustment, title_reasons = _title_adjustment(product.title)
            auto_fit_ok, auto_fit_reasons = _auto_broad_fit(product, title_reasons)
            if not auto_fit_ok:
                taste_blocked.append({"source": source.get("name"), "title": product.title, "category": product.category, "reasons": auto_fit_reasons, "penalties": title_reasons})
                continue
            final_score = int(scored["score"]) + taste.score + title_adjustment + int(source.get("weight", 0))
            if final_score < 100:
                taste_blocked.append({"source": source.get("name"), "title": product.title, "category": product.category, "reasons": ["auto_broad_score_below_threshold"], "penalties": title_reasons})
                continue
            key = (product.url or product.original_url or product.title).split("?", 1)[0].lower()
            item = {"product": product, "score": final_score, "score_reasons": list(scored.get("reasons", [])) + taste.reasons + taste.penalties + title_reasons + auto_fit_reasons, "source": source.get("name")}
            if key and (key not in candidates_by_url or item["score"] > candidates_by_url[key]["score"]):
                candidates_by_url[key] = item
                accepted += 1
        report["accepted_candidates"] = accepted
        source_reports.append(report)

    ranked = sorted(candidates_by_url.values(), key=lambda item: item["score"], reverse=True)
    selected = _enrich_selected_media(ranked[:select_limit])
    candidates_input = work_dir / "auto-source.candidates.txt"
    selected_input = work_dir / "auto-source.selected.txt"
    converted_json = work_dir / "auto-source.converted.json"
    converted_input = work_dir / "auto-source.converted.txt"
    drafts_dir = work_dir / "drafts"
    publish_dir = work_dir / "publish-preview"
    candidates_input.write_text("\n".join(_candidate_line(item["product"]) for item in ranked) + ("\n" if ranked else ""), encoding="utf-8")
    selected_input.write_text("\n".join(_candidate_line(item["product"]) for item in selected) + ("\n" if selected else ""), encoding="utf-8")

    conversion = {"total": 0, "ok_count": 0, "failed_count": 0, "items": [], "dry_run": not real_accesstrade}
    if selected:
        conversion = convert_input_links(selected_input, converted_json, dry_run=not real_accesstrade, limit=select_limit, campaign_key="", allow_channel_urls=False)
        write_converted_input(converted_json, converted_input)
    if not converted_input.exists() or converted_input.stat().st_size == 0:
        summary = {"ok": False, "reason": "no_converted_input", "batch_key": batch_key, "work_dir": str(work_dir), "source_reports": source_reports, "candidate_count": len(ranked), "selected_count": len(selected), "early_blocked_count": len(early_blocked), "taste_blocked_count": len(taste_blocked), "conversion": conversion}
        (work_dir / "auto-source-hunter-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    manifest = create_approval_batch(converted_input, drafts_dir, db_path, batch_key=batch_key, limit=select_limit)
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
        gates.append({"post_id": post.get("post_id"), "passed": passed, "quality": asdict(quality), "product_content": asdict(product_content), "market_fit": asdict(market_fit), "offer": asdict(offer)})
    manifest["posts"] = vetted_posts
    manifest["selected"] = len(vetted_posts)
    manifest["filtered_posts"] = [p.get("post_id") for p in original_posts if p not in vetted_posts]
    AffiliPilotDB(db_path).save_batch(batch_key=batch_key, source=str(converted_input), manifest=manifest)
    messages = queue_approval_batch(db_path, batch_key=batch_key, outbox_path=outbox_path) if queue_telegram and vetted_posts else []
    approval_card_count = sum(1 for message in messages if message.kind == "approval_card")
    ready = build_ready_to_publish_report(db_path=db_path, batch_key=batch_key, outbox_path=outbox_path, out_dir=publish_dir)
    summary = {
        "ok": bool(vetted_posts),
        "reason": "ready_for_operator_approval" if vetted_posts else "no_vetted_posts",
        "batch_key": batch_key,
        "work_dir": str(work_dir),
        "db_path": str(db_path),
        "outbox_path": str(outbox_path),
        "source_reports": source_reports,
        "candidate_count": len(ranked),
        "selected_count": len(selected),
        "early_blocked_count": len(early_blocked),
        "taste_blocked_count": len(taste_blocked),
        "conversion": {"total": conversion.get("total", 0), "ok_count": conversion.get("ok_count", 0), "failed_count": conversion.get("failed_count", 0), "dry_run": conversion.get("dry_run")},
        "vetted_count": len(vetted_posts),
        "filtered_count": len(original_posts) - len(vetted_posts),
        "queued_messages": len(messages),
        "queued_approval_cards": approval_card_count,
        "ready_to_publish": {k: ready.get(k) for k in ("ready_count", "held_count", "publish_safe_pass_count", "publish_safe_block_count", "report_path")},
        "gates": gates,
        "candidates_input": str(candidates_input),
        "selected_input": str(selected_input),
        "converted_input": str(converted_input),
    }
    (work_dir / "auto-source-hunter-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def render_auto_source_hunter(summary: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot auto-source hunter",
        f"Batch: {summary.get('batch_key')}",
        f"Status: {'OK' if summary.get('ok') else 'BLOCK'} ({summary.get('reason')})",
        f"Work dir: {summary.get('work_dir')}",
        "",
        "Sources:",
    ]
    for source in summary.get("source_reports", []):
        errors = [p.get("error") for p in source.get("pages", []) if p.get("error")]
        lines.append(f"- {source.get('name')}: raw={source.get('raw_products', 0)} accepted={source.get('accepted_candidates', 0)} errors={errors[:2]}")
    conv = summary.get("conversion", {})
    ready = summary.get("ready_to_publish", {})
    lines.extend([
        "",
        "Pipeline:",
        f"- candidates: {summary.get('candidate_count', 0)}",
        f"- early blocked: {summary.get('early_blocked_count', 0)}",
        f"- taste blocked: {summary.get('taste_blocked_count', 0)}",
        f"- selected: {summary.get('selected_count', 0)}",
        f"- conversion: ok={conv.get('ok_count', 0)} failed={conv.get('failed_count', 0)} dry_run={conv.get('dry_run')}",
        f"- vetted: {summary.get('vetted_count', 0)} filtered={summary.get('filtered_count', 0)}",
        f"- queued messages: {summary.get('queued_messages', 0)} approval_cards={summary.get('queued_approval_cards', 0)}",
        f"- ready: {ready.get('ready_count', 0)} held={ready.get('held_count', 0)} publish-safe-pass={ready.get('publish_safe_pass_count', 0)}",
        "",
        "Artifacts:",
        f"- summary: {summary.get('work_dir')}/auto-source-hunter-summary.json",
        f"- selected input: {summary.get('selected_input')}",
        f"- converted input: {summary.get('converted_input')}",
        f"- outbox: {summary.get('outbox_path')}",
    ])
    return "\n".join(lines)
