from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass
class BrowserScanPlan:
    url: str
    source: str = "AUTO"
    category: str = "unknown"
    wait_selectors: tuple[str, ...] = (
        '[data-qa-locator="product-item"]',
        '.product-card',
        '.product-info',
        'a[href*="/products/"]',
    )
    extract_fields: tuple[str, ...] = ("title", "url", "price", "image_url")
    safety: str = "discovery_only_no_publish"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["wait_selectors"] = list(self.wait_selectors)
        data["extract_fields"] = list(self.extract_fields)
        return data


def build_browser_scan_plan(url: str, *, source: str = "AUTO", category: str = "unknown", out_path: str | Path | None = None) -> BrowserScanPlan:
    plan = BrowserScanPlan(url=url, source=source, category=category)
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def render_browser_scan_plan(plan: BrowserScanPlan) -> str:
    lines = [
        "🐌 AffiliPilot browser scan plan",
        f"URL: {plan.url}",
        f"Source: {plan.source}",
        f"Category: {plan.category}",
        f"Safety: {plan.safety}",
        "Wait selectors:",
    ]
    lines.extend(f"- {selector}" for selector in plan.wait_selectors)
    lines.extend(["Extract fields:", *[f"- {field}" for field in plan.extract_fields]])
    return "\n".join(lines)
