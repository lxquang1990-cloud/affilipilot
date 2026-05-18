from affilipilot.workflows.discover_convert import render_discover_convert_summary, run_discover_convert


def test_discover_convert_dry_run(monkeypatch, tmp_path):
    import affilipilot.workflows.discover_convert as workflow

    class FakeDiscovery:
        ok = True
        scan_path = ""
        total = 1
        error = ""
        notes = ["discovery_only_no_publish"]

    def fake_browser_render_discover(url, *, out_path, source, category, limit, timeout_ms, wait_ms, headless):
        out_path.write_text('{"source":{"url":"%s","source":"LAZADA","category":"baby_care"},"fetched_at":"x","total":1,"errors":[],"items":[{"url":"https://www.lazada.vn/products/khan-sua-i123-s456.html","title":"Khăn sữa","category":"baby_care","price_vnd":69000,"image_url":"https://img.lazcdn.com/product.jpg","source":"LAZADA","notes":"product_card_discovery","raw":{"media_source":"product_card_image","media_confidence":"high"}}]}' % url, encoding="utf-8")
        d = FakeDiscovery()
        d.scan_path = str(out_path)
        return d

    monkeypatch.setattr(workflow, "browser_render_discover", fake_browser_render_discover)
    summary = run_discover_convert(
        url="https://www.lazada.vn/tag/khan-sua-em-be/",
        work_dir=tmp_path / "work",
        source="LAZADA",
        category="baby_care",
        campaign_key="LAZADA",
        dry_run=True,
        limit=1,
    )

    assert summary["discovery"]["ok"] is True
    assert summary["conversion"]["ok_count"] == 1
    assert "go.isclix.com" in (tmp_path / "work" / "discovered-products.converted.txt").read_text(encoding="utf-8")
    rendered = render_discover_convert_summary(summary)
    assert "Discovery: OK total=1" in rendered
    assert "Conversion: ok=1 failed=0 total=1" in rendered


def test_discover_convert_handles_discovery_failure(monkeypatch, tmp_path):
    import affilipilot.workflows.discover_convert as workflow

    class FakeDiscovery:
        ok = False
        scan_path = ""
        total = 0
        error = "playwright_not_installed"
        notes = []

    monkeypatch.setattr(workflow, "browser_render_discover", lambda *a, **k: FakeDiscovery())
    summary = run_discover_convert(url="https://www.lazada.vn/tag/x/", work_dir=tmp_path / "work", source="LAZADA", category="baby_care")
    assert summary["discovery"]["ok"] is False
    assert summary["conversion"]["ok_count"] == 0
    assert (tmp_path / "work" / "discovered-products.converted.txt").read_text(encoding="utf-8") == ""
