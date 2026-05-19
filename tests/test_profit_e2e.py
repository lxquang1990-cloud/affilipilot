from affilipilot.workflows import e2e_profit


import json


def test_fetch_source_error_does_not_crash(tmp_path, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("temporary upstream issue")
    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", boom)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "bad"}, tmp_path, cache_dir=tmp_path / "global-cache")
    assert report["ok"] is False
    assert report["products"] == []
    assert "source_fetch_error" in report["error"]


def test_fetch_source_uses_cached_fallback_on_upstream_error(tmp_path, monkeypatch):
    cache_dir = tmp_path / "global-cache"
    cache = cache_dir / "bad.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"ok": True, "products": [{"url": "https://lazada.vn/products/a", "title": "Máy lọc không khí", "category": "home_appliance"}]}), encoding="utf-8")

    def boom(**kwargs):
        raise RuntimeError("temporary upstream issue")

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", boom)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "bad"}, tmp_path, cache_dir=cache_dir)
    assert report["ok"] is True
    assert report["source_mode"] == "cached_fallback"
    assert report["fallback_error"].startswith("source_fetch_error")
    assert len(report["products"]) == 1

def test_fetch_source_writes_cross_run_cache_on_success(tmp_path, monkeypatch):
    cache_dir = tmp_path / "global-cache"

    def fake_fetch(**kwargs):
        return {"ok": True, "products": [{"url": "https://lazada.vn/products/a", "title": "Máy lọc không khí", "category": "home_appliance"}]}

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "good"}, tmp_path, cache_dir=cache_dir)
    assert report["ok"] is True
    assert (cache_dir / "good.json").exists()


def test_fetch_source_ignores_placeholder_cache_on_upstream_error(tmp_path, monkeypatch):
    cache_dir = tmp_path / "global-cache"
    cache = cache_dir / "bad.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"ok": True, "products": [{"url": "https://example.com/a", "title": "test", "image_url": "https://example.com/a.jpg"}]}), encoding="utf-8")

    def boom(**kwargs):
        raise RuntimeError("temporary upstream issue")

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", boom)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "bad"}, tmp_path, cache_dir=cache_dir)
    assert report["ok"] is False
    assert report["products"] == []


def test_fetch_source_ignores_lazada_safe_fixture_cache(tmp_path, monkeypatch):
    cache_dir = tmp_path / "global-cache"
    cache = cache_dir / "bad.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"ok": True, "products": [{"url": "https://lazada.vn/products/safe", "title": "fixture", "image_url": "https://lazada.vn/s.jpg"}]}), encoding="utf-8")

    def boom(**kwargs):
        raise RuntimeError("temporary upstream issue")

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", boom)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "bad"}, tmp_path, cache_dir=cache_dir)
    assert report["ok"] is False
    assert report["products"] == []


def test_profit_e2e_standard_flow_with_patched_sources(tmp_path, monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "products": [
                {
                    "url": "https://lazada.vn/products/a",
                    "title": "Máy lọc không khí chính hãng bảo hành 12 tháng",
                    "category": "home_appliance",
                    "price_vnd": 1290000,
                    "discount_vnd": 990000,
                    "discount_rate": 30,
                    "image_url": "https://lazada.vn/a.jpg",
                    "affiliate_url": "https://go.isclix.com/deep_link/a",
                    "product_id": "a1",
                    "merchant": "lazada",
                    "source": "accesstrade_datafeed",
                    "raw": {},
                }
            ],
        }

    def fake_convert(input_path, out_path, **kwargs):
        out_path.write_text('{"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": true}', encoding="utf-8")
        return {"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": True}

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch_datafeeds)
    monkeypatch.setattr(e2e_profit, "fetch_top_products", lambda **kwargs: {"ok": True, "products": []})
    monkeypatch.setattr(e2e_profit, "convert_input_links", fake_convert)
    monkeypatch.setattr(e2e_profit, "write_converted_input", lambda converted_json, out_path: out_path.write_text("", encoding="utf-8"))
    monkeypatch.setattr(e2e_profit, "queue_approval_batch", lambda *args, **kwargs: [])

    summary = e2e_profit.run_profit_first_e2e(
        batch_key="test-profit",
        work_dir=tmp_path / "run",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
        select_limit=1,
        queue_telegram=False,
    )

    assert summary["candidate_count"] == 1
    assert summary["early_blocked_count"] == 0
    assert summary["selected_count"] == 1
    assert summary["conversion"]["ok_count"] == 1
    assert (tmp_path / "run" / "profit-first-e2e-summary.json").exists()


def test_profit_e2e_filters_risky_products_before_conversion(tmp_path, monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "products": [
                {"url": "https://lazada.vn/products/risky", "title": "Vitamin K2D3 tăng đề kháng cho bé", "category": "health_and_beauty", "price_vnd": 199000, "image_url": "https://lazada.vn/r.jpg", "merchant": "lazada_kol", "raw": {}},
                {"url": "https://lazada.vn/products/safe", "title": "Máy lọc không khí chính hãng bảo hành 12 tháng", "category": "home_appliance", "price_vnd": 1290000, "discount_rate": 30, "image_url": "https://lazada.vn/s.jpg", "merchant": "lazada_kol", "raw": {}},
            ],
        }

    def fake_convert(input_path, out_path, **kwargs):
        text = input_path.read_text(encoding="utf-8")
        assert "Vitamin K2D3" not in text
        assert "Máy lọc không khí" in text
        out_path.write_text('{"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": true}', encoding="utf-8")
        return {"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": True}

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch_datafeeds)
    monkeypatch.setattr(e2e_profit, "fetch_top_products", lambda **kwargs: {"ok": True, "products": []})
    monkeypatch.setattr(e2e_profit, "convert_input_links", fake_convert)
    monkeypatch.setattr(e2e_profit, "write_converted_input", lambda converted_json, out_path: out_path.write_text("", encoding="utf-8"))

    summary = e2e_profit.run_profit_first_e2e(
        batch_key="test-filter",
        work_dir=tmp_path / "run-filter",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
        select_limit=1,
        queue_telegram=False,
    )
    assert summary["candidate_count"] == 1
    assert summary["early_blocked_count"] >= 1
    assert "taste_blocked_count" in summary
    assert "portfolio_blocked_count" in summary
    assert any(item["title"] == "Vitamin K2D3 tăng đề kháng cho bé" for item in summary["early_blocked"])
    assert summary["top_early_block_reasons"]
    rendered = e2e_profit.render_profit_first_e2e(summary)
    assert "Source health:" in rendered
    assert "Why no approval-ready cards:" in rendered
    assert "Top early block reasons:" in rendered
    assert "Top taste block reasons:" in rendered
    assert "Top portfolio block reasons:" in rendered
