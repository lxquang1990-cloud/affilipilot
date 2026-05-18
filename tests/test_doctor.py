from affilipilot.cli import main
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post
from affilipilot.workflows.doctor import build_doctor_report


def _batch(tmp_path, db):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/a.jpg", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")


def test_doctor_report_is_read_only_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])

    report = build_doctor_report(db_path=db, outbox_path=outbox_path, batch_key="batch")

    assert report["ok_for_local_workflow"] is True
    assert report["ok_for_publish_config"] is True
    assert report["batch"]["posts"] == 1
    assert report["batch"]["approvals"] == {"approved": 1}
    assert report["outbox"]["statuses"] == {"delivered": 2}


def test_doctor_cli_renders_without_secrets(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "super-secret-token")
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    code = main(["doctor", "--db", str(db), "--batch-key", "batch", "--outbox", str(tmp_path / "missing-outbox.json")])

    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot doctor" in out
    assert "super-secret-token" not in out
    assert "Batch: batch" in out
