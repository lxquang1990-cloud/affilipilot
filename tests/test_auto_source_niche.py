from affilipilot.telegram.outbox import Outbox
from affilipilot.workflows.auto_source_hunter import run_auto_source_hunter


def test_auto_source_hunter_reports_niche_blocked_candidates(tmp_path, monkeypatch):
    products = [
        {
            "url": "https://shopee.vn/bike-part",
            "title": "Shimano củ đề xe đạp phụ tùng thay thế",
            "category": "bike_accessory",
            "price_vnd": 350000,
            "image_url": "https://img.example/bike.jpg",
        },
        {
            "url": "https://shopee.vn/anime-random",
            "title": "Mô hình anime gửi ngẫu nhiên",
            "category": "toy",
            "price_vnd": 99000,
            "image_url": "https://img.example/anime.jpg",
        },
    ]

    def fake_fetch_datafeeds(**kwargs):
        return {"ok": True, "products": products, "source_url": "fake://source"}

    monkeypatch.setattr("affilipilot.workflows.auto_source_hunter.fetch_datafeeds", fake_fetch_datafeeds)
    outbox = tmp_path / "outbox.json"
    summary = run_auto_source_hunter(
        db_path=tmp_path / "affilipilot.db",
        batch_key="niche-test",
        work_dir=tmp_path / "run",
        outbox_path=outbox,
        source_config=None,
        collect_limit=2,
        select_limit=1,
        real_accesstrade=False,
        queue_telegram=True,
    )

    assert summary["ok"] is False
    assert summary["positioning"] == "Mua sắm thông minh — món nhỏ, tiện, đáng tiền, dễ kiểm chứng."
    assert summary["niche_blocked_count"] >= 1
    assert summary["queued_digest"] is True
    messages = Outbox(outbox).load()
    assert messages and messages[0].kind == "digest"
