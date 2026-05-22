from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.facebook import FacebookConfig, check_facebook_config
from affilipilot.security import redact_for_audit

@dataclass
class SocialMetric:
    platform: str
    post_id: str
    provider_post_id: str = ""
    impressions: int = 0
    reach: int = 0
    clicks: int = 0
    reactions: int = 0
    comments: int = 0
    shares: int = 0
    raw: dict[str, Any] | None = None

def ensure_social_metrics_table(db: AffiliPilotDB) -> None:
    db.init()
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS social_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                post_id TEXT NOT NULL,
                provider_post_id TEXT NOT NULL DEFAULT '',
                impressions INTEGER NOT NULL DEFAULT 0,
                reach INTEGER NOT NULL DEFAULT 0,
                clicks INTEGER NOT NULL DEFAULT 0,
                reactions INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, post_id, provider_post_id, captured_at)
            )
            """
        )

def save_social_metric(db_path: str | Path, metric: SocialMetric) -> None:
    db = AffiliPilotDB(db_path)
    ensure_social_metrics_table(db)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO social_metrics(platform, post_id, provider_post_id, impressions, reach, clicks, reactions, comments, shares, raw_json, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric.platform,
                metric.post_id,
                metric.provider_post_id,
                metric.impressions,
                metric.reach,
                metric.clicks,
                metric.reactions,
                metric.comments,
                metric.shares,
                json.dumps(redact_for_audit(metric.raw or {}), ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

def latest_social_metrics(db_path: str | Path, *, post_id: str = "") -> list[dict[str, Any]]:
    db = AffiliPilotDB(db_path)
    ensure_social_metrics_table(db)
    where = "WHERE post_id = ?" if post_id else ""
    params: tuple[Any, ...] = (post_id,) if post_id else ()
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT sm.* FROM social_metrics sm
            JOIN (
                SELECT platform, post_id, provider_post_id, MAX(captured_at) AS captured_at
                FROM social_metrics
                {where}
                GROUP BY platform, post_id, provider_post_id
            ) latest
            ON sm.platform = latest.platform AND sm.post_id = latest.post_id AND sm.provider_post_id = latest.provider_post_id AND sm.captured_at = latest.captured_at
            ORDER BY sm.captured_at DESC
            """,
            params,
        ).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["raw"] = json.loads(data.pop("raw_json") or "{}")
        result.append(data)
    return result

def _extract_metric(raw: dict[str, Any], names: list[str]) -> int:
    for item in raw.get("data", []) or []:
        if item.get("name") in names:
            values = item.get("values") or []
            if values:
                value = values[0].get("value", 0)
                if isinstance(value, dict):
                    return int(sum(v for v in value.values() if isinstance(v, (int, float))))
                if isinstance(value, (int, float)):
                    return int(value)
    return 0

def fetch_facebook_post_metric(provider_post_id: str, *, post_id: str = "", config: FacebookConfig | None = None, timeout: int = 30) -> SocialMetric:
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    if not provider_post_id.strip():
        raise RuntimeError("provider_post_id is required")
    params = urllib.parse.urlencode({"metric": "post_impressions,post_impressions_unique,post_clicks", "access_token": config.page_access_token})
    url = f"https://graph.facebook.com/v19.0/{urllib.parse.quote(provider_post_id)}/insights?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            raw = json.loads(body) if body else {}
        except json.JSONDecodeError:
            raw = {"raw": body[:500]}
        return SocialMetric(platform="facebook_page", post_id=post_id or provider_post_id, provider_post_id=provider_post_id, raw={"ok": False, "status": exc.code, "response": raw})
    return SocialMetric(
        platform="facebook_page",
        post_id=post_id or provider_post_id,
        provider_post_id=provider_post_id,
        impressions=_extract_metric(raw, ["post_impressions"]),
        reach=_extract_metric(raw, ["post_impressions_unique"]),
        clicks=_extract_metric(raw, ["post_clicks"]),
        raw=raw,
    )

def render_social_metrics(rows: list[dict[str, Any]]) -> str:
    lines = ["🐌 AffiliPilot social data cube"]
    if not rows:
        lines.append("- no social metrics yet")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            f"- {row['post_id']} [{row['platform']}]: impressions={row['impressions']} reach={row['reach']} clicks={row['clicks']} comments={row['comments']} shares={row['shares']} captured={row['captured_at']}"
        )
    return "\n".join(lines)
