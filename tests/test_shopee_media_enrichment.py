from affilipilot.scanner.enrich import enrich_product_from_url, extract_shopee_product_media


def test_extract_shopee_product_media_from_embedded_pdp_data():
    html = '''
    <meta property="og:image" content="https://down-vn.img.susercontent.com/file/vn-11134207-81ztc-mmu14tpbpon5d8"/>
    <script>{"item":{"images":["vn-11134207-820l4-mes03lxtdfd0e7","vn-11134207-820l4-mes03ly3efb858"],
    "video_info_list":[{"formats":[{"url":"https://down-cvs-sg.vod.susercontent.com/api/v4/11110105/mms/vn-11110105-abc.1600003.mp4"}],
    "default_format":{"url":"https://mms.vod.susercontent.com/api/v4/11110105/mms/vn-11110105-abc.default.mp4"}}]}}</script>
    <img src="https://deo.shopeemobile.com/shopee/shopee-mobilemall-live-sg/assets/ios_splash_screen_640x1136.png" />
    '''
    media = extract_shopee_product_media(html)
    assert media["image_urls"] == [
        "https://down-vn.img.susercontent.com/file/vn-11134207-81ztc-mmu14tpbpon5d8",
        "https://down-vn.img.susercontent.com/file/vn-11134207-820l4-mes03lxtdfd0e7",
        "https://down-vn.img.susercontent.com/file/vn-11134207-820l4-mes03ly3efb858",
    ]
    assert all("splash" not in url for url in media["image_urls"])
    assert media["video_urls"] == [
        "https://down-cvs-sg.vod.susercontent.com/api/v4/11110105/mms/vn-11110105-abc.1600003.mp4",
        "https://mms.vod.susercontent.com/api/v4/11110105/mms/vn-11110105-abc.default.mp4",
    ]


def test_shopee_enrich_does_not_fallback_to_generic_splash_images(monkeypatch):
    from affilipilot.scanner import enrich

    html = '''
    <html><head><meta property="og:title" content="Máy xay mini" /></head>
    <img src="https://deo.shopeemobile.com/shopee/shopee-mobilemall-live-sg/assets/ios_splash_screen_640x1136.png" />
    <img src="https://deo.shopeemobile.com/shopee/shopee-mobilemall-live-sg/assets/ios_splash_screen_750x1334.png" />
    </html>
    '''

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResponse:
        headers = FakeHeaders()
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return html.encode("utf-8")

    monkeypatch.setattr(enrich, "enrich_shopee_public_api_media", lambda url, timeout=8: {"image_urls": [], "video_urls": [], "price_vnd": None, "error": "blocked"})
    monkeypatch.setattr(enrich.urllib.request, "urlopen", lambda req, timeout=30: FakeResponse())
    monkeypatch.setattr(enrich, "parse_products_from_html", lambda *args, **kwargs: [])

    product = enrich_product_from_url("https://shopee.vn/product/371008594/3988083571", title="Máy xay mini")

    assert product.get("image_urls") in (None, [])
    assert "splash" not in " ".join(product.get("image_urls") or [])
