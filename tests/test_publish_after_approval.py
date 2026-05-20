from affilipilot.publishing.auto_publish_after_approval import publish_after_approval
from affilipilot.publishing.lifecycle import latest_publish_events
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post


def _ready_batch(tmp_path, db):
    image = tmp_path / "product.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        "https://shorten.asia/abc123 | title=Hộp đựng đồ chơi trẻ em gấp gọn có nắp | "
        f"category=storage | price=159000 | image_path={image} | "
        "media_source=product_card_image | media_confidence=high | "
        "campaign_id=4751584435713464237",
        encoding="utf-8",
    )
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    Outbox(tmp_path / "outbox.json").save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])


def test_publish_after_approval_runs_publish_safe_then_publishes(tmp_path, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    _ready_batch(tmp_path, db)

    calls = []
    def fake_publisher(item, payload):
        calls.append((item, payload))
        return {"ok": True, "status": 200, "response": {"id": "fb_123"}, "endpoint": item["endpoint"]}

    result = publish_after_approval(
        db_path=db,
        batch_key="batch",
        post_id="post_20260516_001",
        outbox_path=tmp_path / "outbox.json",
        out_dir=tmp_path / "publish",
        publisher=fake_publisher,
    )

    assert result["ok"] is True
    assert result["facebook_post_id"] == "fb_123"
    assert calls
    assert (tmp_path / "publish" / "facebook-plan.json").exists()
    assert (tmp_path / "publish" / "publish-post_20260516_001.json").exists()
    assert latest_publish_events(db, batch_key="batch")["post_20260516_001"]["state"] == "published"


def test_publish_after_approval_blocks_when_delivery_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    _ready_batch(tmp_path, db)
    Outbox(tmp_path / "outbox.json").save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="pending"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="pending"),
    ])

    result = publish_after_approval(
        db_path=db,
        batch_key="batch",
        post_id="post_20260516_001",
        outbox_path=tmp_path / "outbox.json",
        out_dir=tmp_path / "publish",
        publisher=lambda item, payload: (_ for _ in ()).throw(AssertionError("must not publish")),
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert any(reason.startswith("delivery_not_delivered") for reason in result["reasons"])
    assert latest_publish_events(db, batch_key="batch")["post_20260516_001"]["state"] == "failed"
