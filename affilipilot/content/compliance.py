from __future__ import annotations

from affilipilot.models import ComplianceResult, ComplianceStatus

FORBIDDEN_TERMS = {
    "chữa khỏi": "medical_treatment_claim",
    "trị khỏi": "medical_treatment_claim",
    "điều trị": "medical_treatment_claim",
    "hết ho": "medical_claim",
    "hết sốt": "medical_claim",
    "hết hăm": "medical_claim",
    "tăng chiều cao": "child_growth_claim",
    "phát triển trí não": "child_development_claim",
    "tăng đề kháng": "health_claim",
    "an toàn tuyệt đối": "absolute_safety_claim",
    "tốt nhất": "superlative_claim",
    "số 1": "superlative_claim",
    "mình đã dùng": "unverified_personal_experience",
}

HIGH_RISK_CATEGORIES = {
    "milk",
    "formula",
    "medicine",
    "supplement",
    "vitamin",
    "medical",
    "weight_loss",
    "cosmetic_strong_claim",
}

REQUIRED_DISCLOSURE_HINTS = ["tiếp thị liên kết", "affiliate", "hoa hồng"]


def check_mom_baby_compliance(text: str, *, category: str = "unknown") -> ComplianceResult:
    normalized = text.lower()
    flags: list[str] = []
    edits: list[str] = []

    if category.lower() in HIGH_RISK_CATEGORIES:
        flags.append(f"high_risk_category:{category.lower()}")
        edits.append("Replace product or require manual legal/compliance review.")

    for term, flag in FORBIDDEN_TERMS.items():
        if term in normalized:
            flags.append(flag)
            edits.append(f"Remove or rewrite forbidden claim: '{term}'.")

    if not any(hint in normalized for hint in REQUIRED_DISCLOSURE_HINTS):
        flags.append("missing_affiliate_disclosure")
        edits.append("Add clear affiliate disclosure before publishing.")

    if any(flag.startswith("high_risk_category") for flag in flags):
        return ComplianceResult(ComplianceStatus.BLOCK, flags, edits)
    if any(flag in {"medical_treatment_claim", "medical_claim", "child_growth_claim", "child_development_claim", "health_claim", "absolute_safety_claim", "unverified_personal_experience"} for flag in flags):
        return ComplianceResult(ComplianceStatus.BLOCK, flags, edits)
    if flags:
        return ComplianceResult(ComplianceStatus.NEEDS_REVIEW, flags, edits)
    return ComplianceResult(ComplianceStatus.PASS, [], [])


def default_affiliate_disclosure() -> str:
    return "Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link."
