from __future__ import annotations

from affilipilot.models import ContentDraft
from affilipilot.scoring.product_score import score_product


def render_approval_card(draft: ContentDraft, *, post_id: str = "draft") -> str:
    score = score_product(draft.product)["score"]
    flags = ", ".join(draft.compliance.risk_flags) if draft.compliance.risk_flags else "none"
    buttons = "Buttons: ✅ Approve / ❌ Reject / ✏️ Edit / 🚫 Blacklist"
    if draft.compliance.status.value == "block":
        buttons = "Buttons: ❌ Reject / 🚫 Blacklist only — blocked by compliance gate"
    elif draft.compliance.status.value == "needs_review":
        buttons = "Buttons: ✏️ Edit / ❌ Reject / 🚫 Blacklist — review required before approve"
    return "\n".join([
        f"🐌 AffiliPilot — {post_id}",
        f"Sản phẩm: {draft.product.title or draft.product.url}",
        f"Category: {draft.product.category}",
        f"Money score: {score}/100",
        f"Compliance: {draft.compliance.status.value}",
        f"Risk flags: {flags}",
        "",
        "Hook:",
        draft.hook,
        "",
        "Caption:",
        draft.full_text,
        "",
        buttons,
    ])
