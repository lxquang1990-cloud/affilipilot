import json

from affilipilot.cli import main
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post


def _write_db(db, tmp_path, batch_key="batch-1", post_id="post_1", approved=False):
    image = tmp_path / f"{batch_key}.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file = tmp_path / f"{batch_key}.links.txt"
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Safe product | category=storage | price=129000 | image_path={image}", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / f"{batch_key}-drafts", db, batch_key=batch_key, limit=1)
    if post_id != "post_20260516_001":
        # keep the production gate focused in this legacy test by matching the plan's post id
        from affilipilot.db import AffiliPilotDB
        conn = AffiliPilotDB(db).connect()
        with conn:
            conn.execute("UPDATE approvals SET post_id = ? WHERE batch_key = ?", (post_id, batch_key))
            row = conn.execute("SELECT manifest_json FROM batches WHERE batch_key = ?", (batch_key,)).fetchone()
            import json as _json
            manifest = _json.loads(row[0])
            manifest["posts"][0]["post_id"] = post_id
            conn.execute("UPDATE batches SET manifest_json = ? WHERE batch_key = ?", (_json.dumps(manifest), batch_key))
    if approved:
        decide_post(db, batch_key=batch_key, post_id=post_id, decision="approved")


def test_facebook_publish_requires_delivered_telegram_outbox(tmp_path, monkeypatch, capsys):
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
    db = tmp_path / "affilipilot.db"
    _write_db(db, tmp_path, approved=True)
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch-1:summary", kind="summary", text="summary", status="pending"),
        OutboxMessage(id="batch-1:post_1", kind="approval_card", text="card", status="pending"),
    ])

    try:
        main([
            "facebook-publish-one",
            "--plan", str(plan_path),
            "--post-id", "post_1",
            "--out", str(tmp_path / "result.json"),
            "--require-telegram-sent",
            "--db", str(db),
            "--outbox", str(outbox_path),
            "--batch-key", "batch-1",
        ])
    except SystemExit as exc:
        assert "delivery_not_delivered" in str(exc)
    else:
        raise AssertionError("publish should have been blocked")


def test_facebook_publish_allows_delivered_telegram_outbox(tmp_path, monkeypatch):
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
    db = tmp_path / "affilipilot.db"
    _write_db(db, tmp_path, approved=True)
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch-1:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch-1:post_1", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])

    import affilipilot.cli as cli
    from affilipilot import _cli_legacy
    from affilipilot.cli import facebook as cli_facebook
    from affilipilot.publishing import facebook as fb_module

    # publish_post is imported in several places after the CLI refactor:
    # 1. affilipilot.cli (re-exported for backward compat with this test)
    # 2. affilipilot._cli_legacy (legacy monolithic CLI; bridged for now)
    # 3. affilipilot.cli.facebook (the new domain module; where handler lives)
    # 4. affilipilot.publishing.facebook (the canonical definition)
    # Patch all so the call site resolves to the stub regardless of which
    # binding the handler ends up using.
    fake = lambda post_text, link: {"ok": True, "status": 200, "response": {"id": "fb_1"}, "endpoint": "/page/feed"}
    monkeypatch.setattr(cli, "publish_post", fake)
    monkeypatch.setattr(_cli_legacy, "publish_post", fake)
    monkeypatch.setattr(cli_facebook, "publish_post", fake)
    monkeypatch.setattr(fb_module, "publish_post", fake)

    code = main([
        "facebook-publish-one",
        "--plan", str(plan_path),
        "--post-id", "post_1",
        "--out", str(tmp_path / "result.json"),
        "--require-telegram-sent",
        "--db", str(db),
        "--outbox", str(outbox_path),
        "--batch-key", "batch-1",
    ])
    assert code == 0
