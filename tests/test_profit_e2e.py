from affilipilot.workflows import e2e_profit
from affilipilot.telegram.outbox import Outbox


import json
from pathlib import Path

from affilipilot.media import MediaResult


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

def test_fetch_source_records_target_category_as_internal_note_and_caches(tmp_path, monkeypatch):
    cache_dir = tmp_path / "global-cache"
    seen = {}

    def fake_fetch(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "products": [{"url": "https://lazada.vn/products/a", "title": "Nhiệt kế", "category": "health_and_beauty"}]}

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "broad", "target_category": "home_appliance"}, tmp_path, cache_dir=cache_dir)
    assert report["ok"] is True
    assert report["target_category"] == "home_appliance"
    assert report["requested_page"] == 1
    assert report["source_filter_note"].startswith("category_filter_not_supported_by_accesstrade")
    assert "cat" not in seen
    assert (cache_dir / "broad.json").exists()

def test_fetch_source_rotates_page_by_batch_key(tmp_path, monkeypatch):
    seen = []

    def fake_fetch(**kwargs):
        seen.append(kwargs)
        return {"ok": True, "products": [{"url": "https://lazada.vn/products/a", "title": "Máy lọc không khí", "category": "home_appliance"}]}

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch)
    source = {"kind": "datafeed", "name": "lazada_home", "domain": "lazada.vn"}
    first = e2e_profit._fetch_source(source, tmp_path / "a", cache_dir=tmp_path / "cache-a", batch_key="auto-source-scheduled-20260527-0700")
    second = e2e_profit._fetch_source(source, tmp_path / "b", cache_dir=tmp_path / "cache-b", batch_key="auto-source-scheduled-20260527-0900")
    assert first["requested_page"] == seen[0]["page"]
    assert second["requested_page"] == seen[1]["page"]
    assert first["requested_page"] != second["requested_page"]

def test_fetch_source_explicit_page_overrides_rotation(tmp_path, monkeypatch):
    seen = {}

    def fake_fetch(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "products": [{"url": "https://lazada.vn/products/a", "title": "Máy lọc không khí", "category": "home_appliance"}]}

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch)
    report = e2e_profit._fetch_source({"kind": "datafeed", "name": "fixed", "page": 3}, tmp_path, cache_dir=tmp_path / "cache", batch_key="auto-source-scheduled-20260527-0700")
    assert report["requested_page"] == 3
    assert seen["page"] == 3


def test_early_filter_blocks_fake_tiny_price():
    from affilipilot.content.early_filter import evaluate_early_product_filter
    from affilipilot.models import ProductCandidate

    product = ProductCandidate(
        url="https://shopee.vn/product/123/456",
        title="Kệ đựng mỹ phẩm 4 tầng",
        category="home_organization",
        price_vnd=30,
    )
    result = evaluate_early_product_filter(product)
    assert result.passed is False
    assert "invalid_or_fake_price:<1000vnd" in result.reasons
    assert "invalid_price" in result.risk_flags


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
    state = json.loads((tmp_path / "run" / "snailbot-state.json").read_text(encoding="utf-8"))
    events = (tmp_path / "run" / "snailbot-events.jsonl").read_text(encoding="utf-8").splitlines()
    assert state["batch_key"] == "test-profit"
    assert state["stage"] == "finished"
    assert len(events) >= 6


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
    assert "🐌 AffiliPilot: BLOCK" in rendered
    assert "Filter: early" in rendered
    assert "Lý do chính:" in rendered
    assert "Source health:" not in rendered
    verbose_rendered = e2e_profit.render_profit_first_e2e(summary, verbose=True)
    assert "Source health:" in verbose_rendered
    assert "Top early:" in verbose_rendered
    assert "Top taste:" in verbose_rendered
    assert "Top portfolio:" in verbose_rendered


