from affilipilot.content.regenerator import generate_until_content_gate_passes
from affilipilot.models import ComplianceResult, ComplianceStatus, ContentDraft, ProductCandidate


def _product():
    return ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn kích thước rõ",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;rating=4.8;sold=1200;discount_rate=0.2",
    )


def _draft(product, hook, body, *, source="AI", feedback=None):
    return ContentDraft(
        product=product,
        hook=hook,
        body=body,
        cta="Xem ảnh thật, review và giá hiện tại ở link bên dưới nhé 👇",
        disclosure="Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link.",
        compliance=ComplianceResult(status=ComplianceStatus.PASS),
        metadata={"caption_source": source, "ai_feedback": feedback or []},
    )


def test_quality_failure_retries_ai_with_feedback_before_fallback(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = _product()
    calls = []

    def fake_generator(product, *, feedback=None, prefer_ai=True):
        calls.append({"feedback": feedback, "prefer_ai": prefer_ai})
        if len(calls) == 1:
            return _draft(
                product,
                "Nhà bếp nhiều đồ nhỏ thì mẫu kệ này đáng xem.",
                "Phù hợp với nhà cần sắp xếp đồ nhỏ. Lý do đáng xem: kích thước rõ, tải trọng tốt. "
                "Điểm kiểm chứng hiện có: giá 199.000đ, rating 4.8/5. Đủ để lọc bước đầu chứ không nên mua chỉ vì nhìn ảnh đẹp. "
                "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp/treo, ảnh review thật. "
                "Lưu ý: đo góc định đặt trước khi mua.",
                feedback=feedback,
            )
        return _draft(
            product,
            "Góc bếp nhiều chai lọ nhìn mệt thì chiếc kệ nhỏ này đáng xem.",
            "Phù hợp với nhà cần gom gia vị, chai nước rửa hoặc đồ vệ sinh vào một chỗ dễ lấy. "
            "Lý do đáng xem: giúp góc bếp/phòng tắm gọn hơn, có kích thước rõ và tải trọng tốt. "
            "Điểm kiểm chứng hiện có: giá khoảng 199.000đ, rating 4.8/5 và 1k+ lượt bán. "
            "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp và ảnh review thật. "
            "Lưu ý: đo góc định đặt và không để quá tải.",
            feedback=feedback,
        )

    result = generate_until_content_gate_passes(product, max_regenerations=2, generator=fake_generator, ai_retry_attempts=2)
    assert result.attempts[0].passed is False
    assert result.attempts[-1].passed is True
    assert len(calls) == 2
    assert calls[0]["prefer_ai"] is True
    assert calls[1]["prefer_ai"] is True
    assert calls[1]["feedback"]
    assert any("mechanical_phrase" in item for item in calls[1]["feedback"])


def test_fallback_only_after_ai_retries_exhausted(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = _product()
    calls = []

    def fake_generator(product, *, feedback=None, prefer_ai=True):
        calls.append({"feedback": feedback, "prefer_ai": prefer_ai})
        if prefer_ai:
            return _draft(
                product,
                "Nhà bếp nhiều đồ nhỏ thì mẫu kệ này đáng xem.",
                "Phù hợp với nhà cần sắp xếp đồ nhỏ. Lý do đáng xem: kích thước rõ, tải trọng tốt. "
                "Điểm kiểm chứng hiện có: giá 199.000đ, rating 4.8/5. Đủ để lọc bước đầu chứ không nên mua chỉ vì nhìn ảnh đẹp. "
                "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp/treo, ảnh review thật. "
                "Lưu ý: đo góc định đặt trước khi mua.",
                feedback=feedback,
            )
        return _draft(
            product,
            "Kệ nhỏ giúp góc bếp gọn hơn.",
            "Phù hợp với nhà cần gom đồ nhỏ. Lý do đáng xem: gọn hơn và dễ lấy hơn. "
            "Điểm kiểm chứng hiện có: giá khoảng 199.000đ, rating 4.8/5 và 1k+ lượt bán. "
            "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp và ảnh review thật. "
            "Lưu ý: đo góc định đặt trước khi mua.",
            source="REPAIR_FALLBACK",
            feedback=feedback,
        )

    result = generate_until_content_gate_passes(product, max_regenerations=1, generator=fake_generator, ai_retry_attempts=1)
    assert result.attempts[-1].passed is True
    assert [call["prefer_ai"] for call in calls] == [True, True, False]
