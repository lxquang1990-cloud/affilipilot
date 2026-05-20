from scripts import seed_hunter


def test_seed_hunter_accesstrade_source_does_not_send_keyword_as_cat(tmp_path, monkeypatch):
    config = tmp_path / "keywords.json"
    config.write_text('{"keywords":[{"keyword":"máy hút bụi cầm tay","category":"home_appliance","domains":["lazada.vn"]}]}', encoding="utf-8")
    seen = {}

    def fake_fetch_datafeeds(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "products": []}

    monkeypatch.setattr(seed_hunter, "fetch_datafeeds", fake_fetch_datafeeds)
    summary = seed_hunter.hunt(config, out_dir=tmp_path / "out", per_keyword_limit=5, final_limit=3, source="accesstrade")

    assert summary["count"] == 0
    assert seen["domain"] == "lazada.vn"
    assert seen["status_discount"] == "1"
    assert "cat" not in seen
    assert summary["sources"][0]["source"] == "accesstrade_datafeed_broad"
    assert summary["sources"][0]["note"] == "keyword_filter_not_supported_by_accesstrade_local_match_only"
