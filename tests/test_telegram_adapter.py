import json
from pathlib import Path

from affilipilot.telegram.adapter import AdapterConfig, handle_text_message
from affilipilot.telegram.commands import TelegramIntent, parse_telegram_text


def test_parse_raw_links_as_create_batch():
    parsed = parse_telegram_text("https://shopee.vn/a | title=Giỏ sắp xếp | category=storage | price=129000 | image_url=https://cdn.example/test.jpg")
    assert parsed.intent == TelegramIntent.CREATE_BATCH


def test_parse_approval_command():
    parsed = parse_telegram_text("/aff_approve post_20260516_001 ok")
    assert parsed.intent == TelegramIntent.APPROVE
    assert parsed.args["post_id"] == "post_20260516_001"


def test_parse_quick_approval_reply():
    parsed = parse_telegram_text("ok")
    assert parsed.intent == TelegramIntent.APPROVE
    assert parsed.args["post_id"] == "latest"

    parsed = parse_telegram_text("sửa")
    assert parsed.intent == TelegramIntent.NEEDS_EDIT
    assert parsed.args["post_id"] == "latest"


def test_adapter_create_status_and_approve(tmp_path):
    config = AdapterConfig(db_path=tmp_path / "affilipilot.db", work_dir=tmp_path / "work", limit=1)
    result = handle_text_message("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/storage.jpg", config)
    assert result.intent == TelegramIntent.CREATE_BATCH
    assert "batch created" in result.text
    assert result.attachments and result.attachments[0].exists()

    status = handle_text_message("/status", config)
    assert "pending" in status.text

    # Shorthand approval must use the real generated post id; fabricated ids are rejected
    # instead of being rebound to an unrelated pending post.
    reject_unknown = handle_text_message("/aff_approve post_20260516_001 ok", config)
    assert "Approval not found" in reject_unknown.text

    import re
    post_id = re.search(r"post_[^\s:]+", status.text).group(0)
    approve = handle_text_message("ok", config)
    assert "approved" in approve.text
    assert post_id in approve.text


def test_adapter_queues_telegram_outbox_for_raw_links(tmp_path):
    outbox = tmp_path / "outbox.json"
    config = AdapterConfig(db_path=tmp_path / "affilipilot.db", work_dir=tmp_path / "work", limit=3, outbox_path=outbox)
    result = handle_text_message("\n".join([
        "https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/storage.jpg",
        "https://shopee.vn/b | title=Yếm ăn dặm silicone mềm | category=feeding | price=79000 | image_url=https://cdn.example/bib.jpg",
        "https://shopee.vn/c | title=Khăn sữa cotton mềm | category=baby-care | price=59000 | image_url=https://cdn.example/towel.jpg",
    ]), config)

    assert result.intent == TelegramIntent.CREATE_BATCH
    assert "Telegram outbox queued: 4 messages" in result.text
    assert outbox.exists()
    data = json.loads(outbox.read_text(encoding="utf-8"))
    assert len(data) == 4
    assert data[0]["kind"] == "summary"
    assert "Reply on a card: ok / no / sửa / ban" in data[0]["text"]
    assert [item["kind"] for item in data[1:]] == ["approval_card", "approval_card", "approval_card"]


