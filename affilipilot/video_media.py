from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

MAX_VIDEO_BYTES = 80 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {"mp4", "quicktime"}


@dataclass
class VideoResult:
    ok: bool
    local_path: str = ""
    media_type: str = ""
    reasons: list[str] = field(default_factory=list)


def _safe_name(url: str, fallback: str = "product-video") -> str:
    name = Path(urlparse(url).path).name or fallback
    name = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in name)
    return name[:100] or fallback


def detect_video_type(path: str | Path) -> str:
    data = Path(path).read_bytes()[:64]
    if b"ftyp" in data[:16]:
        major = data[data.find(b"ftyp") + 4:data.find(b"ftyp") + 8].lower()
        if major in {b"qt  "}:
            return "quicktime"
        return "mp4"
    return ""


def validate_video_path(path: str | Path) -> VideoResult:
    path = Path(path)
    reasons: list[str] = []
    if not path.exists():
        return VideoResult(ok=False, reasons=["video_path_not_found"])
    size = path.stat().st_size
    if size <= 0:
        reasons.append("empty_video_file")
    if size > MAX_VIDEO_BYTES:
        reasons.append("video_file_too_large")
    kind = detect_video_type(path)
    if kind not in ALLOWED_VIDEO_TYPES:
        reasons.append(f"unsupported_video_type:{kind or 'unknown'}")
    return VideoResult(ok=not reasons, local_path=str(path), media_type=kind or "", reasons=reasons)


def fetch_video(url: str, out_dir: str | Path, *, name_hint: str = "product-video", timeout: int = 60) -> VideoResult:
    if not url:
        return VideoResult(ok=False, reasons=["missing_video_url"])
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return VideoResult(ok=False, reasons=["unsupported_video_url_scheme"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / _safe_name(url, fallback=name_hint)
    if not target.suffix:
        target = target.with_suffix(".mp4")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AffiliPilot/0.1 video fetch"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "video" not in content_type.lower() and "octet-stream" not in content_type.lower():
                return VideoResult(ok=False, reasons=[f"non_video_content_type:{content_type}"])
            data = resp.read(MAX_VIDEO_BYTES + 1)
    except Exception as exc:  # noqa: BLE001
        return VideoResult(ok=False, reasons=[f"video_fetch_failed:{type(exc).__name__}"])
    if len(data) > MAX_VIDEO_BYTES:
        return VideoResult(ok=False, reasons=["video_file_too_large"])
    target.write_bytes(data)
    return validate_video_path(target)


def prepare_product_video(product: dict, media_dir: str | Path) -> VideoResult:
    if product.get("video_path"):
        return validate_video_path(product["video_path"])
    urls: list[str] = []
    if product.get("video_url"):
        urls.append(product["video_url"])
    for url in product.get("video_urls") or []:
        if url and url not in urls:
            urls.append(url)
    failures: list[str] = []
    for index, video_url in enumerate(urls, 1):
        result = fetch_video(video_url, media_dir, name_hint=(product.get("title") or f"product-video-{index}"))
        if result.ok:
            return result
        failures.extend(result.reasons)
    if urls:
        return VideoResult(ok=False, reasons=failures or ["video_gallery_no_usable_video"])
    return VideoResult(ok=False, reasons=["missing_product_video"])
