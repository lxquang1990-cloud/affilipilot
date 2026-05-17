from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TelegramIntent(str, Enum):
    HELP = "help"
    STATUS = "status"
    CREATE_BATCH = "create_batch"
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EDIT = "needs_edit"
    BLACKLIST = "blacklist"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    intent: TelegramIntent
    args: dict[str, str]
    raw_text: str


def _has_product_links(text: str) -> bool:
    lowered = text.lower()
    return "shopee." in lowered or "accesstrade" in lowered or "http" in lowered


def parse_telegram_text(text: str) -> ParsedCommand:
    raw = text.strip()
    lowered = raw.lower()
    parts = raw.split()
    cmd = parts[0].lower() if parts and parts[0].startswith("/") else ""

    if cmd in {"/help", "/start"}:
        return ParsedCommand(TelegramIntent.HELP, {}, raw)
    if cmd == "/status":
        return ParsedCommand(TelegramIntent.STATUS, {"batch_key": parts[1] if len(parts) > 1 else "latest"}, raw)
    if cmd in {"/approve", "/ok"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.APPROVE, {"post_id": parts[1], "reason": " ".join(parts[2:])}, raw)
    if cmd in {"/reject", "/no"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.REJECT, {"post_id": parts[1], "reason": " ".join(parts[2:])}, raw)
    if cmd in {"/edit", "/needs_edit"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.NEEDS_EDIT, {"post_id": parts[1], "reason": " ".join(parts[2:])}, raw)
    if cmd in {"/blacklist", "/ban"} and len(parts) >= 2:
        return ParsedCommand(TelegramIntent.BLACKLIST, {"post_id": parts[1], "reason": " ".join(parts[2:])}, raw)
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
        "/approve <post_id> [reason]",
        "/reject <post_id> [reason]",
        "/edit <post_id> [reason]",
        "/blacklist <post_id> [reason]",
    ])
