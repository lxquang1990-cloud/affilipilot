import json

from affilipilot.cli import main
from affilipilot.telegram.outbox import Outbox, OutboxMessage


def test_facebook_publish_requires_sent_telegram_outbox(tmp_path, monkeypatch, capsys):
    plan = {
        "batch_key": "batch-1",
        "plans": [
            {
                "post_id": "post_1",
                "status": "publishable_dry_run",
                "endpoint": "/page/feed",
                "payload_preview": {"message": "hello", "link": "https://go.isclix.com/x"},
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    outbox_path = tmp_path / "outbox.json"
    outbox = Outbox(outbox_path)
    outbox.save([
        OutboxMessage(id="batch-1:summary", kind="summary", text="summary", status="pending"),
        OutboxMessage(id="batch-1:post_1", kind="approval_card", text="card", status="pending"),
    ])

    try:
        main([
            "facebook-publish-one",
            "--plan", str(plan_path),
            "--post-id", "post_1",
            "--out", str(tmp_path / "result.json"),
            "--require-telegram-sent",
            "--outbox", str(outbox_path),
            "--batch-key", "batch-1",
        ])
    except SystemExit as exc:
        assert "not marked sent" in str(exc)
    else:
        raise AssertionError("publish should have been blocked")


def test_facebook_publish_allows_sent_telegram_outbox(tmp_path, monkeypatch):
    plan = {
        "batch_key": "batch-1",
        "plans": [
            {
                "post_id": "post_1",
                "status": "publishable_dry_run",
                "endpoint": "/page/feed",
                "payload_preview": {"message": "hello", "link": "https://go.isclix.com/x"},
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch-1:summary", kind="summary", text="summary", status="sent"),
        OutboxMessage(id="batch-1:post_1", kind="approval_card", text="card", status="sent"),
    ])

    import affilipilot.cli as cli
    monkeypatch.setattr(cli, "publish_post", lambda post_text, link: {"ok": True, "status": 200, "response": {"id": "fb_1"}, "endpoint": "/page/feed"})

    code = main([
        "facebook-publish-one",
        "--plan", str(plan_path),
        "--post-id", "post_1",
        "--out", str(tmp_path / "result.json"),
        "--require-telegram-sent",
        "--outbox", str(outbox_path),
        "--batch-key", "batch-1",
    ])
    assert code == 0
