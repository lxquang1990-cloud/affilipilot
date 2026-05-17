from __future__ import annotations

import os
import stat
from pathlib import Path

from affilipilot.config import DEFAULT_SECRET_PATH

ENV_TEMPLATE = """# AffiliPilot secrets — fill locally, never commit or paste into chat.
# chmod 600 this file.

# Accesstrade
ACCESSTRADE_TOKEN=
ACCESSTRADE_SHOPEE_CAMPAIGN_ID=

# Facebook Page publishing
FACEBOOK_PAGE_ID=
FACEBOOK_PAGE_ACCESS_TOKEN=

# LLM / 9Router
9ROUTER_API_KEY=
9ROUTER_API_ENDPOINT=http://100.103.10.31:20128/v1
AFFILIPILOT_DAILY_BUDGET_VND=30000

# Telegram control plane, optional if routed through OpenClaw later
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
"""


def write_secret_template(path: str | Path = DEFAULT_SECRET_PATH, *, overwrite: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return path
    path.write_text(ENV_TEMPLATE, encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


def check_secret_file_permissions(path: str | Path = DEFAULT_SECRET_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {"exists": False, "mode": None, "secure": False, "reason": "missing"}
    mode = stat.S_IMODE(path.stat().st_mode)
    secure = mode == 0o600
    return {"exists": True, "mode": oct(mode), "secure": secure, "reason": "ok" if secure else "expected_0600"}
