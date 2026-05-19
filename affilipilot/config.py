from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _resolve_default_secret_path() -> Path:
    """Resolve secret file path with sensible fallbacks.

    Priority:
    1. ``AFFILIPILOT_SECRETS`` environment variable (explicit operator choice).
    2. Legacy Pi location ``/home/snail/.openclaw/workspace/secrets/affilipilot.env``
       if running on Snail's Pi (still the primary deployment target).
    3. XDG-style ``~/.config/affilipilot/secrets.env`` on any other host.
    """
    override = os.environ.get("AFFILIPILOT_SECRETS")
    if override:
        return Path(override).expanduser()
    legacy = Path("/home/snail/.openclaw/workspace/secrets/affilipilot.env")
    if legacy.exists() or legacy.parent.exists():
        return legacy
    return Path.home() / ".config" / "affilipilot" / "secrets.env"


DEFAULT_SECRET_PATH = _resolve_default_secret_path()


@dataclass
class AffiliPilotConfig:
    accesstrade_token_present: bool = False
    accesstrade_campaign_present: bool = False
    accesstrade_campaign_count: int = 0
    facebook_page_id_present: bool = False
    facebook_page_token_present: bool = False
    router_key_present: bool = False
    router_endpoint_present: bool = False
    telegram_config_present: bool = False
    daily_budget_vnd: int = 30_000
    soft_budget_ratio: float = 0.8
    secret_path: Path = DEFAULT_SECRET_PATH

    @property
    def soft_budget_vnd(self) -> int:
        return int(self.daily_budget_vnd * self.soft_budget_ratio)


@lru_cache(maxsize=8)
def _load_env_file_cached(path_str: str, mtime_ns: int) -> tuple[tuple[str, str], ...]:
    """Internal cache keyed by (path, mtime). Returns tuple for hashability."""
    path = Path(path_str)
    if not path.exists():
        return ()
    values: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.append((key.strip(), value.strip().strip('"').strip("'")))
    return tuple(values)


def load_env_file(path: str | Path = DEFAULT_SECRET_PATH) -> dict[str, str]:
    """Read a dotenv-style secret file. Cached by (path, mtime) for E2E hot paths."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        mtime_ns = p.stat().st_mtime_ns
    except OSError:
        return {}
    return dict(_load_env_file_cached(str(p), mtime_ns))


def load_config(secret_path: str | Path = DEFAULT_SECRET_PATH) -> AffiliPilotConfig:
    env_file = load_env_file(secret_path)

    def present(name: str) -> bool:
        return bool(os.environ.get(name) or env_file.get(name))

    merged = {**env_file, **os.environ}
    campaign_keys = [key for key, value in merged.items() if key.startswith("ACCESSTRADE_CAMPAIGN_") and value and not key.endswith(("_CHANNEL_ID", "_DOMAINS"))]
    generic_campaign_present = present("ACCESSTRADE_CAMPAIGN_ID") or present("ACCESSTRADE_SHOPEE_CAMPAIGN_ID") or bool(campaign_keys)

    budget_raw = os.environ.get("AFFILIPILOT_DAILY_BUDGET_VND") or env_file.get("AFFILIPILOT_DAILY_BUDGET_VND") or "30000"
    try:
        budget = int(budget_raw)
    except ValueError:
        budget = 30_000

    return AffiliPilotConfig(
        accesstrade_token_present=present("ACCESSTRADE_TOKEN"),
        accesstrade_campaign_present=generic_campaign_present,
        accesstrade_campaign_count=len(campaign_keys) + (1 if present("ACCESSTRADE_CAMPAIGN_ID") or present("ACCESSTRADE_SHOPEE_CAMPAIGN_ID") else 0),
        facebook_page_id_present=present("FACEBOOK_PAGE_ID"),
        facebook_page_token_present=present("FACEBOOK_PAGE_ACCESS_TOKEN"),
        router_key_present=present("9ROUTER_API_KEY"),
        router_endpoint_present=present("9ROUTER_API_ENDPOINT"),
        telegram_config_present=present("TELEGRAM_BOT_TOKEN") and present("TELEGRAM_CHAT_ID"),
        daily_budget_vnd=budget,
        secret_path=Path(secret_path),
    )


def render_config_status(config: AffiliPilotConfig) -> str:
    return "\n".join([
        "🐌 AffiliPilot config status",
        f"Accesstrade token: {'present' if config.accesstrade_token_present else 'missing'}",
        f"Accesstrade campaigns: {'present' if config.accesstrade_campaign_present else 'pending/missing'} ({config.accesstrade_campaign_count})",
        f"Facebook Page ID: {'present' if config.facebook_page_id_present else 'missing'}",
        f"Facebook Page token: {'present' if config.facebook_page_token_present else 'missing'}",
        f"9Router key: {'present' if config.router_key_present else 'missing'}",
        f"9Router endpoint: {'present' if config.router_endpoint_present else 'missing'}",
        f"Telegram config: {'present' if config.telegram_config_present else 'missing'}",
        f"Daily budget: {config.daily_budget_vnd} VND",
        f"Soft budget: {config.soft_budget_vnd} VND",
        f"Secret path: {config.secret_path}",
    ])
