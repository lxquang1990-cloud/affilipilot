from affilipilot.publishing.media_gate import evaluate_publish_media_gate
from affilipilot.publishing.restrictions import get_platform_restriction
from affilipilot.publishing.strategy import PublishStrategy
from affilipilot.video_probe import VideoProbe


def _jpeg(path):
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    return str(path)


def test_photo_post_requires_image(tmp_path):
    strategy = PublishStrategy("facebook_page", "photo_post", "feed_post", "test")
    gate = evaluate_publish_media_gate({"files": {}, "product": {"url": "https://example.com"}}, strategy=strategy, restriction=get_platform_restriction("facebook_page", "photo_post"))
    assert gate.passed is False
    assert "photo_post_requires_image" in gate.reasons


def test_link_post_passes_with_warning():
    strategy = PublishStrategy("facebook_page", "link_post", "feed_post", "test")
    gate = evaluate_publish_media_gate({"files": {}, "product": {"url": "https://example.com"}}, strategy=strategy, restriction=get_platform_restriction("facebook_page", "link_post"))
    assert gate.passed is True
    assert "link_post_media_weak_fallback" in gate.warnings


def test_reel_requires_vertical_video(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"0" * 32)
    monkeypatch.setattr("affilipilot.publishing.media_gate.probe_video", lambda path: VideoProbe(ok=True, path=str(path), width=1280, height=720, duration_seconds=30))
    strategy = PublishStrategy("facebook_page", "reel", "reel", "test")
    gate = evaluate_publish_media_gate({"files": {"video": str(video)}, "product": {"url": "https://example.com"}}, strategy=strategy, restriction=get_platform_restriction("facebook_page", "reel"))
    assert gate.passed is False
    assert "reel_requires_vertical_video" in gate.reasons


def test_reel_blocks_long_video(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"0" * 32)
    monkeypatch.setattr("affilipilot.publishing.media_gate.probe_video", lambda path: VideoProbe(ok=True, path=str(path), width=720, height=1280, duration_seconds=120))
    strategy = PublishStrategy("facebook_page", "reel", "reel", "test")
    gate = evaluate_publish_media_gate({"files": {"video": str(video)}, "product": {"url": "https://example.com"}}, strategy=strategy, restriction=get_platform_restriction("facebook_page", "reel"))
    assert gate.passed is False
    assert any(reason.startswith("video_too_long") for reason in gate.reasons)


def test_video_post_accepts_valid_video_with_probe_warning(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"0" * 32)
    monkeypatch.setattr("affilipilot.publishing.media_gate.probe_video", lambda path: VideoProbe(ok=False, path=str(path), reasons=["ffprobe_not_found"]))
    strategy = PublishStrategy("facebook_page", "video_post", "feed_video", "test")
    gate = evaluate_publish_media_gate({"files": {"video": str(video)}, "product": {"url": "https://example.com"}}, strategy=strategy, restriction=get_platform_restriction("facebook_page", "video_post"))
    assert gate.passed is True
    assert "ffprobe_not_found" in gate.warnings
