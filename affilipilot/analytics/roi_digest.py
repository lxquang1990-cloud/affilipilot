from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.reports import fetch_order_list, save_orders
from affilipilot.analytics.feedback import build_feedback_report
from affilipilot.telegram.outbox import Outbox, OutboxMessage


def _vnd(value: float | int) -> str:
    return f"{float(value):,.0f}đ".replace(",", ".")


def _top_category(summary: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    rows = summary.get("by_category", {}) or {}
    if not rows:
        return "(chưa có)", {}
    return max(rows.items(), key=lambda kv: (kv[1].get("commission_vnd", 0), kv[1].get("confirmed_orders", 0), kv[1].get("orders", 0)))


def build_roi_digest(db_path: str | Path, *, batch_key: str = "", label: str = "Hôm nay") -> dict[str, Any]:
    report = build_feedback_report(db_path, batch_key=batch_key)
    summary = report["summary"]
    cat_name, cat = _top_category(summary)
    top_posts = summary.get("top_posts", [])
    best = top_posts[0] if top_posts else {}
    lines = [
        f"🐌 AffiliPilot ROI digest — {label}",
        f"Published: {summary['published_posts']}",
        f"Orders: {summary['orders']} total / {summary['confirmed_orders']} confirmed / {summary['pending_orders']} pending / {summary['rejected_orders']} rejected",
        f"Commission: {_vnd(summary['commission_vnd'])}",
        f"Billing: {_vnd(summary['billing_vnd'])}",
        "",
        f"Best category: {cat_name}" + (f" — orders={cat.get('orders', 0)} commission={_vnd(cat.get('commission_vnd', 0))}" if cat else ""),
        f"Best post: {best.get('post_id', '(chưa có)')}" + (f" — {best.get('title', '')[:80]}" if best else ""),
        "",
        "Notes:",
        "- Click data: chưa đồng bộ riêng; hiện dùng order/conversion từ Accesstrade theo utm_content/post_id.",
        "- Nếu commission vẫn 0đ, hệ thống vẫn OK nhưng chưa có đơn/đơn chưa sync.",
    ]
    return {"text": "\n".join(lines), "feedback": report}


def queue_roi_digest(db_path: str | Path, *, outbox_path: str | Path, batch_key: str = "", label: str = "Hôm nay", message_id: str = "") -> dict[str, Any]:
    digest = build_roi_digest(db_path, batch_key=batch_key, label=label)
    outbox = Outbox(outbox_path)
    msg_id = message_id or f"roi-digest-{date.today().isoformat()}" + (f"-{batch_key}" if batch_key else "")
    outbox.add(OutboxMessage(id=msg_id, kind="digest", text=digest["text"]))
    return {"outbox": str(outbox_path), "message_id": msg_id, "text": digest["text"], "feedback": digest["feedback"]}


def sync_orders_and_build_roi_digest(
    db_path: str | Path,
    *,
    since: str | None = None,
    until: str | None = None,
    merchant: str = "",
    status: str = "",
    batch_key: str = "",
    label: str = "Hôm nay",
    outbox_path: str | Path = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    today = date.today()
    since = since or (today - timedelta(days=1)).isoformat()
    until = until or today.isoformat()
    fetched: dict[str, Any] = {"ok": True, "orders": [], "dry_run": True, "since": since, "until": until}
    saved = 0
    if not dry_run:
        fetched = fetch_order_list(since=since, until=until, merchant=merchant, status=status)
        if fetched.get("ok"):
            saved = save_orders(db_path, fetched.get("orders", []))
    digest = build_roi_digest(db_path, batch_key=batch_key, label=label)
    queued: dict[str, Any] | None = None
    if outbox_path:
        queued = queue_roi_digest(db_path, outbox_path=outbox_path, batch_key=batch_key, label=label)
    return {"ok": bool(fetched.get("ok")), "since": since, "until": until, "fetched": len(fetched.get("orders", [])), "saved": saved, "dry_run": dry_run, "digest": digest, "queued": queued, "error": fetched.get("error", "")}
