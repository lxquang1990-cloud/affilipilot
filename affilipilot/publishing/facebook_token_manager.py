from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file
from affilipilot.publishing.facebook_token import check_facebook_token

GRAPH_URL = "https://graph.facebook.com/v19.0"

@dataclass
class FacebookSecretValues:
    app_id: str = ""
    app_secret: str = ""
    page_id: str = ""
    page_access_token: str = ""
    user_access_token: str = ""
    token_expires: str = ""
    secret_path: Path = DEFAULT_SECRET_PATH

@dataclass
class FacebookTokenManagerResult:
    ok: bool
    action: str
    message: str
    updated_keys: list[str] = field(default_factory=list)
    expires_at: str = ""
    days_left: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


def load_facebook_secret_values(secret_path: str | Path = DEFAULT_SECRET_PATH) -> FacebookSecretValues:
    env = load_env_file(secret_path)
    def value(*names: str) -> str:
        for name in names:
            if os.environ.get(name):
                return os.environ[name]
            if env.get(name):
                return env[name]
        return ""
    return FacebookSecretValues(
        app_id=value("FACEBOOK_APP_ID", "FB_APP_ID", "APP_ID"),
        app_secret=value("FACEBOOK_APP_SECRET", "FB_APP_SECRET", "APP_SECRET"),
        page_id=value("FACEBOOK_PAGE_ID", "FB_PAGE_ID"),
        page_access_token=value("FACEBOOK_PAGE_ACCESS_TOKEN", "FB_PAGE_TOKEN"),
        user_access_token=value("FACEBOOK_USER_ACCESS_TOKEN", "FB_USER_TOKEN"),
        token_expires=value("FACEBOOK_USER_TOKEN_EXPIRES", "FB_TOKEN_EXPIRES"),
        secret_path=Path(secret_path),
    )


def _get_json(endpoint: str, params: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body[:500]}
        message = payload.get("error", {}).get("message") or payload.get("error") or f"http_{exc.code}"
        raise RuntimeError(str(message)) from exc


def inspect_token(token: str, app_id: str, app_secret: str, *, timeout: int = 30) -> dict[str, Any]:
    return _get_json(
        f"{GRAPH_URL}/debug_token",
        {"input_token": token, "access_token": f"{app_id}|{app_secret}"},
        timeout=timeout,
    ).get("data", {})


def exchange_to_long_lived_user_token(short_token: str, app_id: str, app_secret: str, *, timeout: int = 30) -> dict[str, Any]:
    return _get_json(
        f"{GRAPH_URL}/oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=timeout,
    )


def get_page_token(user_token: str, page_id: str, *, timeout: int = 30) -> tuple[str, list[dict[str, Any]]]:
    payload = _get_json(f"{GRAPH_URL}/me/accounts", {"access_token": user_token}, timeout=timeout)
    pages = payload.get("data", []) if isinstance(payload.get("data"), list) else []
    for page in pages:
        if str(page.get("id")) == str(page_id):
            return str(page.get("access_token", "")), pages
    return "", pages


def update_secret_file(path: str | Path, updates: dict[str, str]) -> list[str]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    done: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            done.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in done:
            new_lines.append(f"{key}={value}")
            done.add(key)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return sorted(done)


def _expires_date_from_seconds(expires_in: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).date().isoformat()


def _days_left_from_date(date_text: str) -> int | None:
    if not date_text:
        return None
    try:
        target = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (target - datetime.now(timezone.utc)).days


def exchange_short_token(short_token: str, *, secret_path: str | Path = DEFAULT_SECRET_PATH, write: bool = True, timeout: int = 30) -> FacebookTokenManagerResult:
    values = load_facebook_secret_values(secret_path)
    if not values.app_id or not values.app_secret:
        return FacebookTokenManagerResult(False, "exchange", "missing_FACEBOOK_APP_ID_or_FACEBOOK_APP_SECRET")
    if not values.page_id:
        return FacebookTokenManagerResult(False, "exchange", "missing_FACEBOOK_PAGE_ID")
    if not short_token:
        return FacebookTokenManagerResult(False, "exchange", "missing_short_token")

    exchanged = exchange_to_long_lived_user_token(short_token, values.app_id, values.app_secret, timeout=timeout)
    user_token = exchanged.get("access_token", "")
    expires_in = int(exchanged.get("expires_in") or 0)
    if not user_token:
        return FacebookTokenManagerResult(False, "exchange", "facebook_exchange_returned_no_access_token")
    page_token, pages = get_page_token(user_token, values.page_id, timeout=timeout)
    if not page_token:
        return FacebookTokenManagerResult(False, "exchange", "page_token_not_found_for_FACEBOOK_PAGE_ID", details={"pages": [{"id": p.get("id"), "name": p.get("name")} for p in pages]})

    expires_at = _expires_date_from_seconds(expires_in) if expires_in else ""
    updates = {
        "FACEBOOK_USER_ACCESS_TOKEN": user_token,
        "FACEBOOK_PAGE_ACCESS_TOKEN": page_token,
    }
    if expires_at:
        updates["FACEBOOK_USER_TOKEN_EXPIRES"] = expires_at
    updated = update_secret_file(secret_path, updates) if write else []
    return FacebookTokenManagerResult(True, "exchange", "long_lived_user_and_page_token_ready", updated_keys=updated, expires_at=expires_at, days_left=_days_left_from_date(expires_at))


