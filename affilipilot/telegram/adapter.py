from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from affilipilot.db import AffiliPilotDB
from affilipilot.engagement import approve_comment_reply, ignore_comment, render_comment_action
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

def _batch_key_for_post_id(db_path: Path, post_id: str) -> str | None:
    """Resolve old shorthand commands only when the post_id is globally unique."""
    db = AffiliPilotDB(db_path)
    db.init()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT batch_key FROM approvals WHERE post_id = ? ORDER BY id DESC",
            (post_id,),
        ).fetchall()
    if not rows:
        return None
    unique = sorted({row["batch_key"] for row in rows})
    if len(unique) == 1:
        return unique[0]
    raise ValueError(
        "Ambiguous post_id; use /aff_approve <batch_key> <post_id>. "
        + "Matches: "
        + ", ".join(unique[:8])
    )


def _latest_pending_approval(db_path: Path) -> tuple[str, str] | None:
    """Return the newest pending approval for quick replies like 'ok' or 'no'."""
    db = AffiliPilotDB(db_path)
    db.init()
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT batch_key, post_id
            FROM approvals
            WHERE status = 'pending'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return row["batch_key"], row["post_id"]


def _write_inbound_links(work_dir: Path, body: str, batch_key: str) -> Path:
    inbound_dir = work_dir / "inbound"
    inbound_dir.mkdir(parents=True, exist_ok=True)
    path = inbound_dir / f"{batch_key}.links.txt"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path

def _outbox_has_message(outbox_path: Path, batch_key: str, post_id: str) -> bool:
    if not outbox_path.exists():
        return False
    needle = f'"id": "{batch_key}:{post_id}"'
    try:
        return needle in outbox_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False

def _resolve_publish_dir(config: AdapterConfig, batch_key: str) -> Path:
    """Resolve approval-triggered publish artifacts to a batch-scoped directory.

    The Telegram bot may pass a shared publish directory such as
    data/publish/telegram. Writing every approval-triggered facebook-plan.json to
    that shared directory makes later quick replies susceptible to stale or
    cross-batch plan/context. Keep artifacts under <publish_dir>/<batch_key>
    unless the caller already supplied a batch-specific directory.
    """
    base = config.publish_dir or (config.work_dir / "publish")
    base = base.expanduser()
    if base.name == batch_key:
        return base
    return base / batch_key


def _resolve_delivery_outbox(config: AdapterConfig, batch_key: str, post_id: str) -> Path | None:
    """Resolve the concrete outbox file for delivery proof.

    Scheduled E2E runs write one file per batch under data/outbox/<batch>.json,
    while older adapter invocations may pass a generic outbox path. Quick replies
    can approve a DB batch successfully but auto-publish must mark the exact
    delivered approval card, so prefer a batch-specific file when available.
    """
    candidates: list[Path] = []
    if config.outbox_path:
        candidates.append(config.outbox_path)
        if config.outbox_path.is_dir():
            candidates.append(config.outbox_path / f"{batch_key}.json")
        else:
            candidates.append(config.outbox_path.parent / f"{batch_key}.json")
    candidates.extend([
        config.work_dir / "outbox" / f"{batch_key}.json",
        config.work_dir / "data" / "outbox" / f"{batch_key}.json",
        config.db_path.parent / "outbox" / f"{batch_key}.json",
        Path("data/outbox") / f"{batch_key}.json",
    ])
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.expanduser()
        if candidate in seen:
            continue
        seen.add(candidate)
        if _outbox_has_message(candidate, batch_key, post_id):
            return candidate
    return config.outbox_path


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
        out_dir = _resolve_publish_dir(config, batch_key)
        status = build_campaign_status(db_path=config.db_path, batch_key=batch_key, outbox_path=outbox_path, out_dir=out_dir)
        return AdapterResult(command.intent, render_campaign_status(status), [])

    if command.intent == TelegramIntent.NEXT_ACTION:
        batch_key = command.args.get("batch_key") or "latest"
        if batch_key == "latest":
            batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        outbox_path = config.outbox_path or (config.work_dir / "outbox.json")
        plan_path = _resolve_publish_dir(config, batch_key) / "facebook-plan.json"
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

    if command.intent == TelegramIntent.AFF_REPLY:
        result = approve_comment_reply(config.db_path, comment_id=command.args["comment_id"], message=command.args["message"])
        return AdapterResult(command.intent, render_comment_action(result), [])

    if command.intent == TelegramIntent.AFF_IGNORE:
        result = ignore_comment(config.db_path, comment_id=command.args["comment_id"])
        return AdapterResult(command.intent, render_comment_action(result), [])

    if command.intent in {TelegramIntent.APPROVE, TelegramIntent.REJECT, TelegramIntent.NEEDS_EDIT, TelegramIntent.BLACKLIST}:
        post_id = command.args["post_id"]
        if post_id == "latest":
            latest = _latest_pending_approval(config.db_path)
            if not latest:
                return AdapterResult(command.intent, "No pending approval found for quick reply.", [])
            batch_key, post_id = latest
        elif command.args.get("batch_key"):
            batch_key = command.args["batch_key"]
        else:
            try:
                batch_key = _batch_key_for_post_id(config.db_path, post_id)
            except ValueError as exc:
                return AdapterResult(command.intent, f"⚠️ {exc}", [])
            if not batch_key:
                batch_key = _latest_batch_key(config.db_path)
        if not batch_key:
            return AdapterResult(command.intent, "No batch found yet.", [])
        decision_map = {
            TelegramIntent.APPROVE: "approved",
            TelegramIntent.REJECT: "rejected",
            TelegramIntent.NEEDS_EDIT: "needs_edit",
            TelegramIntent.BLACKLIST: "blacklisted",
        }
        reason = command.args.get("reason", "")
        decision = decision_map[command.intent]
        try:
            decide_post(config.db_path, batch_key=batch_key, post_id=post_id, decision=decision, reason=reason)
        except KeyError as exc:
            return AdapterResult(command.intent, f"⚠️ Approval not found: {batch_key}/{post_id}. Use the exact command from the approval card.", [])
        status_text = render_status(config.db_path, batch_key=batch_key)
        if command.intent == TelegramIntent.APPROVE and config.auto_publish_on_approve:
            delivery_outbox = _resolve_delivery_outbox(config, batch_key, post_id)
            if not delivery_outbox:
                return AdapterResult(command.intent, status_text + "\n\n⚠️ Auto-publish skipped: missing outbox path for delivery proof.", [])
            receipt = config.approval_receipt or f"local-approval:{batch_key}:{post_id}"
            try:
                mark_batch_delivered(delivery_outbox, batch_key=batch_key, post_id=post_id, receipt=receipt)
                publish_result = publish_after_approval(
                    db_path=config.db_path,
                    batch_key=batch_key,
                    post_id=post_id,
                    outbox_path=delivery_outbox,
                    out_dir=_resolve_publish_dir(config, batch_key),
                    publisher=dispatch_publish_strategy,
                )
                status_text += "\n\n" + render_publish_after_approval(publish_result)
            except Exception as exc:  # keep adapter responsive; surface blocker to operator
                status_text += f"\n\n⚠️ Auto-publish failed after approval: {exc}"
        return AdapterResult(command.intent, status_text, [])

    return AdapterResult(command.intent, help_text(), [])
