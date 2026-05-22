from __future__ import annotations

from affilipilot.models import ContentDraft
from affilipilot.telegram.approval_context import ApprovalContext, build_approval_context


def _fmt_list(items: list[str], *, empty: str = "none", limit: int = 4) -> str:
    if not items:
        return empty
    return "; ".join(str(item) for item in items[:limit])


def render_approval_card(draft: ContentDraft, *, post_id: str = "draft", batch_key: str = "", context: ApprovalContext | None = None) -> str:
    context = context or build_approval_context(draft)
    flags = ", ".join(draft.compliance.risk_flags) if draft.compliance.risk_flags else "none"
    approve = f"/aff_approve {batch_key} {post_id}" if batch_key else f"/aff_approve {post_id}"
    reject = f"/aff_reject {batch_key} {post_id}" if batch_key else f"/aff_reject {post_id}"
    edit = f"/aff_edit {batch_key} {post_id}" if batch_key else f"/aff_edit {post_id}"
    blacklist = f"/aff_blacklist {batch_key} {post_id}" if batch_key else f"/aff_blacklist {post_id}"
    buttons = f"Commands: {approve} | {reject} | {edit} | {blacklist}"
    if draft.compliance.status.value == "block":
        buttons = f"Commands: {reject} | {blacklist} — blocked by compliance gate"
    elif draft.compliance.status.value == "needs_review":
        buttons = f"Commands: {edit} | {reject} | {blacklist} — review required before approve"
    return "\n".join([
        f"🐌 AffiliPilot — {post_id}",
        "Approval Card v2",
        f"Batch: {batch_key or 'unspecified'}",
        f"Sản phẩm: {draft.product.title or draft.product.url}",
        f"Category: {draft.product.category}",
        f"Money score: {context.money_score}/100",
        f"Niche fit: {'PASS' if context.niche_passed else 'BLOCK'} ({context.niche_score}/100)",
        f"Content gate: {'PASS' if context.content_passed else 'UNKNOWN/BLOCK'} ({context.content_score})",
        f"Caption source: {context.caption_source}{(' via ' + context.ai_provider) if context.ai_provider else ''}",
        f"AI/fallback reason: {context.ai_reason or 'none'}",
        f"AI caption quality: {'PASS' if context.caption_quality_passed else 'BLOCK/UNKNOWN'} ({context.caption_quality_score}/100){(' via ' + context.caption_quality_source) if context.caption_quality_source else ''}",
        f"AI caption quality reasons: {', '.join(context.caption_quality_reasons[:3]) if context.caption_quality_reasons else 'none'}",
        f"Media: {context.media_status}",
        f"Media warnings: {_fmt_list(context.media_warnings)}",
        f"Blockers: {_fmt_list(context.blockers)}",
        f"Why selected: {_fmt_list(context.top_reasons)}",
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
