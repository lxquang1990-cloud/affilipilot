from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from affilipilot.db import AffiliPilotDB
from affilipilot.telegram.commands import TelegramIntent, help_text, parse_telegram_text
from affilipilot.publishing.auto_publish_after_approval import publish_after_approval, render_publish_after_approval
from affilipilot.publishing.dispatch import dispatch_publish_strategy
from affilipilot.telegram.delivery import mark_batch_delivered, queue_approval_batch
from affilipilot.workflows.approval import create_approval_batch, decide_post, render_status
from affilipilot.workflows.campaign_status import build_campaign_status, render_campaign_status
from affilipilot.workflows.doctor import build_doctor_report, render_doctor_report
from affilipilot.workflows.next_action import recommend_next_action, render_next_action


@dataclass
class AdapterConfig:
    db_path: Path
    work_dir: Path
    limit: int = 5
    outbox_path: Path | None = None
    publish_dir: Path | None = None
    auto_publish_on_approve: bool = False
    approval_receipt: str = ""


@dataclass
class AdapterResult:
    intent: TelegramIntent
    text: str
    attachments: list[Path]


def _latest_batch_key(db_path: Path) -> str | None:
    db = AffiliPilotDB(db_path)
    db.init()
    with db.connect() as conn:
        row = conn.execute("SELECT batch_key FROM batches ORDER BY id DESC LIMIT 1").fetchone()
    return row["batch_key"] if row else None


def _write_inbound_links(work_dir: Path, body: str, batch_key: str) -> Path:
    inbound_dir = work_dir / "inbound"
    inbound_dir.mkdir(parents=True, exist_ok=True)
    path = inbound_dir / f"{batch_key}.links.txt"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def handle_text_message(text: str, config: AdapterConfig) -> AdapterResult:
    command = parse_telegram_text(text)
    config.work_dir.mkdir(parents=True, exist_ok=True)

    if command.intent == TelegramIntent.HELP:
        return AdapterResult(command.intent, help_text(), [])

    if command.intent == TelegramIntent.CREATE_BATCH:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        batch_key = f"tg-{stamp}"
        input_path = _write_inbound_links(config.work_dir, command.args.get("body", ""), batch_key)
        out_dir = config.work_dir / "drafts" / batch_key
        manifest = create_approval_batch(input_path, out_dir, config.db_path, batch_key=batch_key, limit=config.limit)
        preview = out_dir / "approval_batch_preview.txt"
        queued_count = 0
        if config.outbox_path:
            queued_count = len(queue_approval_batch(config.db_path, batch_key=batch_key, outbox_path=config.outbox_path))
        lines = [
            f"🐌 AffiliPilot batch created: {batch_key}",
            f"Selected: {manifest['selected']}/{manifest['total_products']}",
            f"Status: /status {batch_key}",
            "Review preview attached/generated.",
        ]
        if config.outbox_path:
            lines.append(f"Telegram outbox queued: {queued_count} messages")
        return AdapterResult(command.intent, "\n".join(lines), [preview])

    if command.intent == TelegramIntent.STATUS:
        batch_key = command.args.get("batch_key") or "latest"
        if batch_key == "latest":
            batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        return AdapterResult(command.intent, render_status(config.db_path, batch_key=batch_key), [])

    if command.intent == TelegramIntent.CAMPAIGN_STATUS:
        batch_key = command.args.get("batch_key") or "latest"
        if batch_key == "latest":
            batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        outbox_path = config.outbox_path or (config.work_dir / "outbox.json")
        out_dir = config.publish_dir or (config.work_dir / "publish" / batch_key)
        status = build_campaign_status(db_path=config.db_path, batch_key=batch_key, outbox_path=outbox_path, out_dir=out_dir)
        return AdapterResult(command.intent, render_campaign_status(status), [])

    if command.intent == TelegramIntent.NEXT_ACTION:
        batch_key = command.args.get("batch_key") or "latest"
        if batch_key == "latest":
            batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        outbox_path = config.outbox_path or (config.work_dir / "outbox.json")
        plan_path = (config.publish_dir or (config.work_dir / "publish" / batch_key)) / "facebook-plan.json"
        result = recommend_next_action(db_path=config.db_path, batch_key=batch_key, outbox_path=outbox_path, plan_path=plan_path)
        return AdapterResult(command.intent, render_next_action(result), [])

    if command.intent == TelegramIntent.DOCTOR:
        batch_key = command.args.get("batch_key") or "latest"
        if batch_key == "latest":
            batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        outbox_path = config.outbox_path or (config.work_dir / "outbox.json")
        report = build_doctor_report(db_path=config.db_path, batch_key=batch_key, outbox_path=outbox_path)
        return AdapterResult(command.intent, render_doctor_report(report), [])

    if command.intent in {TelegramIntent.APPROVE, TelegramIntent.REJECT, TelegramIntent.NEEDS_EDIT, TelegramIntent.BLACKLIST}:
        batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        decision_map = {
            TelegramIntent.APPROVE: "approved",
            TelegramIntent.REJECT: "rejected",
            TelegramIntent.NEEDS_EDIT: "needs_edit",
            TelegramIntent.BLACKLIST: "blacklisted",
        }
        post_id = command.args["post_id"]
        reason = command.args.get("reason", "")
        decision = decision_map[command.intent]
        decide_post(config.db_path, batch_key=batch_key, post_id=post_id, decision=decision, reason=reason)
        status_text = render_status(config.db_path, batch_key=batch_key)
        if command.intent == TelegramIntent.APPROVE and config.auto_publish_on_approve:
            if not config.outbox_path:
                return AdapterResult(command.intent, status_text + "\n\n⚠️ Auto-publish skipped: missing outbox path for delivery proof.", [])
            receipt = config.approval_receipt or f"local-approval:{batch_key}:{post_id}"
            try:
                mark_batch_delivered(config.outbox_path, batch_key=batch_key, post_id=post_id, receipt=receipt)
                publish_result = publish_after_approval(
                    db_path=config.db_path,
                    batch_key=batch_key,
                    post_id=post_id,
                    outbox_path=config.outbox_path,
                    out_dir=config.publish_dir or (config.work_dir / "publish" / batch_key),
                    publisher=dispatch_publish_strategy,
                )
                status_text += "\n\n" + render_publish_after_approval(publish_result)
            except Exception as exc:  # keep adapter responsive; surface blocker to operator
                status_text += f"\n\n⚠️ Auto-publish failed after approval: {exc}"
        return AdapterResult(command.intent, status_text, [])

    return AdapterResult(command.intent, help_text(), [])
