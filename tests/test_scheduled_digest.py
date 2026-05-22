from affilipilot.telegram.outbox import Outbox
from affilipilot.workflows.auto_source_hunter import run_auto_source_hunter


def test_auto_source_hunter_queues_digest_when_no_vetted_posts(tmp_path, monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return []

    monkeypatch.setattr("affilipilot.workflows.auto_source_hunter.fetch_datafeeds", fake_fetch_datafeeds)
    outbox = tmp_path / "outbox.json"
    summary = run_auto_source_hunter(
        db_path=tmp_path / "affilipilot.db",
        batch_key="scheduled-empty",
        work_dir=tmp_path / "run",
        outbox_path=outbox,
        collect_limit=5,
        select_limit=1,
        real_accesstrade=False,
        queue_telegram=True,
    )

    assert summary["ok"] is False
    assert summary["queued_digest"] is True
    messages = Outbox(outbox).load()
    assert len(messages) == 1
    assert messages[0].kind == "digest"
    assert "no publish-ready approval cards" in messages[0].text
    assert "no post was silently published" in messages[0].text
