from affilipilot.content.ai_caption import _chat_completions_endpoint
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate
from affilipilot.telegram.approval_context import build_approval_context
from affilipilot.telegram.cards import render_approval_card


def test_ai_endpoint_normalizes_base_v1_to_chat_completions():
    assert _chat_completions_endpoint("http://router.local:20128/v1") == "http://router.local:20128/v1/chat/completions"
    assert _chat_completions_endpoint("https://api.example.com/v1/chat/completions") == "https://api.example.com/v1/chat/completions"


def test_ai_caption_source_metadata_when_ai_passes(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    def fake_ai(product, **kwargs):
        class Result:
            ok = True
            hook = "AI hook cho góc bếp gọn hơn."
            body = (
                "Phù hợp với nhà cần gom chai lọ và đồ nhỏ cho dễ lấy. "
                "Lý do đáng xem: giúp góc bếp gọn hơn, có kích thước rõ và tải trọng tốt. "
                "Điểm kiểm chứng hiện có: giá tham khảo khoảng 199.000đ, rating khoảng 4.8/5, 1k+ lượt bán. "
                "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp, ảnh review thật. "
                "Lưu ý: đo góc định đặt trước khi mua và kiểm tra chính sách đổi trả."
            )
            reason = ""
            provider = "9router"
        return Result()

    monkeypatch.setattr("affilipilot.content.generator.generate_ai_caption", fake_ai)
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn kích thước rõ",
        category="storage",
        price_vnd=199000,
        image_url="https://example.com/p.jpg",
    )
    draft = generate_safe_facebook_draft(product)
    assert draft.metadata["caption_source"] == "AI"
    ctx = build_approval_context(draft, content_gate={"passed": True, "score": 1.0, "caption_source": "AI", "ai_provider": "9router"})
    card = render_approval_card(draft, batch_key="batch", post_id="post_1", context=ctx)
    assert "Caption source: AI via 9router" in card


def test_ai_unavailable_holds_instead_of_planner_fallback(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION", "1")
    def fake_ai(product, **kwargs):
        class Result:
            ok = False
            reason = "ai_caption_http_error:404:model_not_found"
            provider = "9router"
        return Result()

    monkeypatch.setattr("affilipilot.content.generator.generate_ai_caption", fake_ai)
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn kích thước rõ",
        category="storage",
        price_vnd=199000,
        image_url="https://example.com/p.jpg",
    )
    draft = generate_safe_facebook_draft(product)
    assert draft.metadata["caption_source"] == "HELD_FOR_ENRICHMENT"
    assert "model_not_found" in draft.metadata["ai_reason"]
    ctx = build_approval_context(draft, content_gate={"passed": True, "score": 1.0, **draft.metadata})
    card = render_approval_card(draft, batch_key="batch", post_id="post_1", context=ctx)
    assert "HELD_FOR_ENRICHMENT" in card
    assert "AI/fallback reason: ai_caption_http_error:404:model_not_found" in card
