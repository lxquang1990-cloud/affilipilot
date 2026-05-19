from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Tier(str, Enum):
    AUTO = "auto"
    SOFT_GATE = "soft_gate"
    MANUAL = "manual"
    BLOCKED = "blocked"


@dataclass
class TierConfig:
    auto_threshold: float = 0.85
    soft_threshold: float = 0.70
    manual_threshold: float = 0.50
    soft_gate_cooldown_minutes: int = 60
    max_auto_per_day: int = 20
    max_auto_per_hour: int = 5


def load_tier_config(path: str | Path | None = None) -> TierConfig:
    if not path or not Path(path).exists():
        return TierConfig()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TierConfig(**{k: v for k, v in data.items() if k in TierConfig.__dataclass_fields__})


def classify_tier(score: float, signals: dict, config: TierConfig | None = None) -> Tier:
    if os.environ.get("AFFILIPILOT_FORCE_MANUAL") == "1":
        return Tier.MANUAL
    cfg = config or TierConfig()
    if float(signals.get("compliance_signal", 0.0)) < 0.5:
        return Tier.BLOCKED
    if score >= cfg.auto_threshold:
        return Tier.AUTO
    if score >= cfg.soft_threshold:
        return Tier.SOFT_GATE
    if score >= cfg.manual_threshold:
        return Tier.MANUAL
    return Tier.BLOCKED


def render_tier_result(score: float, tier: Tier, signals: dict) -> str:
    return f"tier={tier.value} score={score:.3f} compliance={signals.get('compliance_signal')} media={signals.get('media_signal')}"
