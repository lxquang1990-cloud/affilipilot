"""Optional SnailBot upgrade prototype integration for AffiliPilot.

This module is passive: importing it does not change existing AffiliPilot
workflow behavior. It provides adapters to write structured state/events using
`snailbot-upgrades` when the workspace module is available.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sys

_UPGRADES_PATH = Path(__file__).resolve().parents[2].parent / "snailbot-upgrades"
if _UPGRADES_PATH.exists() and str(_UPGRADES_PATH) not in sys.path:
    sys.path.insert(0, str(_UPGRADES_PATH))

try:  # pragma: no cover - fallback is exercised by interface safety
    from snailbot_upgrades.events import Event
    from snailbot_upgrades.tracing import TraceSpan
except Exception:  # pragma: no cover
    Event = None  # type: ignore
    TraceSpan = None  # type: ignore


@dataclass
class AffiliPilotRunState:
    """Small serializable state snapshot for an AffiliPilot batch/run."""

    batch_key: str
    stage: str
    status: str = "running"
    selected_posts: list[str] = field(default_factory=list)
    approvals: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: dict[str, Any] = field(default_factory=dict)

    def state_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        return data

    @classmethod
    def load_state_dict(cls, data: dict[str, Any]) -> "AffiliPilotRunState":
        return cls(**data)


def write_run_state(path: str | Path, state: AffiliPilotRunState) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.state_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def append_event(path: str | Path, *, run_id: str, kind: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append structured JSONL event. Uses upgrade Event if available."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if Event is not None:
        payload = Event(kind=kind, run_id=run_id, message=message, data=data or {}).to_dict()  # type: ignore[arg-type]
    else:
        payload = {
            "kind": kind,
            "run_id": run_id,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload
