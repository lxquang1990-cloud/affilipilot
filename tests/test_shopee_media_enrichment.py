from affilipilot.scanner.enrich import extract_shopee_product_media


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
