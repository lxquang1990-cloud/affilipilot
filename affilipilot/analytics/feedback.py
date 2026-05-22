from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.reports import ensure_reporting_schema
from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.lifecycle import ensure_publish_events_table

@dataclass
class PostFeedback:
    batch_key: str
    post_id: str
    title: str = ""
    category: str = "unknown"
    campaign_key: str = ""
    money_score: int = 0
    niche_score: int = 0
    facebook_post_id: str = ""
    published_at: str = ""
    orders: int = 0
    confirmed_orders: int = 0
    pending_orders: int = 0
    rejected_orders: int = 0
    billing_vnd: float = 0.0
    commission_vnd: float = 0.0
    signals: list[str] = field(default_factory=list)


def _latest_published_events(db: AffiliPilotDB, batch_key: str = "") -> dict[tuple[str, str], dict[str, Any]]:
    ensure_publish_events_table(db)
    where = "WHERE state = 'published'" + (" AND batch_key = ?" if batch_key else "")
    params = (batch_key,) if batch_key else ()
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM publish_events {where} ORDER BY created_at ASC, id ASC",
            params,
        ).fetchall()
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        latest[(data["batch_key"], data["post_id"])] = data
    return latest


def _orders_by_post_id(db: AffiliPilotDB) -> dict[str, list[dict[str, Any]]]:
    ensure_reporting_schema(db)
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM accesstrade_orders").fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        data = dict(row)
        post_id = data.get("utm_content") or ""
        if post_id:
            result.setdefault(post_id, []).append(data)
    return result


def _status_bucket(order: dict[str, Any]) -> str:
    status = str(order.get("status") or order.get("is_confirmed") or "").lower()
    if status in {"approved", "success", "confirmed", "1", "true"}:
        return "confirmed"
    if status in {"rejected", "cancelled", "canceled", "failed", "0", "false"}:
        return "rejected"
    return "pending"


def _post_from_batches(db: AffiliPilotDB, batch_key: str, post_id: str) -> dict[str, Any] | None:
    batch = db.get_batch(batch_key)
    if not batch:
        return None
    for post in batch.get("manifest", {}).get("posts", []):
        if post.get("post_id") == post_id:
            return post
    return None


def _niche_score_from_reasons(reasons: list[str]) -> int:
    for reason in reasons:
        if str(reason).startswith("niche_fit:"):
            raw = str(reason).split(":", 1)[1]
            number = raw.split("+", 1)[0].split("-", 1)[0]
            try:
                return int(float(number))
            except ValueError:
                return 0
    return 0


def build_post_feedback(db_path: str | Path, *, batch_key: str = "") -> list[PostFeedback]:
    db = AffiliPilotDB(db_path)
    published = _latest_published_events(db, batch_key=batch_key)
    orders_by_post = _orders_by_post_id(db)
    items: list[PostFeedback] = []
    for (event_batch, post_id), event in sorted(published.items()):
        post = _post_from_batches(db, event_batch, post_id) or {}
        product = post.get("product", {})
        score_reasons = [str(x) for x in post.get("score_reasons", [])]
        orders = orders_by_post.get(post_id, [])
        buckets = [_status_bucket(order) for order in orders]
        signals: list[str] = []
        if orders:
            signals.append("has_orders")
        if any(bucket == "confirmed" for bucket in buckets):
            signals.append("has_confirmed_order")
        if post.get("media", {}).get("gallery_count", 0):
            signals.append("has_gallery_media")
        if product.get("video_url") or product.get("video_urls"):
            signals.append("has_video")
        items.append(PostFeedback(
            batch_key=event_batch,
            post_id=post_id,
            title=product.get("title", ""),
            category=product.get("category", "unknown"),
            campaign_key=product.get("campaign_key", ""),
            money_score=int(post.get("score") or 0),
            niche_score=_niche_score_from_reasons(score_reasons),
            facebook_post_id=event.get("facebook_post_id", ""),
            published_at=event.get("created_at", ""),
            orders=len(orders),
            confirmed_orders=sum(1 for bucket in buckets if bucket == "confirmed"),
            pending_orders=sum(1 for bucket in buckets if bucket == "pending"),
            rejected_orders=sum(1 for bucket in buckets if bucket == "rejected"),
            billing_vnd=sum(float(order.get("billing") or 0) for order in orders),
            commission_vnd=sum(float(order.get("pub_commission") or 0) for order in orders),
            signals=signals,
        ))
    return items


def summarize_feedback(items: list[PostFeedback]) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
    for item in items:
        row = by_category.setdefault(item.category or "unknown", {"posts": 0, "orders": 0, "confirmed_orders": 0, "commission_vnd": 0.0})
        row["posts"] += 1
        row["orders"] += item.orders
        row["confirmed_orders"] += item.confirmed_orders
        row["commission_vnd"] += item.commission_vnd
    top_posts = sorted(items, key=lambda x: (x.commission_vnd, x.confirmed_orders, x.orders), reverse=True)[:10]
    return {
        "published_posts": len(items),
        "orders": sum(i.orders for i in items),
        "confirmed_orders": sum(i.confirmed_orders for i in items),
        "pending_orders": sum(i.pending_orders for i in items),
        "rejected_orders": sum(i.rejected_orders for i in items),
        "billing_vnd": sum(i.billing_vnd for i in items),
        "commission_vnd": sum(i.commission_vnd for i in items),
        "by_category": by_category,
        "top_posts": [item.__dict__ for item in top_posts],
    }


def build_feedback_report(db_path: str | Path, *, batch_key: str = "") -> dict[str, Any]:
    items = build_post_feedback(db_path, batch_key=batch_key)
    return {"items": [item.__dict__ for item in items], "summary": summarize_feedback(items)}


def render_feedback_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "🐌 AffiliPilot performance feedback loop",
        f"Published posts: {summary['published_posts']}",
        f"Orders: {summary['orders']} total / {summary['confirmed_orders']} confirmed / {summary['pending_orders']} pending / {summary['rejected_orders']} rejected",
        f"Billing: {summary['billing_vnd']:,.0f} VND",
        f"Commission: {summary['commission_vnd']:,.0f} VND",
        "",
        "By category:",
    ]
    for category, row in sorted(summary.get("by_category", {}).items(), key=lambda kv: kv[1].get("commission_vnd", 0), reverse=True):
        lines.append(f"- {category}: posts={row['posts']} orders={row['orders']} confirmed={row['confirmed_orders']} commission={row['commission_vnd']:,.0f} VND")
    if summary.get("top_posts"):
        lines.append("")
        lines.append("Top posts:")
        for post in summary["top_posts"][:5]:
            lines.append(f"- {post['post_id']} | {post.get('category')}: orders={post['orders']} confirmed={post['confirmed_orders']} commission={post['commission_vnd']:,.0f} VND | {post.get('title')}")
    return "\n".join(lines)


def write_feedback_json(out_path: str | Path, report: dict[str, Any]) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
