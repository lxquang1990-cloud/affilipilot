from affilipilot.telegram.adapter import AdapterConfig, handle_text_message
from affilipilot.telegram.commands import TelegramIntent, parse_telegram_text
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch


def _batch(tmp_path, db):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/a.jpg", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)


def test_parse_status_commands():
    assert parse_telegram_text("/campaign_status batch").intent == TelegramIntent.CAMPAIGN_STATUS
    assert parse_telegram_text("/campaign-status batch").intent == TelegramIntent.CAMPAIGN_STATUS
    assert parse_telegram_text("/campaign batch").intent == TelegramIntent.CAMPAIGN_STATUS
    assert parse_telegram_text("/next_action batch").intent == TelegramIntent.NEXT_ACTION
    assert parse_telegram_text("/next-action batch").intent == TelegramIntent.NEXT_ACTION
    assert parse_telegram_text("/next batch").intent == TelegramIntent.NEXT_ACTION
    assert parse_telegram_text("/doctor batch").intent == TelegramIntent.DOCTOR


def test_adapter_campaign_next_doctor_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    outbox = tmp_path / "outbox.json"
    _batch(tmp_path, db)
    Outbox(outbox).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])
    cfg = AdapterConfig(db_path=db, work_dir=tmp_path / "work", outbox_path=outbox, publish_dir=tmp_path / "publish")

    campaign = handle_text_message("/campaign_status batch", cfg)
    assert campaign.intent == TelegramIntent.CAMPAIGN_STATUS
    assert "AffiliPilot campaign status" in campaign.text
    assert "NEEDS_APPROVAL" in campaign.text

    next_action = handle_text_message("/next_action batch", cfg)
    assert next_action.intent == TelegramIntent.NEXT_ACTION
    assert "AffiliPilot next action" in next_action.text

    doctor = handle_text_message("/doctor batch", cfg)
    assert doctor.intent == TelegramIntent.DOCTOR
    assert "AffiliPilot doctor" in doctor.text
    assert "token" not in doctor.text


def test_help_mentions_status_commands():
    result = handle_text_message("/help", AdapterConfig(db_path=__import__('pathlib').Path('/tmp/help.db'), work_dir=__import__('pathlib').Path('/tmp/help-work')))
    assert "/campaign_status" in result.text
    assert "/next_action" in result.text
    assert "/doctor" in result.text
