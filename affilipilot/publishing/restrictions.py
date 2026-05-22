from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(frozen=True)
class PlatformRestriction:
    platform: str
    publish_type: str
    metrics_profile: str
    caption_max_chars: int
    image_min_count: int = 0
    image_max_count: int = 0
    image_max_mb: int = 10
    video_required: bool = False
    video_max_mb: int = 0
    video_duration_seconds: tuple[int, int] = (0, 0)
    allowed_image_types: tuple[str, ...] = ("jpg", "jpeg", "png", "webp")
    allowed_video_types: tuple[str, ...] = ("mp4", "mov")
    rules: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        return f"{self.platform}.{self.publish_type}"

COMMON_RULES = (
    "Require delivered Telegram approval before production publish.",
    "Caption must follow AffiliPilot minimal caption policy: one AI sentence + fixed CTA + hashtags.",
)

FACEBOOK_PHOTO_POST = PlatformRestriction(
    platform="facebook_page",
    publish_type="photo_post",
    metrics_profile="feed_post",
    caption_max_chars=5000,
    image_min_count=1,
    image_max_count=10,
    image_max_mb=10,
    rules=COMMON_RULES + (
        "Use 1-10 product images and keep affiliate link visible/shortened.",
        "If product video is available but not publish-ready, hold instead of silently publishing image-only.",
    ),
)

FACEBOOK_VIDEO_POST = PlatformRestriction(
    platform="facebook_page",
    publish_type="video_post",
    metrics_profile="feed_video",
    caption_max_chars=5000,
    image_min_count=0,
    image_max_count=4,
    video_required=True,
    video_max_mb=1024,
    video_duration_seconds=(3, 240 * 60),
    rules=COMMON_RULES + (
        "Use when product video is available and publish-ready.",
        "Images may be used as supporting material/thumbnail only.",
    ),
)

FACEBOOK_REEL = PlatformRestriction(
    platform="facebook_page",
    publish_type="reel",
    metrics_profile="reel",
    caption_max_chars=2200,
    image_min_count=0,
    image_max_count=0,
    video_required=True,
    video_max_mb=1024,
    video_duration_seconds=(3, 90),
    rules=COMMON_RULES + (
        "Use short vertical video when available; optimize for plays/watch time rather than feed-click behavior.",
        "Affiliate CTA remains in caption; do not assume link preview behavior equals feed posts.",
    ),
)

FACEBOOK_LINK_POST = PlatformRestriction(
    platform="facebook_page",
    publish_type="link_post",
    metrics_profile="feed_post",
    caption_max_chars=5000,
    image_min_count=0,
    image_max_count=0,
    rules=COMMON_RULES + (
        "Fallback only when no good media exists; prefer photo/video posts for affiliate conversion.",
    ),
)

FACEBOOK_TEXT_POST = PlatformRestriction(
    platform="facebook_page",
    publish_type="text_post",
    metrics_profile="feed_post",
    caption_max_chars=5000,
    image_min_count=0,
    image_max_count=0,
    rules=COMMON_RULES + (
        "Last-resort fallback; generally hold affiliate posts without a valid link/media.",
    ),
)

ALL_RESTRICTIONS = [FACEBOOK_PHOTO_POST, FACEBOOK_VIDEO_POST, FACEBOOK_REEL, FACEBOOK_LINK_POST, FACEBOOK_TEXT_POST]
RESTRICTIONS: dict[str, PlatformRestriction] = {}
for item in ALL_RESTRICTIONS:
    RESTRICTIONS[item.key] = item
    RESTRICTIONS.setdefault(item.platform, item)  # Backward-compatible default = photo_post.
RESTRICTIONS["facebook"] = FACEBOOK_PHOTO_POST

def get_platform_restriction(platform: str, publish_type: str = "") -> PlatformRestriction:
    platform_key = platform.strip().lower()
    key = f"{platform_key}.{publish_type.strip().lower()}" if publish_type else platform_key
    if key not in RESTRICTIONS:
        raise KeyError(f"Unsupported platform restriction: {platform}{'.' + publish_type if publish_type else ''}")
    return RESTRICTIONS[key]

def render_platform_restrictions(platforms: list[str]) -> str:
    lines = ["🐌 AffiliPilot platform restrictions"]
    for platform in platforms:
        selected = [RESTRICTIONS[platform.strip().lower()]] if "." in platform or platform.strip().lower() in {"facebook"} else [item for item in ALL_RESTRICTIONS if item.platform == platform.strip().lower()]
        if not selected:
            selected = [get_platform_restriction(platform)]
        for item in selected:
            lines.extend([
                "",
                f"## {item.key}",
                f"- Publish type: {item.publish_type}",
                f"- Metrics profile: {item.metrics_profile}",
                f"- Caption max: {item.caption_max_chars} chars",
            ])
            if item.image_max_count:
                lines.append(f"- Images: {item.image_min_count}-{item.image_max_count}, ≤{item.image_max_mb}MB each, types={', '.join(item.allowed_image_types)}")
            else:
                lines.append("- Images: not required")
            if item.video_required or item.video_max_mb:
                lines.append(f"- Video: {'required' if item.video_required else 'optional'}, ≤{item.video_max_mb}MB, {item.video_duration_seconds[0]}-{item.video_duration_seconds[1]}s, types={', '.join(item.allowed_video_types)}")
            lines.extend(f"- {rule}" for rule in item.rules)
    return "\n".join(lines)

def restrictions_as_dict(platform: str, publish_type: str = "") -> dict[str, Any]:
    item = get_platform_restriction(platform, publish_type=publish_type)
    data = asdict(item)
    data["video_duration_seconds"] = list(item.video_duration_seconds)
    data["allowed_image_types"] = list(item.allowed_image_types)
    data["allowed_video_types"] = list(item.allowed_video_types)
    data["rules"] = list(item.rules)
    data["key"] = item.key
    return data
