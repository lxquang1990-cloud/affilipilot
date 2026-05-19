from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONVERSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_id TEXT NOT NULL,
    draft_id TEXT NOT NULL DEFAULT '',
    post_id TEXT NOT NULL DEFAULT '',
    campaign_id TEXT NOT NULL DEFAULT '',
    order_id TEXT NOT NULL DEFAULT '',
    order_status TEXT NOT NULL DEFAULT '',
    commission_vnd INTEGER DEFAULT 0,
    order_value_vnd INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    converted_at TEXT,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sub_id, order_id)
);
CREATE INDEX IF NOT EXISTS idx_conversions_sub_id ON conversions(sub_id);
CREATE INDEX IF NOT EXISTS idx_conversions_draft_id ON conversions(draft_id);
"""


@dataclass
class ConversionSummary:
    total_orders: int
    approved_orders: int
    pending_orders: int
    rejected_orders: int
    revenue_vnd: int
    commission_vnd: int


def init_conversion_schema(db_path: str | Path) -> None:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.executescript(CONVERSION_SCHEMA)


def upsert_conversion(db_path: str | Path, order: dict[str, Any]) -> None:
    init_conversion_schema(db_path)
    sub_id = str(order.get("sub_id") or order.get("sub1") or "")
    order_id = str(order.get("order_id") or order.get("id") or sub_id)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO conversions(sub_id, draft_id, post_id, campaign_id, order_id, order_status, commission_vnd, order_value_vnd, click_count, converted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sub_id,
                str(order.get("draft_id") or ""),
                str(order.get("post_id") or ""),
                str(order.get("campaign_id") or ""),
                order_id,
                str(order.get("order_status") or order.get("status") or ""),
                int(float(order.get("commission_vnd") or order.get("commission") or 0)),
                int(float(order.get("order_value_vnd") or order.get("order_value") or order.get("value") or 0)),
                int(order.get("click_count") or 0),
                order.get("converted_at") or order.get("created_at"),
            ),
        )


def summarize_conversions(db_path: str | Path) -> ConversionSummary:
    init_conversion_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT order_status, commission_vnd, order_value_vnd FROM conversions").fetchall()
    total = len(rows)
    approved = sum(1 for status, *_ in rows if str(status).lower() in {"approved", "success", "confirmed"})
    pending = sum(1 for status, *_ in rows if str(status).lower() in {"pending", "new", ""})
    rejected = total - approved - pending
    revenue = sum(int(row[2] or 0) for row in rows)
    commission = sum(int(row[1] or 0) for row in rows)
    return ConversionSummary(total, approved, pending, rejected, revenue, commission)


def render_conversion_summary(summary: ConversionSummary) -> str:
    return "\n".join([
        "AffiliPilot conversion summary",
        f"Orders: total={summary.total_orders} approved={summary.approved_orders} pending={summary.pending_orders} rejected={summary.rejected_orders}",
        f"Revenue: {summary.revenue_vnd:,} VND",
        f"Commission: {summary.commission_vnd:,} VND",
    ])