def test_single_card_batch_queues_only_concise_card(tmp_path):
    outbox = tmp_path / "outbox.json"
    config = AdapterConfig(db_path=tmp_path / "affilipilot.db", work_dir=tmp_path / "work", limit=1, outbox_path=outbox)
    result = handle_text_message(
        "https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/storage.jpg",
        config,
    )

    assert result.intent == TelegramIntent.CREATE_BATCH
    assert "Telegram outbox queued: 1 messages" in result.text
    data = json.loads(outbox.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["kind"] == "approval_card"
    assert "Reply: ok = approve+publish" in data[0]["text"]
    assert "Fallback: /aff_approve" in data[0]["text"]
    assert "| /aff_reject" not in data[0]["text"]


def test_auto_publish_resolves_batch_specific_outbox_for_quick_reply(tmp_path, monkeypatch):
    from affilipilot.db import AffiliPilotDB
    from affilipilot.telegram.delivery import Outbox, OutboxMessage
    from affilipilot.telegram import adapter

    db_path = tmp_path / "data" / "affilipilot.db"
    db_path.parent.mkdir(parents=True)
    batch_key = "auto-source-scheduled-test"
    post_id = "post_1"
    manifest = {
        "posts": [
            {
                "post_id": post_id,
                "approval_eligible": True,
                "product": {"url": "https://shopee.vn/product/1/2", "title": "Khăn giấy", "image_url": "https://cdn.example/p.jpg"},
                "files": {},
            }
        ]
    }
    AffiliPilotDB(db_path).save_batch(batch_key, "fixture", manifest)

    batch_outbox = tmp_path / "data" / "outbox" / f"{batch_key}.json"
    Outbox(batch_outbox).save([OutboxMessage(id=f"{batch_key}:{post_id}", kind="approval_card", text="card")])
    generic_outbox = tmp_path / "data" / "outbox.json"
    Outbox(generic_outbox).save([])

    calls = {}

    def fake_publish_after_approval(**kwargs):
        calls["outbox_path"] = kwargs["outbox_path"]
        calls["out_dir"] = kwargs["out_dir"]
        return {"ok": True, "status": "published", "batch_key": batch_key, "post_id": post_id, "facebook_post_id": "fb_1", "result_path": str(tmp_path / "publish.json"), "reasons": [], "publish_safe": {"ok": True}}

    monkeypatch.setattr(adapter, "publish_after_approval", fake_publish_after_approval)

    cfg = AdapterConfig(
        db_path=db_path,
        work_dir=tmp_path,
        outbox_path=generic_outbox,
        publish_dir=tmp_path / "publish",
        auto_publish_on_approve=True,
        approval_receipt="telegram:640968010:19674",
    )
    result = handle_text_message("ok", cfg)

    assert "approved" in result.text
    assert "Auto-publish failed" not in result.text
    assert calls["outbox_path"] == batch_outbox
    assert calls["out_dir"] == tmp_path / "publish" / batch_key
    data = json.loads(batch_outbox.read_text(encoding="utf-8"))
    assert data[0]["status"] == "delivered"


def test_auto_publish_scopes_shared_telegram_publish_dir_by_batch_for_quick_reply(tmp_path, monkeypatch):
    from affilipilot.db import AffiliPilotDB
    from affilipilot.telegram.delivery import Outbox, OutboxMessage
    from affilipilot.telegram import adapter

    db_path = tmp_path / "data" / "affilipilot.db"
    db_path.parent.mkdir(parents=True)
    batch_key = "auto-source-scheduled-20260610-0700"
    post_id = "post_20260610_0700_mini_blender_001"
    manifest = {
        "posts": [
            {
                "post_id": post_id,
                "approval_eligible": True,
                "product": {"url": "https://shopee.vn/product/1/2", "title": "Máy xay mini", "image_url": "https://cdn.example/p.jpg"},
                "files": {},
            }
        ]
    }
    AffiliPilotDB(db_path).save_batch(batch_key, "fixture", manifest)

    batch_outbox = tmp_path / "data" / "outbox" / f"{batch_key}.json"
    Outbox(batch_outbox).save([OutboxMessage(id=f"{batch_key}:{post_id}", kind="approval_card", text="card", status="delivered")])
    shared_publish_dir = tmp_path / "data" / "publish" / "telegram"
    shared_publish_dir.mkdir(parents=True)
    (shared_publish_dir / "facebook-plan.json").write_text('{"batch_key":"stale-other-batch","plans":[]}', encoding="utf-8")

    calls = {}

    def fake_publish_after_approval(**kwargs):
        calls["out_dir"] = kwargs["out_dir"]
        assert kwargs["out_dir"] != shared_publish_dir
        assert kwargs["out_dir"] == shared_publish_dir / batch_key
        return {"ok": True, "status": "published", "batch_key": batch_key, "post_id": post_id, "facebook_post_id": "fb_1", "result_path": str(kwargs["out_dir"] / "publish.json"), "reasons": [], "publish_safe": {"ok": True}}

    monkeypatch.setattr(adapter, "publish_after_approval", fake_publish_after_approval)

    result = handle_text_message(
        "ok",
        AdapterConfig(
            db_path=db_path,
            work_dir=tmp_path,
            outbox_path=tmp_path / "data" / "outbox.json",
            publish_dir=shared_publish_dir,
            auto_publish_on_approve=True,
            approval_receipt="telegram:640968010:20237",
        ),
    )

    assert "approved" in result.text
    assert "Auto-publish failed" not in result.text
    assert calls["out_dir"] == shared_publish_dir / batch_key
    assert (shared_publish_dir / "facebook-plan.json").read_text(encoding="utf-8") == '{"batch_key":"stale-other-batch","plans":[]}'
