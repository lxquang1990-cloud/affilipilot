from __future__ import annotations

import json
import os
import shlex
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Any

from affilipilot.db import AffiliPilotDB
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.config import load_env_file


def deliver_outbox_dry_run(outbox_path: str | Path, *, mark_sent: bool = False, mark_delivered: bool = False, receipt: str = "", limit: int | None = None) -> dict:
    """Render pending outbox messages for operator review; optionally mark status.

    This intentionally does not call Telegram APIs. Real delivery must be wired
    through an approved provider adapter so secrets never enter chat/history.
    `delivered` is stricter than `sent`: use it only after the channel/provider
    confirms the approval card was actually delivered to the operator chat.
    """
    if mark_sent and mark_delivered:
        raise ValueError("mark_sent and mark_delivered are mutually exclusive")
    if mark_delivered and not receipt:
        raise ValueError("mark_delivered requires a non-empty receipt")

    outbox = Outbox(outbox_path)
    pending = outbox.pending()
    selected = pending[:limit] if limit is not None else pending
    status = "delivered" if mark_delivered else "sent" if mark_sent else "dry_run"
    delivered = []
    for message in selected:
        delivered.append({
            "id": message.id,
            "kind": message.kind,
            "text": message.text,
            "attachments": message.attachments,
            "status": status,
            "receipt": receipt,
        })
        if mark_delivered:
            outbox.mark(message.id, "delivered", receipt=receipt)
        elif mark_sent:
            outbox.mark(message.id, "sent")
    return {
        "outbox": str(outbox_path),
        "mode": "mark_delivered" if mark_delivered else "mark_sent" if mark_sent else "dry_run",
        "pending_before": len(pending),
        "processed": len(delivered),
        "receipt": receipt,
        "messages": delivered,
    }


def build_openclaw_telegram_plan(
    outbox_path: str | Path,
    *,
    reply_to: str,
    reply_channel: str = "telegram",
    account: str = "",
    agent: str | None = None,
    limit: int | None = None,
) -> dict:
    """Build reviewable OpenClaw CLI commands for Telegram delivery.

    This is plan-only: it does not execute OpenClaw and does not mark outbox
    messages as sent. The operator can copy/run a command after review.
    """
    outbox = Outbox(outbox_path)
    pending = outbox.pending()
    selected = pending[:limit] if limit is not None else pending
    commands = []
    for message in selected:
        body = message.text
        if message.attachments:
            body += "\n\nAttachments:\n" + "\n".join(message.attachments)
        cmd = [
            "openclaw",
            "message",
            "send",
            "--channel",
            reply_channel,
            "--target",
            reply_to,
            "--message",
            body,
            "--json",
        ]
        if account:
            cmd.extend(["--account", account])
        if agent:
            # Deprecated compatibility hint; direct message sends do not use agent routing.
            pass
        commands.append({
            "id": message.id,
            "kind": message.kind,
            "command": " ".join(shlex.quote(part) for part in cmd),
            "chars": len(body),
        })
    return {
        "outbox": str(outbox_path),
        "mode": "openclaw_plan_only",
        "reply_channel": reply_channel,
        "reply_to": reply_to,
        "account": account,
        "pending_before": len(pending),
        "planned": len(commands),
        "commands": commands,
    }

def _receipt_from_output(output: str, *, reply_channel: str, reply_to: str) -> str:
    text = output.strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if isinstance(payload, dict):
        explicit = payload.get("receipt") or payload.get("message_receipt")
        if explicit:
            return str(explicit)
        nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        message_id = payload.get("message_id") or payload.get("messageId") or payload.get("id") or nested.get("message_id") or nested.get("messageId") or nested.get("id")
        chat_id = payload.get("chat_id") or payload.get("chatId") or payload.get("reply_to") or nested.get("chat_id") or nested.get("chatId") or nested.get("reply_to") or reply_to
        if message_id:
            return f"{reply_channel}:{chat_id}:{message_id}"
    return ""

