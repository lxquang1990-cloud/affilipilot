#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from affilipilot.accesstrade.catalog import fetch_datafeeds, write_products_input  # noqa: E402
from affilipilot.content.early_filter import evaluate_early_product_filter  # noqa: E402
from affilipilot.content.product_taste import evaluate_product_taste  # noqa: E402
from affilipilot.models import ProductCandidate  # noqa: E402
from affilipilot.scoring.product_score import score_product  # noqa: E402


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
    return _keyword_match_ratio(cand.title, keyword) < 0.45


def hunt(config_path: Path, *, out_dir: Path, per_keyword_limit: int, final_limit: int) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[SeedCandidate] = []
    source_reports = []
    for item in config.get("keywords", []):
        keyword = item["keyword"]
        category = item.get("category", "unknown")
        for domain in item.get("domains", ["shopee.vn", "lazada.vn"]):
            try:
                result = fetch_datafeeds(domain=domain, cat=keyword, limit=per_keyword_limit, timeout=30)
            except Exception as exc:  # noqa: BLE001
                source_reports.append({"keyword": keyword, "domain": domain, "ok": False, "error": type(exc).__name__, "products": 0})
                continue
            products = result.get("products") or []
            source_reports.append({"keyword": keyword, "domain": domain, "ok": result.get("ok"), "error": result.get("error", ""), "products": len(products)})
            for product in products:
                cand = _as_candidate(product, keyword=keyword, category=category)
                if _seed_hard_block(cand, keyword):
                    continue
                early = evaluate_early_product_filter(cand)
                if not early.passed:
                    continue
                taste = evaluate_product_taste(cand)
                if not taste.passed:
                    continue
                scored = score_product(cand)
                score = scored["score"] + _keyword_match_score(cand.title, keyword) + max(taste.score - 50, -25)
                if cand.image_url:
                    score += 10
                if cand.price_vnd and 80_000 <= int(cand.price_vnd) <= 1_500_000:
                    score += 10
                candidates.append(SeedCandidate(product=asdict(cand), keyword=keyword, domain=domain, score=score, reasons=scored["reasons"] + taste.reasons + taste.penalties))
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
    args = parser.parse_args()
    summary = hunt(Path(args.config), out_dir=Path(args.out_dir), per_keyword_limit=args.per_keyword_limit, final_limit=args.limit)
    print(render(summary))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
