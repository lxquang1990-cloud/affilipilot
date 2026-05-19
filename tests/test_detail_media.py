from affilipilot.scanner.detail_media import extract_detail_media_from_html


def test_extract_detail_media_finds_lazada_gallery_and_video():
    html = r'''
    <html><head><meta property="og:title" content="Sản phẩm tốt"></head>
    <script>
    window.__data = {"gallery":["https:\/\/img.lazcdn.com\/g\/p\/a.jpg_200x200q80.jpg","https:\/\/img.lazcdn.com\/g\/p\/b.jpg_200x200q80.jpg"],"video":"https:\/\/cdn.example.com\/v.mp4"}
    </script></html>
    '''
    result = extract_detail_media_from_html(html, base_url="https://www.lazada.vn/products/pdp-i1.html")
    assert result.qualified
    assert len(result.image_urls) == 2
    assert all("_720x720q80" in url for url in result.image_urls)
    assert result.video_urls == ["https://cdn.example.com/v.mp4"]
