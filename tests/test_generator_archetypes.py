from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.models import ProductCandidate


def _assert_passes(product: ProductCandidate):
    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    result = evaluate_product_content(product.__dict__, draft.full_text)
    assert result.passed, result.reasons
    assert "đừng chỉ nhìn giá" not in draft.full_text.lower()
    assert "nhu cầu, ngân sách và bối cảnh" not in draft.full_text.lower()
    return draft


def test_feeding_archetype_has_specific_cleaning_material_context():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Bình thìa ăn dặm silicone cho bé dễ bóp",
        category="feeding",
        price_vnd=79000,
        notes="merchant=shopee;rating=4.8;sold=1200",
    )
    draft = _assert_passes(product)
    text = draft.full_text.lower()
    assert "ăn dặm" in text
    assert "vệ sinh" in text or "dễ rửa" in text
    assert "chất liệu" in text
    assert "1k+ lượt bán" in text


def test_storage_archetype_has_real_home_organization_context():
    product = ProductCandidate(
        url="https://www.lazada.vn/products/a.html",
        title="Giỏ sắp xếp đồ bỉm sữa treo xe đẩy và đầu giường",
        category="storage",
        price_vnd=129000,
        notes="merchant=lazada_kol;discount_rate=0.25",
    )
    draft = _assert_passes(product)
    text = draft.full_text.lower()
    assert "gọn" in text
    assert "kích thước" in text
    assert "tải trọng" in text or "lắp" in text or "treo" in text
    assert "25%" in text


def test_cleaning_appliance_archetype_is_not_generic_home_copy():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Máy hút bụi cầm tay không dây cho gia đình",
        category="home_appliance",
        price_vnd=599000,
        notes="merchant=shopee;rating=4.9;review_count=230",
    )
    draft = _assert_passes(product)
    text = draft.full_text.lower()
    assert "hút bụi" in text or "dọn dẹp" in text
    assert "công suất" in text or "dung tích" in text
    assert "độ ồn" in text
    assert "bảo hành" in text


def test_unknown_category_can_still_use_title_archetype():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Hộp đựng đồ chơi trẻ em gấp gọn có nắp",
        category="unknown",
        price_vnd=159000,
        notes="merchant=shopee",
    )
    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    text = draft.full_text.lower()
    assert "sắp xếp" in text or "gọn" in text
    assert "kích thước" in text
    assert "tải trọng" in text or "chất liệu" in text
