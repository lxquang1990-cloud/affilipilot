from affilipilot.content.content_gate import evaluate_content_gates
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate


def test_household_tissue_generated_copy_is_specific_and_gate_passes():
    product = ProductCandidate(
        url="https://shopee.vn/search?keyword=kh%C4%83n%20gi%E1%BA%A5y",
        title="Khăn giấy rút đa năng cho gia đình",
        category="home_consumable",
        price_vnd=99000,
        notes="merchant=shopee;keyword=khăn giấy",
    )

    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    text = draft.full_text.lower()
    result = evaluate_content_gates(product.__dict__, draft.full_text)

    assert result.passed, result.reasons
    assert "thông tin sản phẩm đủ rõ" not in text
    assert "hợp đúng việc cần dùng" not in text
    assert "các thông tin chính đều rõ ràng" not in text
    assert "lớp giấy" in text or "số tờ" in text
    assert "bụi" in text
    assert "lau tay" in text or "lau miệng" in text or "lau bếp" in text
    assert "#khangiay" in text


def test_content_gate_blocks_generic_tissue_copy_before_approval():
    product = {"title": "Khăn giấy rút đa năng cho gia đình", "category": "home_consumable"}
    text = """
    Khăn giấy rút đa năng cho gia đình chỉ đáng mua khi thông tin sản phẩm đủ rõ và hợp đúng việc cần dùng.

    Khăn giấy rút đa năng cho gia đình phù hợp để cân nhắc nếu các thông tin chính đều rõ ràng, không chỉ vì đang được gắn nhãn sale.
    Trước khi chốt nên kiểm tra: kích thước, chất liệu, cách dùng thực tế, ảnh/review thật, đổi trả.

    Xem ảnh thật, review và giá hiện tại ở link bên dưới nhé 👇
    Bài viết có link tiếp thị liên kết; page có thể nhận hoa hồng nhỏ nếu bạn mua qua link.
    """

    result = evaluate_content_gates(product, text)

    assert not result.passed
    assert "gate_A:no.generic_template" in result.reasons
    assert "gate_B:product_quality.pass" in result.reasons
    assert "gate_B:category_specific.household_tissue" in result.reasons
