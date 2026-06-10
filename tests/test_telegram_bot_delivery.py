import json
from pathlib import Path

from affilipilot.telegram.delivery import send_telegram_bot_outbox, render_telegram_bot_send_report
from affilipilot.telegram.outbox import Outbox, OutboxMessage


def test_telegram_bot_send_marks_delivered_without_leaking_token(tmp_path):
    outbox_path = tmp_path / "outbox.json"
    secret = tmp_path / "affilipilot.env"
    secret.write_text("TELEGRAM_BOT_TOKEN=secret-token\nTELEGRAM_CHAT_ID=12345\n", encoding="utf-8")
    Outbox(outbox_path).save([OutboxMessage(id="m1", kind="digest", text="hello")])
    seen = {}

    def fake_sender(token, chat_id, text):
        seen["token"] = token
        seen["chat_id"] = chat_id
        seen["text"] = text
        return {"ok": True, "result": {"message_id": 777}}

    result = send_telegram_bot_outbox(outbox_path, secret_path=secret, sender=fake_sender)
    assert seen == {"token": "secret-token", "chat_id": "12345", "text": "hello"}
    assert result["messages"][0]["status"] == "delivered"
    assert result["messages"][0]["receipt"] == "telegram:12345:777"
    rendered = render_telegram_bot_send_report(result)
    assert "secret-token" not in json.dumps(result)
    assert "secret-token" not in rendered
    stored = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert stored[0]["status"] == "delivered"


def test_telegram_bot_send_marks_failed_on_api_error(tmp_path):
    outbox_path = tmp_path / "outbox.json"
    secret = tmp_path / "affilipilot.env"
    secret.write_text("TELEGRAM_BOT_TOKEN=secret-token\nTELEGRAM_CHAT_ID=12345\n", encoding="utf-8")
    Outbox(outbox_path).save([OutboxMessage(id="m1", kind="digest", text="hello")])

    def fake_sender(token, chat_id, text):
        return {"ok": False, "description": "blocked"}

    result = send_telegram_bot_outbox(outbox_path, secret_path=secret, sender=fake_sender)
    assert result["messages"][0]["status"] == "failed"
    stored = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert stored[0]["status"] == "failed"
