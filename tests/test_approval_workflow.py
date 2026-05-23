from affilipilot.db import AffiliPilotDB
from affilipilot.workflows.approval import create_approval_batch, decide_post, render_status


def test_create_batch_and_decide(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/test.jpg", encoding="utf-8")
    out_dir = tmp_path / "out"
    db_path = tmp_path / "affilipilot.db"

    manifest = create_approval_batch(input_file, out_dir, db_path, batch_key="test-batch", limit=1)
    assert manifest["selected"] == 1

    db = AffiliPilotDB(db_path)
    approvals = db.get_approvals("test-batch")
    assert len(approvals) == 1
    assert approvals[0]["status"] == "pending"

    post_id = approvals[0]["post_id"]
    updated = decide_post(db_path, batch_key="test-batch", post_id=post_id, decision="approved", reason="looks good")
    assert updated[0]["status"] == "approved"
    assert "approved" in render_status(db_path, batch_key="test-batch")


def test_blacklist_decision_records_blacklist(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/test.jpg", encoding="utf-8")
    out_dir = tmp_path / "out"
    db_path = tmp_path / "affilipilot.db"
    create_approval_batch(input_file, out_dir, db_path, batch_key="test-batch", limit=1)
    db = AffiliPilotDB(db_path)
    post_id = db.get_approvals("test-batch")[0]["post_id"]
    decide_post(db_path, batch_key="test-batch", post_id=post_id, decision="blacklisted", reason="bad shop")
    with db.connect() as conn:
        rows = conn.execute("SELECT kind, value, reason FROM blacklist").fetchall()
    assert len(rows) == 1
    assert rows[0]["kind"] == "product"
