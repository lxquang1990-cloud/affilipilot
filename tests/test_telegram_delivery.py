from affilipilot.telegram.delivery import build_openclaw_telegram_plan, deliver_outbox_dry_run, queue_approval_batch, render_delivery_report, render_openclaw_telegram_plan, render_outbox_preview
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
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000", encoding="utf-8")
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


def test_openclaw_telegram_plan_is_plan_only(tmp_path):
    outbox = Outbox(tmp_path / "outbox.json")
    outbox.add(OutboxMessage(id="m1", kind="summary", text="hello world"))

    plan = build_openclaw_telegram_plan(outbox.path, reply_to="640968010", limit=1)
    assert plan["mode"] == "openclaw_plan_only"
    assert plan["planned"] == 1
    assert len(outbox.pending()) == 1
    rendered = render_openclaw_telegram_plan(plan)
    assert "openclaw agent" in rendered
    assert "--deliver" in rendered
    assert "--reply-channel telegram" in rendered
    assert "hello world" in rendered
