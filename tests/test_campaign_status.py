from affilipilot.cli import main
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post
from affilipilot.workflows.campaign_status import build_campaign_status


def _batch(tmp_path, db):
    input_file = tmp_path / "links.txt"
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={image_file}", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)


def test_campaign_status_blocks_pending_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])

    status = build_campaign_status(db_path=db, batch_key="batch", outbox_path=outbox_path, out_dir=tmp_path / "status")

    assert status["next_action"]["status"] == "NEEDS_APPROVAL"
    assert status["ready_to_publish"]["publish_safe_pass_count"] == 0
    assert (tmp_path / "status" / "ready-to-publish.json").exists()


def test_campaign_status_ready_to_publish(tmp_path, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])

    status = build_campaign_status(db_path=db, batch_key="batch", outbox_path=outbox_path, out_dir=tmp_path / "status")

    assert status["next_action"]["status"] == "READY_TO_PUBLISH"
    assert status["ready_to_publish"]["publish_safe_pass_count"] == 1


def test_campaign_status_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    _batch(tmp_path, db)
    code = main([
        "campaign-status",
        "--db", str(db),
        "--batch-key", "batch",
        "--outbox", str(tmp_path / "missing-outbox.json"),
        "--out-dir", str(tmp_path / "status"),
        "--no-build-ready",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot campaign status" in out
    assert "Next:" in out