def test_profit_e2e_queues_digest_when_no_effective_input(tmp_path, monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "products": [
                {"url": "https://lazada.vn/products/risky", "title": "Vitamin K2D3 tăng đề kháng cho bé", "category": "health_and_beauty", "price_vnd": 199000, "image_url": "https://lazada.vn/r.jpg", "merchant": "lazada_kol", "raw": {}},
            ],
        }

    outbox_path = tmp_path / "outbox.json"
    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch_datafeeds)
    monkeypatch.setattr(e2e_profit, "fetch_top_products", lambda **kwargs: {"ok": True, "products": []})

    summary = e2e_profit.run_profit_first_e2e(
        batch_key="test-no-effective-input",
        work_dir=tmp_path / "run-no-input",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=outbox_path,
        select_limit=1,
        queue_telegram=True,
    )

    assert summary["ok"] is False
    assert summary["reason"] == "no_effective_input"
    assert summary["queued_digest"] is True
    assert summary["queued_messages"] == 1
    messages = Outbox(outbox_path).load()
    assert len(messages) == 1
    assert messages[0].kind == "digest"
    assert messages[0].status == "pending"
    assert "🐌 AffiliPilot: BLOCK" in messages[0].text
    assert "Vì sao chưa có card:" in messages[0].text
    assert "blocked_category:medical" in messages[0].text


def test_expected_profit_prefers_higher_commission_product():
    from affilipilot.models import ProductCandidate

    cheap = ProductCandidate(url="https://lazada.vn/products/cheap", title="Hộp đựng đồ gia đình", category="home_organization", price_vnd=150000, image_url="https://lazada.vn/c.jpg")
    expensive = ProductCandidate(url="https://lazada.vn/products/expensive", title="Máy hút bụi gia đình", category="home_appliance", price_vnd=1500000, image_url="https://lazada.vn/e.jpg")

    cheap_score, cheap_metrics, cheap_reasons = e2e_profit._expected_profit_score(
        cheap, base_score=80, taste_score=80, commission_rate=0.03, commission_reasons=["commission_policy:test"]
    )
    expensive_score, expensive_metrics, expensive_reasons = e2e_profit._expected_profit_score(
        expensive, base_score=80, taste_score=80, commission_rate=0.08, commission_reasons=["commission_policy:test"]
    )

    assert expensive_metrics["expected_profit_vnd"] > cheap_metrics["expected_profit_vnd"]
    assert expensive_score > cheap_score
    assert "score_model:expected_profit" in expensive_reasons

def test_profit_e2e_enriches_media_before_quality_gate(tmp_path, monkeypatch):
    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "products": [
                {
                    "url": "https://lazada.vn/products/vacuum",
                    "title": "Máy hút bụi gia đình chính hãng",
                    "category": "home_appliance",
                    "price_vnd": 1500000,
                    "image_url": "https://lazada.vn/vacuum.jpg",
                    "merchant": "lazada_kol",
                    "raw": {},
                },
            ],
        }

    def fake_convert(input_path, out_path, **kwargs):
        text = Path(input_path).read_text(encoding="utf-8")
        Path(out_path).write_text(json.dumps({"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": True}), encoding="utf-8")
        converted = text.replace("https://lazada.vn/products/vacuum", "https://go.isclix.com/deep_link/abc", 1) + " | affiliate_url=https://go.isclix.com/deep_link/abc | tracking_url=https://go.isclix.com/deep_link/abc | original_url=https://lazada.vn/products/vacuum"
        (Path(out_path).parent / "profit-first.converted.txt").write_text(converted + "\n", encoding="utf-8")
        return {"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": True}

    def fake_write_converted(converted_json, out_path):
        if not Path(out_path).exists():
            out_path.write_text("", encoding="utf-8")

    def fake_fetch_image(url, out_dir, *, name_hint="product", timeout=30):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        local = out_dir / "vacuum.jpg"
        # Minimal JPEG header with 800x800 dimensions for media_quality.
        local.write_bytes(bytes.fromhex("ffd8ffc00011080320032003012200021101031101ffd9"))
        return MediaResult(ok=True, local_path=str(local), media_type="jpeg", reasons=[])

    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch_datafeeds)
    monkeypatch.setattr(e2e_profit, "fetch_top_products", lambda **kwargs: {"ok": True, "products": []})
    monkeypatch.setattr(e2e_profit, "write_campaign_registry", lambda path: {"ok": True, "campaigns": [{"campaign_id": "5087153089503673507", "approval": "successful", "status": "1", "aliases": ["lazada.vn"], "max_commission": "8"}]})
    monkeypatch.setattr(e2e_profit, "convert_input_links", fake_convert)
    monkeypatch.setattr(e2e_profit, "write_converted_input", fake_write_converted)
    monkeypatch.setattr("affilipilot.media.fetch_image", fake_fetch_image)

    summary = e2e_profit.run_profit_first_e2e(
        batch_key="test-media-enrich",
        work_dir=tmp_path / "run-media-enrich",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
        select_limit=1,
        real_accesstrade=True,
        queue_telegram=False,
    )

    assert summary["ok"] is True
    assert summary["vetted_count"] == 1
    assert summary["gates"][0]["passed"] is True
    assert "media_not_downloaded" not in json.dumps(summary["gates"], ensure_ascii=False)
    assert "media_quality_missing_local_image" not in json.dumps(summary["gates"], ensure_ascii=False)


