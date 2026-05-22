from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate


def test_generator_uses_ai_caption_first_when_gate_passes(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    def fake_ai(product, **kwargs):
        class Result:
            ok = True
            hook = ""
            body = "Kệ nhỏ giúp gom chai lọ và đồ dùng bếp vào một chỗ, mặt bếp nhìn gọn hơn mà không tốn nhiều diện tích."
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
    assert draft.hook == ""
    assert draft.body == "Kệ nhỏ giúp gom chai lọ và đồ dùng bếp vào một chỗ, mặt bếp nhìn gọn hơn mà không tốn nhiều diện tích."
    assert "Giá tham khảo trên Shopee 199.000đ, link affiliate 👇" in draft.full_text


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
