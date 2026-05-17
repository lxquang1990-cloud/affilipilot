from affilipilot.workflows.approval import decide_post
from affilipilot.workflows.run_day import run_day


def test_run_day_outputs_report(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000", encoding="utf-8")
    result = run_day(input_file, tmp_path / "work", tmp_path / "db.sqlite", batch_key="day-test", limit=1)
    assert result["batch_key"] == "day-test"
    assert result["ready_count"] == 0
    assert result["held_count"] == 1
    report = tmp_path / "work" / "reports" / "day-test.md"
    assert report.exists()
    assert "AffiliPilot Day Report" in report.read_text(encoding="utf-8")


def test_run_day_then_approve_ready_package(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    run_day(input_file, tmp_path / "work", db, batch_key="day-test", limit=1)
    updated = decide_post(db, batch_key="day-test", post_id="post_20260516_001", decision="approved")
    assert updated[0]["status"] == "approved"
