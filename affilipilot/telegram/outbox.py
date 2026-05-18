from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

MessageKind = Literal["summary", "approval_card", "digest", "alert"]


@dataclass
class OutboxMessage:
    id: str
    kind: MessageKind
    text: str
    attachments: list[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delivered_at: str = ""
    receipt: str = ""


class Outbox:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[OutboxMessage]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [OutboxMessage(**item) for item in data]

    def save(self, messages: list[OutboxMessage]) -> None:
        self.path.write_text(json.dumps([asdict(m) for m in messages], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def add(self, message: OutboxMessage) -> None:
        messages = self.load()
        messages.append(message)
        self.save(messages)

    def pending(self) -> list[OutboxMessage]:
        return [m for m in self.load() if m.status == "pending"]

    def mark(self, message_id: str, status: str, *, receipt: str = "") -> None:
        if status not in {"pending", "sent", "delivered", "failed", "skipped"}:
            raise ValueError(f"Unsupported outbox status: {status}")
        if status == "delivered" and not receipt:
            raise ValueError("delivered status requires receipt")
        messages = self.load()
        found = False
        for m in messages:
            if m.id == message_id:
                m.status = status
                if status == "delivered":
                    m.receipt = receipt
                    m.delivered_at = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if not found:
            raise KeyError(message_id)
        self.save(messages)
