from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB

VALID_PUBLISH_STATES = {"planned", "published", "hidden", "deleted", "failed"}


def ensure_publish_events_table(db: AffiliPilotDB) -> None:
    db.init()
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publish_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_key TEXT NOT NULL,
                post_id TEXT NOT NULL,
                state TEXT NOT NULL,
                facebook_post_id TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def record_publish_event(db_path: str | Path, *, batch_key: str, post_id: str, state: str, facebook_post_id: str = "", reason: str = "", payload: dict[str, Any] | None = None) -> None:
    if state not in VALID_PUBLISH_STATES:
        raise ValueError(f"Unsupported publish state: {state}")
    db = AffiliPilotDB(db_path)
    ensure_publish_events_table(db)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO publish_events(batch_key, post_id, state, facebook_post_id, reason, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_key, post_id, state, facebook_post_id, reason, json.dumps(payload or {}, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )


def latest_publish_events(db_path: str | Path, *, batch_key: str) -> dict[str, dict[str, Any]]:
    db = AffiliPilotDB(db_path)
    ensure_publish_events_table(db)
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM publish_events
            WHERE batch_key = ?
            ORDER BY created_at ASC, id ASC
            """,
            (batch_key,),
        ).fetchall()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        latest[data["post_id"]] = data
    return latest


def render_publish_status(db_path: str | Path, *, batch_key: str) -> str:
    latest = latest_publish_events(db_path, batch_key=batch_key)
    lines = [f"🐌 AffiliPilot publish status — {batch_key}"]
    if not latest:
        lines.append("- no publish events")
        return "\n".join(lines)
    for post_id in sorted(latest):
        row = latest[post_id]
        suffix = f" facebook_id={row['facebook_post_id']}" if row.get("facebook_post_id") else ""
        reason = f" reason={row['reason']}" if row.get("reason") else ""
        lines.append(f"- {post_id}: {row['state']}{suffix}{reason}")
    return "\n".join(lines)
