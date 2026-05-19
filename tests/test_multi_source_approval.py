from pathlib import Path

from affilipilot.workflows.multi_source_approval import render_multi_source_approval, run_multi_source_approval


def test_multi_source_approval_queues_vetted(monkeypatch, tmp_path):
    import affilipilot.workflows.multi_source_approval as workflow

    media = tmp_path / "img.jpg"
    media.write_bytes(b"\xff\xd8\xff\xc0\x00\x11\x08\x03\x20\x03\x20\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9")

    def fake_scan(**kwargs):
        merged = tmp_path / "selected.txt"
        merged.write_text(
            f"https://go.isclix.com/deep_link/v5/a | title=Khăn sữa mềm cho bé | category=baby_care | image_path={media} | affiliate_url=https://go.isclix.com/deep_link/v5/a | media_source=product_card_image | media_confidence=high\n",
            encoding="utf-8",
        )
        return {"source_count": 2, "candidate_count": 1, "selected_count": 1, "merged_input": str(merged), "selected": []}

    monkeypatch.setattr(workflow, "run_multi_source_discovery", fake_scan)
    summary = run_multi_source_approval(
        sources=[{"name": "one", "url": "https://example.com", "source": "LAZADA", "category": "baby_care"}],
        batch_key="batch",
        work_dir=tmp_path / "work",
        db_path=tmp_path / "db.sqlite",
        outbox_path=tmp_path / "outbox.json",
    )
    assert summary["ok"] is True
    assert summary["vetted_count"] == 1
    assert summary["queued_messages"] >= 1
    assert "multi-source approval" in render_multi_source_approval(summary)
