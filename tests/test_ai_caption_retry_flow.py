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
        cta="Giá tham khảo trên Shopee 199.000đ, link affiliate 👇",
        disclosure="",
        compliance=ComplianceResult(status=ComplianceStatus.PASS),
        metadata={"caption_source": source, "ai_feedback": feedback or []},
    )

def _bad_ai_draft(product, feedback=None):
    return _draft(
        product,
        "Nhà bếp nhiều đồ nhỏ thì mẫu kệ này đáng xem.",
        "Phù hợp với nhà cần sắp xếp đồ nhỏ. Lý do đáng xem: kích thước rõ, tải trọng tốt. "
        "Điểm kiểm chứng hiện có: giá 199.000đ, rating 4.8/5. Đủ để lọc bước đầu chứ không nên mua chỉ vì nhìn ảnh đẹp. "
        "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp/treo, ảnh review thật. "
        "Lưu ý: đo góc định đặt trước khi mua.",
        feedback=feedback,
    )

def _good_minimal_ai_draft(product, feedback=None):
    return _draft(
        product,
        "",
        "Kệ nhỏ giúp gom chai lọ và đồ lặt vặt ở bếp/phòng tắm gọn hơn, dễ lấy hơn và hợp với nhà cần tiết kiệm diện tích.",
        feedback=feedback,
    )

def test_quality_failure_retries_ai_with_feedback_before_hold(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = _product()
    calls = []

    def fake_generator(product, *, feedback=None, prefer_ai=True):
        calls.append({"feedback": feedback, "prefer_ai": prefer_ai})
        if len(calls) == 1:
            return _bad_ai_draft(product, feedback=feedback)
        return _good_minimal_ai_draft(product, feedback=feedback)

    result = generate_until_content_gate_passes(product, max_regenerations=2, generator=fake_generator, ai_retry_attempts=2)
    assert result.attempts[0].passed is False
    assert result.attempts[-1].passed is True
    assert len(calls) == 2
    assert calls[0]["prefer_ai"] is True
    assert calls[1]["prefer_ai"] is True
    assert calls[1]["feedback"]
    assert any("mechanical_phrase" in item for item in calls[1]["feedback"])

def test_holds_after_ai_retries_exhausted_without_repair_fallback(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = _product()
    calls = []

    def fake_generator(product, *, feedback=None, prefer_ai=True):
        calls.append({"feedback": feedback, "prefer_ai": prefer_ai})
        return _bad_ai_draft(product, feedback=feedback)

    result = generate_until_content_gate_passes(product, max_regenerations=1, generator=fake_generator, ai_retry_attempts=1)
    assert result.attempts[-1].passed is False
    assert [call["prefer_ai"] for call in calls] == [True, True]
    assert result.draft.metadata["caption_source"] == "AI"
