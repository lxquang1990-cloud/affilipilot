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
    approve = handle_text_message(f"/aff_approve {post_id} ok", config)
    assert "approved" in approve.text


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
    assert [item["kind"] for item in data[1:]] == ["approval_card", "approval_card", "approval_card"]