def send_openclaw_telegram_outbox(
    outbox_path: str | Path,
    *,
    reply_to: str,
    reply_channel: str = "telegram",
    account: str = "",
    agent: str | None = None,
    to: str = "",
    session_id: str = "",
    limit: int = 1,
    runner: Callable[..., Any] | None = None,
) -> dict:
    """Send pending outbox messages through OpenClaw CLI with strict receipt gating.

    Marks a message as `sent` after a zero exit code. Marks `delivered` only when
    OpenClaw output contains a JSON `receipt`, `message_id`, or `id`.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    outbox = Outbox(outbox_path)
    pending = outbox.pending()
    selected = pending[:limit]
    run = runner or subprocess.run
    results = []
    for message in selected:
        body = message.text
        if message.attachments:
            body += "\n\nAttachments:\n" + "\n".join(message.attachments)
        cmd = [
            "openclaw",
            "message",
            "send",
            "--channel",
            reply_channel,
            "--target",
            reply_to,
            "--message",
            body,
            "--json",
        ]
        if account:
            cmd.extend(["--account", account])
        if agent or to or session_id:
            # Kept in the function signature for backward-compatible CLI args,
            # but direct channel sends do not use agent/session routing.
            pass
        completed = run(cmd, capture_output=True, text=True, timeout=60)
        stdout = getattr(completed, "stdout", "") or ""
        stderr = getattr(completed, "stderr", "") or ""
        returncode = int(getattr(completed, "returncode", 1))
        receipt = _receipt_from_output(stdout, reply_channel=reply_channel, reply_to=reply_to)
        if returncode == 0 and receipt:
            outbox.mark(message.id, "delivered", receipt=receipt)
            status = "delivered"
        elif returncode == 0:
            outbox.mark(message.id, "sent")
            status = "sent"
        else:
            outbox.mark(message.id, "failed")
            status = "failed"
        results.append({
            "id": message.id,
            "kind": message.kind,
            "status": status,
            "receipt": receipt,
            "returncode": returncode,
            "stdout": stdout[:500],
            "stderr": stderr[:500],
        })
    return {
        "outbox": str(outbox_path),
        "mode": "openclaw_send",
        "reply_channel": reply_channel,
        "reply_to": reply_to,
        "account": account,
        "agent": agent or "",
        "to": to,
        "session_id": session_id,
        "pending_before": len(pending),
        "processed": len(results),
        "messages": results,
    }



def _load_telegram_bot_config(secret_path: str | Path = "") -> tuple[str, str]:
    env_file = load_env_file(secret_path) if secret_path else load_env_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_file.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or env_file.get("TELEGRAM_CHAT_ID", "")
    return token.strip(), chat_id.strip()

def _telegram_bot_send(token: str, chat_id: str, text: str, *, timeout: int = 60) -> dict[str, Any]:
    if not token or not chat_id:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload

def send_telegram_bot_outbox(
    outbox_path: str | Path,
    *,
    secret_path: str | Path = "",
    chat_id: str = "",
    limit: int = 1,
    sender: Callable[..., Any] | None = None,
) -> dict:
    """Send pending outbox messages through a project-local Telegram bot token.

    Secrets are loaded from env/AffiliPilot secret file and are never returned in
    reports. Messages are marked delivered only after Telegram returns ok+message_id.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    token, default_chat_id = _load_telegram_bot_config(secret_path)
    target_chat = str(chat_id or default_chat_id).strip()
    if not token or not target_chat:
        raise ValueError("Missing Telegram bot token/chat config")
    outbox = Outbox(outbox_path)
    pending = outbox.pending()
    selected = pending[:limit]
    send = sender or _telegram_bot_send
    results = []
    for message in selected:
        body = message.text
        if message.attachments:
            body += "\n\nAttachments:\n" + "\n".join(message.attachments)
        try:
            payload = send(token, target_chat, body)
            ok = bool(payload.get("ok")) if isinstance(payload, dict) else False
            result = payload.get("result", {}) if isinstance(payload, dict) and isinstance(payload.get("result"), dict) else {}
            message_id = result.get("message_id")
            if ok and message_id:
                receipt = f"telegram:{target_chat}:{message_id}"
                outbox.mark(message.id, "delivered", receipt=receipt)
                status = "delivered"
            else:
                receipt = ""
                outbox.mark(message.id, "failed")
                status = "failed"
        except Exception as exc:
            receipt = ""
            outbox.mark(message.id, "failed")
            status = "failed"
            payload = {"ok": False, "error": str(exc)}
        results.append({
            "id": message.id,
            "kind": message.kind,
            "status": status,
            "receipt": receipt,
            "telegram_ok": bool(payload.get("ok")) if isinstance(payload, dict) else False,
            "error": str(payload.get("error", ""))[:300] if isinstance(payload, dict) else "",
        })
    return {
        "outbox": str(outbox_path),
        "mode": "telegram_bot_send",
        "chat_id": target_chat,
        "pending_before": len(pending),
        "processed": len(results),
        "messages": results,
    }

