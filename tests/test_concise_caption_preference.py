from affilipilot.content.caption_quality_ai import judge_caption_quality
from affilipilot.models import ProductCandidate


def _product():
    return ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn kích thước rõ",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;rating=4.8;sold=1200;discount_rate=0.2",
    )


def test_concise_buyer_facing_caption_passes(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    text = (
        "Món này hợp với nhà có nhiều đồ nhỏ ở bếp, phòng tắm hoặc góc giặt: "
        "chai gia vị, hũ đựng, khăn, đồ vệ sinh… cứ để rải rác là nhìn rất bừa. "
        "Giá tham khảo trên Shopee khoảng 199.000đ.\n\n"
        "Link affiliate nhé 👇\n"
        "#sapxepnhacua #dogiadung #muasamthongminh"
    )
    result = judge_caption_quality(_product(), text)
    assert result.passed is True
    assert result.score >= 72


def test_internal_long_caption_is_penalized(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    text = (
        "Góc bếp hay lộn xộn vì chai lọ, hộp nhỏ? Kệ để đồ kiểu này đáng xem nếu bạn muốn gom gọn mà không tốn nhiều diện tích.\n\n"
        "Món này hợp với nhà có nhiều đồ nhỏ ở bếp, phòng tắm hoặc góc giặt: chai gia vị, hũ đựng, khăn, đồ vệ sinh. "
        "Điểm đáng xem là kệ có kích thước ghi rõ, giá tham khảo khoảng 199.000đ, hiện data đang có giảm khoảng 20%, "
        "rating khoảng 4.8/5 và hơn 1.200 lượt bán — đủ để mình ưu tiên xem tiếp thay vì lướt qua. "
        "Trước khi mua nên check kỹ: chiều dài/rộng/cao có vừa góc đặt không, tải trọng shop ghi là bao nhiêu, "
        "chất liệu có dễ lau không, lắp đặt/đặt sàn hay treo, và ảnh review thật có giống nhu cầu nhà mình không. "
        "Lưu ý rủi ro: nếu để đồ quá nặng hoặc đặt ở nơi ẩm lâu có thể kém bền.\n\n"
        "Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link."
    )
    result = judge_caption_quality(_product(), text)
    assert result.passed is False
    assert any("internal_evaluation_phrase" in reason or "too_checklist" in reason for reason in result.reasons)


def test_ultra_short_provider_price_style_passes(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    text = (
        "Món này hợp với nhà có nhiều đồ nhỏ ở bếp, phòng tắm hoặc góc giặt: "
        "chai gia vị, hũ đựng, khăn, đồ vệ sinh… cứ để rải rác là nhìn rất bừa. "
        "Giá tham khảo trên Shopee khoảng 199.000đ.\n"
        "Link affiliate nhé 👇\n"
        "#sapxepnhacua #dogiadung #muasamthongminh"
    )
    result = judge_caption_quality(_product(), text)
    assert result.passed is True
    assert result.score >= 85


def test_provider_placeholder_is_blocked(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    text = (
        "Món này hợp với nhà có nhiều đồ nhỏ ở bếp. "
        "Giá tham khảo trên <provider> khoảng 199.000đ.\n"
        "Link affiliate nhé 👇"
    )
    result = judge_caption_quality(_product(), text)
    assert result.passed is False
    assert "provider_placeholder_not_resolved" in result.reasons


def test_minimal_approval_caption_style_passes(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    text = (
        "Cầu trượt gập gọn giúp bé có góc vận động vui trong nhà, dùng xong cất lại đỡ chiếm chỗ nên hợp với căn hộ nhỏ.\n\n"
        "Giá tham khảo trên Shopee xem tại link, link affiliate 👇\n"
        "#chobevui #dodungchobe #muasamthongminh"
    )
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="cầu trượt cho bé trong nhà có thể gập lại",
        category="unknown",
        image_url="https://img.example/p.jpg",
    )
    result = judge_caption_quality(product, text)
    assert result.passed is True
    assert result.score >= 80
    assert "too_checklist_heavy" not in result.reasons


def test_minimal_caption_blocks_warning_checklist(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    text = (
        "Mẫu cầu trượt trong nhà có thể gập lại, hợp với gia đình muốn thêm một món chơi vận động mà không chiếm chỗ cố định. "
        "Trước khi mua nên xem kỹ kích thước, chất liệu, ảnh thật và luôn để người lớn ở cạnh khi bé chơi.\n\n"
        "Giá tham khảo trên Shopee xem tại link, link affiliate 👇"
    )
    result = judge_caption_quality(ProductCandidate(url="https://shopee.vn/p", title="cầu trượt cho bé", category="unknown"), text)
    assert result.passed is False
    assert any(reason in result.reasons for reason in ("too_checklist_heavy", "baby_play_warning_checklist"))