def refresh_from_user_token(*, secret_path: str | Path = DEFAULT_SECRET_PATH, auto: bool = False, threshold_days: int = 15, write: bool = True, timeout: int = 30) -> FacebookTokenManagerResult:
    values = load_facebook_secret_values(secret_path)
    if not values.app_id or not values.app_secret:
        return FacebookTokenManagerResult(False, "refresh", "missing_FACEBOOK_APP_ID_or_FACEBOOK_APP_SECRET")
    if not values.user_access_token:
        return FacebookTokenManagerResult(False, "refresh", "missing_FACEBOOK_USER_ACCESS_TOKEN; run exchange with a fresh short-lived user token")
    if not values.page_id:
        return FacebookTokenManagerResult(False, "refresh", "missing_FACEBOOK_PAGE_ID")

    days_left = _days_left_from_date(values.token_expires)
    if auto and days_left is not None and days_left > threshold_days:
        return FacebookTokenManagerResult(True, "refresh", f"skip_refresh_user_token_still_has_{days_left}_days", days_left=days_left, expires_at=values.token_expires)

    info = inspect_token(values.user_access_token, values.app_id, values.app_secret, timeout=timeout)
    if not info.get("is_valid"):
        return FacebookTokenManagerResult(False, "refresh", "FACEBOOK_USER_ACCESS_TOKEN_invalid_or_expired; manual OAuth exchange required")

    exchanged = exchange_to_long_lived_user_token(values.user_access_token, values.app_id, values.app_secret, timeout=timeout)
    new_user_token = exchanged.get("access_token", "")
    expires_in = int(exchanged.get("expires_in") or 0)
    if not new_user_token:
        return FacebookTokenManagerResult(False, "refresh", "facebook_refresh_returned_no_access_token")
    page_token, pages = get_page_token(new_user_token, values.page_id, timeout=timeout)
    if not page_token:
        return FacebookTokenManagerResult(False, "refresh", "page_token_not_found_for_FACEBOOK_PAGE_ID", details={"pages": [{"id": p.get("id"), "name": p.get("name")} for p in pages]})

    expires_at = _expires_date_from_seconds(expires_in) if expires_in else ""
    updates = {
        "FACEBOOK_USER_ACCESS_TOKEN": new_user_token,
        "FACEBOOK_PAGE_ACCESS_TOKEN": page_token,
    }
    if expires_at:
        updates["FACEBOOK_USER_TOKEN_EXPIRES"] = expires_at
    updated = update_secret_file(secret_path, updates) if write else []
    return FacebookTokenManagerResult(True, "refresh", "facebook_user_and_page_token_refreshed", updated_keys=updated, expires_at=expires_at, days_left=_days_left_from_date(expires_at))


def derive_page_token(*, secret_path: str | Path = DEFAULT_SECRET_PATH, write: bool = True, timeout: int = 30) -> FacebookTokenManagerResult:
    values = load_facebook_secret_values(secret_path)
    if not values.user_access_token:
        return FacebookTokenManagerResult(False, "page-token", "missing_FACEBOOK_USER_ACCESS_TOKEN")
    if not values.page_id:
        return FacebookTokenManagerResult(False, "page-token", "missing_FACEBOOK_PAGE_ID")
    page_token, pages = get_page_token(values.user_access_token, values.page_id, timeout=timeout)
    if not page_token:
        return FacebookTokenManagerResult(False, "page-token", "page_token_not_found_for_FACEBOOK_PAGE_ID", details={"pages": [{"id": p.get("id"), "name": p.get("name")} for p in pages]})
    updated = update_secret_file(secret_path, {"FACEBOOK_PAGE_ACCESS_TOKEN": page_token}) if write else []
    return FacebookTokenManagerResult(True, "page-token", "facebook_page_token_ready", updated_keys=updated)


def render_token_manager_result(result: FacebookTokenManagerResult) -> str:
    lines = [
        "🐌 Facebook token manager",
        f"Action: {result.action}",
        f"Status: {'ok' if result.ok else 'blocked'}",
        f"Message: {result.message}",
    ]
    if result.expires_at:
        lines.append(f"User token expires: {result.expires_at}")
    if result.days_left is not None:
        lines.append(f"Days left: {result.days_left}")
    if result.updated_keys:
        lines.append("Updated keys: " + ", ".join(result.updated_keys))
    if result.details.get("pages"):
        lines.append("Available pages:")
        for page in result.details["pages"]:
            lines.append(f"- {page.get('id')}: {page.get('name')}")
    lines.append("No token values are printed.")
    return "\n".join(lines)


def inspect_current_page_token(*, timeout: int = 30) -> FacebookTokenManagerResult:
    report = check_facebook_token(timeout=timeout)
    if report.valid and not report.missing_scopes and report.page_probe_ok:
        return FacebookTokenManagerResult(True, "inspect", "facebook_page_token_valid", expires_at=str(report.expires_at or ""), details={"scopes": report.scopes})
    return FacebookTokenManagerResult(False, "inspect", report.error or report.page_probe_error or "facebook_page_token_not_ready", expires_at=str(report.expires_at or ""), details={"missing_scopes": report.missing_scopes})