def render_openclaw_telegram_send_report(result: dict) -> str:
    lines = [
        "🐌 AffiliPilot OpenClaw Telegram delivery",
        f"Mode: {result['mode']}",
        f"Outbox: {result['outbox']}",
        f"Target: {result['reply_channel']}:{result['reply_to']}",
        f"Account: {result.get('account') or '(default/inferred)'}",
        f"Pending before: {result['pending_before']}",
        f"Processed: {result['processed']}",
        "",
    ]
    if not result["messages"]:
        lines.append("No pending messages to send.")
        return "\n".join(lines)
    for item in result["messages"]:
        lines.append(f"## {item['id']} [{item['kind']}] -> {item['status']}")
        if item.get("receipt"):
            lines.append(f"Receipt: {item['receipt']}")
        elif item["status"] == "sent":
            lines.append("Receipt: missing — publish gate remains blocked until delivered proof exists.")
        if item["status"] == "failed" and item.get("stderr"):
            lines.append(f"Error: {item['stderr']}")
        lines.append("")
    return "\n".join(lines).rstrip()

def render_openclaw_telegram_plan(plan: dict) -> str:
    lines = [
        "🐌 AffiliPilot OpenClaw Telegram delivery plan",
        f"Mode: {plan['mode']} — no messages sent",
        f"Outbox: {plan['outbox']}",
        f"Target: {plan['reply_channel']}:{plan['reply_to']}",
        f"Account: {plan.get('account') or '(default/inferred)'}",
        f"Pending before: {plan['pending_before']}",
        f"Planned commands: {plan['planned']}",
        "",
    ]
    if not plan["commands"]:
        lines.append("No pending messages to plan.")
        return "\n".join(lines)
    lines.append("Review each command before running it. Do not paste secrets into --message.")
    lines.append("")
    for item in plan["commands"]:
        lines.append(f"## {item['id']} [{item['kind']}] — {item['chars']} chars")
        lines.append("```bash")
        lines.append(item["command"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip()

def render_delivery_report(result: dict) -> str:
    lines = [
        f"🐌 AffiliPilot delivery — {result['mode']}",
        f"Outbox: {result['outbox']}",
        f"Pending before: {result['pending_before']}",
        f"Processed: {result['processed']}",
        "",
    ]
    if not result["messages"]:
        lines.append("No pending messages to deliver.")
        return "\n".join(lines)
    for message in result["messages"]:
        lines.append(f"## {message['id']} [{message['kind']}] -> {message['status']}")
        if message.get("receipt"):
            lines.append(f"Receipt: {message['receipt']}")
        lines.append(message["text"])
        if message["attachments"]:
            lines.append("Attachments: " + ", ".join(message["attachments"]))
        lines.append("")
    return "\n".join(lines).rstrip()


def queue_approval_batch(db_path: str | Path, *, batch_key: str, outbox_path: str | Path) -> list[OutboxMessage]:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        raise KeyError(f"Batch not found: {batch_key}")
    outbox = Outbox(outbox_path)
    manifest = batch["manifest"]
    preview_path = Path(manifest["out_dir"]) / "approval_batch_preview.txt"
    eligible_posts = [post for post in manifest.get("posts", []) if post.get("approval_eligible", True)]
    held_posts = [post for post in manifest.get("posts", []) if not post.get("approval_eligible", True)]
    messages = []
    should_send_summary = len(eligible_posts) != 1 or bool(held_posts)
    if should_send_summary:
        messages.append(OutboxMessage(
            id=f"{batch_key}:summary",
            kind="summary",
            text="\n".join([
                f"🐌 AffiliPilot batch — {batch_key}",
                f"Selected: {manifest.get('selected')}/{manifest.get('total_products')} | Ready: {len(eligible_posts)} | Held: {len(held_posts)}",
                "Reply on a card: ok / no / sửa / ban",
                f"Preview: {preview_path}",
            ]),
            attachments=[str(preview_path)] if preview_path.exists() else [],
        ))
        if held_posts and not eligible_posts:
            messages[0].text += "\nStatus: HELD — missing title/media, not queued for approval."
    for post in eligible_posts:
        card_path = Path(post["files"].get("telegram_card", ""))
        if not card_path.exists():
            continue
        text = card_path.read_text(encoding="utf-8", errors="ignore")
        attachments = [post["files"].get("post_text", "")] if post["files"].get("post_text") else []
        messages.append(OutboxMessage(
            id=f"{batch_key}:{post['post_id']}",
            kind="approval_card",
            text=text,
            attachments=attachments,
        ))
    for message in messages:
        outbox.add(message)
    return messages


def mark_batch_delivered(outbox_path: str | Path, *, batch_key: str, post_id: str, receipt: str) -> dict:
    if not receipt:
        raise ValueError("receipt is required")
    outbox = Outbox(outbox_path)
    current = {m.id: m for m in outbox.load()}
    expected_ids = [message_id for message_id in [f"{batch_key}:summary", f"{batch_key}:{post_id}"] if message_id in current]
    missing_card = f"{batch_key}:{post_id}" not in current
    if missing_card:
        raise KeyError("Missing outbox message: " + f"{batch_key}:{post_id}")
    for message_id in expected_ids:
        outbox.mark(message_id, "delivered", receipt=receipt)
    return {
        "outbox": str(outbox_path),
        "mode": "mark_batch_delivered",
        "batch_key": batch_key,
        "post_id": post_id,
        "receipt": receipt,
        "processed": len(expected_ids),
        "messages": expected_ids,
    }

def render_batch_delivery_report(result: dict) -> str:
    lines = [
        "🐌 AffiliPilot batch delivery proof",
        f"Mode: {result['mode']}",
        f"Batch: {result['batch_key']}",
        f"Post: {result['post_id']}",
        f"Receipt: {result['receipt']}",
        f"Processed: {result['processed']}",
        "",
    ]
    for message_id in result["messages"]:
        lines.append(f"- {message_id} -> delivered")
    return "\n".join(lines)


def render_telegram_bot_send_report(result: dict) -> str:
    lines = [
        "🐌 AffiliPilot Telegram bot delivery",
        f"Mode: {result['mode']}",
        f"Outbox: {result['outbox']}",
        f"Target: telegram:{result['chat_id']}",
        f"Pending before: {result['pending_before']}",
        f"Processed: {result['processed']}",
    ]
    for item in result["messages"]:
        receipt = f" receipt={item['receipt']}" if item.get("receipt") else ""
        error = f" error={item['error']}" if item.get("error") else ""
        lines.append(f"- {item['id']}: {item['status']}{receipt}{error}")
    return "\n".join(lines)

def render_outbox_preview(outbox_path: str | Path) -> str:
    outbox = Outbox(outbox_path)
    messages = outbox.load()
    if not messages:
        return "No outbox messages."
    pending_count = len([m for m in messages if m.status == "pending"])
    lines = [f"🐌 AffiliPilot outbox — {pending_count} pending / {len(messages)} total", ""]
    for msg in messages:
        lines.append(f"## {msg.id} [{msg.kind}] — {msg.status}")
        if msg.receipt:
            lines.append(f"Receipt: {msg.receipt}")
        lines.append(msg.text)
        if msg.attachments:
            lines.append("Attachments: " + ", ".join(msg.attachments))
        lines.append("")
    return "\n".join(lines)
