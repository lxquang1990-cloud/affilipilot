from affilipilot.accesstrade.catalog import AccesstradeConfig, _product_from_item, fetch_datafeeds
from affilipilot.accesstrade.product_detail import fetch_product_detail
from affilipilot.accesstrade.reports import _ORDER_LIST_CACHE, fetch_order_list


def test_datafeed_uses_official_filters_and_caps_limit(monkeypatch):
    seen = {}

    def fake_request_json(url, *, token, timeout=30):
        seen["url"] = url
        return {"data": []}

    monkeypatch.setattr("affilipilot.accesstrade.catalog._request_json", fake_request_json)
    fetch_datafeeds(
        config=AccesstradeConfig(token="tok"),
        domain="shopee.vn",
        discount_rate_from="20",
        discount_rate_to="50",
        discount_amount_from="10000",
        discount_amount_to="90000",
        discount_from="100000",
        discount_to="200000",
        update_from="27-05-2026",
        update_to="28-05-2026",
        limit=999,
    )

    url = seen["url"]
    assert "/v1/datafeeds?" in url
    assert "domain=shopee.vn" in url
    assert "discount_rate_from=20" in url
    assert "discount_rate_to=50" in url
    assert "discount_amount_from=10000" in url
    assert "discount_amount_to=90000" in url
    assert "discount_from=100000" in url
    assert "discount_to=200000" in url
    assert "update_from=27-05-2026" in url
    assert "update_to=28-05-2026" in url
    assert "limit=200" in url


def test_official_datafeed_discount_is_sale_price():
    product = _product_from_item(
        {"url": "https://shop.example/p", "name": "Official item", "price": 250000, "discount": 175000, "discount_amount": 75000, "discount_rate": 30},
        source="accesstrade_datafeed",
    )
    assert product.price_vnd == 250000
    assert product.discount_vnd == 175000


def test_percent_like_discount_fallback_handles_observed_shopee_anomaly():
    product = _product_from_item(
        {"url": "https://shopee.vn/product/123/456", "name": "Shopee anomaly", "price": 250000, "discount": 30, "discount_amount": 249970},
        source="accesstrade_datafeed",
    )
    assert product.discount_vnd == 175000


def test_fetch_product_detail_maps_official_response(monkeypatch):
    seen = {}

    def fake_request_json(url, *, token, timeout=30):
        seen["url"] = url
        return {
            "name": "Tên sản phẩm",
            "price": 1000000.0,
            "discount": 800000.0,
            "link": "https://merchant.example/p",
            "image": "https://cdn.example/p.jpg",
            "category_name": "Sức khỏe",
            "brand": "Brand",
        }

    monkeypatch.setattr("affilipilot.accesstrade.product_detail._request_json", fake_request_json)
    data = fetch_product_detail(config=AccesstradeConfig(token="tok"), merchant="fpt_longchau", product_id="00033675--80799010-N-1")

    assert data["ok"] is True
    assert "/v1/product_detail?" in seen["url"]
    assert "merchant=fpt_longchau" in seen["url"]
    assert data["product"]["title"] == "Tên sản phẩm"
    assert data["product"]["discount_vnd"] == 800000
    assert data["product"]["source"] == "accesstrade_product_detail"


def test_order_list_uses_60_second_cache(monkeypatch):
    _ORDER_LIST_CACHE.clear()
    calls = []

    def fake_request_json(url, *, token, timeout=30):
        calls.append(url)
        return {"total": 1, "data": [{"order_id": "o1", "merchant": "shopee", "billing": 100000, "pub_commission": 5000}]}

    monkeypatch.setattr("affilipilot.accesstrade.reports._request_json", fake_request_json)
    monkeypatch.setattr("affilipilot.accesstrade.reports._rate_limit_pause", lambda: None)

    config = AccesstradeConfig(token="tok")
    first = fetch_order_list(config=config, since="2026-05-01T00:00:00Z", until="2026-05-27T00:00:00Z")
    second = fetch_order_list(config=config, since="2026-05-01T00:00:00Z", until="2026-05-27T00:00:00Z")

    assert first["orders"] == second["orders"]
    assert len(calls) == 1
