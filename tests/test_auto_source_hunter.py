from affilipilot.workflows import auto_source_hunter


def test_auto_source_hunter_collects_filters_and_writes_summary(tmp_path, monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "products": [
                {
                    "url": "https://shopee.vn/Máy-hút-bụi-cầm-tay-i.1.1",
                    "title": "Máy hút bụi cầm tay cho gia đình chính hãng",
                    "category": "home_appliance",
                    "price_vnd": 299000,
                    "image_url": "https://cdn.example/a.jpg",
                    "affiliate_url": "https://go.isclix.com/deep_link/a",
                    "merchant": "shopee",
                },
                {
                    "url": "https://shopee.vn/Nhiệt-kế-i.1.2",
                    "title": "Nhiệt kế hồng ngoại đo đường huyết",
                    "category": "health_and_beauty",
                    "price_vnd": 199000,
                    "image_url": "https://cdn.example/b.jpg",
                    "affiliate_url": "https://go.isclix.com/deep_link/b",
                    "merchant": "shopee",
                },
            ],
        }

    def fake_convert(input_path, out_path, **kwargs):
        text = input_path.read_text(encoding="utf-8")
        assert "Máy hút bụi" in text
        assert "Nhiệt kế" not in text
        out_path.write_text('{"total":1,"ok_count":0,"failed_count":1,"items":[],"dry_run":true}', encoding="utf-8")
        return {"total": 1, "ok_count": 0, "failed_count": 1, "items": [], "dry_run": True}

    monkeypatch.setattr(auto_source_hunter, "fetch_datafeeds", fake_fetch_datafeeds)
    monkeypatch.setattr(auto_source_hunter, "convert_input_links", fake_convert)
    monkeypatch.setattr(auto_source_hunter, "write_converted_input", lambda converted_json, out_path: out_path.write_text("", encoding="utf-8"))

    source_config = tmp_path / "sources.json"
    source_config.write_text('{"sources":[{"name":"fake","domain":"shopee.vn","campaign_key":"SHOPEE","pages":1,"limit":10,"weight":10}]}', encoding="utf-8")
    summary = auto_source_hunter.run_auto_source_hunter(
        batch_key="test-auto",
        work_dir=tmp_path / "run",
        db_path=tmp_path / "db.sqlite",
        outbox_path=tmp_path / "outbox.json",
        source_config=source_config,
        collect_limit=5,
        select_limit=1,
        real_accesstrade=False,
        queue_telegram=False,
    )

    assert summary["ok"] is False
    assert summary["reason"] == "no_converted_input"
    assert summary["candidate_count"] >= 1
    assert summary["early_blocked_count"] >= 1
    assert (tmp_path / "run" / "auto-source-hunter-summary.json").exists()
    rendered = auto_source_hunter.render_auto_source_hunter(summary)
    assert "auto-source hunter" in rendered
    assert "Sources:" in rendered
