from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class VideoProbe:
    ok: bool
    path: str = ""
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    rotation: int = 0
    reasons: list[str] = field(default_factory=list)
    source: str = "ffprobe"

    @property
    def is_vertical(self) -> bool:
        if not self.width or not self.height:
            return False
        rotated = abs(self.rotation) in {90, 270}
        width, height = (self.height, self.width) if rotated else (self.width, self.height)
        return height > width

    @property
    def is_short_form(self) -> bool:
        return 0 < self.duration_seconds <= 90

    @property
    def is_reel_candidate(self) -> bool:
        return self.ok and self.is_vertical and self.is_short_form

def _rotation(stream: dict[str, Any]) -> int:
    tags = stream.get("tags") or {}
    for key in ("rotate", "rotation"):
        if key in tags:
            try:
                return int(float(tags[key]))
            except (TypeError, ValueError):
                pass
    side_data = stream.get("side_data_list") or []
    for item in side_data:
        if "rotation" in item:
            try:
                return int(float(item["rotation"]))
            except (TypeError, ValueError):
                pass
    return 0

def probe_video(path: str | Path, *, timeout: int = 15) -> VideoProbe:
    path = Path(path)
    if not path.exists():
        return VideoProbe(ok=False, path=str(path), reasons=["video_path_not_found"])
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return VideoProbe(ok=False, path=str(path), reasons=["ffprobe_not_found"], source="unavailable")
    cmd = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,tags,side_data_list:format=duration",
        "-of", "json",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return VideoProbe(ok=False, path=str(path), reasons=["ffprobe_timeout"])
    except Exception as exc:  # noqa: BLE001
        return VideoProbe(ok=False, path=str(path), reasons=[f"ffprobe_error:{type(exc).__name__}"])
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:160]
        return VideoProbe(ok=False, path=str(path), reasons=[f"ffprobe_failed:{detail or proc.returncode}"])
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return VideoProbe(ok=False, path=str(path), reasons=["ffprobe_invalid_json"])
    streams = data.get("streams") or []
    if not streams:
        return VideoProbe(ok=False, path=str(path), reasons=["ffprobe_no_video_stream"])
    stream = streams[0]
    try:
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    duration_raw = stream.get("duration") or (data.get("format") or {}).get("duration") or 0
    try:
        duration = float(duration_raw or 0)
    except (TypeError, ValueError):
        duration = 0.0
    reasons = []
    if width <= 0 or height <= 0:
        reasons.append("missing_video_dimensions")
    if duration <= 0:
        reasons.append("missing_video_duration")
    return VideoProbe(ok=not reasons, path=str(path), width=width, height=height, duration_seconds=duration, rotation=_rotation(stream), reasons=reasons)
