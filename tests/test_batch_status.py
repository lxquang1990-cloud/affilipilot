from affilipilot.cli import main
from affilipilot.publishing.facebook import FacebookConfig
from affilipilot.publishing.facebook_plan import plan_facebook_batch
from affilipilot.workflows.approval import create_approval_batch, decide_post
from affilipilot.workflows.batch_status import build_batch_status, render_batch_status


def test_demo_happy_path_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    code = main([
        "demo-happy-path",
        "--work-dir", str(tmp_path / "demo"),
        "--db", str(tmp_path / "demo.db"),
        "--batch-key", "happy",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot demo happy path: happy" in out
    assert "Publishable dry-run: 1" in out
    assert "approval=approved plan=publishable_dry_run" in out
    assert (tmp_path / "demo" / "approved" / "facebook-plan.json").exists()


def test_batch_status_summarizes_approvals_and_plan(tmp_path, capsys):
    input_file = tmp_path / "links.txt"
    input_file.write_text("\n".join([
        "https://go.isclix.com/deep_link/product-a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/a.jpg",
        "https://go.isclix.com/deep_link/product-b | title=Yếm ăn dặm silicone mềm | category=feeding | price=79000 | image_url=https://cdn.example/b.jpg",
    ]), encoding="utf-8")
    db = tmp_path / "db.sqlite"
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=2)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan_path = tmp_path / "facebook-plan.json"
    plan_facebook_batch(db, batch_key="batch", out_path=plan_path, config=FacebookConfig(page_id="page", page_access_token="token"))

    status = build_batch_status(db, batch_key="batch", facebook_plan=plan_path)
    assert status["approval_counts"] == {"approved": 1, "pending": 1}
    assert status["facebook_plan_counts"] == {"publishable_dry_run": 1, "blocked": 1}
    rendered = render_batch_status(status)
    assert "approval=approved plan=publishable_dry_run" in rendered
    assert "not_approved_by_snail" in rendered

    code = main(["batch-status", "--db", str(db), "--batch-key", "batch", "--facebook-plan", str(plan_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot batch status — batch" in out
