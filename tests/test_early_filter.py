from affilipilot.content.early_filter import evaluate_early_product_filter, normalize_category
from affilipilot.models import ProductCandidate


def test_early_filter_blocks_medical_supplement_before_conversion():
    product = ProductCandidate(
        url="https://www.lazada.vn/products/x.html",
        title="Máy đo đường huyết Safe Accu chính hãng phát hiện tiểu đường",
        category="health_and_beauty",
        notes="merchant=lazada_kol;discount_rate=0.38",
    )
    result = evaluate_early_product_filter(product)
    assert not result.passed
    assert "medical_device" in result.reasons
    assert "unsafe_category" in result.risk_flags


def test_early_filter_allows_home_appliance_deal():
    product = ProductCandidate(
        url="https://www.lazada.vn/products/a.html",
        title="Máy lọc không khí chính hãng bảo hành 12 tháng",
        category="home_appliance",
        notes="merchant=lazada_kol;discount_rate=0.30",
    )
    result = evaluate_early_product_filter(product)
    assert result.passed, result.reasons
    assert normalize_category(product) == "home_appliance"
