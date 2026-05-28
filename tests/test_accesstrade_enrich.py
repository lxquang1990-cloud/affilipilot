from affilipilot.accesstrade.enrich import enrich_product_from_accesstrade
from affilipilot.models import ProductCandidate


def test_enrich_product_from_accesstrade_prefers_datafeed_match(monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        assert kwargs["domain"] == "lazada.vn"
        return {
            "ok": True,
            "raw_redacted": {
                "data": [
                    {
                        "url": "https://www.lazada.vn/products/salvo-hop-i3262536517-s1.html",
                        "name": "SALVO Hộp Đựng Dung Tích Cực Lớn",
                        "cate": "storage",
                        "price": 200000,
                        "discount": 149000,
                        "discount_rate": 0.25,
                        "image": "https://img.lazcdn.com/salvo.jpg",
                        "aff_link": "https://go.isclix.com/deep_link/x",
                        "product_id": "476_1",
                        "merchant": "lazada_kol",
                    }
                ]
            },
        }

    monkeypatch.setattr("affilipilot.accesstrade.enrich.fetch_datafeeds", fake_fetch_datafeeds)
    product = ProductCandidate(
        url="https://www.lazada.vn/products/pdp-i3262536517.html",
        title="SALVO Hộp Đựng Dung Tích Cực Lớn",
        category="unknown",
    )

    enriched = enrich_product_from_accesstrade(product)

    assert enriched.price_vnd == 149000
    assert enriched.image_url == "https://img.lazcdn.com/salvo.jpg"
    assert enriched.affiliate_url == "https://go.isclix.com/deep_link/x"
    assert enriched.media_source == "accesstrade_api"
    assert "accesstrade_enriched" in enriched.notes


def test_enrich_product_from_accesstrade_computes_sale_price_from_percent_discount(monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "raw_redacted": {
                "data": [
                    {
                        "url": "https://shopee.vn/product/123470472/3716728845",
                        "name": "Kệ đựng mỹ phẩm 4 tầng trắng 30cm",
                        "price": 250000.0,
                        "discount": 30.0,
                        "discount_amount": 249970.0,
                        "discount_rate": 1.0,
                        "image": "https://cf.shopee.vn/file/x",
                        "aff_link": "https://go.isclix.com/deep_link/x",
                        "merchant": "shopee",
                    }
                ]
            },
        }

    monkeypatch.setattr("affilipilot.accesstrade.enrich.fetch_datafeeds", fake_fetch_datafeeds)
    product = ProductCandidate(
        url="https://shopee.vn/product/123470472/3716728845",
        title="Kệ đựng mỹ phẩm 4 tầng trắng 30cm",
        category="home_organization",
        price_vnd=250000,
    )

    enriched = enrich_product_from_accesstrade(product, pages=1)

    assert enriched.price_vnd == 175000


def test_enrich_product_from_accesstrade_keeps_product_when_no_reliable_match(monkeypatch):
    monkeypatch.setattr(
        "affilipilot.accesstrade.enrich.fetch_datafeeds",
        lambda **kwargs: {"ok": True, "raw_redacted": {"data": [{"url": "https://www.lazada.vn/products/other-i9.html", "name": "Khác", "price": 1}]}},
    )
    product = ProductCandidate(url="https://www.lazada.vn/products/pdp-i3262536517.html", title="SALVO Hộp Đựng")

    enriched = enrich_product_from_accesstrade(product, pages=1)

    assert enriched.price_vnd is None
    assert enriched.title == "SALVO Hộp Đựng"


def test_enrich_product_from_accesstrade_scans_multiple_pages(monkeypatch):
    calls = []

    def fake_fetch_datafeeds(**kwargs):
        calls.append(kwargs["page"])
        if kwargs["page"] == 1:
            return {"ok": True, "raw_redacted": {"data": [{"url": "https://www.lazada.vn/products/other-i9.html", "name": "Khác", "price": 1}]}}
        return {
            "ok": True,
            "raw_redacted": {
                "data": [
                    {
                        "url": "https://www.lazada.vn/products/salvo-hop-i3262536517-s1.html",
                        "name": "SALVO Hộp Đựng Dung Tích Cực Lớn",
                        "price": 200000,
                        "discount": 149000,
                        "image": "https://img.lazcdn.com/salvo.jpg",
                    }
                ]
            },
        }

    monkeypatch.setattr("affilipilot.accesstrade.enrich.fetch_datafeeds", fake_fetch_datafeeds)
    product = ProductCandidate(url="https://www.lazada.vn/products/pdp-i3262536517.html", title="SALVO Hộp Đựng Dung Tích Cực Lớn")

    enriched = enrich_product_from_accesstrade(product, pages=3)

    assert calls == [1, 2]
    assert enriched.price_vnd == 149000
