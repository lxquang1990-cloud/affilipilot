from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

@dataclass
class OfferValidationResult:
    passed: bool
    score: int
    url: str
    status: int | None = None
    final_url: str = ""
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

def _looks_bad_url(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in ("example", "test-safe", "localhost", "/test"))

def validate_offer(url: str, *, expected_title: str = "", expected_image: str = "", network: bool = False, timeout: int = 15) -> OfferValidationResult:
    reasons: list[str] = []
    checks: dict[str, Any] = {"network": network}
    parsed = urlparse(url or "")
    if not url:
        reasons.append("missing_offer_url")
    elif parsed.scheme not in {"http", "https"}:
        reasons.append("unsupported_offer_url_scheme")
    elif _looks_bad_url(url):
        reasons.append("demo_or_test_offer_url")

    status: int | None = None
    final_url = ""
    if network and not reasons:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "AffiliPilot/0.1 offer validator"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                final_url = resp.geturl()
                content_type = resp.headers.get("Content-Type", "")
                checks["content_type"] = content_type
                sample = resp.read(120_000).decode("utf-8", errors="ignore").lower()
                if status >= 400:
                    reasons.append(f"offer_http_status:{status}")
                if expected_title:
                    title_terms = [term for term in expected_title.lower().replace("|", " ").split() if len(term) >= 4][:4]
                    if title_terms and not any(term in sample for term in title_terms):
                        reasons.append("landing_title_mismatch")
                if expected_image and expected_image not in sample:
                    checks["image_exact_match"] = False
        except urllib.error.HTTPError as exc:
            status = exc.code
            reasons.append(f"offer_http_status:{exc.code}")
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"offer_check_failed:{type(exc).__name__}")

    score = 100 - 25 * len(reasons)
    score = max(0, score)
    return OfferValidationResult(passed=not reasons and score >= 75, score=score, url=url, status=status, final_url=final_url, reasons=reasons, checks=checks)

def render_offer_validation(result: OfferValidationResult) -> str:
    lines = ["🐌 AffiliPilot offer validation", f"URL: {result.url or '(missing)'}", f"Score: {result.score}/100", f"Status: {'PASS' if result.passed else 'BLOCK'}"]
    if result.status is not None:
        lines.append(f"HTTP: {result.status}")
    if result.final_url:
        lines.append(f"Final URL: {result.final_url}")
    if result.reasons:
        lines.append("Reasons:")
        lines.extend(f"- {reason}" for reason in result.reasons)
    return "\n".join(lines)
