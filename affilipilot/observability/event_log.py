from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVENT_LOG = Path("data/logs/affilipilot-events.jsonl")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


class EventLog:
    def __init__(self, path: str | Path = DEFAULT_EVENT_LOG):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event_type: str, **fields: Any) -> dict[str, Any]:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **{key: _jsonable(value) for key, value in fields.items()},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record


def read_events(path: str | Path = DEFAULT_EVENT_LOG, *, limit: int = 50) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def render_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "AffiliPilot event log: no events"
    lines = [f"AffiliPilot event log: {len(events)} events"]
    for event in events:
        ts = event.get("ts", "")
        name = event.get("event", "")
        detail = {k: v for k, v in event.items() if k not in {"ts", "event"}}
        lines.append(f"- {ts} {name} {json.dumps(detail, ensure_ascii=False)}")
    return "\n".join(lines)
