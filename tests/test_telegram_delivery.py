import subprocess

from affilipilot.telegram.delivery import build_openclaw_telegram_plan, deliver_outbox_dry_run, mark_batch_delivered, queue_approval_batch, render_batch_delivery_report, render_delivery_report, render_openclaw_telegram_plan, render_openclaw_telegram_send_report, render_outbox_preview, send_openclaw_telegram_outbox
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch


def test_outbox_add_pending_mark(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello"))
    assert len(outbox.pending()) == 1
    outbox.mark("m1", "sent")
    assert len(outbox.pending()) == 0


def test_queue_approval_batch(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/test.jpg", encoding="utf-8")
    db_path = tmp_path / "db.sqlite"
    create_approval_batch(input_file, tmp_path / "drafts", db_path, batch_key="batch", limit=1)
    outbox_path = tmp_path / "outbox.json"
    messages = queue_approval_batch(db_path, batch_key="batch", outbox_path=outbox_path)
    assert len(messages) == 2
    preview = render_outbox_preview(outbox_path)
    assert "batch:summary" in preview
    assert "approval_card" in preview


def test_deliver_outbox_dry_run_and_mark_sent(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello"))
    outbox.add(OutboxMessage(id="m2", kind="approval_card", text="approve me"))

    dry = deliver_outbox_dry_run(outbox.path, limit=1)
    assert dry["mode"] == "dry_run"
    assert dry["processed"] == 1
    assert len(outbox.pending()) == 2
    assert "m1" in render_delivery_report(dry)

    marked = deliver_outbox_dry_run(outbox.path, mark_sent=True)
    assert marked["mode"] == "mark_sent"
    assert marked["processed"] == 2
    assert len(outbox.pending()) == 0

def test_deliver_outbox_mark_delivered_requires_receipt(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello"))
    try:
        deliver_outbox_dry_run(outbox.path, mark_delivered=True)
    except ValueError as exc:
        assert "requires a non-empty receipt" in str(exc)
    else:
        raise AssertionError("mark_delivered should require receipt")

    delivered = deliver_outbox_dry_run(outbox.path, mark_delivered=True, receipt="telegram:640968010:7532")
    assert delivered["mode"] == "mark_delivered"
    assert delivered["messages"][0]["status"] == "delivered"
    assert "Receipt: telegram:640968010:7532" in render_delivery_report(delivered)
    saved = outbox.load()[0]
    assert saved.receipt == "telegram:640968010:7532"
    assert saved.delivered_at
    assert len(outbox.pending()) == 0


def test_mark_batch_delivered_marks_summary_and_selected_card(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="batch:summary", kind="summary", text="summary"))
    outbox.add(OutboxMessage(id="batch:post_1", kind="approval_card", text="card"))
    outbox.add(OutboxMessage(id="batch:post_2", kind="approval_card", text="other card"))

    result = mark_batch_delivered(outbox.path, batch_key="batch", post_id="post_1", receipt="telegram:640968010:7555")

    assert result["processed"] == 2
    rendered = render_batch_delivery_report(result)
    assert "batch:summary -> delivered" in rendered
    messages = {m.id: m for m in outbox.load()}
    assert messages["batch:summary"].status == "delivered"
    assert messages["batch:post_1"].status == "delivered"
    assert messages["batch:post_2"].status == "pending"
    assert messages["batch:post_1"].receipt == "telegram:640968010:7555"


def test_openclaw_telegram_plan_is_plan_only(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello world"))

    plan = build_openclaw_telegram_plan(outbox.path, reply_to="640968010", limit=1)
    assert plan["mode"] == "openclaw_plan_only"
    assert plan["planned"] == 1
    assert len(outbox.pending()) == 1
    rendered = render_openclaw_telegram_plan(plan)
    assert "openclaw message send" in rendered
    assert "--channel telegram" in rendered
    assert "--target 640968010" in rendered
    assert "hello world" in rendered

def test_openclaw_telegram_send_marks_sent_without_receipt(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello world"))

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    result = send_openclaw_telegram_outbox(outbox.path, reply_to="640968010", runner=runner)

    assert result["messages"][0]["status"] == "sent"
    saved = outbox.load()[0]
    assert saved.status == "sent"
    assert not saved.receipt
    rendered = render_openclaw_telegram_send_report(result)
    assert "publish gate remains blocked" in rendered

def test_openclaw_telegram_send_marks_delivered_with_receipt(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello world"))

    def runner(cmd, **kwargs):
        assert "--account" in cmd
        assert "secops" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout='{"payload":{"messageId":"7691","chatId":"640968010"}}', stderr="")

    result = send_openclaw_telegram_outbox(outbox.path, reply_to="640968010", account="secops", runner=runner)

    assert result["messages"][0]["status"] == "delivered"
    assert result["messages"][0]["receipt"] == "telegram:640968010:7691"
    saved = outbox.load()[0]
    assert saved.status == "delivered"
    assert saved.receipt == "telegram:640968010:7691"

def test_openclaw_telegram_send_marks_failed_on_error(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello world"))

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    result = send_openclaw_telegram_outbox(outbox.path, reply_to="640968010", runner=runner)

    assert result["messages"][0]["status"] == "failed"
    assert outbox.load()[0].status == "failed"
