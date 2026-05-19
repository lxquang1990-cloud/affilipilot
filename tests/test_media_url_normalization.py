from affilipilot.media import _normalize_remote_image_url


def test_media_fetch_upgrades_lazada_thumbnail_url():
    url = "https://img.lazcdn.com/g/p/a.jpg_200x200q80.jpg"
    assert _normalize_remote_image_url(url).endswith(".jpg_720x720q80.jpg")


def test_media_fetch_keeps_https_shopee_url():
    url = "https://cf.shopee.vn/file/abc"
    assert _normalize_remote_image_url(url) == url
