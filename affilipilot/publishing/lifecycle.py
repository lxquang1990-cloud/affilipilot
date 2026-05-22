from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB

VALID_PUBLISH_STATES = {"draft_created", "approval_sent", "approved", "planned", "publish_queued", "publishing", "published", "hidden", "deleted", "failed", "held"}
LEGACY_STATE_MAP = {"planned": "planned", "published": "published", "hidden": "hidden", "deleted": "deleted", "failed": "failed"}
TERMINAL_STATES = {"published", "hidden", "deleted", "failed", "held"}

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publish_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_key TEXT NOT NULL,
                post_id TEXT NOT NULL,
                flow_id TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT 'facebook_page',
                state TEXT NOT NULL,
                provider_post_id TEXT NOT NULL DEFAULT '',
                work_link TEXT NOT NULL DEFAULT '',
                error_msg TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(batch_key, post_id, platform)
            )
            """
        )

def upsert_publish_task(
    db_path: str | Path,
    *,
    batch_key: str,
    post_id: str,
    state: str,
    platform: str = "facebook_page",
    flow_id: str = "",
    provider_post_id: str = "",
    work_link: str = "",
    error_msg: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    if state not in VALID_PUBLISH_STATES:
        raise ValueError(f"Unsupported publish state: {state}")
    db = AffiliPilotDB(db_path)
    ensure_publish_events_table(db)
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO publish_tasks(batch_key, post_id, flow_id, platform, state, provider_post_id, work_link, error_msg, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(batch_key, post_id, platform) DO UPDATE SET
              flow_id=CASE WHEN excluded.flow_id != '' THEN excluded.flow_id ELSE publish_tasks.flow_id END,
              state=excluded.state,
              provider_post_id=CASE WHEN excluded.provider_post_id != '' THEN excluded.provider_post_id ELSE publish_tasks.provider_post_id END,
              work_link=CASE WHEN excluded.work_link != '' THEN excluded.work_link ELSE publish_tasks.work_link END,
              error_msg=excluded.error_msg,
              payload_json=excluded.payload_json,
              updated_at=excluded.updated_at
            """,
            (batch_key, post_id, flow_id, platform, state, provider_post_id, work_link, error_msg, json.dumps(payload or {}, ensure_ascii=False), now, now),
        )

def record_publish_event(db_path: str | Path, *, batch_key: str, post_id: str, state: str, facebook_post_id: str = "", reason: str = "", payload: dict[str, Any] | None = None) -> None:
    state = LEGACY_STATE_MAP.get(state, state)
    if state not in VALID_PUBLISH_STATES:
        raise ValueError(f"Unsupported publish state: {state}")
    db = AffiliPilotDB(db_path)
    ensure_publish_events_table(db)
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO publish_events(batch_key, post_id, state, facebook_post_id, reason, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_key, post_id, state, facebook_post_id, reason, json.dumps(payload or {}, ensure_ascii=False), now),
        )
    upsert_publish_task(db_path, batch_key=batch_key, post_id=post_id, state=state, provider_post_id=facebook_post_id, error_msg=reason if state == "failed" else "", payload=payload)

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

def latest_publish_tasks(db_path: str | Path, *, batch_key: str = "", post_id: str = "") -> list[dict[str, Any]]:
    db = AffiliPilotDB(db_path)
    ensure_publish_events_table(db)
    filters = []
    params: list[Any] = []
    if batch_key:
        filters.append("batch_key = ?")
        params.append(batch_key)
    if post_id:
        filters.append("post_id = ?")
        params.append(post_id)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with db.connect() as conn:
        rows = conn.execute(f"SELECT * FROM publish_tasks {where} ORDER BY updated_at DESC, id DESC", tuple(params)).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        result.append(data)
    return result

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

def render_publish_tasks(db_path: str | Path, *, batch_key: str = "", post_id: str = "") -> str:
    rows = latest_publish_tasks(db_path, batch_key=batch_key, post_id=post_id)
    title = f"🐌 AffiliPilot publish tasks" + (f" — {batch_key}" if batch_key else "")
    lines = [title]
    if not rows:
        lines.append("- no publish tasks")
        return "\n".join(lines)
    for row in rows:
        provider = f" provider_id={row['provider_post_id']}" if row.get("provider_post_id") else ""
        err = f" error={row['error_msg']}" if row.get("error_msg") else ""
        lines.append(f"- {row['post_id']} [{row['platform']}]: {row['state']}{provider}{err} updated={row['updated_at']}")
    return "\n".join(lines)
