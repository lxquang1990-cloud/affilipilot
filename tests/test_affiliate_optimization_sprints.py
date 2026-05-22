from affilipilot.analytics.performance import PostPerformance, record_performance, summarize_performance
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.variants import generate_content_variants
from affilipilot.models import ProductCandidate
from affilipilot.offer import validate_offer
from affilipilot.strategy import default_strategy


def test_market_fit_blocks_generic_phone_for_mother_baby():
    product = {"title": "Samsung Galaxy S26 Ultra", "category": "electronics", "price_vnd": 30490000}
    text = "Một gợi ý nhỏ cho mẹ đang tìm đồ tiện dùng trong sinh hoạt hằng ngày với bé. #CellphoneSAffiliate"
    result = evaluate_market_fit(product, text, audience="mother_baby")
    assert not result.passed
    assert "generic_mother_baby_template_mismatch" in result.reasons
    assert "missing_family_electronics_angle" in result.reasons


def test_content_variants_create_passed_family_camera_angle():
    product = ProductCandidate(url="https://go.isclix.com/deep_link/v5/x", title="Samsung Galaxy S26 Ultra", category="electronics", price_vnd=30490000)
    variants = generate_content_variants(product)
    assert variants[0].passed
    assert variants[0].angle in {"family_camera", "storage_memory", "tech_review"}
    assert "#CellphoneSAffiliate" not in variants[0].text


def test_offer_validation_blocks_demo_url_without_network():
    result = validate_offer("https://go.isclix.com/deep_link/test-safe-mom-baby", network=False)
    assert not result.passed
    assert "demo_or_test_offer_url" in result.reasons


def test_performance_summary_groups_by_category_and_angle(tmp_path):
    path = tmp_path / "performance.json"
    record_performance(path, PostPerformance(batch_key="b", post_id="p1", category="electronics", angle="family_camera", clicks=10, conversions=1, commission_vnd=50000))
    record_performance(path, PostPerformance(batch_key="b", post_id="p2", category="feeding", angle="checklist", clicks=5, conversions=0, commission_vnd=0))
    summary = summarize_performance(path)
    assert summary["total_posts"] == 2
    assert summary["total_clicks"] == 15
    assert summary["by_category"]["electronics"]["commission_vnd"] == 50000
    assert summary["by_angle"]["family_camera"]["conversions"] == 1


def test_default_strategy_smart_shopping_by_default():
    strategy = default_strategy()
    assert strategy.primary_lane == "smart_shopping_multi_category"
    assert "raw_affiliate_links" in strategy.blocked_lanes


def test_default_strategy_mother_baby_when_requested():
    strategy = default_strategy(audience="mother_baby")
    assert strategy.primary_lane == "mother_baby_core"
    assert "generic_flagship_tech" in strategy.blocked_lanes
