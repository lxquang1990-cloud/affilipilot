#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from affilipilot.accesstrade.catalog import fetch_datafeeds  # noqa: E402
from affilipilot.content.early_filter import evaluate_early_product_filter  # noqa: E402
from affilipilot.marketplaces.shopee_public_api import search_products  # noqa: E402
from affilipilot.content.product_taste import evaluate_product_taste  # noqa: E402
from affilipilot.models import ProductCandidate  # noqa: E402
from affilipilot.scoring.product_score import score_product  # noqa: E402
from affilipilot.sources.manual_input import parse_link_lines  # noqa: E402


@dataclass
class SeedCandidate:
    product: dict
    keyword: str
    domain: str
    score: int
    reasons: list[str] = field(default_factory=list)


def _as_candidate(product: dict, *, keyword: str, category: str) -> ProductCandidate:
    return ProductCandidate(
        url=str(product.get("url") or ""),
        title=str(product.get("title") or ""),
        category=category or str(product.get("category") or "unknown"),
        price_vnd=product.get("discount_vnd") or product.get("price_vnd"),
        image_url=str(product.get("image_url") or ""),
        affiliate_url=str(product.get("affiliate_url") or ""),
        tracking_url=str(product.get("affiliate_url") or ""),
        notes=(str(product.get("merchant") or "") + f";seed_keyword={keyword};seed_hunter").strip(";"),
        media_source="accesstrade_api" if product.get("image_url") else "",
        media_confidence="official" if product.get("image_url") else "",
        original_url=str(product.get("url") or ""),
    )


def _keyword_match_score(title: str, keyword: str) -> int:
    title_l = title.lower()
    tokens = [t for t in keyword.lower().split() if len(t) >= 2]
    if not tokens:
        return 0
    hits = sum(1 for token in tokens if token in title_l)
    return int(30 * hits / len(tokens))


def _keyword_match_ratio(title: str, keyword: str) -> float:
    title_l = title.lower()
    tokens = [t for t in keyword.lower().split() if len(t) >= 2]
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in title_l)
    return hits / len(tokens)


def _seed_hard_block(cand: ProductCandidate, keyword: str) -> bool:
    text = f"{cand.title} {cand.category} {cand.notes} {cand.url}".lower()
    blocked = (
        "xe đạp", "shimano", "sên xích", "ghi đông", "sang đề", "phụ tùng",
        "xuyên tâm liên", "viên uống", "khẩu trang", "sát khuẩn", "sát trùng", "alcohol", "chống nắng",
        "thuốc", "thảo mộc", "hô hấp", "vi khuẩn", "virut", "virus",
    )
    if any(term in text for term in blocked):
        return True
    if "source=seed_file" in text:
        return False
    return _keyword_match_ratio(cand.title, keyword) < 0.45


def _candidate_bonus(cand: ProductCandidate) -> tuple[int, list[str]]:
    text = cand.notes.lower()
    bonus = 0
    reasons: list[str] = []
    if "rating=" in text:
        try:
            rating = float(text.split("rating=", 1)[1].split(";", 1)[0])
            if rating >= 4.7:
                bonus += 12
                reasons.append("rating>=4.7+12")
        except ValueError:
            pass
    for key, threshold, points in (("sold=", 100, 10), ("historical_sold=", 300, 10), ("review_count=", 30, 8)):
        if key in text:
            try:
                value = int(float(text.split(key, 1)[1].split(";", 1)[0]))
            except ValueError:
                value = 0
            if value >= threshold:
                bonus += points
                reasons.append(f"{key.rstrip('=')}>={threshold}+{points}")
    if "official_shop" in text or "shopee_verified" in text:
        bonus += 8
        reasons.append("shop_trust+8")
    if cand.video_urls:
        bonus += 10
        reasons.append("has_video+10")
    return bonus, reasons


def _accept_candidate(cand: ProductCandidate, keyword: str) -> tuple[bool, int, list[str]]:
    if _seed_hard_block(cand, keyword):
        return False, 0, ["seed_hard_block"]
    early = evaluate_early_product_filter(cand)
    if not early.passed:
        return False, 0, early.reasons
    taste = evaluate_product_taste(cand)
    if not taste.passed:
        return False, 0, taste.penalties
    scored = score_product(cand)
    bonus, bonus_reasons = _candidate_bonus(cand)
    score = scored["score"] + _keyword_match_score(cand.title, keyword) + max(taste.score - 50, -25) + bonus
    if cand.image_url:
        score += 10
    if cand.price_vnd and 80_000 <= int(cand.price_vnd) <= 1_500_000:
        score += 10
    return True, score, scored["reasons"] + taste.reasons + taste.penalties + bonus_reasons


def _keyword_for_candidate(cand: ProductCandidate, config: dict) -> tuple[str, str]:
    title = cand.title.lower()
    for item in config.get("keywords", []):
        keyword = item["keyword"]
        if _keyword_match_ratio(title, keyword) >= 0.35:
            return keyword, item.get("category", cand.category or "unknown")
    first = (config.get("keywords") or [{"keyword": "manual_seed", "category": cand.category or "unknown"}])[0]
    return first["keyword"], first.get("category", cand.category or "unknown")


