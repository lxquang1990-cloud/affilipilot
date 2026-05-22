from affilipilot.publishing.strategy import select_facebook_publish_strategy
from affilipilot.video_probe import VideoProbe, probe_video


def test_probe_video_reports_missing_file(tmp_path):
    result = probe_video(tmp_path / "missing.mp4")
    assert result.ok is False
    assert "video_path_not_found" in result.reasons


def test_strategy_uses_probe_for_vertical_short_video(monkeypatch, tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"not a real video but monkeypatched")

    monkeypatch.setattr("affilipilot.publishing.strategy.probe_video", lambda path: VideoProbe(ok=True, path=str(path), width=720, height=1280, duration_seconds=30))

    strategy = select_facebook_publish_strategy({"files": {"video": str(video)}, "product": {"url": "https://example.com"}})

    assert strategy.publish_type == "reel"
    assert strategy.metrics_profile == "reel"
    assert strategy.video_width == 720
    assert strategy.video_height == 1280
    assert strategy.video_duration_seconds == 30


def test_strategy_uses_probe_for_landscape_video_post(monkeypatch, tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"not a real video but monkeypatched")

    monkeypatch.setattr("affilipilot.publishing.strategy.probe_video", lambda path: VideoProbe(ok=True, path=str(path), width=1280, height=720, duration_seconds=60))

    strategy = select_facebook_publish_strategy({"files": {"video": str(video)}, "product": {"url": "https://example.com"}})

    assert strategy.publish_type == "video_post"
    assert strategy.metrics_profile == "feed_video"


def test_strategy_keeps_explicit_reel_hint_when_probe_unavailable(monkeypatch, tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"not a real video but monkeypatched")

    monkeypatch.setattr("affilipilot.publishing.strategy.probe_video", lambda path: VideoProbe(ok=False, path=str(path), reasons=["ffprobe_not_found"]))

    strategy = select_facebook_publish_strategy({"files": {"video": str(video)}, "product": {"url": "https://example.com", "video_kind": "vertical reel"}})

    assert strategy.publish_type == "reel"
