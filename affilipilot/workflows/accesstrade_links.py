from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.client import AccesstradeCampaign, AccesstradeConfig, create_tracking_link
from affilipilot.links.subid import build_utm, make_tracking_identity
from affilipilot.marketplaces import classify_url, discovery_advice
from affilipilot.workflows.daily_batch import load_products


def _preflight_conversion_url(url: str) -> tuple[bool, dict]:
    classification = classify_url(url)
    advice = discovery_advice(url)
    if classification.marketplace == "UNKNOWN":
        return True, {"ok": True, "classification": asdict(classification), "advice": asdict(advice)}
    if classification.kind == "product":
        return True, {"ok": True, "classification": asdict(classification), "advice": asdict(advice)}
    return False, {
        "ok": False,
        "classification": asdict(classification),
        "advice": asdict(advice),
        "error": f"marketplace_preflight_block:{classification.marketplace}:{classification.kind}",
    }


def _list_meta(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        text = value.strip()
        if text == "[]":
            return ""
        if text.startswith("["):
            try:
                return _list_meta(json.loads(text))
            except json.JSONDecodeError:
                return text
        return text
    return ""


def convert_input_links(input_path: str | Path, out_path: str | Path, *, dry_run: bool = True, limit: int | None = None, campaign_key: str = "", allow_channel_urls: bool = False) -> dict:
    products = load_products(input_path)
    if limit is not None:
        products = products[:limit]
    converted = []
    for index, product in enumerate(products, 1):
        identity = make_tracking_identity(product.title or product.url, index)
        utm = build_utm(identity)
        preflight_ok, preflight = _preflight_conversion_url(product.url)
        if not preflight_ok and not allow_channel_urls:
            result = {
                "ok": False,
                "original_url": product.url,
                "affiliate_url": "",
                "payload": {},
                "status": 0,
                "error": preflight["error"],
                "dry_run": dry_run,
                "campaign_key": campaign_key,
            }
        else:
            try:
                config = None
                effective_campaign_key = campaign_key or product.campaign_key
                if product.campaign_id:
                    key = effective_campaign_key or "PRODUCT"
                    config = AccesstradeConfig.from_env()
                    config.campaigns[key] = AccesstradeCampaign(key=key, campaign_id=product.campaign_id)
                    effective_campaign_key = key
                link_result = create_tracking_link(url=product.url, utm=utm, config=config, dry_run=dry_run, campaign_key=effective_campaign_key)
                result = asdict(link_result)
            except Exception as exc:  # noqa: BLE001
                result = {
                    "ok": False,
                    "original_url": product.url,
                    "affiliate_url": "",
                    "payload": {},
                    "status": 0,
                    "error": f"accesstrade_convert_failed:{type(exc).__name__}",
                    "dry_run": dry_run,
                    "campaign_key": campaign_key,
                }
        row = {
            "index": index,
            "product": asdict(product),
            "tracking_identity": asdict(identity),
            "utm": utm,
            "preflight": preflight,
            "result": result,
        }
        if result.get("ok") and result.get("affiliate_url"):
            row["product"]["affiliate_url"] = result["affiliate_url"]
            row["product"]["tracking_url"] = result["affiliate_url"]
            row["product"]["campaign_key"] = result.get("campaign_key", "")
            row["product"]["campaign_id"] = str((result.get("payload") or {}).get("campaign_id", ""))
            row["product"]["link_status"] = result.get("link_status", "")
            if result.get("short_url"):
                row["product"]["short_url"] = result["short_url"]
        converted.append(row)
    summary = {
        "input_path": str(input_path),
        "dry_run": dry_run,
        "allow_channel_urls": allow_channel_urls,
        "total": len(converted),
        "ok_count": sum(1 for row in converted if row["result"].get("ok")),
        "failed_count": sum(1 for row in converted if not row["result"].get("ok")),
        "items": converted,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def write_converted_input(converted_json: str | Path, out_path: str | Path) -> Path:
    data = json.loads(Path(converted_json).read_text(encoding="utf-8"))
    lines = []
    for row in data.get("items", []):
        if not row.get("result", {}).get("ok"):
            continue
        product = row["product"]
        link = product.get("affiliate_url") or product.get("tracking_url") or product.get("url", "")
        parts = [link]
        raw = product.get("raw") or {}
        image_urls_meta = _list_meta(raw.get("image_urls")) or _list_meta(product.get("image_urls"))
        video_urls_meta = _list_meta(raw.get("video_urls")) or _list_meta(product.get("video_urls"))
        if image_urls_meta:
            product["image_urls"] = image_urls_meta
        if video_urls_meta:
            product["video_urls"] = video_urls_meta
        for key in ("title", "category", "price_vnd", "commission_rate", "image_url", "image_path", "image_urls", "video_url", "video_path", "video_urls", "affiliate_url", "tracking_url", "short_url", "campaign_id", "campaign_key", "link_status", "notes"):
            value = product.get(key)
            if value not in (None, ""):
                out_key = "price" if key == "price_vnd" else key
                parts.append(f"{out_key}={value}")
        lines.append(" | ".join(parts))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out_path
