from __future__ import annotations

import json
from pathlib import Path

from affilipilot.scanner.core import scan_result_to_input_lines, scan_url, write_scan_result
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input
from affilipilot.workflows.approval import create_approval_batch


def run_product_scan(url: str, out_path: str | Path, *, source: str = "AUTO", category: str = "unknown", campaign_key: str = "", limit: int = 10, timeout: int = 30) -> dict:
    result = scan_url(url, source=source, category=category, campaign_key=campaign_key, limit=limit, timeout=timeout)
    path = write_scan_result(result, out_path)
    return {"scan_path": str(path), **result.to_dict()}


def draft_from_scan(
    scan_json: str | Path,
    *,
    work_dir: str | Path,
    db_path: str | Path,
    batch_key: str,
    outbox_path: str | Path,
    limit: int = 5,
    convert_affiliate: bool = False,
    real_accesstrade: bool = False,
    campaign_key: str = "",
) -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / "scan-products.input.txt"
    lines = scan_result_to_input_lines(scan_json, max_items=limit)
    input_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    effective_input = input_path
    conversion_summary = None
    if convert_affiliate and lines:
        converted_json = work_dir / "scan-products.converted.json"
        converted_txt = work_dir / "scan-products.converted.txt"
        conversion_summary = convert_input_links(input_path, converted_json, dry_run=not real_accesstrade, limit=limit, campaign_key=campaign_key)
        write_converted_input(converted_json, converted_txt)
        effective_input = converted_txt

    drafts_dir = work_dir / "drafts"
    manifest = create_approval_batch(effective_input, drafts_dir, db_path, batch_key=batch_key, limit=limit)
    messages = queue_approval_batch(db_path, batch_key=batch_key, outbox_path=outbox_path)
    summary = {
        "scan_json": str(scan_json),
        "input_path": str(input_path),
        "effective_input": str(effective_input),
        "batch_key": batch_key,
        "db_path": str(db_path),
        "drafts_dir": str(drafts_dir),
        "outbox_path": str(outbox_path),
        "selected": manifest["selected"],
        "total_products": manifest["total_products"],
        "outbox_messages": len(messages),
        "conversion": conversion_summary,
    }
    (work_dir / "scan-draft-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
