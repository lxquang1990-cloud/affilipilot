from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(frozen=True)
class PlatformRestriction:
    platform: str
    caption_max_chars: int
    image_max_count: int
    image_max_mb: int
    video_max_mb: int
    video_duration_seconds: tuple[int, int]
    allowed_image_types: tuple[str, ...] = ("jpg", "jpeg", "png", "webp")
    allowed_video_types: tuple[str, ...] = ("mp4", "mov")
    rules: tuple[str, ...] = field(default_factory=tuple)

FACEBOOK_PAGE = PlatformRestriction(
    platform="facebook_page",
    caption_max_chars=5000,
    image_max_count=10,
    image_max_mb=10,
    video_max_mb=1024,
    video_duration_seconds=(3, 240 * 60),
    rules=(
        "Require delivered Telegram approval before production publish.",
        "Use 1-10 images or one video; keep affiliate link visible and shortened.",
        "Caption must follow AffiliPilot minimal caption policy: one AI sentence + fixed CTA + hashtags.",
        "Do not publish image-only when product video is available but not publish-ready; hold instead.",
    ),
)

RESTRICTIONS: dict[str, PlatformRestriction] = {FACEBOOK_PAGE.platform: FACEBOOK_PAGE, "facebook": FACEBOOK_PAGE}

def get_platform_restriction(platform: str) -> PlatformRestriction:
    key = platform.strip().lower()
    if key not in RESTRICTIONS:
        raise KeyError(f"Unsupported platform: {platform}")
    return RESTRICTIONS[key]

def render_platform_restrictions(platforms: list[str]) -> str:
    lines = ["🐌 AffiliPilot platform restrictions"]
    for platform in platforms:
        item = get_platform_restriction(platform)
        lines.extend([
            "",
            f"## {item.platform}",
            f"- Caption max: {item.caption_max_chars} chars",
            f"- Images: 1-{item.image_max_count}, ≤{item.image_max_mb}MB each, types={', '.join(item.allowed_image_types)}",
            f"- Video: ≤{item.video_max_mb}MB, {item.video_duration_seconds[0]}-{item.video_duration_seconds[1]}s, types={', '.join(item.allowed_video_types)}",
        ])
        lines.extend(f"- {rule}" for rule in item.rules)
    return "\n".join(lines)

def restrictions_as_dict(platform: str) -> dict[str, Any]:
    item = get_platform_restriction(platform)
    data = asdict(item)
    data["video_duration_seconds"] = list(item.video_duration_seconds)
    data["allowed_image_types"] = list(item.allowed_image_types)
    data["allowed_video_types"] = list(item.allowed_video_types)
    data["rules"] = list(item.rules)
    return data
