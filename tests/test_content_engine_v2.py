from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.content.product_quality import evaluate_product_content
from affilipilot.models import ProductCandidate


def test_home_appliance_caption_contains_concrete_buying_facts():
    product = ProductCandidate(
        url="https://www.lazada.vn/products/a.html",
        title="Máy lọc không khí chính hãng bảo hành 12 tháng",
        category="home_appliance",
        price_vnd=1290000,
        notes="merchant=lazada_kol;discount_rate=0.45;discount_vnd=500000",
    )
    draft = generate_safe_facebook_draft(product)
    text = draft.full_text.lower()
    assert "bảo hành" in text
    assert any(term in text for term in ["đánh giá", "review", "công suất", "độ ồn"])
    assert "45%" in text
    result = evaluate_product_content(product.__dict__, draft.full_text)
    assert result.passed, result.reasons


def test_product_quality_blocks_risky_claims_in_caption():
    product = {"title": "Vitamin K2D3 cho bé", "category": "mother_baby"}
    text = "Vitamin này giúp tăng đề kháng, ăn ngon và phát triển trí não tốt hơn. Giá đang tốt, mua ngay."
    result = evaluate_product_content(product, text)
    assert not result.passed
    assert "risky_health_or_body_claim" in result.reasons
