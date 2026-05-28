from affilipilot.scanner.enrich import enrich_product_from_url, enrich_shopee_public_api_media, extract_shopee_product_media


def test_extract_shopee_product_media_finds_default_format_video_url():
    html = '''
    <script>{"item":{"images":["vn-11134207-820l4-mes03lxtdfd0e7"],
    "video_info_list":[{"default_format":{"url":"https://down-cvs-sg.vod.susercontent.com/api/v4/11110105/mms/vn-video.default.mp4"}}]}}</script>
    '''
    media = extract_shopee_product_media(html)
    assert media["image_urls"] == ["https://down-vn.img.susercontent.com/file/vn-11134207-820l4-mes03lxtdfd0e7"]
    assert media["video_urls"] == ["https://down-cvs-sg.vod.susercontent.com/api/v4/11110105/mms/vn-video.default.mp4"]


def test_enrich_shopee_public_api_media_returns_video_and_price(monkeypatch):
    class FakeProduct:
        image_urls = ["https://down-vn.img.susercontent.com/file/img1"]
        video_urls = ["https://down-cvs-sg.vod.susercontent.com/api/v4/v.mp4"]
        price_vnd = 175000

    monkeypatch.setattr("affilipilot.scanner.enrich.get_product_detail", lambda shop_id, item_id, timeout=30: FakeProduct())

    media = enrich_shopee_public_api_media("https://shopee.vn/product/123470472/3716728845")

    assert media["price_vnd"] == 175000
    assert media["video_urls"] == ["https://down-cvs-sg.vod.susercontent.com/api/v4/v.mp4"]
    assert media["media_source"] == "shopee_public_api"


def test_enrich_product_from_url_prefers_shopee_api_video_and_price(monkeypatch):
    html = '<html><script>{"images":["vn-11134207-820l4-mes03lxtdfd0e7"]}</script></html>'

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResp:
        headers = FakeHeaders()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return html.encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=30: FakeResp())
    monkeypatch.setattr("affilipilot.scanner.enrich.parse_products_from_html", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "affilipilot.scanner.enrich.enrich_shopee_public_api_media",
        lambda url: {
            "image_urls": ["https://down-vn.img.susercontent.com/file/img-api"],
            "video_urls": ["https://down-cvs-sg.vod.susercontent.com/api/v4/v.mp4"],
            "price_vnd": 175000,
            "media_source": "shopee_public_api",
            "media_confidence": "official",
        },
    )

    product = enrich_product_from_url("https://shopee.vn/product/123470472/3716728845")

    assert product["price_vnd"] == 175000
    assert product["video_url"] == "https://down-cvs-sg.vod.susercontent.com/api/v4/v.mp4"
    assert product["video_urls"] == ["https://down-cvs-sg.vod.susercontent.com/api/v4/v.mp4"]
    assert product["media_source"] == "shopee_public_api"
