from affilipilot.cli import main
from affilipilot.marketplaces import classify_url, discovery_advice
from affilipilot.marketplaces.lazada import LazadaAdapter
from affilipilot.marketplaces.shopee import ShopeeAdapter


def test_lazada_classifies_product_vs_tag_and_navigation():
    adapter = LazadaAdapter()
    product = adapter.classify_url("https://www.lazada.vn/products/khan-sua-cotton-i123-s456.html?spm=a2o4n")
    assert product.kind == "product"
    assert product.is_product

    tag = adapter.classify_url("https://www.lazada.vn/tag/khan-sua-em-be/")
    assert tag.kind == "tag"
    assert tag.is_channel
    assert "lazada_tag_page_requires_discovery" in tag.reasons

    support = adapter.classify_url("https://helpcenter.lazada.vn/s/faq")
    assert support.kind == "blocked"
    assert "lazada_navigation_or_support_url" in support.reasons


def test_lazada_channel_advice_requires_discovery_not_conversion():
    advice = discovery_advice("https://www.lazada.vn/tag/khan-sua-em-be/")
    assert not advice.ok
    assert advice.action == "discover_product_details"
    assert "browser-discover" in advice.command_hint


def test_shopee_classifies_product_shortlink_and_search():
    adapter = ShopeeAdapter()
    product = adapter.classify_url("https://shopee.vn/ao-cho-be-i.123456.987654")
    assert product.kind == "product"
    assert product.is_product

    shortlink = adapter.classify_url("https://s.shopee.vn/abc123")
    assert shortlink.kind == "shortlink"
    assert "shopee_shortlink_requires_resolution_before_validation" in shortlink.reasons

    search = adapter.classify_url("https://shopee.vn/search?keyword=khan%20sua")
    assert search.kind == "search"
    assert search.is_channel


def test_marketplace_classify_cli(capsys):
    code = main(["marketplace-classify", "--url", "https://www.lazada.vn/tag/khan-sua-em-be/", "--allow-needs-discovery"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Marketplace: LAZADA" in out
    assert "Kind: tag" in out
    assert "Action: discover_product_details" in out
