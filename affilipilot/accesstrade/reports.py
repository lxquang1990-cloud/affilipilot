from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from affilipilot.accesstrade.client import AccesstradeConfig, redact_for_audit
from affilipilot.db import AffiliPilotDB

@dataclass
class AccesstradeOrder:
    order_id: str = ""
    merchant: str = ""
    billing: float = 0.0
    pub_commission: float = 0.0
    status: str = ""
    is_confirmed: str = ""
    click_time: str = ""
    sales_time: str = ""
    update_time: str = ""
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    utm_content: str = ""
    product_category: str = ""
    raw: dict[str, Any] | None = None

def _request_json(url: str, *, token: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET", headers={"Content-Type": "application/json", "Authorization": f"Token {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}

def _list(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data")
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

def fetch_order_list(*, config: AccesstradeConfig | None = None, since: str, until: str, merchant: str = "", status: str = "", page: int = 1, limit: int = 300, timeout: int = 30) -> dict[str, Any]:
    config = config or AccesstradeConfig.from_env()
    if not config.token:
        return {"ok": False, "error": "missing_ACCESSTRADE_TOKEN", "orders": []}
    params = {"since": since, "until": until, "page": str(page), "limit": str(limit)}
    if merchant:
        params["merchant"] = merchant
    if status:
        params["status"] = status
    url = f"{config.base_url.rstrip('/')}/v1/order-list?{urllib.parse.urlencode(params)}"
    response = _request_json(url, token=config.token, timeout=timeout)
    orders = []
    for item in _list(response):
        orders.append(AccesstradeOrder(
            order_id=str(item.get("order_id") or ""),
            merchant=str(item.get("merchant") or ""),
            billing=float(item.get("billing") or 0),
            pub_commission=float(item.get("pub_commission") or 0),
            status=str(item.get("status") or ""),
            is_confirmed=str(item.get("is_confirmed") or ""),
            click_time=str(item.get("click_time") or ""),
            sales_time=str(item.get("sales_time") or ""),
            update_time=str(item.get("update_time") or ""),
            utm_source=str(item.get("utm_source") or ""),
            utm_medium=str(item.get("utm_medium") or ""),
            utm_campaign=str(item.get("utm_campaign") or ""),
            utm_content=str(item.get("utm_content") or ""),
            product_category=str(item.get("product_category") or item.get("category_name") or ""),
            raw=item,
        ))
    return {"ok": True, "source_url": url, "total": response.get("total", len(orders)), "orders": [asdict(o) for o in orders], "raw_redacted": redact_for_audit(response)}

def ensure_reporting_schema(db: AffiliPilotDB) -> None:
    db.init()
    with db.connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS accesstrade_orders (
            order_id TEXT PRIMARY KEY,
            merchant TEXT NOT NULL DEFAULT '',
            billing REAL NOT NULL DEFAULT 0,
            pub_commission REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '',
            is_confirmed TEXT NOT NULL DEFAULT '',
            click_time TEXT NOT NULL DEFAULT '',
            sales_time TEXT NOT NULL DEFAULT '',
            update_time TEXT NOT NULL DEFAULT '',
            utm_source TEXT NOT NULL DEFAULT '',
            utm_medium TEXT NOT NULL DEFAULT '',
            utm_campaign TEXT NOT NULL DEFAULT '',
            utm_content TEXT NOT NULL DEFAULT '',
            product_category TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}',
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)

def save_orders(db_path: str | Path, orders: list[dict[str, Any]]) -> int:
    db = AffiliPilotDB(db_path); ensure_reporting_schema(db)
    with db.connect() as conn:
        for order in orders:
            conn.execute(
                """
                INSERT OR REPLACE INTO accesstrade_orders(order_id, merchant, billing, pub_commission, status, is_confirmed, click_time, sales_time, update_time, utm_source, utm_medium, utm_campaign, utm_content, product_category, raw_json, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (order.get("order_id"), order.get("merchant", ""), order.get("billing", 0), order.get("pub_commission", 0), order.get("status", ""), order.get("is_confirmed", ""), order.get("click_time", ""), order.get("sales_time", ""), order.get("update_time", ""), order.get("utm_source", ""), order.get("utm_medium", ""), order.get("utm_campaign", ""), order.get("utm_content", ""), order.get("product_category", ""), json.dumps(order.get("raw") or order, ensure_ascii=False)),
            )
    return len(orders)

def summarize_orders(db_path: str | Path) -> dict[str, Any]:
    db = AffiliPilotDB(db_path); ensure_reporting_schema(db)
    with db.connect() as conn:
        total = conn.execute("select count(*) from accesstrade_orders").fetchone()[0]
        sums = conn.execute("select coalesce(sum(billing),0), coalesce(sum(pub_commission),0) from accesstrade_orders").fetchone()
        by_merchant = [dict(r) for r in conn.execute("select merchant, count(*) orders, sum(pub_commission) commission from accesstrade_orders group by merchant order by commission desc")]
        by_content = [dict(r) for r in conn.execute("select utm_content, count(*) orders, sum(pub_commission) commission from accesstrade_orders where utm_content != '' group by utm_content order by commission desc limit 20")]
    return {"total_orders": total, "billing": sums[0], "commission": sums[1], "by_merchant": by_merchant, "by_utm_content": by_content}

def render_order_summary(summary: dict[str, Any]) -> str:
    lines = ["🐌 Accesstrade order performance", f"Orders: {summary['total_orders']}", f"Billing: {summary['billing']:,.0f} VND", f"Commission: {summary['commission']:,.0f} VND", "", "Top merchants:"]
    for row in summary.get("by_merchant", [])[:10]:
        lines.append(f"- {row.get('merchant') or '(unknown)'}: {row.get('orders')} orders, {float(row.get('commission') or 0):,.0f} VND")
    if summary.get("by_utm_content"):
        lines.append("")
        lines.append("Top posts/utm_content:")
        for row in summary["by_utm_content"][:10]:
            lines.append(f"- {row.get('utm_content')}: {row.get('orders')} orders, {float(row.get('commission') or 0):,.0f} VND")
    return "\n".join(lines)

def write_json(out_path: str | Path, data: dict[str, Any]) -> Path:
    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
