from affilipilot.content.caption_planner import build_caption_plan
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.models import ProductCandidate


def _draft(product: ProductCandidate):
    draft = generate_safe_facebook_draft(product, prefer_ai=False)
    quality = evaluate_product_content(product.__dict__, draft.full_text)
    assert quality.passed, quality.reasons
    text = draft.full_text.lower()
    assert "phù hợp với" in text
    assert "lý do đáng xem" in text
    assert "điểm kiểm chứng hiện có" in text
    assert "trước khi chốt" in text
    assert "lưu ý" in text
    assert "đừng chỉ nhìn giá" not in text
    assert "nhu cầu, ngân sách và bối cảnh" not in text
    return draft


def test_storage_caption_v2_has_who_why_proof_risk_cta():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực sắp xếp gọn",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;rating=4.8;sold=1200;discount_rate=0.2",
    )
    draft = _draft(product)
    text = draft.full_text.lower()
    assert "góc nhà" in text or "nhà bếp" in text
    assert "kích thước" in text
    assert "tải trọng" in text
    assert "1k+ lượt bán" in text
    assert "20%" in text


def test_tissue_caption_v2_keeps_concrete_tissue_checks():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Khăn giấy rút đa năng 3 lớp mềm dai ít bụi cho bàn ăn",
        category="home_consumable",
        price_vnd=49000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;rating=4.9;review_count=300",
    )
    draft = _draft(product)
    text = draft.full_text.lower()
    assert "số tờ" in text or "lớp giấy" in text
    assert "độ mềm" in text
    assert "ít bụi" in text or "bụi giấy" in text
    assert "lau tay" in text or "lau miệng" in text or "lau" in text


def test_electronics_adapter_caption_v2_mentions_spec_compatibility():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Sạc màn hình LCD Samsung 14V 3A Adapter nguồn jack 6.5x4.4mm",
        category="electronics",
        price_vnd=115000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;rating=4.8;sold=600",
    )
    draft = _draft(product)
    text = draft.full_text.lower()
    assert "thông số" in text
    assert "độ tương thích" in text or "tương thích" in text
    assert "bảo hành" in text
    assert "điện áp" in text or "công suất" in text or "adapter" in text or "jack" in text


def test_caption_plan_exposes_angle_for_household_storage():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Hộp đựng đồ chơi trẻ em gấp gọn có nắp",
        category="storage",
        price_vnd=159000,
        image_url="https://img.example/p.jpg",
    )
    plan = build_caption_plan(product)
    assert plan.angle == "tidy_household_storage"
    assert plan.audience
    assert plan.why_buy
    assert plan.buying_checks
