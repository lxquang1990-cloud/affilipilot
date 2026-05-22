from pathlib import Path

from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate
from affilipilot.telegram.approval_context import build_approval_context
from affilipilot.telegram.cards import render_approval_card
from affilipilot.workflows.approval import create_approval_batch


def _jpeg(path: Path, width: int, height: int) -> None:
    path.write_bytes(
        b"\xff\xd8"
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def test_approval_card_v2_shows_scores_commands_and_media_warning(tmp_path):
    image = tmp_path / "pdp.jpg"
    _jpeg(image, 422, 422)
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Khăn giấy rút đa năng 3 lớp mềm dai ít bụi cho bàn ăn",
        category="storage",
        price_vnd=49000,
        image_url="https://down-vn.img.susercontent.com/file/abc",
        image_path=str(image),
        media_source="shopee_pdp",
        media_confidence="high",
    )
    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    post = {
        "product": product.__dict__,
        "media": {"local_path": str(image), "source": "shopee_pdp", "confidence": "high"},
        "files": {"image": str(image)},
    }
    context = build_approval_context(draft, post=post, content_gate={"passed": True, "score": 1.0, "reasons": []})
    card = render_approval_card(draft, batch_key="batch-1", post_id="post_abc", context=context)
    assert "Approval Card v2" in card
    assert "Money score:" in card
    assert "Niche fit: PASS" in card
    assert "Content gate: PASS" in card
    assert "Media: PASS_WITH_WARNING" in card
    assert "media_image_small_but_trusted:422x422" in card
    assert "Why selected:" in card
    assert "/aff_approve batch-1 post_abc" in card


def test_build_batch_writes_card_v2_with_context(tmp_path):
    image = tmp_path / "product.jpg"
    _jpeg(image, 900, 900)
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        f"https://shopee.vn/a | title=Kệ để đồ nhà bếp chịu lực sắp xếp gọn kích thước rõ chịu lực tốt | category=storage | price=199000 | image_path={image} | media_source=user_uploaded_image | media_confidence=high",
        encoding="utf-8",
    )
    db = tmp_path / "db.sqlite"
    manifest = create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    card_path = Path(manifest["posts"][0]["files"]["telegram_card"])
    text = card_path.read_text(encoding="utf-8")
    assert "Approval Card v2" in text
    assert "Niche fit:" in text
    assert "Content gate:" in text
    assert "Media:" in text
    assert "Blockers:" in text
    assert "Why selected:" in text
