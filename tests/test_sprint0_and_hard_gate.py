import json

from affilipilot.cli import main
from affilipilot.telegram.outbox import Outbox, OutboxMessage


def test_facebook_publish_blocks_without_delivery_proof_by_default(tmp_path):
    plan = {
        "batch_key": "batch-1",
        "plans": [
            {
                "post_id": "post_1",
                "status": "publishable_dry_run",
                "endpoint": "/page/feed",
                "payload_preview": {"message": "hello", "link": "https://go.isclix.com/x"},
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    try:
        main(["facebook-publish-one", "--plan", str(plan_path), "--post-id", "post_1"])
    except SystemExit as exc:
        assert "needs --outbox and --batch-key" in str(exc)
    else:
        raise AssertionError("publish should require Telegram delivery proof by default")


def test_facebook_publish_requires_delivered_not_sent(tmp_path):
    plan = {
        "batch_key": "batch-1",
        "plans": [
            {
                "post_id": "post_1",
                "status": "publishable_dry_run",
                "endpoint": "/page/feed",
                "payload_preview": {"message": "hello", "link": "https://go.isclix.com/x"},
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch-1:summary", kind="summary", text="summary", status="sent"),
        OutboxMessage(id="batch-1:post_1", kind="approval_card", text="card", status="sent"),
    ])

    try:
        main([
            "facebook-publish-one",
            "--plan", str(plan_path),
            "--post-id", "post_1",
            "--outbox", str(outbox_path),
            "--batch-key", "batch-1",
        ])
    except SystemExit as exc:
        assert "delivery_not_delivered" in str(exc)
    else:
        raise AssertionError("publish should require delivered status, not local sent status")


def test_sprint0_cli_creates_drafts_and_outbox(tmp_path, capsys):
    db = tmp_path / "affilipilot.db"
    work_dir = tmp_path / "runs"
    outbox = tmp_path / "outbox.json"

    code = main([
        "sprint0",
        "--link", "https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/a.jpg",
        "--work-dir", str(work_dir),
        "--db", str(db),
        "--batch-key", "sprint0-test",
        "--outbox", str(outbox),
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot Sprint 0 workflow ready: sprint0-test" in out
    assert "Next safe steps" in out
    assert (work_dir / "sprint0-test" / "drafts" / "approval_batch_preview.txt").exists()
    assert outbox.exists()
    assert "sprint0-test:summary" in outbox.read_text(encoding="utf-8")
