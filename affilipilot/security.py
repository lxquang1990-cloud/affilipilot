from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH

# Regex used to identify sensitive keys in nested response payloads (Accesstrade,
# Facebook Graph API, Telegram, 9Router). Match anywhere in the key name and
# case-insensitive so partials like "page_access_token" or "Authorization" hit.
SECRET_KEY_RE = re.compile(
    r"(token|authorization|access_key|secret|password|api_key|bearer|cookie|set-cookie)",
    re.IGNORECASE,
)

# Inline patterns that look like bearer tokens or long opaque secrets embedded in
# free-form strings (error messages, raw HTML). Conservative: only redact obvious
# matches to avoid mangling user-visible content.
_INLINE_TOKEN_PATTERNS = (
    re.compile(r"(access_token=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"(EAA[A-Za-z0-9]{20,})"),  # Facebook Graph token prefix
)


def redact_for_audit(value: Any, *, max_string_length: int = 500) -> Any:
    """Recursively redact secrets from API response payloads before logging.

    Used by Accesstrade and (after this patch) Facebook publishing to ensure
    raw provider responses never leak tokens into JSON files or event logs.
    """
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if SECRET_KEY_RE.search(str(key)) else redact_for_audit(item, max_string_length=max_string_length))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_for_audit(item, max_string_length=max_string_length) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_for_audit(item, max_string_length=max_string_length) for item in value)
    if isinstance(value, str):
        redacted = value
        for pattern in _INLINE_TOKEN_PATTERNS:
            redacted = pattern.sub(lambda m: m.group(1) + "[REDACTED]" if m.lastindex else "[REDACTED]", redacted)
        if len(redacted) > max_string_length:
            return redacted[:max_string_length] + "...[truncated]"
        return redacted
    return value


def redact_response(result: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of a publish/API result dict with response payload redacted.

    Convenience wrapper for the common pattern: provider responses are stored
    under the ``response`` key, and we want everything else (ok, status, endpoint)
    to pass through verbatim.
    """
    if not isinstance(result, dict):
        return result
    redacted = dict(result)
    if "response" in redacted:
        redacted["response"] = redact_for_audit(redacted["response"])
    return redacted


ENV_TEMPLATE = """# AffiliPilot secrets — fill locally, never commit or paste into chat.
# chmod 600 this file.

# Accesstrade
ACCESSTRADE_TOKEN=
# Generic default campaign. For multiple campaigns, prefer ACCESSTRADE_CAMPAIGN_<KEY>.
ACCESSTRADE_CAMPAIGN_ID=
ACCESSTRADE_CHANNEL_ID=

# Optional multi-campaign examples.
ACCESSTRADE_CAMPAIGN_SHOPEE=
ACCESSTRADE_CAMPAIGN_SHOPEE_CHANNEL_ID=
ACCESSTRADE_CAMPAIGN_SHOPEE_DOMAINS=shopee.vn,shopee.com
ACCESSTRADE_CAMPAIGN_LAZADA=
ACCESSTRADE_CAMPAIGN_LAZADA_CHANNEL_ID=
ACCESSTRADE_CAMPAIGN_LAZADA_DOMAINS=lazada.vn,lazada.com

# Backward-compatible legacy key; still supported.
ACCESSTRADE_SHOPEE_CAMPAIGN_ID=

# Facebook Page publishing
FACEBOOK_PAGE_ID=
FACEBOOK_PAGE_ACCESS_TOKEN=
FACEBOOK_USER_ACCESS_TOKEN=
FACEBOOK_USER_TOKEN_EXPIRES=

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
