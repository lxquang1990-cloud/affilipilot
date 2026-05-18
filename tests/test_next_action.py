import json

from affilipilot.cli import main
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post
from affilipilot.workflows.next_action import recommend_next_action


def _batch(tmp_path, db):
    image = tmp_path / "product.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file = tmp_path / "links.txt"
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={image}", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)


def test_next_action_no_batch(tmp_path):
    result = recommend_next_action(db_path=tmp_path / "empty.db", outbox_path=tmp_path / "outbox.json")
    assert result["status"] == "NO_BATCH"
    assert result["action"] == "create_batch"


def test_next_action_needs_outbox(tmp_path):
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    result = recommend_next_action(db_path=db, batch_key="batch", outbox_path=tmp_path / "outbox.json")
    assert result["status"] == "NEEDS_OUTBOX"
    assert "queue-telegram" in result["command"]


def test_next_action_needs_delivery_then_approval_then_ready_to_publish(tmp_path):
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="pending"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="pending"),
    ])
    result = recommend_next_action(db_path=db, batch_key="batch", outbox_path=outbox_path)
    assert result["status"] == "NEEDS_DELIVERY_PROOF"

    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])
    result = recommend_next_action(db_path=db, batch_key="batch", outbox_path=outbox_path)
    assert result["status"] == "NEEDS_APPROVAL"

    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    result = recommend_next_action(db_path=db, batch_key="batch", outbox_path=outbox_path)
    assert result["status"] == "NEEDS_READY_TO_PUBLISH"


def test_next_action_ready_to_publish(tmp_path):
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])
    plan_path = tmp_path / "facebook-plan.json"
    plan_path.write_text(json.dumps({"batch_key": "batch", "plans": [{"post_id": "post_20260516_001", "status": "publishable_dry_run"}]}), encoding="utf-8")

    result = recommend_next_action(db_path=db, batch_key="batch", outbox_path=outbox_path, plan_path=plan_path)

    assert result["status"] == "READY_TO_PUBLISH"
    assert "publish-safe" in result["command"]


def test_next_action_cli(tmp_path, capsys):
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    code = main(["next-action", "--db", str(db), "--batch-key", "batch", "--outbox", str(tmp_path / "outbox.json")])
    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot next action" in out
    assert "NEEDS_OUTBOX" in out
