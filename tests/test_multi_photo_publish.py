from pathlib import Path

from affilipilot.media import prepare_product_media_gallery
from affilipilot.publishing.facebook_plan import build_graph_payload


def _jpeg(width: int, height: int) -> bytes:
    return b"\xff\xd8\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9"


def test_prepare_product_media_gallery_returns_multiple_quality_images(monkeypatch, tmp_path):
    def fake_fetch(url, out_dir, *, name_hint="product", timeout=30):
        from affilipilot.media import validate_image_path
        path = Path(out_dir) / (url.rsplit("/", 1)[-1])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_jpeg(800, 800))
        return validate_image_path(path)

    monkeypatch.setattr("affilipilot.media.fetch_image", fake_fetch)
    results = prepare_product_media_gallery({"image_urls": ["https://cdn/1.jpg", "https://cdn/2.jpg"]}, tmp_path)
    assert len(results) == 2
    assert all(item.ok for item in results)


def test_facebook_plan_uses_multi_photo_strategy_for_multiple_images():
    graph = build_graph_payload(
        page_id="page",
        message="hello",
        link="https://go.isclix.com/deep_link/v5/a?x=1",
        image_path="one.jpg",
        image_paths=["one.jpg", "two.jpg"],
    )
    assert graph["strategy"] == "multi_photo"
    assert graph["endpoint"] == "/page/feed"
    assert graph["payload"]["local_image_paths"] == ["one.jpg", "two.jpg"]
