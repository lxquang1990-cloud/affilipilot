from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_key TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'drafted',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    manifest_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_key TEXT NOT NULL,
    post_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL DEFAULT '',
    decided_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_key, post_id)
);

CREATE TABLE IF NOT EXISTS blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kind, value)
);
"""


class AffiliPilotDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def save_batch(self, batch_key: str, source: str, manifest: dict[str, Any]) -> None:
        self.init()
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO batches(batch_key, source, status, manifest_json) VALUES (?, ?, ?, ?)",
                (batch_key, source, "drafted", json.dumps(manifest, ensure_ascii=False)),
            )
            for post in manifest.get("posts", []):
                conn.execute(
                    "INSERT OR IGNORE INTO approvals(batch_key, post_id, status) VALUES (?, ?, 'pending')",
                    (batch_key, post["post_id"]),
                )

    def set_decision(self, batch_key: str, post_id: str, status: str, reason: str = "") -> None:
        if status not in {"pending", "approved", "rejected", "needs_edit", "blacklisted"}:
            raise ValueError(f"Unsupported approval status: {status}")
        self.init()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE approvals
                SET status = ?, reason = ?, decided_at = CURRENT_TIMESTAMP
                WHERE batch_key = ? AND post_id = ?
                """,
                (status, reason, batch_key, post_id),
            )
            if conn.total_changes == 0:
                raise KeyError(f"Approval not found: {batch_key}/{post_id}")

    def get_approvals(self, batch_key: str) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT batch_key, post_id, status, reason, decided_at FROM approvals WHERE batch_key = ? ORDER BY post_id",
                (batch_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_batch(self, batch_key: str) -> dict[str, Any] | None:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM batches WHERE batch_key = ?", (batch_key,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["manifest"] = json.loads(data.pop("manifest_json"))
        return data

    def add_blacklist(self, kind: str, value: str, reason: str = "") -> None:
        self.init()
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist(kind, value, reason) VALUES (?, ?, ?)",
                (kind, value, reason),
            )
