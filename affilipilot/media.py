from __future__ import annotations

import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from affilipilot.media_quality import evaluate_media_quality, upgrade_lazada_image_url

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
    parsed = urlparse(url)
    path = parsed.path
    name = Path(path).name or fallback
    name = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in name)
    # Tiki/Lazada CDN thumbnails often share the same basename across sizes.
    # Include a short query-derived suffix so gallery downloads do not overwrite
    # each other before validation/planning.
    if parsed.query:
        import hashlib
        stem = Path(name).stem or fallback
        suffix = Path(name).suffix
        digest = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
        name = f"{stem}-{digest}{suffix}"
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


def _normalize_remote_image_url(url: str) -> str:
    if not url:
        return ""
    url = upgrade_lazada_image_url(url)
    parsed = urlparse(url)
    if parsed.netloc.endswith("shopee.vn") and "/file/" in parsed.path and not parsed.scheme:
        return f"https:{url}"
    return url


def fetch_image(url: str, out_dir: str | Path, *, name_hint: str = "product", timeout: int = 30) -> MediaResult:
    if not url:
        return MediaResult(ok=False, reasons=["missing_image_url"])
    url = _normalize_remote_image_url(url)
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


def _rank_gallery_urls(image_urls: list[str]) -> list[str]:
    """Prefer a diverse production gallery over the first N scraped images."""
    def score(item: tuple[int, str]) -> tuple[int, int]:
        index, url = item
        lower = url.lower()
        value = 0
        if any(term in lower for term in ("main", "cover", "product", "sku", "1")):
            value += 30
        if any(term in lower for term in ("detail", "usage", "use", "scene", "size", "dimension", "benefit")):
            value += 20
        if any(term in lower for term in ("logo", "sprite", "icon", "avatar", "shop")):
            value -= 100
        return (value, -index)
    return [url for _, url in sorted(enumerate(image_urls), key=score, reverse=True)]


def prepare_product_media_gallery(product: dict, media_dir: str | Path, *, limit: int = 4) -> list[MediaResult]:
    image_urls: list[str] = []
    if product.get("image_url"):
        image_urls.append(product["image_url"])
    for url in product.get("image_urls") or []:
        if url and url not in image_urls:
            image_urls.append(url)
    image_urls = _rank_gallery_urls(image_urls)
    results: list[MediaResult] = []
    failures: list[MediaResult] = []
    for index, image_url in enumerate(image_urls, 1):
        if len(results) >= limit:
            break
        result = fetch_image(image_url, media_dir, name_hint=(product.get("title") or f"product-{index}"))
        if not result.ok:
            failures.append(result)
            continue
        quality = evaluate_media_quality({"files": {"image": result.local_path}, "product": {"image_url": image_url}})
        if quality.passed:
            results.append(result)
        else:
            failures.append(MediaResult(ok=False, local_path=result.local_path, media_type=result.media_type, reasons=quality.reasons))
    if len(image_urls) >= 4 and len(results) < min(4, limit):
        # Keep the gate strict: a rich product gallery should produce 3-4 usable assets,
        # not silently publish with only the first two acceptable files.
        return results
    return results


def prepare_product_media(product: dict, media_dir: str | Path) -> MediaResult:
    if product.get("image_path"):
        return validate_image_path(product["image_path"])
    image_urls: list[str] = []
    if product.get("image_url"):
        image_urls.append(product["image_url"])
    for url in product.get("image_urls") or []:
        if url and url not in image_urls:
            image_urls.append(url)
    failures: list[str] = []
    for index, image_url in enumerate(image_urls, 1):
        result = fetch_image(image_url, media_dir, name_hint=(product.get("title") or f"product-{index}"))
        if not result.ok:
            failures.extend(result.reasons)
            continue
        quality = evaluate_media_quality({"files": {"image": result.local_path}, "product": {"image_url": image_url}})
        if quality.passed:
            return result
        failures.extend(quality.reasons)
    if image_urls:
        return MediaResult(ok=False, reasons=failures or ["media_gallery_no_usable_image"])
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
