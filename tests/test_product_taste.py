from affilipilot.content.product_taste import evaluate_product_taste
from affilipilot.models import ProductCandidate


def test_product_taste_prefers_broad_household_item_over_replacement_part():
    good = ProductCandidate(
        url="https://shopee.vn/a",
        title="Máy hút bụi mini chính hãng bảo hành dùng trong nhà",
        category="home_appliance",
        price_vnd=399000,
        image_url="https://example.com/a.jpg",
    )
    niche = ProductCandidate(
        url="https://shopee.vn/b",
        title="Củ đề sau xe đạp Shimano Tourney RD TY300 6/7/8 tốc độ",
        category="bike_accessory",
        price_vnd=245000,
        image_url="https://example.com/b.jpg",
    )
    good_result = evaluate_product_taste(good)
    niche_result = evaluate_product_taste(niche)
    assert good_result.passed
    assert not niche_result.passed
    assert good_result.score > niche_result.score
    assert "niche_or_replacement_part-25" in niche_result.penalties


def test_product_taste_blocks_unknown_without_broad_use_case():
    product = ProductCandidate(url="https://example.com/x", title="Mã linh kiện thay thế ABC123", category="unknown", price_vnd=150000)
    result = evaluate_product_taste(product)
    assert not result.passed
    assert "low_fit_category:unknown-18" in result.penalties


def test_product_taste_hard_blocks_anime_figure_and_tv_remote():
    figure = ProductCandidate(url="https://shopee.vn/a", title="Mô hình Demon Slayer có đèn led", category="electronics", price_vnd=390000, image_url="https://example.com/a.jpg")
    remote = ProductCandidate(url="https://shopee.vn/b", title="Điều khiển tivi TCL chính hãng", category="electronics", price_vnd=250000, image_url="https://example.com/b.jpg")
    toy_noise = ProductCandidate(url="https://shopee.vn/c", title="Đồ Chơi Đường Đua MC Queen tàu Thomas shop gửi ngẫu nhiên", category="toy", price_vnd=285000, image_url="https://example.com/c.jpg")
    assert not evaluate_product_taste(figure).passed
    assert not evaluate_product_taste(remote).passed
    assert not evaluate_product_taste(toy_noise).passed
    assert "hard_block_low_approval_fit-60" in evaluate_product_taste(figure).penalties
