from datetime import date

from affilipilot.models import ProductCandidate
from affilipilot.scoring.product_score import score_product
from affilipilot.scoring.shopee_sourcing import score_shopee_sourcing


def test_shopee_brand_bonus_active_scores_source():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Kệ nhà bếp gọn",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;brand_bonus=true;brand_commission=6%;brand_bonus_start=2026-05-01;brand_bonus_end=2026-05-31;apply_to=whole_shop;campaign_window=payday;source_tag=hot_sku,shopee_choice",
    )
    result = score_shopee_sourcing(product, today=date(2026, 5, 21))
    assert result.score >= 40
    assert "brand_bonus_active+16" in result.reasons
    assert "brand_commission_good:6.0%+9" in result.reasons
    assert "brand_bonus_apply_whole_shop+5" in result.reasons
    assert "campaign_window:payday+8" in result.reasons
    assert "source_tag:hot_sku+8" in result.reasons
    assert "source_tag:shopee_choice+6" in result.reasons


def test_expired_brand_bonus_penalized():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Kệ nhà bếp gọn",
        category="storage",
        notes="merchant=shopee;brand_bonus=true;brand_commission=10%;brand_bonus_start=2026-04-01;brand_bonus_end=2026-04-30",
    )
    result = score_shopee_sourcing(product, today=date(2026, 5, 21))
    assert "brand_bonus_expired_or_not_started-8" in result.reasons
    assert not any(reason.startswith("brand_commission_excellent") for reason in result.reasons)


def test_product_score_includes_shopee_sourcing_reasons():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Kệ nhà bếp gọn kích thước rõ chịu lực tốt",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/p.jpg",
        notes="merchant=shopee;brand_bonus=true;brand_commission=6%;apply_to=whole_shop;source_tag=hot_sku;discount_rate=0.2;kích thước rõ;tải trọng tốt",
    )
    result = score_product(product)
    assert result["score"] == 100
    assert "brand_bonus_active+16" in result["reasons"]
    assert "source_tag:hot_sku+8" in result["reasons"]
