from affilipilot.analytics.insights_sync import sync_published_facebook_insights
from affilipilot.db import AffiliPilotDB
from affilipilot.engagement import CommentRecord, ignore_comment, save_comment
from affilipilot.publishing.dispatch import dispatch_publish_strategy
from affilipilot.publishing.lifecycle import record_publish_event
from affilipilot.telegram.commands import TelegramIntent, parse_telegram_text


def test_dispatch_uses_reel_publisher(monkeypatch, tmp_path):
    called = {}

    def fake_reel(**kwargs):
        called.update(kwargs)
        return {"ok": True, "status": 200, "response": {"id": "fb_reel_1"}, "endpoint": "/page/video_reels"}

    monkeypatch.setattr("affilipilot.publishing.dispatch.publish_reel_post", fake_reel)
    result = dispatch_publish_strategy(
        {"endpoint": "/page/video_reels"},
        {"strategy": "reel_primary", "description": "caption", "local_video_path": str(tmp_path / "v.mp4"), "url": "https://shorten.asia/x"},
    )
    assert result["ok"] is True
    assert called["description"] == "caption"


def test_aff_reply_and_ignore_commands_parse():
    reply = parse_telegram_text("/aff_reply cmt_1 Dạ mình gửi link nhé")
    assert reply.intent == TelegramIntent.AFF_REPLY
    assert reply.args["comment_id"] == "cmt_1"
    assert reply.args["message"] == "Dạ mình gửi link nhé"
    ignore = parse_telegram_text("/aff_ignore cmt_1")
    assert ignore.intent == TelegramIntent.AFF_IGNORE
    assert ignore.args["comment_id"] == "cmt_1"


def test_ignore_comment_updates_status(tmp_path):
    db = tmp_path / "aff.db"
    save_comment(db, CommentRecord(platform="facebook_page", post_id="post_1", provider_post_id="fb_1", comment_id="cmt_1", message="xin giá"))
    result = ignore_comment(db, comment_id="cmt_1")
    assert result["ok"] is True
    assert result["comment"]["status"] == "ignored"


def test_scheduled_insights_sync_uses_published_tasks(monkeypatch, tmp_path):
    db = tmp_path / "aff.db"
    record_publish_event(
        db,
        batch_key="batch_1",
        post_id="post_1",
        state="published",
        facebook_post_id="fb_1",
        payload={"publish_type": "reel", "metrics_profile": "reel"},
    )

    class Metric:
        platform = "facebook_page"
        post_id = "post_1"
        provider_post_id = "fb_1"
        impressions = 10
        reach = 8
        clicks = 2
        reactions = 1
        comments = 0
        shares = 0
        raw = {"ok": True}

    monkeypatch.setattr("affilipilot.analytics.insights_sync.fetch_facebook_post_metric", lambda provider_post_id, post_id="": Metric())
    summary = sync_published_facebook_insights(db, batch_key="batch_1")
    assert summary["synced"] == 1
    rows = AffiliPilotDB(db).connect().execute("SELECT publish_type, metrics_profile FROM social_metrics").fetchall()
    assert rows[0]["publish_type"] == "reel"
    assert rows[0]["metrics_profile"] == "reel"


def test_reel_upload_phase_error_falls_back_to_video_post(monkeypatch, tmp_path):
    from affilipilot.publishing import dispatch

    def fake_reel(**kwargs):
        return {
            "ok": False,
            "status": 400,
            "response": {"error": {"code": 100, "message": "(#100) The parameter upload_phase is required."}},
        }

    def fake_video(**kwargs):
        return {"ok": True, "status": 200, "response": {"id": "video_1"}, "endpoint": "/page/videos"}

    monkeypatch.setattr(dispatch, "publish_reel_post", fake_reel)
    monkeypatch.setattr(dispatch, "publish_video_post", fake_video)

    result = dispatch.dispatch_publish_strategy(
        {"endpoint": "/page/video_reels"},
        {"strategy": "reel_primary", "description": "caption", "local_video_path": str(tmp_path / "v.mp4"), "url": "https://shorten.asia/x"},
    )

    assert result["ok"] is True
    assert result["fallback_from"] == "video_reels"
    assert result["fallback_reason"] == "facebook_reels_upload_flow_unavailable"


def test_reel_comment_image_failure_keeps_primary_publish_ok(monkeypatch, tmp_path):
    from affilipilot.publishing import dispatch

    def fake_reel(**kwargs):
        return {"ok": True, "status": 200, "response": {"id": "reel_1"}}

    def fake_comments(**kwargs):
        return {"ok": False, "status": 403, "results": []}

    monkeypatch.setattr(dispatch, "publish_reel_post", fake_reel)
    monkeypatch.setattr(dispatch, "publish_gallery_comment", fake_comments)

    result = dispatch.dispatch_publish_strategy(
        {"endpoint": "/page/video_reels"},
        {
            "strategy": "reel_primary_with_image_comment",
            "description": "caption",
            "local_video_path": str(tmp_path / "v.mp4"),
            "url": "https://shorten.asia/x",
            "local_image_paths": [str(tmp_path / "p.jpg")],
        },
    )

    assert result["ok"] is True
    assert result["status_detail"] == "published_with_image_comment_warning"
    assert "image_comment_failed" in result["warnings"]
