from affilipilot.cli import main
from affilipilot.publishing.ready_to_publish import build_ready_to_publish_report
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post


def test_ready_to_publish_report_blocks_without_delivery(tmp_path):
    db = tmp_path / "affilipilot.db"
    input_file = tmp_path / "links.txt"
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={image_file}", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="pending"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="pending"),
    ])

    report = build_ready_to_publish_report(db_path=db, batch_key="batch", outbox_path=outbox_path, out_dir=tmp_path / "publish")

    assert report["publish_safe_pass_count"] == 0
    assert report["publish_safe_block_count"] == 1
    assert (tmp_path / "publish" / "facebook-plan.json").exists()
    assert (tmp_path / "publish" / "ready-to-publish.json").exists()


def test_ready_to_publish_cli_passes_when_all_gates_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    db = tmp_path / "affilipilot.db"
    input_file = tmp_path / "links.txt"
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={image_file}", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])

    code = main([
        "ready-to-publish",
        "--db", str(db),
        "--batch-key", "batch",
        "--outbox", str(outbox_path),
        "--out-dir", str(tmp_path / "publish"),
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "Publish-safe: 1 PASS / 0 BLOCK" in out
    assert "✅ PASS post_20260516_001" in out
