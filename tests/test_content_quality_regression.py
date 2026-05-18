from pathlib import Path

from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate
from affilipilot.quality import evaluate_quality_gate


def test_baby_care_khan_sua_uses_specific_human_copy():
    product = ProductCandidate(
        url="https://go.isclix.com/deep_link/v5/abc",
        affiliate_url="https://go.isclix.com/deep_link/v5/abc",
        title="Set 5 khăn sữa trẻ em TILO vải muslin 100% cotton mềm mịn",
        category="baby_care",
        image_path="/tmp/khan.jpg",
        media_source="product_card_image",
        media_confidence="high",
    )
    draft = generate_safe_facebook_draft(product)
    text = draft.full_text.lower()
    assert "khăn sữa" in text
    assert "muslin" in text or "cotton" in text or "sợi tre" in text
    assert "so sánh cấu hình" not in text
    assert "đừng chỉ nhìn giá" not in text
    assert "#tiepthilienket" not in text
    assert "#khansua" in text
    assert len(draft.hook) < 180


def test_quality_blocks_old_generic_affiliate_template_for_baby_care(tmp_path):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"fake")
    post_text = tmp_path / "post.txt"
    post_text.write_text(
        "Đang cân nhắc Khăn sữa? Đừng chỉ nhìn giá — hãy xem nó giải quyết nhu cầu nào của mình trước.\n\n"
        "Sản phẩm này phù hợp hơn khi nhu cầu, ngân sách và bối cảnh dùng thật sự rõ ràng.\n\n"
        "Xem chi tiết, so sánh cấu hình/màu và kiểm tra giá hiện tại ở link bên dưới nhé.\n\n"
        "Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.\n"
        "#tiepthilienket #muasamthongminh",
        encoding="utf-8",
    )
    post = {
        "product": {
            "title": "Khăn sữa",
            "category": "baby_care",
            "url": "https://go.isclix.com/deep_link/v5/abc",
            "affiliate_url": "https://go.isclix.com/deep_link/v5/abc",
        },
        "media": {"ok": True, "local_path": str(image), "source": "product_card_image", "confidence": "high"},
        "files": {"post_text": str(post_text)},
    }
    result = evaluate_quality_gate(post)
    assert not result.passed
    assert "spammy_generic_affiliate_template" in result.reasons
    assert "internal_hashtag_primary" in result.reasons
    assert "wrong_category_tech_language" in result.reasons
