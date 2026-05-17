from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file
from affilipilot.publishing.facebook import FacebookConfig

REQUIRED_PAGE_SCOPES = {"pages_manage_posts", "pages_read_engagement"}


@dataclass
class FacebookTokenReport:
    valid: bool
    app_id_present: bool
    app_secret_present: bool
    token_present: bool
    page_id_present: bool
    scopes: list[str] = field(default_factory=list)
    missing_scopes: list[str] = field(default_factory=list)
    expires_at: int | None = None
    data_access_expires_at: int | None = None
    user_id: str = ""
    app_id: str = ""
    page_probe_ok: bool = False
    page_probe_status: int | None = None
    page_probe_error: str = ""
    error: str = ""


def _read_facebook_secret_values() -> dict[str, str]:
    env = load_env_file(DEFAULT_SECRET_PATH)
    return {
        "app_id": env.get("FACEBOOK_APP_ID") or env.get("APP_ID") or env.get("App_ID") or "",
        "app_secret": env.get("FACEBOOK_APP_SECRET") or env.get("APP_SECRET") or env.get("App_Secret") or "",
        "page_id": env.get("FACEBOOK_PAGE_ID", ""),
        "page_access_token": env.get("FACEBOOK_PAGE_ACCESS_TOKEN", ""),
    }


def _get_json(url: str, timeout: int = 30) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        return exc.code, parsed


def check_facebook_token(timeout: int = 30) -> FacebookTokenReport:
    values = _read_facebook_secret_values()
    report = FacebookTokenReport(
        valid=False,
        app_id_present=bool(values["app_id"]),
        app_secret_present=bool(values["app_secret"]),
        token_present=bool(values["page_access_token"]),
        page_id_present=bool(values["page_id"]),
    )
    if not (report.app_id_present and report.app_secret_present and report.token_present):
        report.error = "missing_app_id_app_secret_or_token"
        report.missing_scopes = sorted(REQUIRED_PAGE_SCOPES)
        return report

    app_access_token = f"{values['app_id']}|{values['app_secret']}"
    params = urllib.parse.urlencode({
        "input_token": values["page_access_token"],
        "access_token": app_access_token,
    })
    status, payload = _get_json(f"https://graph.facebook.com/debug_token?{params}", timeout=timeout)
    if status != 200:
        report.error = payload.get("error", {}).get("message", f"debug_token_http_{status}")
        report.missing_scopes = sorted(REQUIRED_PAGE_SCOPES)
        return report

    data = payload.get("data", {})
    report.valid = bool(data.get("is_valid"))
    report.scopes = sorted(data.get("scopes") or data.get("granular_scopes") or [])
    if data.get("granular_scopes") and not data.get("scopes"):
        # granular_scopes can be list of dicts; normalize names when present.
        names = []
        for item in data.get("granular_scopes", []):
            if isinstance(item, dict) and item.get("scope"):
                names.append(item["scope"])
        report.scopes = sorted(names)
    report.expires_at = data.get("expires_at")
    report.data_access_expires_at = data.get("data_access_expires_at")
    report.user_id = str(data.get("user_id", ""))
    report.app_id = str(data.get("app_id", ""))
    scope_set = set(report.scopes)
    report.missing_scopes = sorted(REQUIRED_PAGE_SCOPES - scope_set)

    if values["page_id"] and values["page_access_token"]:
        probe_params = urllib.parse.urlencode({
            "fields": "id,name,access_token",
            "access_token": values["page_access_token"],
        })
        pstatus, ppayload = _get_json(f"https://graph.facebook.com/v19.0/{values['page_id']}?{probe_params}", timeout=timeout)
        report.page_probe_status = pstatus
        report.page_probe_ok = pstatus == 200 and ppayload.get("id") == values["page_id"]
        if not report.page_probe_ok:
            report.page_probe_error = ppayload.get("error", {}).get("message", f"page_probe_http_{pstatus}")
    return report


def render_facebook_token_report(report: FacebookTokenReport) -> str:
    lines = [
        "🐌 Facebook token check",
        f"App ID: {'present' if report.app_id_present else 'missing'}",
        f"App Secret: {'present' if report.app_secret_present else 'missing'}",
        f"Page ID: {'present' if report.page_id_present else 'missing'}",
        f"Page token: {'present' if report.token_present else 'missing'}",
        f"Token valid: {'yes' if report.valid else 'no'}",
        f"Scopes: {', '.join(report.scopes) if report.scopes else 'none/unknown'}",
        f"Missing required scopes: {', '.join(report.missing_scopes) if report.missing_scopes else 'none'}",
        f"Expires at: {report.expires_at if report.expires_at else 'unknown/never'}",
        f"Data access expires at: {report.data_access_expires_at if report.data_access_expires_at else 'unknown'}",
        f"Page probe: {'ok' if report.page_probe_ok else 'not ok'}",
    ]
    if report.error:
        lines.append(f"Debug error: {report.error}")
    if report.page_probe_error:
        lines.append(f"Page probe error: {report.page_probe_error}")
    return "\n".join(lines)
