from affilipilot.content.caption_quality_ai import judge_caption_quality
from affilipilot.content.regenerator import generate_until_content_gate_passes
from affilipilot.models import ComplianceResult, ComplianceStatus, ContentDraft, ProductCandidate
from affilipilot.telegram.approval_context import build_approval_context
from affilipilot.telegram.cards import render_approval_card


def _product():
    return ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn kích thước rõ",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;rating=4.8;sold=1200;discount_rate=0.2",
    )


def test_caption_quality_blocks_mechanical_ai_copy(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = _product()
    text = (
        "Kệ này phù hợp với nhà cần sắp xếp đồ nhỏ. "
        "Lý do đáng xem: kích thước rõ, tải trọng tốt. "
        "Điểm kiểm chứng hiện có: giá 199.000đ, rating 4.8/5. "
        "Đủ để lọc bước đầu chứ không nên mua chỉ vì nhìn ảnh đẹp. "
        "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp/treo, ảnh review thật. "
        "Lưu ý: đo góc định đặt trước khi mua. "
        "Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link."
    )
    result = judge_caption_quality(product, text)
    assert result.passed is False
    assert result.score < 72
    assert any("mechanical_phrase" in reason for reason in result.reasons)


def test_regenerator_uses_caption_quality_gate(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = _product()
    calls = {"count": 0}

    def fake_generator(product, feedback=None):
        calls["count"] += 1
        if calls["count"] == 1:
            body = (
                "Phù hợp với nhà cần sắp xếp đồ nhỏ. Lý do đáng xem: kích thước rõ, tải trọng tốt. "
                "Điểm kiểm chứng hiện có: giá 199.000đ, rating 4.8/5. Đủ để lọc bước đầu chứ không nên mua chỉ vì nhìn ảnh đẹp. "
                "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp/treo, ảnh review thật. "
                "Lưu ý: đo góc định đặt trước khi mua."
            )
        else:
            body = (
                "Phù hợp với nhà cần gom chai lọ và đồ nhỏ ở bếp/phòng tắm cho dễ lấy. "
                "Lý do đáng xem: giúp góc nhà gọn hơn, có kích thước rõ và tải trọng tốt. "
                "Điểm kiểm chứng hiện có: giá khoảng 199.000đ, rating 4.8/5 và 1k+ lượt bán. "
                "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp, ảnh review thật. "
                "Lưu ý: đo góc định đặt và xem chính sách đổi trả trước khi mua."
            )
        return ContentDraft(
            product=product,
            hook="Kệ nhỏ giúp góc bếp gọn hơn.",
            body=body,
            cta="Xem ảnh thật, review và giá hiện tại ở link bên dưới nhé 👇",
            disclosure="Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link.",
            compliance=ComplianceResult(status=ComplianceStatus.PASS),
            metadata={"caption_source": "AI" if calls["count"] == 1 else "REPAIR_FALLBACK"},
        )

    result = generate_until_content_gate_passes(product, max_regenerations=1, generator=fake_generator)
    assert calls["count"] == 2
    assert result.attempts[0].passed is False
    assert any("caption_quality" in reason for reason in result.attempts[0].reasons)
    assert result.attempts[-1].passed is True


def test_approval_card_shows_ai_caption_quality():
    product = _product()
    draft = ContentDraft(
        product=product,
        hook="Kệ nhỏ giúp góc bếp gọn hơn.",
        body="Phù hợp với nhà cần gom đồ nhỏ. Lý do đáng xem: gọn hơn. Điểm kiểm chứng hiện có: giá 199.000đ. Trước khi chốt, nên kiểm tra kích thước. Lưu ý: đo góc trước khi mua.",
        cta="Xem link nhé",
        disclosure="Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link.",
        compliance=ComplianceResult(status=ComplianceStatus.PASS),
        metadata={"caption_source": "AI", "ai_provider": "9router", "caption_quality_passed": True, "caption_quality_score": 86, "caption_quality_source": "ai", "caption_quality_reasons": []},
    )
    ctx = build_approval_context(draft, content_gate={"passed": True, "score": 0.86, **draft.metadata})
    card = render_approval_card(draft, batch_key="batch", post_id="post", context=ctx)
    assert "AI caption quality: PASS (86/100) via ai" in card
