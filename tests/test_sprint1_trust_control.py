from datetime import datetime
from pathlib import Path

from affilipilot.links.subid import make_post_id
from affilipilot.media_quality import evaluate_media_quality
from affilipilot.telegram.commands import TelegramIntent, parse_telegram_text
from affilipilot.telegram.cards import render_approval_card
from affilipilot.models import ComplianceResult, ComplianceStatus, ContentDraft, ProductCandidate


def _jpeg(path: Path, width: int, height: int) -> None:
    path.write_bytes(
        b"\xff\xd8"
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def test_make_post_id_includes_time_and_slug_for_datetime():
    post_id = make_post_id(datetime(2026, 5, 21, 10, 0), 1, slug="Sạc LCD Samsung 14V")
    assert post_id.startswith("post_20260521_1000_")
    assert post_id.endswith("_001")
    assert "sạc-lcd-samsung-14v" in post_id


def test_parse_batch_aware_approval_command():
    parsed = parse_telegram_text("/aff_approve batch-123 post_abc looks good")
    assert parsed.intent == TelegramIntent.APPROVE
    assert parsed.args["batch_key"] == "batch-123"
    assert parsed.args["post_id"] == "post_abc"
    assert parsed.args["reason"] == "looks good"


def test_render_approval_card_uses_batch_safe_commands():
    draft = ContentDraft(
        product=ProductCandidate(url="https://example.com/p", title="Khăn giấy rút", category="household_tissue"),
        hook="Hook",
        body="Body",
        cta="CTA",
        disclosure="Có thể nhận hoa hồng tiếp thị liên kết.",
        compliance=ComplianceResult(ComplianceStatus.PASS),
    )
    text = render_approval_card(draft, batch_key="batch-123", post_id="post_abc")
    assert "Batch: batch-123" in text
    assert "/aff_approve batch-123 post_abc" in text


def test_trusted_422_pdp_image_passes_with_warning(tmp_path):
    img = tmp_path / "pdp.jpg"
    _jpeg(img, 422, 422)
    post = {
        "files": {"image": str(img)},
        "media": {"local_path": str(img), "source": "shopee_pdp", "confidence": "high"},
        "product": {"image_url": "https://down-vn.img.susercontent.com/file/abc", "media_source": "shopee_pdp", "media_confidence": "high"},
    }
    result = evaluate_media_quality(post)
    assert result.passed
    assert result.warnings == ["media_image_small_but_trusted:422x422"]
