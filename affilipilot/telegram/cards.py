from __future__ import annotations

from affilipilot.models import ContentDraft
from affilipilot.scoring.product_score import score_product


def render_approval_card(draft: ContentDraft, *, post_id: str = "draft") -> str:
    score = score_product(draft.product)["score"]
    flags = ", ".join(draft.compliance.risk_flags) if draft.compliance.risk_flags else "none"
    buttons = "Commands: /aff_approve {0} | /aff_reject {0} | /aff_edit {0} | /aff_blacklist {0}".format(post_id)
    if draft.compliance.status.value == "block":
        buttons = "Commands: /aff_reject {0} | /aff_blacklist {0} — blocked by compliance gate".format(post_id)
    elif draft.compliance.status.value == "needs_review":
        buttons = "Commands: /aff_edit {0} | /aff_reject {0} | /aff_blacklist {0} — review required before approve".format(post_id)
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
