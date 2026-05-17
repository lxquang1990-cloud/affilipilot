from affilipilot.scanner.discovery import discover_product_details_from_html


def test_discover_product_cards_only_keeps_detail_urls():
    html = '''
    <a href="/tag/binh-thia/"><img alt="Tag"></a>
    <a href="/products/ghe-an-dam-i123-s456.html"><img src="https://img.lazcdn.com/media/catalog/product/ghe.jpg" alt="Ghế ăn dặm"><span>299.000đ</span></a>
    '''
    result = discover_product_details_from_html(html, page_url="https://www.lazada.vn/mother-baby/", source="LAZADA", category="feeding")
    assert len(result.items) == 1
    item = result.items[0]
    assert item.url == "https://www.lazada.vn/products/ghe-an-dam-i123-s456.html"
    assert item.image_url.endswith("ghe.jpg")
    assert item.raw["media_source"] == "product_card_image"
    assert item.raw["media_confidence"] == "high"


def test_discover_lazada_links_from_embedded_json():
    html = r'''{"url":"https:\/\/www.lazada.vn\/products\/binh-thia-i11-s22.html?spm=x"}'''
    result = discover_product_details_from_html(html, page_url="https://www.lazada.vn/tag/binh-thia/", source="LAZADA", category="feeding")
    assert [item.url for item in result.items] == ["https://www.lazada.vn/products/binh-thia-i11-s22.html"]
    assert result.items[0].notes == "product_url_discovery"
