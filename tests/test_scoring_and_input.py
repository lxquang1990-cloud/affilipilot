from affilipilot.models import ProductCandidate
from affilipilot.scoring.product_score import score_product
from affilipilot.sources.manual_input import parse_link_lines


def test_safe_product_scores_higher_than_risky_product():
    safe = ProductCandidate(url="https://shopee.vn/a", title="Giỏ sắp xếp đồ bé tiện gọn", category="storage", price_vnd=129000, commission_rate=0.08)
    risky = ProductCandidate(url="https://shopee.vn/b", title="Vitamin tăng đề kháng", category="vitamin", price_vnd=299000, commission_rate=0.1)
    assert score_product(safe)["score"] > score_product(risky)["score"]


def test_parse_link_lines_with_metadata():
    text = "https://shopee.vn/a | title=Hộp chia sữa | category=feeding | price=99000"
    products = parse_link_lines(text)
    assert len(products) == 1
    assert products[0].title == "Hộp chia sữa"
    assert products[0].category == "feeding"
    assert products[0].price_vnd == 99000