def hunt(config_path: Path, *, out_dir: Path, per_keyword_limit: int, final_limit: int, source: str = "shopee_api", seed_file: Path | None = None) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[SeedCandidate] = []
    source_reports = []
    if seed_file:
        manual_candidates = parse_link_lines(seed_file.read_text(encoding="utf-8"))
        source_reports.append({"keyword": "manual_seed_file", "domain": "manual", "source": "seed_file", "ok": True, "error": "", "products": len(manual_candidates)})
        for cand in manual_candidates:
            keyword, category = _keyword_for_candidate(cand, config)
            cand.category = category
            cand.notes = (cand.notes + ";" if cand.notes else "") + "source=seed_file;seed_hunter"
            ok, score, reasons = _accept_candidate(cand, keyword)
            if ok:
                candidates.append(SeedCandidate(product=asdict(cand), keyword=keyword, domain="manual", score=score, reasons=reasons))
    for item in config.get("keywords", []):
        keyword = item["keyword"]
        category = item.get("category", "unknown")
        if source in ("shopee_api", "all"):
            try:
                products = search_products(keyword, limit=per_keyword_limit)
                source_reports.append({"keyword": keyword, "domain": "shopee.vn", "source": "shopee_api", "ok": True, "error": "", "products": len(products)})
            except Exception as exc:  # noqa: BLE001
                products = []
                source_reports.append({"keyword": keyword, "domain": "shopee.vn", "source": "shopee_api", "ok": False, "error": str(exc) or type(exc).__name__, "products": 0})
            for product in products:
                cand = product.to_candidate(category=category, keyword=keyword)
                ok, score, reasons = _accept_candidate(cand, keyword)
                if ok:
                    candidates.append(SeedCandidate(product=asdict(cand), keyword=keyword, domain="shopee.vn", score=score, reasons=reasons))
        if source in ("accesstrade", "all"):
            for domain in item.get("domains", ["shopee.vn", "lazada.vn"]):
                try:
                    result = fetch_datafeeds(domain=domain, cat=keyword, limit=per_keyword_limit, timeout=30)
                except Exception as exc:  # noqa: BLE001
                    source_reports.append({"keyword": keyword, "domain": domain, "source": "accesstrade_datafeed", "ok": False, "error": type(exc).__name__, "products": 0})
                    continue
                products = result.get("products") or []
                source_reports.append({"keyword": keyword, "domain": domain, "source": "accesstrade_datafeed", "ok": result.get("ok"), "error": result.get("error", ""), "products": len(products)})
                for product in products:
                    cand = _as_candidate(product, keyword=keyword, category=category)
                    ok, score, reasons = _accept_candidate(cand, keyword)
                    if ok:
                        candidates.append(SeedCandidate(product=asdict(cand), keyword=keyword, domain=domain, score=score, reasons=reasons))
    candidates.sort(key=lambda item: item.score, reverse=True)
    deduped: list[SeedCandidate] = []
    seen = set()
    for item in candidates:
        key = (item.product.get("url") or item.product.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= final_limit:
            break
    products = [item.product for item in deduped]
    input_path = out_dir / "seed-hunter.input.txt"
    # write_products_input expects Accesstrade-shaped dicts; write manually from normalized candidate.
    lines = []
    for item in deduped:
        p = item.product
        parts = [p.get("url", "")]
        for key in ("title", "category", "price_vnd", "image_url", "affiliate_url", "tracking_url", "notes", "media_source", "media_confidence", "original_url"):
            val = p.get(key)
            if val not in (None, ""):
                parts.append(f"{key.replace('price_vnd','price')}={val}")
        lines.append(" | ".join(str(x) for x in parts))
    input_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    summary = {"ok": bool(deduped), "count": len(deduped), "input_path": str(input_path), "sources": source_reports, "seeds": [asdict(item) for item in deduped]}
    (out_dir / "seed-hunter-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def render(summary: dict) -> str:
    lines = ["🐌 AffiliPilot Seed Hunter", f"Seeds: {summary['count']}", f"Input: {summary['input_path']}", ""]
    for item in summary.get("seeds", [])[:10]:
        p = item["product"]
        lines.append(f"- {item['score']} | {item['keyword']} | {p.get('title')} | {p.get('url')}")
    if not summary.get("seeds"):
        lines.append("No seed candidates passed filters.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/seed-hunter-keywords.json")
    parser.add_argument("--out-dir", default="data/runs/seed-hunter")
    parser.add_argument("--per-keyword-limit", type=int, default=20)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source", choices=["shopee_api", "accesstrade", "all", "seed_file"], default="shopee_api")
    parser.add_argument("--seed-file", default="")
    args = parser.parse_args()
    source = "shopee_api" if args.source == "seed_file" else args.source
    summary = hunt(Path(args.config), out_dir=Path(args.out_dir), per_keyword_limit=args.per_keyword_limit, final_limit=args.limit, source=source, seed_file=Path(args.seed_file) if args.seed_file else None)
    print(render(summary))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
