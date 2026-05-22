from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TelegramIntent(str, Enum):
    HELP = "help"
    STATUS = "status"
    CAMPAIGN_STATUS = "campaign_status"
    NEXT_ACTION = "next_action"
    DOCTOR = "doctor"
    CREATE_BATCH = "create_batch"
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EDIT = "needs_edit"
    BLACKLIST = "blacklist"
    AFF_REPLY = "aff_reply"
    AFF_IGNORE = "aff_ignore"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    intent: TelegramIntent
    args: dict[str, str]
    raw_text: str


def _has_product_links(text: str) -> bool:
    lowered = text.lower()
    return "shopee." in lowered or "accesstrade" in lowered or "http" in lowered


def _decision_args(parts: list[str]) -> dict[str, str]:
    # Backward-compatible: /aff_approve <post_id> [reason]
    # Batch-safe: /aff_approve <batch_key> <post_id> [reason]
    if len(parts) >= 3 and parts[2].startswith("post_"):
        return {"batch_key": parts[1], "post_id": parts[2], "reason": " ".join(parts[3:])}
    return {"post_id": parts[1], "reason": " ".join(parts[2:])}

def parse_telegram_text(text: str) -> ParsedCommand:
    raw = text.strip()
    lowered = raw.lower()
    parts = raw.split()
    cmd = parts[0].lower() if parts and parts[0].startswith("/") else ""

    if cmd in {"/help", "/start"}:
        return ParsedCommand(TelegramIntent.HELP, {}, raw)
    if cmd == "/status":
        return ParsedCommand(TelegramIntent.STATUS, {"batch_key": parts[1] if len(parts) > 1 else "latest"}, raw)
    if cmd in {"/campaign_status", "/campaign-status", "/campaign"}:
        return ParsedCommand(TelegramIntent.CAMPAIGN_STATUS, {"batch_key": parts[1] if len(parts) > 1 else "latest"}, raw)
    if cmd in {"/next_action", "/next-action", "/next"}:
        return ParsedCommand(TelegramIntent.NEXT_ACTION, {"batch_key": parts[1] if len(parts) > 1 else "latest"}, raw)
    if cmd == "/doctor":
        return ParsedCommand(TelegramIntent.DOCTOR, {"batch_key": parts[1] if len(parts) > 1 else "latest"}, raw)
    if cmd in {"/aff_approve", "/ap_approve", "/ok_aff"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.APPROVE, _decision_args(parts), raw)
    if cmd in {"/aff_reject", "/ap_reject", "/no_aff"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.REJECT, _decision_args(parts), raw)
    if cmd in {"/aff_edit", "/ap_edit", "/aff_needs_edit"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.NEEDS_EDIT, _decision_args(parts), raw)
    if cmd in {"/aff_blacklist", "/ap_blacklist", "/aff_ban"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.BLACKLIST, _decision_args(parts), raw)
    if cmd == "/aff_reply" and len(parts) >= 3:
        return ParsedCommand(TelegramIntent.AFF_REPLY, {"comment_id": parts[1], "message": " ".join(parts[2:])}, raw)
    if cmd == "/aff_ignore" and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.AFF_IGNORE, {"comment_id": parts[1]}, raw)
    if cmd == "/batch":
        body = raw.split("\n", 1)[1] if "\n" in raw else ""
        return ParsedCommand(TelegramIntent.CREATE_BATCH, {"body": body}, raw)
    if _has_product_links(raw):
        return ParsedCommand(TelegramIntent.CREATE_BATCH, {"body": raw}, raw)
    return ParsedCommand(TelegramIntent.UNKNOWN, {}, raw)


def help_text() -> str:
    return "\n".join([
        "🐌 AffiliPilot commands",
        "",
        "Paste 20-50 Shopee/Accesstrade links to create a batch.",
        "Or use:",
        "/batch <links> — create approval batch",
        "/status [batch_key] — show approval status",
        "/campaign_status [batch_key] — one-screen campaign dashboard",
        "/next_action [batch_key] — show exact next operator step",
        "/doctor [batch_key] — read-only system/batch audit",
        "/aff_approve <batch_key> <post_id> [reason]",
        "/aff_reject <batch_key> <post_id> [reason]",
        "/aff_edit <batch_key> <post_id> [reason]",
        "/aff_blacklist <batch_key> <post_id> [reason]",
        "/aff_reply <comment_id> <nội dung> — approve and send comment reply",
        "/aff_ignore <comment_id> — ignore a queued comment",
    ])
