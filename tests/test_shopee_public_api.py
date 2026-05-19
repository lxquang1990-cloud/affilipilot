from affilipilot.marketplaces.shopee_public_api import parse_shopee_ids, product_from_item


def test_parse_shopee_ids_slug_and_product_urls():
    assert parse_shopee_ids("https://shopee.vn/foo-i.460071422.43319590852") == (460071422, 43319590852)
    assert parse_shopee_ids("https://shopee.vn/product/460071422/43319590852") == (460071422, 43319590852)


def test_product_from_item_maps_core_fields():
    item = {
        "shopid": 1,
        "itemid": 2,
        "name": "Máy hút bụi cầm tay mini",
        "price": 29900000000,
        "image": "vn-11134207-7r98o-testimage",
        "images": ["vn-11134207-7r98o-testimage"],
        "sold": 120,
        "historical_sold": 500,
        "item_rating": {"rating_star": 4.8, "rating_count": [33, 0, 0, 1, 2, 30]},
        "video_info_list": [{"url": "https://cf.shopee.vn/file/video.mp4"}],
        "shopee_verified": True,
    }
    product = product_from_item(item)
    assert product is not None
    assert product.title == "Máy hút bụi cầm tay mini"
    assert product.price_vnd == 299000
    assert product.sold == 120
    assert product.rating == 4.8
    assert product.review_count == 33
    assert product.video_urls == ["https://cf.shopee.vn/file/video.mp4"]
    candidate = product.to_candidate(category="home_appliance", keyword="máy hút bụi cầm tay")
    assert candidate.media_source == "shopee_public_api"
    assert "seed_keyword=máy hút bụi cầm tay" in candidate.notes
