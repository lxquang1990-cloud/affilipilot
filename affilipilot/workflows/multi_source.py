from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.scanner.browser_exec import browser_render_discover
from affilipilot.scoring.product_score import score_product
from affilipilot.sources.manual_input import parse_link_lines
from affilipilot.workflows.discover_convert import run_discover_convert

DEFAULT_SOURCES = [
    {
        "name": "lazada_khan_sua",
        "url": "https://www.lazada.vn/tag/khan-sua-em-be/",
        "source": "LAZADA",
        "category": "baby_care",
        "campaign_key": "LAZADA",
    },
]


def load_source_config(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return DEFAULT_SOURCES
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("sources", [])
    if not isinstance(data, list):
        raise ValueError("source config must be a list or {'sources': [...]} object")
    return data


def _norm_url(url: str) -> str:
    return (url or "").split("?", 1)[0].rstrip("/")


def run_multi_source_discovery(
    *,
    sources: list[dict[str, Any]],
    work_dir: str | Path,
    per_source_limit: int = 5,
    final_limit: int = 5,
    dry_run: bool = True,
    timeout_ms: int = 45000,
    wait_ms: int = 3000,
    headless: bool = True,
) -> dict[str, Any]:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    source_reports = []
    candidates_by_url: dict[str, dict[str, Any]] = {}

    for index, source_cfg in enumerate(sources, 1):
        name = source_cfg.get("name") or f"source_{index}"
        source_dir = work_dir / name
        url = source_cfg["url"]
        source = source_cfg.get("source", "AUTO")
        category = source_cfg.get("category", "unknown")
        campaign_key = source_cfg.get("campaign_key", source)
        report = run_discover_convert(
            url=url,
            work_dir=source_dir,
            source=source,
            category=category,
            campaign_key=campaign_key,
            limit=per_source_limit,
            dry_run=dry_run,
            timeout_ms=timeout_ms,
            wait_ms=wait_ms,
            headless=headless,
        )
        source_reports.append(report)
        converted_input = Path(report.get("converted_input", ""))
        if not converted_input.exists():
            continue
        for product in parse_link_lines(converted_input.read_text(encoding="utf-8")):
            key = _norm_url(product.affiliate_url or product.tracking_url or product.url)
            score_info = score_product(product)
            item = {
                "score": int(score_info["score"]),
                "score_reasons": score_info.get("reasons", []),
                "source_name": name,
                "source_url": url,
                "line": " | ".join(part for part in [
                    product.affiliate_url or product.tracking_url or product.url,
                    f"title={product.title}",
                    f"category={product.category}",
                    f"image_url={product.image_url}" if product.image_url else "",
                    f"image_path={product.image_path}" if product.image_path else "",
                    f"image_urls={','.join(product.image_urls)}" if product.image_urls else "",
                    f"video_url={product.video_url}" if product.video_url else "",
                    f"video_urls={','.join(product.video_urls)}" if product.video_urls else "",
                    f"affiliate_url={product.affiliate_url}" if product.affiliate_url else "",
                    f"tracking_url={product.tracking_url}" if product.tracking_url else "",
                    f"notes={product.notes}" if product.notes else "",
                ] if part).strip(" |"),
            }
            if key not in candidates_by_url or item["score"] > candidates_by_url[key]["score"]:
                candidates_by_url[key] = item

    candidates = sorted(candidates_by_url.values(), key=lambda item: item["score"], reverse=True)
    selected = candidates[:final_limit]
    merged_input = work_dir / "multi-source.selected.txt"
    merged_input.write_text("\n".join(item["line"] for item in selected) + ("\n" if selected else ""), encoding="utf-8")
    summary = {
        "work_dir": str(work_dir),
        "source_count": len(sources),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "merged_input": str(merged_input),
        "selected": selected,
        "sources": source_reports,
    }
    (work_dir / "multi-source-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def render_multi_source_summary(summary: dict[str, Any]) -> str:
    lines = [
        "🐌 AffiliPilot multi-source scanner",
        f"Sources: {summary['source_count']}",
        f"Candidates: {summary['candidate_count']}",
        f"Selected: {summary['selected_count']}",
        f"Merged input: {summary['merged_input']}",
        "",
        "Top selected:",
    ]
    for item in summary.get("selected", [])[:10]:
        lines.append(f"- score={item['score']} source={item['source_name']} title={item['line'].split('title=', 1)[-1].split(' | ', 1)[0]}")
    return "\n".join(lines)