def test_profit_e2e_uses_campaign_commission_policy(tmp_path, monkeypatch):
    def fake_registry(path):
        Path(path).write_text('{"ok": true, "campaigns": []}', encoding="utf-8")
        return {
            "ok": True,
            "campaigns": [
                {
                    "campaign_id": "cmp-lazada",
                    "name": "Lazada",
                    "merchant": "lazada",
                    "approval": "successful",
                    "status": "1",
                    "url": "https://lazada.vn",
                    "max_commission": 8,
                    "aliases": ["lazada", "lazada.vn"],
                }
            ],
        }

    def fake_fetch_datafeeds(**kwargs):
        return {
            "ok": True,
            "products": [
                {
                    "url": "https://lazada.vn/products/a",
                    "title": "Máy hút bụi gia đình chính hãng",
                    "category": "home_appliance",
                    "price_vnd": 1500000,
                    "image_url": "https://lazada.vn/a.jpg",
                    "merchant": "lazada",
                    "source": "accesstrade_datafeed",
                    "raw": {},
                }
            ],
        }

    def fake_convert(input_path, out_path, **kwargs):
        text = input_path.read_text(encoding="utf-8")
        assert "commission_rate=0.08" in text
        assert "campaign_id=cmp-lazada" in text
        out_path.write_text('{"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": true}', encoding="utf-8")
        return {"items": [], "total": 1, "ok_count": 1, "failed_count": 0, "dry_run": True}

    monkeypatch.setattr(e2e_profit, "write_campaign_registry", fake_registry)
    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", fake_fetch_datafeeds)
    monkeypatch.setattr(e2e_profit, "fetch_top_products", lambda **kwargs: {"ok": True, "products": []})
    monkeypatch.setattr(e2e_profit, "convert_input_links", fake_convert)
    monkeypatch.setattr(e2e_profit, "write_converted_input", lambda converted_json, out_path: out_path.write_text("", encoding="utf-8"))
    monkeypatch.setattr(e2e_profit, "queue_approval_batch", lambda *args, **kwargs: [])

    summary = e2e_profit.run_profit_first_e2e(
        batch_key="test-commission",
        work_dir=tmp_path / "run-commission",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
        select_limit=1,
        real_accesstrade=True,
        queue_telegram=False,
    )

    assert summary["selected_count"] == 1
    metrics = summary["selected_profit_metrics"][0]["profit_metrics"]
    assert metrics["commission_rate"] == 0.08
    assert metrics["expected_commission_vnd"] == 120000

def test_profit_e2e_writes_blocked_state_events(tmp_path, monkeypatch):
    monkeypatch.setattr(e2e_profit, "write_campaign_registry", lambda path: {"ok": True, "campaigns": []})
    monkeypatch.setattr(e2e_profit, "fetch_datafeeds", lambda **kwargs: {"ok": True, "products": []})
    monkeypatch.setattr(e2e_profit, "fetch_top_products", lambda **kwargs: {"ok": True, "products": []})

    summary = e2e_profit.run_profit_first_e2e(
        batch_key="test-blocked-events",
        work_dir=tmp_path / "run-blocked-events",
        db_path=tmp_path / "affilipilot.db",
        outbox_path=tmp_path / "outbox.json",
        select_limit=1,
        real_accesstrade=True,
        queue_telegram=False,
    )

    assert summary["ok"] is False
    state = json.loads((tmp_path / "run-blocked-events" / "snailbot-state.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (tmp_path / "run-blocked-events" / "snailbot-events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert state["status"] == "blocked"
    assert state["stage"] == "blocked"
    assert any(event["data"].get("stage") == "blocked" for event in events)
