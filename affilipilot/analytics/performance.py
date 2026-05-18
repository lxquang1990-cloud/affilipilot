from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass
class PostPerformance:
    batch_key: str
    post_id: str
    facebook_post_id: str = ""
    category: str = ""
    angle: str = ""
    price_vnd: int = 0
    visual_type: str = "catalog"
    clicks: int = 0
    conversions: int = 0
    commission_vnd: int = 0

    @property
    def ctr_proxy(self) -> float:
        return float(self.clicks)

    @property
    def cvr(self) -> float:
        return self.conversions / self.clicks if self.clicks else 0.0

def load_performance(path: str | Path) -> list[PostPerformance]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8") or "[]")
    return [PostPerformance(**item) for item in data]

def save_performance(path: str | Path, items: list[PostPerformance]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def record_performance(path: str | Path, item: PostPerformance) -> None:
    items = load_performance(path)
    replaced = False
    for idx, existing in enumerate(items):
        if existing.batch_key == item.batch_key and existing.post_id == item.post_id:
            items[idx] = item
            replaced = True
            break
    if not replaced:
        items.append(item)
    save_performance(path, items)

def summarize_performance(path: str | Path) -> dict[str, Any]:
    items = load_performance(path)
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"posts": 0, "clicks": 0, "conversions": 0, "commission_vnd": 0})
    by_angle: dict[str, dict[str, int]] = defaultdict(lambda: {"posts": 0, "clicks": 0, "conversions": 0, "commission_vnd": 0})
    for item in items:
        for bucket, key in ((by_category, item.category or "unknown"), (by_angle, item.angle or "unknown")):
            bucket[key]["posts"] += 1
            bucket[key]["clicks"] += item.clicks
            bucket[key]["conversions"] += item.conversions
            bucket[key]["commission_vnd"] += item.commission_vnd
    return {
        "total_posts": len(items),
        "total_clicks": sum(i.clicks for i in items),
        "total_conversions": sum(i.conversions for i in items),
        "total_commission_vnd": sum(i.commission_vnd for i in items),
        "by_category": dict(by_category),
        "by_angle": dict(by_angle),
    }

def render_performance_summary(summary: dict[str, Any]) -> str:
    lines = ["🐌 AffiliPilot performance summary", f"Posts: {summary['total_posts']}", f"Clicks: {summary['total_clicks']}", f"Conversions: {summary['total_conversions']}", f"Commission: {summary['total_commission_vnd']:,}đ".replace(",", ".")]
    lines.append("By category:")
    for key, value in sorted(summary.get("by_category", {}).items()):
        lines.append(f"- {key}: posts={value['posts']} clicks={value['clicks']} conversions={value['conversions']} commission={value['commission_vnd']}")
    lines.append("By angle:")
    for key, value in sorted(summary.get("by_angle", {}).items()):
        lines.append(f"- {key}: posts={value['posts']} clicks={value['clicks']} conversions={value['conversions']} commission={value['commission_vnd']}")
    return "\n".join(lines)
