from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from affilipilot.observability.event_log import DEFAULT_EVENT_LOG, EventLog, read_events

DEFAULT_STATE_PATH = Path("data/auto_publish_state.json")
DEFAULT_KILL_PATH = Path("/tmp/affilipilot.KILL")


@dataclass
class CircuitStatus:
    allowed: bool
    reason: str = "ok"
    kill_switch: bool = False
    consecutive_publish_errors: int = 0
    publish_error_threshold: int = 3
    state_enabled: bool = True
    state_expired: bool = False


def _load_state(path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"enabled": True}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"enabled": False, "error": "invalid_state_json"}


def _is_expired(state: dict[str, Any]) -> bool:
    raw = state.get("expires_at")
    if not raw:
        return False
    try:
        expires = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) > expires


def _consecutive_publish_errors(events: list[dict[str, Any]]) -> int:
    count = 0
    for event in reversed(events):
        name = str(event.get("event", ""))
        if name in {"publish_succeeded", "auto_publish_succeeded"}:
            break
        if name in {"publish_failed", "auto_publish_failed", "auto_publish_exception"}:
            count += 1
    return count


def check_circuit(
    *,
    state_path: str | Path = DEFAULT_STATE_PATH,
    kill_path: str | Path = DEFAULT_KILL_PATH,
    event_log_path: str | Path = DEFAULT_EVENT_LOG,
    publish_error_threshold: int = 3,
) -> CircuitStatus:
    state = _load_state(state_path)
    kill = Path(kill_path).exists()
    expired = _is_expired(state)
    enabled = bool(state.get("enabled", True))
    events = read_events(event_log_path, limit=100)
    errors = _consecutive_publish_errors(events)
    if kill:
        return CircuitStatus(False, "manual_kill_switch", True, errors, publish_error_threshold, enabled, expired)
    if not enabled:
        return CircuitStatus(False, "state_disabled", False, errors, publish_error_threshold, enabled, expired)
    if expired:
        return CircuitStatus(False, "state_expired", False, errors, publish_error_threshold, enabled, expired)
    if errors >= publish_error_threshold:
        return CircuitStatus(False, "consecutive_publish_errors", False, errors, publish_error_threshold, enabled, expired)
    return CircuitStatus(True, "ok", False, errors, publish_error_threshold, enabled, expired)


def set_kill_switch(enabled: bool, *, kill_path: str | Path = DEFAULT_KILL_PATH, event_log_path: str | Path = DEFAULT_EVENT_LOG, reason: str = "operator") -> CircuitStatus:
    p = Path(kill_path)
    if enabled:
        p.write_text(reason + "\n", encoding="utf-8")
    elif p.exists():
        p.unlink()
    status = check_circuit(kill_path=p, event_log_path=event_log_path)
    EventLog(event_log_path).event("kill_switch_changed", enabled=enabled, reason=reason, circuit_allowed=status.allowed, circuit_reason=status.reason)
    return status


def render_circuit_status(status: CircuitStatus) -> str:
    icon = "PASS" if status.allowed else "BLOCK"
    return "\n".join([
        f"AffiliPilot circuit: {icon}",
        f"Reason: {status.reason}",
        f"Kill switch: {status.kill_switch}",
        f"State enabled: {status.state_enabled}",
        f"State expired: {status.state_expired}",
        f"Consecutive publish errors: {status.consecutive_publish_errors}/{status.publish_error_threshold}",
    ])
