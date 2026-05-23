from affilipilot.models import ProductCandidate
from affilipilot.scoring.product_score import score_product
from affilipilot.sources.manual_input import parse_link_lines


def test_safe_product_scores_higher_than_risky_product():
    safe = ProductCandidate(url="https://shopee.vn/a", title="Giỏ sắp xếp đồ bé tiện gọn chính hãng", category="storage", price_vnd=129000, commission_rate=0.08, image_url="https://example.com/a.jpg", notes="merchant=shopee;discount_rate=0.25")
    risky = ProductCandidate(url="https://shopee.vn/b", title="Vitamin tăng đề kháng", category="vitamin", price_vnd=299000, commission_rate=0.1, image_url="https://example.com/b.jpg")
    assert score_product(safe)["score"] > score_product(risky)["score"]


def test_profit_scorer_rewards_trust_discount_and_caption_facts():
    product = ProductCandidate(
        url="https://www.lazada.vn/products/a.html",
        title="Máy lọc không khí chính hãng bảo hành 12 tháng công suất lớn",
        category="home_appliance",
        price_vnd=1290000,
        image_url="https://example.com/a.jpg",
        notes="merchant=lazada_kol;discount_rate=0.45;discount_vnd=500000",
    )
    result = score_product(product)
    assert result["score"] >= 85
    assert "trusted_merchant:lazada_kol+10" in result["reasons"]
    assert "discount_excellent+16" in result["reasons"]
    assert "enough_facts_for_caption+10" in result["reasons"]


def test_parse_link_lines_with_metadata():
    text = "https://shopee.vn/a | title=Hộp chia sữa | category=feeding | price=99000 | image_url=https://cdn.example/test.jpg"
    products = parse_link_lines(text)
    assert len(products) == 1
    assert products[0].title == "Hộp chia sữa"
    assert products[0].category == "feeding"
    assert products[0].price_vnd == 99000
