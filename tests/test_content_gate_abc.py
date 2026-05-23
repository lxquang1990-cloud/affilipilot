from affilipilot.content.content_gate import evaluate_content_gates
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate
from affilipilot.quality import evaluate_quality_gate


def test_content_gate_abc_passes_generated_feeding_caption():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Bình thìa ăn dặm silicone cho bé dễ vệ sinh",
        category="feeding",
        price_vnd=79000,
        image_url="https://cdn.example/test.jpg",
    )
    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    result = evaluate_content_gates(product.__dict__, draft.full_text)
    assert result.passed, result.reasons
    assert result.layer("A").passed
    assert result.layer("B").passed
    assert result.layer("C").passed


def test_content_gate_blocks_generic_template_before_approval():
    product = {"title": "Bình thìa ăn dặm silicone cho bé", "category": "feeding"}
    text = (
        "Đang cân nhắc sản phẩm này? Đừng chỉ nhìn giá — hãy xem nó giải quyết nhu cầu nào của mình trước.\n\n"
        "Sản phẩm này phù hợp hơn khi nhu cầu, ngân sách và bối cảnh dùng thật sự rõ ràng.\n\n"
        "Xem chi tiết ở link bên dưới nhé.\n\n"
        "Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ."
    )
    result = evaluate_content_gates(product, text)
    assert not result.passed
    assert "gate_A:no.generic_template" in result.reasons
    assert "gate_B:category_specific.feeding" in result.reasons
    assert not result.layer("C").passed


def test_quality_gate_surfaces_content_gate_reasons(tmp_path):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"fake")
    post_text = tmp_path / "post.txt"
    post_text.write_text(
        "Đang cân nhắc sản phẩm này? Đừng chỉ nhìn giá — hãy xem nó giải quyết nhu cầu nào của mình trước.\n\n"
        "Sản phẩm này phù hợp hơn khi nhu cầu, ngân sách và bối cảnh dùng thật sự rõ ràng.\n\n"
        "Xem chi tiết ở link bên dưới nhé.\n\n"
        "Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.",
        encoding="utf-8",
    )
    post = {
        "product": {
            "title": "Bình thìa ăn dặm silicone cho bé",
            "category": "feeding",
            "url": "https://shopee.vn/p",
            "affiliate_url": "https://short.example/p",
            "image_path": str(image),
        },
        "media": {"ok": True, "local_path": str(image), "source": "product_card_image", "confidence": "high"},
        "files": {"post_text": str(post_text)},
    }
    result = evaluate_quality_gate(post)
    assert not result.passed
    assert "gate_A:no.generic_template" in result.reasons
    assert "gate_B:category_specific.feeding" in result.reasons
