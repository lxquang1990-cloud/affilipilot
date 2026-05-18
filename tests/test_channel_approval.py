from affilipilot.workflows.channel_approval import render_channel_to_approval, run_channel_to_approval


def test_channel_to_approval_one_command(monkeypatch, tmp_path):
    import affilipilot.workflows.channel_approval as workflow

    media = tmp_path / "khan.jpg"
    media.write_bytes(b"fake image")

    def fake_discover_convert(**kwargs):
        converted = tmp_path / "converted.txt"
        converted.write_text(
            f"https://go.isclix.com/deep_link/v5/abc | title=Khăn sữa mềm cho bé | category=baby_care | image_path={media} | affiliate_url=https://go.isclix.com/deep_link/v5/abc | media_source=product_card_image | media_confidence=high\n",
            encoding="utf-8",
        )
        return {
            "converted_input": str(converted),
            "discovery": {"ok": True, "total": 1},
            "conversion": {"ok_count": 1, "failed_count": 0, "total": 1, "items": []},
        }

    monkeypatch.setattr(workflow, "run_discover_convert", fake_discover_convert)
    summary = run_channel_to_approval(
        url="https://www.lazada.vn/tag/khan-sua-em-be/",
        batch_key="test-channel",
        work_dir=tmp_path / "work",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
        source="LAZADA",
        category="baby_care",
        campaign_key="LAZADA",
        queue_telegram=True,
    )

    assert summary["ok"] is True
    assert summary["manifest"]["selected"] == 1
    assert summary["vetted_count"] == 1
    assert summary["filtered_count"] == 0
    assert summary["queued_messages"] >= 1
    assert (tmp_path / "work" / "channel-to-approval-summary.json").exists()
    rendered = render_channel_to_approval(summary)
    assert "channel-to-approval" in rendered
    assert "Outbox queued" in rendered


def test_channel_to_approval_blocks_when_no_converted_products(monkeypatch, tmp_path):
    import affilipilot.workflows.channel_approval as workflow

    converted = tmp_path / "empty.txt"
    converted.write_text("", encoding="utf-8")
    monkeypatch.setattr(workflow, "run_discover_convert", lambda **kwargs: {
        "converted_input": str(converted),
        "discovery": {"ok": True, "total": 0},
        "conversion": {"ok_count": 0, "failed_count": 0, "total": 0, "items": []},
    })
    summary = run_channel_to_approval(
        url="https://www.lazada.vn/tag/empty/",
        batch_key="empty",
        work_dir=tmp_path / "work",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
    )
    assert summary["ok"] is False
    assert summary["reason"] == "no_converted_products"
