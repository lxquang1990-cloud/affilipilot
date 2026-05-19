from pathlib import Path

from affilipilot.media import prepare_product_media
from affilipilot.scanner.discovery import discover_product_details_from_html
from affilipilot.sources.manual_input import parse_link_lines


def _jpeg(width: int, height: int) -> bytes:
    return b"\xff\xd8\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9"


def test_discovery_extracts_image_gallery_and_video_urls():
    html = """
    <a href="/products/pdp-i1.html">
      <img src="https://img.lazcdn.com/a.jpg_200x200q80.jpg" alt="Khăn sữa mềm" />
      <img data-src="https://img.lazcdn.com/b.jpg_200x200q80.jpg" />
      <video src="https://cdn.example/video.mp4"></video>
    </a>
    """
    result = discover_product_details_from_html(html, page_url="https://www.lazada.vn/tag/x/", source="LAZADA", category="baby_care")
    item = result.items[0]
    assert item.image_url.endswith("_720x720q80.jpg")
    assert len(item.raw["image_urls"]) == 2
    assert item.raw["video_urls"] == ["https://cdn.example/video.mp4"]


def test_manual_input_parses_gallery_fields():
    product = parse_link_lines("https://x | image_urls=https://a,https://b | video_urls=https://v1,https://v2")[0]
    assert product.image_urls == ["https://a", "https://b"]
    assert product.video_urls == ["https://v1", "https://v2"]


def test_prepare_product_media_chooses_first_quality_gallery_image(monkeypatch, tmp_path):
    def fake_fetch(url, out_dir, *, name_hint="product", timeout=30):
        from affilipilot.media import MediaResult, validate_image_path
        path = Path(out_dir) / ("small.jpg" if "small" in url else "large.jpg")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_jpeg(200, 200) if "small" in url else _jpeg(800, 800))
        return validate_image_path(path)

    monkeypatch.setattr("affilipilot.media.fetch_image", fake_fetch)
    result = prepare_product_media({"title": "x", "image_urls": ["https://cdn/small.jpg", "https://cdn/large.jpg"]}, tmp_path)
    assert result.ok
    assert result.local_path.endswith("large.jpg")
