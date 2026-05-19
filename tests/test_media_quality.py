from pathlib import Path

from affilipilot.media_quality import evaluate_media_quality, upgrade_lazada_image_url


def test_upgrade_lazada_thumbnail_url():
    url = "https://img.lazcdn.com/g/p/abc.jpg_200x200q80.jpg"
    assert upgrade_lazada_image_url(url).endswith("abc.jpg_720x720q80.jpg")


def test_media_quality_blocks_small_jpeg_fixture(tmp_path):
    # Minimal JPEG SOF0 with 200x200 dimensions for parser regression.
    img = tmp_path / "small.jpg"
    img.write_bytes(
        b"\xff\xd8"
        b"\xff\xc0\x00\x11\x08\x00\xc8\x00\xc8\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        b"\xff\xd9"
    )
    post = {"files": {"image": str(img)}, "media": {"local_path": str(img)}, "product": {"image_url": "https://img.lazcdn.com/g/p/abc.jpg_200x200q80.jpg"}}
    result = evaluate_media_quality(post)
    assert not result.passed
    assert "media_image_too_small:200x200" in result.reasons
    assert "media_remote_thumbnail_url" in result.reasons


def test_media_quality_blocks_shopee_splash_asset(tmp_path):
    img = tmp_path / "ios_splash_screen_640x1136.png"
    img.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x02\x80\x00\x00\x04\x70\x08\x02\x00\x00\x00"
        b"\x00\x00\x00\x00"
    )
    post = {"files": {"image": str(img)}, "media": {"local_path": str(img)}, "product": {"image_url": "https://deo.shopeemobile.com/shopee/shopee-mobilemall-live-sg/assets/ios_splash_screen_640x1136.png"}}
    result = evaluate_media_quality(post)
    assert not result.passed
    assert "media_non_product_asset" in result.reasons
