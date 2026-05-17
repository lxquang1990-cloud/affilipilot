from affilipilot.cli import main


def test_draft_links_cli_generates_batch_and_outbox(tmp_path, capsys):
    db = tmp_path / "affilipilot.db"
    work_dir = tmp_path / "runs"
    outbox = tmp_path / "outbox.json"

    code = main([
        "draft-links",
        "--link", "https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000",
        "--link", "https://shopee.vn/b | title=Yếm ăn dặm silicone mềm | category=feeding | price=79000",
        "--link", "https://shopee.vn/c | title=Khăn sữa cotton mềm | category=baby-care | price=59000",
        "--work-dir", str(work_dir),
        "--db", str(db),
        "--batch-key", "test-draft-links",
        "--limit", "3",
        "--outbox", str(outbox),
    ])

    captured = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot draft-links complete: test-draft-links" in captured
    assert (work_dir / "inline_links.txt").exists()
    assert (work_dir / "test-draft-links" / "drafts" / "approval_batch_preview.txt").exists()
    assert outbox.exists()
    assert "post_20260516_001" in outbox.read_text(encoding="utf-8")
