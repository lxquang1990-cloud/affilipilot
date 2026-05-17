from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.publishing.requirements import check_affiliate_link, check_media


@dataclass
class PublishGateResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    fallback_required: bool = False


def evaluate_publish_gate(post: dict[str, Any], *, approved: bool, facebook_verified: bool, dry_run_passed: bool, kill_switch: bool = False) -> PublishGateResult:
    reasons: list[str] = []
    compliance = post.get("compliance", {})
    files = post.get("files", {})

    if not approved:
        reasons.append("not_approved_by_snail")
    if compliance.get("status") != "pass":
        reasons.append(f"compliance_not_pass:{compliance.get('status')}")
    if "post_text" not in files or not Path(files["post_text"]).exists():
        reasons.append("missing_post_text")
    else:
        text = Path(files["post_text"]).read_text(encoding="utf-8", errors="ignore").lower()
        if "tiếp thị liên kết" not in text and "affiliate" not in text and "hoa hồng" not in text:
            reasons.append("missing_affiliate_disclosure")
    affiliate_check = check_affiliate_link(post)
    if not affiliate_check.passed:
        reasons.extend(affiliate_check.reasons)
    media_check = check_media(post)
    if not media_check.passed:
        reasons.extend(media_check.reasons)
    if not facebook_verified:
        reasons.append("facebook_not_verified")
    if not dry_run_passed:
        reasons.append("publish_dry_run_not_passed")
    if kill_switch:
        reasons.append("kill_switch_on")

    allowed = not reasons
    return PublishGateResult(allowed=allowed, reasons=reasons, fallback_required=not allowed)
