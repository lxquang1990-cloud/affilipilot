from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_IMAGE_TYPES = {"jpeg", "png", "webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def detect_image_type(path: str | Path) -> str:
    data = Path(path).read_bytes()[:16]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return ""


@dataclass
class MediaResult:
    ok: bool
    local_path: str = ""
    media_type: str = ""
    reasons: list[str] = field(default_factory=list)


def _safe_name(url: str, fallback: str = "product") -> str:
    path = urlparse(url).path
    name = Path(path).name or fallback
    name = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in name)
    return name[:80] or fallback


def validate_image_path(path: str | Path) -> MediaResult:
    path = Path(path)
    reasons: list[str] = []
    if not path.exists():
        return MediaResult(ok=False, reasons=["media_path_not_found"])
    size = path.stat().st_size
    if size <= 0:
        reasons.append("empty_media_file")
    if size > MAX_IMAGE_BYTES:
        reasons.append("media_file_too_large")
    kind = detect_image_type(path)
    if kind not in ALLOWED_IMAGE_TYPES:
        reasons.append(f"unsupported_image_type:{kind or 'unknown'}")
    return MediaResult(ok=not reasons, local_path=str(path), media_type=kind or "", reasons=reasons)


def fetch_image(url: str, out_dir: str | Path, *, name_hint: str = "product", timeout: int = 30) -> MediaResult:
    if not url:
        return MediaResult(ok=False, reasons=["missing_image_url"])
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return MediaResult(ok=False, reasons=["unsupported_image_url_scheme"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / _safe_name(url, fallback=name_hint)
    if not target.suffix:
        target = target.with_suffix(".img")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AffiliPilot/0.1 media fetch"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type.lower():
                return MediaResult(ok=False, reasons=[f"non_image_content_type:{content_type}"])
            data = resp.read(MAX_IMAGE_BYTES + 1)
    except Exception as exc:  # noqa: BLE001 - convert to safe reason string
        return MediaResult(ok=False, reasons=[f"fetch_failed:{type(exc).__name__}"])
    if len(data) > MAX_IMAGE_BYTES:
        return MediaResult(ok=False, reasons=["media_file_too_large"])
    target.write_bytes(data)
    return validate_image_path(target)


def prepare_product_media(product: dict, media_dir: str | Path) -> MediaResult:
    if product.get("image_path"):
        return validate_image_path(product["image_path"])
    if product.get("image_url"):
        return fetch_image(product["image_url"], media_dir, name_hint=product.get("title") or "product")
    return MediaResult(ok=False, reasons=["missing_product_media"])


def copy_local_image(src: str | Path, out_dir: str | Path, *, name_hint: str = "product") -> MediaResult:
    src = Path(src)
    check = validate_image_path(src)
    if not check.ok:
        return check
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / (src.name or f"{name_hint}.jpg")
    shutil.copy2(src, dst)
    return validate_image_path(dst)
