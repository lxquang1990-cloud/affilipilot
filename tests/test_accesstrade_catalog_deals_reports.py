import sqlite3

from affilipilot.accesstrade.catalog import AccesstradeConfig, _product_from_item, fetch_datafeeds, write_products_input
from affilipilot.accesstrade.deals import match_deals_for_product
from affilipilot.accesstrade.reports import save_orders, summarize_orders


def test_datafeed_product_to_input(tmp_path):
    item = {
        "url": "https://www.lazada.vn/products/a.html",
        "name": "Khăn sữa em bé",
        "cate": "baby_care",
        "price": 120000,
        "discount": 89000,
        "discount_rate": 25,
        "image": "https://cdn.example/a.jpg",
        "aff_link": "https://go.isclix.com/deep_link/a",
        "product_id": "sku1",
        "merchant": "lazada",
    }
    product = _product_from_item(item, source="accesstrade_datafeed")
    assert product.title == "Khăn sữa em bé"
    assert product.discount_vnd == 89000
    out = write_products_input([product.__dict__], tmp_path / "input.txt")
    text = out.read_text(encoding="utf-8")
    assert "title=Khăn sữa em bé" in text
    assert "affiliate_url=https://go.isclix.com/deep_link/a" in text
    assert "media_source=accesstrade_api" in text


def test_fetch_datafeeds_supports_category_param(monkeypatch):
    seen = {}
    def fake_request_json(url, *, token, timeout=30):
        seen["url"] = url
        return {"data": []}
    monkeypatch.setattr("affilipilot.accesstrade.catalog._request_json", fake_request_json)
    data = fetch_datafeeds(config=AccesstradeConfig(token="tok"), domain="lazada.vn", cat="thiet-bi-gia-dung", limit=3)
    assert data["ok"] is True
    assert "cat=thiet-bi-gia-dung" in seen["url"]


def test_match_active_deals_for_product():
    product = {"url": "https://www.lazada.vn/products/a.html", "merchant": "lazada", "category": "baby_care"}
    deals = [
        {"merchant": "lazada", "domain": "lazada.vn", "discount_value": "20000", "active_hint": True},
        {"merchant": "shopee", "domain": "shopee.vn", "discount_value": "10000", "active_hint": True},
        {"merchant": "lazada", "domain": "lazada.vn", "discount_value": "5000", "active_hint": False},
    ]
    matched = match_deals_for_product(product, deals)
    assert len(matched) == 1
    assert matched[0]["discount_value"] == "20000"


def test_save_and_summarize_orders(tmp_path):
    db = tmp_path / "affilipilot.db"
    orders = [
        {"order_id": "o1", "merchant": "lazada", "billing": 100000, "pub_commission": 5000, "utm_content": "post_1", "raw": {"x": 1}},
        {"order_id": "o2", "merchant": "lazada", "billing": 200000, "pub_commission": 10000, "utm_content": "post_2", "raw": {"x": 2}},
    ]
    assert save_orders(db, orders) == 2
    summary = summarize_orders(db)
    assert summary["total_orders"] == 2
    assert summary["commission"] == 15000
    assert summary["by_merchant"][0]["merchant"] == "lazada"
    with sqlite3.connect(db) as conn:
        assert conn.execute("select count(*) from accesstrade_orders").fetchone()[0] == 2
