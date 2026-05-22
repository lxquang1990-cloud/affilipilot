from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate


def test_generator_uses_ai_caption_first_when_gate_passes(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    def fake_ai(product, **kwargs):
        class Result:
            ok = True
            hook = "AI hook riêng cho kệ bếp gọn nhà."
            body = (
                "Phù hợp với nhà cần sắp xếp đồ nhỏ trong bếp cho dễ lấy. "
                "Lý do đáng xem: kệ giúp gom chai lọ và đồ dùng vào một chỗ, giảm cảnh mặt bếp lộn xộn. "
                "Điểm kiểm chứng hiện có: giá tham khảo khoảng 199.000đ, có hình sản phẩm để đối chiếu. "
                "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp/treo, ảnh review trong không gian thật. "
                "Lưu ý: đo kích thước góc định đặt trước khi mua; kiểm tra đánh giá shop, ảnh thật và chính sách đổi trả."
            )
        return Result()

    monkeypatch.setattr("affilipilot.content.generator.generate_ai_caption", fake_ai)
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
    )
    draft = generate_safe_facebook_draft(product)
    assert draft.hook == "AI hook riêng cho kệ bếp gọn nhà."
    assert "Lý do đáng xem" in draft.body


def test_generator_returns_failed_ai_draft_for_retry_loop(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    def fake_ai(product, **kwargs):
        class Result:
            ok = True
            hook = "Mua đi vì đang sale."
            body = "Đừng chỉ nhìn giá. Nhu cầu, ngân sách và bối cảnh đều quan trọng."
        return Result()

    monkeypatch.setattr("affilipilot.content.generator.generate_ai_caption", fake_ai)
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Khăn giấy rút đa năng 3 lớp mềm dai ít bụi cho bàn ăn",
        category="home_consumable",
        price_vnd=49000,
        image_url="https://img.example/p.jpg",
    )
    draft = generate_safe_facebook_draft(product)
    text = draft.full_text.lower()
    assert draft.hook == "Mua đi vì đang sale."
    assert draft.metadata["caption_source"] == "AI"
    assert draft.metadata["caption_quality_passed"] is False
    assert "đừng chỉ nhìn giá" in text


def test_generator_can_disable_ai_for_deterministic_fallback(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    called = {"value": False}

    def fake_ai(product, **kwargs):
        called["value"] = True
        raise AssertionError("AI should not be called")

    monkeypatch.setattr("affilipilot.content.generator.generate_ai_caption", fake_ai)
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Hộp đựng đồ chơi trẻ em gấp gọn có nắp",
        category="storage",
        price_vnd=159000,
        image_url="https://img.example/p.jpg",
    )
    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    assert called["value"] is False
    assert "lý do đáng xem" in draft.full_text.lower()
