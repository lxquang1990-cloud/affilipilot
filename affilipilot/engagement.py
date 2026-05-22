from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file
from affilipilot.content.ai_caption import generate_ai_caption
from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.facebook import FacebookConfig, check_facebook_config, reply_to_comment
from affilipilot.security import redact_for_audit
from affilipilot.telegram.outbox import Outbox, OutboxMessage

@dataclass
class CommentRecord:
    platform: str
    post_id: str
    provider_post_id: str
    comment_id: str
    author: str = ""
    message: str = ""
    reply_suggestion: str = ""
    status: str = "new"
    raw: dict[str, Any] | None = None

def ensure_engagement_tables(db: AffiliPilotDB) -> None:
    db.init()
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS engagement_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                post_id TEXT NOT NULL,
                provider_post_id TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '',
                reply_suggestion TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, comment_id)
            )
            """
        )

def save_comment(db_path: str | Path, comment: CommentRecord) -> None:
    db = AffiliPilotDB(db_path)
    ensure_engagement_tables(db)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO engagement_comments(platform, post_id, provider_post_id, comment_id, author, message, reply_suggestion, status, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, comment_id) DO UPDATE SET
              author=excluded.author,
              message=excluded.message,
              reply_suggestion=CASE WHEN engagement_comments.reply_suggestion = '' THEN excluded.reply_suggestion ELSE engagement_comments.reply_suggestion END,
              raw_json=excluded.raw_json,
              updated_at=excluded.updated_at
            """,
            (
                comment.platform,
                comment.post_id,
                comment.provider_post_id,
                comment.comment_id,
                comment.author,
                comment.message,
                comment.reply_suggestion,
                comment.status,
                json.dumps(redact_for_audit(comment.raw or {}), ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

def list_comments(db_path: str | Path, *, post_id: str = "", status: str = "new") -> list[dict[str, Any]]:
    db = AffiliPilotDB(db_path)
    ensure_engagement_tables(db)
    filters = []
    params: list[Any] = []
    if post_id:
        filters.append("post_id = ?")
        params.append(post_id)
    if status:
        filters.append("status = ?")
        params.append(status)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with db.connect() as conn:
        rows = conn.execute(f"SELECT * FROM engagement_comments {where} ORDER BY created_at DESC", tuple(params)).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["raw"] = json.loads(data.pop("raw_json") or "{}")
        result.append(data)
    return result

def fetch_facebook_comments(provider_post_id: str, *, post_id: str = "", config: FacebookConfig | None = None, limit: int = 25, timeout: int = 30) -> list[CommentRecord]:
    config = config or FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise RuntimeError("Facebook config is not verified: " + ",".join(health.reasons))
    params = urllib.parse.urlencode({"fields": "id,message,from,created_time", "limit": str(limit), "access_token": config.page_access_token})
    url = f"https://graph.facebook.com/v19.0/{urllib.parse.quote(provider_post_id)}/comments?{params}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    records = []
    for item in raw.get("data", []) or []:
        author = item.get("from", {}).get("name", "") if isinstance(item.get("from"), dict) else ""
        records.append(CommentRecord(platform="facebook_page", post_id=post_id or provider_post_id, provider_post_id=provider_post_id, comment_id=item.get("id", ""), author=author, message=item.get("message", ""), raw=item))
    return [record for record in records if record.comment_id]

def suggest_reply(comment: str, *, product_title: str = "", model: str = "") -> str:
    prompt = (
        "Viết 1 câu trả lời Facebook ngắn, thân thiện, bằng tiếng Việt cho comment khách hàng. "
        "Không tự bịa giá. Nếu khách hỏi link/giá thì nói mình gửi link ở bình luận/tin nhắn và mời xem chi tiết. "
        f"Sản phẩm: {product_title or '(không rõ)'}\nComment: {comment}"
    )
    generated = generate_ai_caption(prompt, model=model or None)
    if generated.ok and generated.body.strip():
        return generated.body.strip()
    text = comment.lower()
    if any(word in text for word in ["giá", "bao nhiêu", "link", "mua"]):
        return "Dạ mình gửi link sản phẩm để bạn xem chi tiết và giá hiện tại nhé."
    return "Dạ cảm ơn bạn đã quan tâm, mình hỗ trợ thêm ngay nhé."

def queue_comment_reply_review(db_path: str | Path, *, outbox_path: str | Path, post_id: str = "", limit: int = 10) -> dict[str, Any]:
    rows = list_comments(db_path, post_id=post_id, status="new")[:limit]
    outbox = Outbox(outbox_path)
    queued = 0
    for row in rows:
        suggestion = row.get("reply_suggestion") or suggest_reply(row.get("message", ""))
        text = (
            f"🐌 AffiliPilot comment review\n"
            f"Post: {row['post_id']}\n"
            f"Comment: {row.get('author') or 'khách'} — {row.get('message', '')}\n\n"
            f"Gợi ý reply:\n{suggestion}\n\n"
            f"Lệnh: /aff_reply {row['comment_id']} <nội dung> hoặc /aff_ignore {row['comment_id']}"
        )
        outbox.add(OutboxMessage(id=f"comment-review-{row['comment_id']}", kind="alert", text=text))
        queued += 1
    return {"queued": queued, "outbox": str(outbox_path)}

def update_comment_status(db_path: str | Path, *, comment_id: str, status: str, reply_text: str = "", raw: dict[str, Any] | None = None) -> dict[str, Any]:
    if status not in {"new", "queued", "replied", "ignored", "failed"}:
        raise ValueError(f"Unsupported comment status: {status}")
    db = AffiliPilotDB(db_path)
    ensure_engagement_tables(db)
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM engagement_comments WHERE comment_id = ?", (comment_id,)).fetchone()
        if not row:
            raise KeyError(f"Comment not found: {comment_id}")
        existing_raw = json.loads(row["raw_json"] or "{}")
        if raw:
            existing_raw.update(redact_for_audit(raw))
        if reply_text:
            existing_raw["approved_reply_text"] = reply_text
        conn.execute(
            """
            UPDATE engagement_comments
            SET status = ?, raw_json = ?, updated_at = ?
            WHERE comment_id = ?
            """,
            (status, json.dumps(existing_raw, ensure_ascii=False), now, comment_id),
        )
        updated = conn.execute("SELECT * FROM engagement_comments WHERE comment_id = ?", (comment_id,)).fetchone()
    data = dict(updated)
    data["raw"] = json.loads(data.pop("raw_json") or "{}")
    return data

def approve_comment_reply(db_path: str | Path, *, comment_id: str, message: str) -> dict[str, Any]:
    rows = list_comments(db_path, status="")
    row = next((item for item in rows if item.get("comment_id") == comment_id), None)
    if not row:
        raise KeyError(f"Comment not found: {comment_id}")
    result = reply_to_comment(comment_id=comment_id, message=message)
    status = "replied" if result.get("ok") else "failed"
    updated = update_comment_status(db_path, comment_id=comment_id, status=status, reply_text=message, raw={"reply_result": result})
    return {"ok": bool(result.get("ok")), "status": status, "comment": updated, "result": result}

def ignore_comment(db_path: str | Path, *, comment_id: str) -> dict[str, Any]:
    updated = update_comment_status(db_path, comment_id=comment_id, status="ignored")
    return {"ok": True, "status": "ignored", "comment": updated}

def render_comment_action(result: dict[str, Any]) -> str:
    comment = result.get("comment", {})
    return "\n".join([
        f"🐌 AffiliPilot comment action: {result.get('status')}",
        f"Comment: {comment.get('comment_id', '')}",
        f"OK: {bool(result.get('ok'))}",
    ])

def render_comments(rows: list[dict[str, Any]]) -> str:
    lines = ["🐌 AffiliPilot engagement comments"]
    if not rows:
        lines.append("- no comments")
        return "\n".join(lines)
    for row in rows:
        lines.append(f"- {row['comment_id']} [{row['status']}] {row.get('author') or 'khách'}: {row.get('message', '')[:120]}")
        if row.get("reply_suggestion"):
            lines.append(f"  reply: {row['reply_suggestion']}")
    return "\n".join(lines)
