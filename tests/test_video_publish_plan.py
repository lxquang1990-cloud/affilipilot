import json
from pathlib import Path

from affilipilot.publishing.facebook_plan import build_graph_payload
from affilipilot.video_media import validate_video_path


def _mp4() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"0" * 32


def test_validate_video_path_accepts_mp4_fixture(tmp_path):
    video = tmp_path / "product.mp4"
    video.write_bytes(_mp4())
    result = validate_video_path(video)
    assert result.ok
    assert result.media_type == "mp4"


def test_graph_payload_prefers_video_with_image_comment_when_gallery_exists():
    graph = build_graph_payload(
        page_id="page",
        message="caption",
        link="https://shorten.asia/abc",
        image_paths=["a.jpg", "b.jpg"],
        video_path="product.mp4",
    )
    assert graph["endpoint"] == "/page/videos"
    assert graph["strategy"] == "video_primary_with_image_comment"
    assert graph["payload"]["local_video_path"] == "product.mp4"
    assert graph["payload"]["local_image_paths"] == ["a.jpg", "b.jpg"]


def test_graph_payload_uses_video_primary_without_gallery():
    graph = build_graph_payload(
        page_id="page",
        message="caption",
        link="https://shorten.asia/abc",
        video_path="product.mp4",
    )
    assert graph["endpoint"] == "/page/videos"
    assert graph["strategy"] == "video_primary"
