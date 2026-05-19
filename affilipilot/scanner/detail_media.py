from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from affilipilot.media_quality import upgrade_lazada_image_url


@dataclass
class DetailMediaResult:
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    title: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def qualified(self) -> bool:
        return len(self.image_urls) >= 2 or bool(self.video_urls)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _candidate_image_urls(text: str, base_url: str) -> list[str]:
    urls: list[str] = []
    normalized = text.replace('\\/', '/')
    patterns = [
        r'https?://img\.lazcdn\.com/[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:_[0-9]+x[0-9]+q[0-9]+\.jpg)?',
        r'//img\.lazcdn\.com/[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:_[0-9]+x[0-9]+q[0-9]+\.jpg)?',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, normalized, flags=re.I):
            url = match
            if url.startswith('//'):
                url = 'https:' + url
            url = urljoin(base_url, url)
            urls.append(upgrade_lazada_image_url(url))
    return _dedupe(urls)


def _candidate_video_urls(text: str, base_url: str) -> list[str]:
    urls: list[str] = []
    normalized = text.replace('\\/', '/')
    for match in re.findall(r'https?://[^"\'<>\s]+?\.(?:mp4|m3u8)', normalized, flags=re.I):
        urls.append(urljoin(base_url, match))
    return _dedupe(urls)


def _title_from_html(html_text: str) -> str:
    for prop in ("og:title", "twitter:title"):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']', html_text, flags=re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""


def extract_detail_media_from_html(html_text: str, *, base_url: str) -> DetailMediaResult:
    images = _candidate_image_urls(html_text, base_url)
    videos = _candidate_video_urls(html_text, base_url)
    reasons: list[str] = []
    if len(images) < 2:
        reasons.append(f"detail_media_images_lt_2:{len(images)}")
    if not videos:
        reasons.append("detail_media_no_video")
    return DetailMediaResult(image_urls=images, video_urls=videos, title=_title_from_html(html_text), reasons=reasons)
