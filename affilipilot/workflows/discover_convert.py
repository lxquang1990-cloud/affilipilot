from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.scanner.browser_exec import browser_render_discover
from affilipilot.scanner.core import scan_result_to_input_lines
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input


def run_discover_convert(
    *,
    url: str,
    work_dir: str | Path,
    source: str = "AUTO",
    category: str = "unknown",
    campaign_key: str = "",
    limit: int = 10,
    dry_run: bool = True,
    timeout_ms: int = 45000,
    wait_ms: int = 3000,
    headless: bool = True,
) -> dict[str, Any]:
    """Discover product-detail URLs from a dynamic page, then convert only discovered products.

    This workflow performs no drafting, no approval delivery, and no publishing.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    scan_path = work_dir / "discovered-products.json"
    input_path = work_dir / "discovered-products.input.txt"
    converted_json = work_dir / "discovered-products.converted.json"
    converted_input = work_dir / "discovered-products.converted.txt"

    discovery = browser_render_discover(
        url,
        out_path=scan_path,
        source=source,
        category=category,
        limit=limit,
        timeout_ms=timeout_ms,
        wait_ms=wait_ms,
        headless=headless,
    )
    input_lines: list[str] = []
    conversion: dict[str, Any] | None = None
    if discovery.ok and discovery.scan_path:
        input_lines = scan_result_to_input_lines(discovery.scan_path, max_items=limit)
        input_path.write_text("\n".join(input_lines) + ("\n" if input_lines else ""), encoding="utf-8")
        conversion = convert_input_links(input_path, converted_json, dry_run=dry_run, limit=limit, campaign_key=campaign_key)
        write_converted_input(converted_json, converted_input)
    else:
        input_path.write_text("", encoding="utf-8")
        converted_json.write_text(json.dumps({"total": 0, "ok_count": 0, "failed_count": 0, "items": [], "error": discovery.error}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        converted_input.write_text("", encoding="utf-8")

    summary = {
        "url": url,
        "source": source,
        "category": category,
        "campaign_key": campaign_key,
        "dry_run": dry_run,
        "work_dir": str(work_dir),
        "discovery": {
            "ok": discovery.ok,
            "total": discovery.total,
            "scan_path": discovery.scan_path,
            "error": discovery.error,
            "notes": discovery.notes,
        },
        "input_path": str(input_path),
        "converted_json": str(converted_json),
        "converted_input": str(converted_input),
        "conversion": conversion or {"total": 0, "ok_count": 0, "failed_count": 0, "items": []},
    }
    (work_dir / "discover-convert-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def render_discover_convert_summary(summary: dict[str, Any]) -> str:
    discovery = summary.get("discovery", {})
    conversion = summary.get("conversion", {})
    lines = [
        "🐌 AffiliPilot discover-convert",
        f"URL: {summary['url']}",
        f"Source: {summary['source']} category={summary['category']} campaign={summary['campaign_key'] or '(auto)'}",
        f"Dry run: {summary['dry_run']}",
        f"Discovery: {'OK' if discovery.get('ok') else 'BLOCK'} total={discovery.get('total', 0)}",
    ]
    if discovery.get("error"):
        lines.append(f"Discovery error: {discovery['error']}")
    lines.extend([
        f"Conversion: ok={conversion.get('ok_count', 0)} failed={conversion.get('failed_count', 0)} total={conversion.get('total', 0)}",
        f"Input: {summary['input_path']}",
        f"Converted input: {summary['converted_input']}",
        f"Report: {summary['work_dir']}/discover-convert-summary.json",
    ])
    if conversion.get("failed_count"):
        lines.append("Blocked rows:")
        for row in conversion.get("items", []):
            if not row.get("result", {}).get("ok"):
                cls = row.get("preflight", {}).get("classification", {})
                lines.append(f"- index={row.get('index')} marketplace={cls.get('marketplace')} kind={cls.get('kind')} error={row.get('result', {}).get('error')}")
    return "\n".join(lines)
