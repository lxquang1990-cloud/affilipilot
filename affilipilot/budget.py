from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class BudgetEvent:
    phase: str
    amount_vnd: int
    note: str = ""


@dataclass
class BudgetStatus:
    date: str
    cap_vnd: int
    soft_cap_vnd: int
    spent_vnd: int
    events: list[BudgetEvent] = field(default_factory=list)

    @property
    def remaining_vnd(self) -> int:
        return max(0, self.cap_vnd - self.spent_vnd)

    @property
    def soft_exceeded(self) -> bool:
        return self.spent_vnd >= self.soft_cap_vnd

    @property
    def hard_exceeded(self) -> bool:
        return self.spent_vnd >= self.cap_vnd

    @property
    def mode(self) -> str:
        if self.hard_exceeded:
            return "hard_stop"
        if self.soft_exceeded:
            return "cheap_model_only"
        return "normal"


def load_budget(path: str | Path, *, cap_vnd: int = 30_000, day: date | None = None) -> BudgetStatus:
    path = Path(path)
    day_str = (day or date.today()).isoformat()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        events = [BudgetEvent(**e) for e in data.get("events", [])]
        return BudgetStatus(date=data.get("date", day_str), cap_vnd=int(data.get("cap_vnd", cap_vnd)), soft_cap_vnd=int(data.get("soft_cap_vnd", cap_vnd * 0.8)), spent_vnd=int(data.get("spent_vnd", 0)), events=events)
    return BudgetStatus(date=day_str, cap_vnd=cap_vnd, soft_cap_vnd=int(cap_vnd * 0.8), spent_vnd=0, events=[])


def save_budget(path: str | Path, status: BudgetStatus) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "date": status.date,
        "cap_vnd": status.cap_vnd,
        "soft_cap_vnd": status.soft_cap_vnd,
        "spent_vnd": status.spent_vnd,
        "remaining_vnd": status.remaining_vnd,
        "mode": status.mode,
        "events": [e.__dict__ for e in status.events],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_spend(path: str | Path, *, phase: str, amount_vnd: int, note: str = "", cap_vnd: int = 30_000) -> BudgetStatus:
    status = load_budget(path, cap_vnd=cap_vnd)
    event = BudgetEvent(phase=phase, amount_vnd=amount_vnd, note=note)
    status.events.append(event)
    status.spent_vnd += amount_vnd
    save_budget(path, status)
    return status
