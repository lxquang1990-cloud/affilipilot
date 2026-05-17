from __future__ import annotations

import json
import shlex
from pathlib import Path

from affilipilot.db import AffiliPilotDB
from affilipilot.telegram.outbox import Outbox, OutboxMessage


def deliver_outbox_dry_run(outbox_path: str | Path, *, mark_sent: bool = False, limit: int | None = None) -> dict:
    """Render pending outbox messages for operator review; optionally mark as sent.

    This intentionally does not call Telegram APIs. Real delivery must be wired
    through an approved provider adapter so secrets never enter chat/history.
    """
    outbox = Outbox(outbox_path)
    pending = outbox.pending()
    selected = pending[:limit] if limit is not None else pending
    delivered = []
    for message in selected:
        delivered.append({
            "id": message.id,
            "kind": message.kind,
            "text": message.text,
            "attachments": message.attachments,
            "status": "sent" if mark_sent else "dry_run",
        })
        if mark_sent:
            outbox.mark(message.id, "sent")
    return {
        "outbox": str(outbox_path),
        "mode": "mark_sent" if mark_sent else "dry_run",
        "pending_before": len(pending),
        "processed": len(delivered),
        "messages": delivered,
    }


def build_openclaw_telegram_plan(
    outbox_path: str | Path,
    *,
    reply_to: str,
    reply_channel: str = "telegram",
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
            "agent",
            "--message",
            body,
            "--deliver",
            "--reply-channel",
            reply_channel,
            "--reply-to",
            reply_to,
        ]
        if agent:
            cmd.extend(["--agent", agent])
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
        "pending_before": len(pending),
        "planned": len(commands),
        "commands": commands,
    }

def render_openclaw_telegram_plan(plan: dict) -> str:
    lines = [
        "🐌 AffiliPilot OpenClaw Telegram delivery plan",
        f"Mode: {plan['mode']} — no messages sent",
        f"Outbox: {plan['outbox']}",
        f"Target: {plan['reply_channel']}:{plan['reply_to']}",
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
    messages = [
        OutboxMessage(
            id=f"{batch_key}:summary",
            kind="summary",
            text="\n".join([
                f"🐌 AffiliPilot approval batch — {batch_key}",
                f"Products considered: {manifest.get('total_products')}",
                f"Drafts selected: {manifest.get('selected')}",
                f"Preview file: {preview_path}",
                "Commands: /approve <post_id>, /reject <post_id>, /edit <post_id>, /blacklist <post_id>",
            ]),
            attachments=[str(preview_path)] if preview_path.exists() else [],
        )
    ]
    for post in manifest.get("posts", []):
        card_path = Path(post["files"]["telegram_card"])
        text = card_path.read_text(encoding="utf-8", errors="ignore") if card_path.exists() else json.dumps(post, ensure_ascii=False)
        messages.append(OutboxMessage(
            id=f"{batch_key}:{post['post_id']}",
            kind="approval_card",
            text=text,
            attachments=[post["files"].get("post_text", "")],
        ))
    for message in messages:
        outbox.add(message)
    return messages


def render_outbox_preview(outbox_path: str | Path) -> str:
    outbox = Outbox(outbox_path)
    pending = outbox.pending()
    if not pending:
        return "No pending outbox messages."
    lines = [f"🐌 AffiliPilot outbox — {len(pending)} pending", ""]
    for msg in pending:
        lines.append(f"## {msg.id} [{msg.kind}]")
        lines.append(msg.text)
        if msg.attachments:
            lines.append("Attachments: " + ", ".join(msg.attachments))
        lines.append("")
    return "\n".join(lines)
