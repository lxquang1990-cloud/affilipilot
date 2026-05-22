from affilipilot.content.niche_policy import POSITIONING, evaluate_niche_fit
from affilipilot.models import ProductCandidate
from affilipilot.scoring.product_score import score_product


def test_niche_policy_accepts_small_household_value_product():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Hộp đựng thực phẩm chia ngăn cho nhà bếp, bảo quản gọn, combo 3 hộp",
        category="home_living",
        price_vnd=129000,
        image_url="https://img.example/p.jpg",
    )
    result = evaluate_niche_fit(product)
    assert result.passed
    assert result.positioning == POSITIONING
    assert result.score >= 70
    assert any("core_smart_shopping_category" in reason for reason in result.reasons)


def test_niche_policy_blocks_low_fit_bike_part():
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Shimano củ đề xe đạp phụ tùng thay thế",
        category="bike_accessory",
        price_vnd=350000,
        image_url="https://img.example/p.jpg",
    )
    result = evaluate_niche_fit(product)
    assert not result.passed
    assert any("blocked_smart_shopping_category" in penalty or "low_niche_fit_terms" in penalty for penalty in result.penalties)


def test_product_score_rewards_niche_fit_over_generic_unknown():
    good = ProductCandidate(
        url="https://shopee.vn/good",
        title="Kệ để đồ nhà bếp chịu lực, sắp xếp gọn, kích thước rõ",
        category="storage",
        price_vnd=199000,
        image_url="https://img.example/good.jpg",
        notes="discount_rate=20; bảo hành",
    )
    bad = ProductCandidate(
        url="https://shopee.vn/bad",
        title="Mô hình anime gửi ngẫu nhiên",
        category="toy",
        price_vnd=199000,
        image_url="https://img.example/bad.jpg",
    )
    good_score = score_product(good)
    bad_score = score_product(bad)
    assert good_score["score"] > bad_score["score"]
    assert any(str(reason).startswith("niche_fit:") for reason in good_score["reasons"])
