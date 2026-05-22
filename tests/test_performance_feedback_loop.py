import sqlite3
from pathlib import Path

from affilipilot.analytics.feedback import build_feedback_report, render_feedback_report
from affilipilot.cli import main
from affilipilot.db import AffiliPilotDB
from affilipilot.models import ProductCandidate
from affilipilot.publishing.lifecycle import record_publish_event
from affilipilot.scoring.product_score import score_product


def _save_batch(db_path: Path):
    image = db_path.parent / "p.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    manifest = {
        "posts": [{
            "post_id": "post_20260521_1000_ke-bep_001",
            "product": {
                "title": "Kệ để đồ nhà bếp chịu lực gọn góc bếp",
                "category": "storage",
                "price_vnd": 199000,
                "campaign_key": "SHOPEE",
                "image_path": str(image),
            },
            "score": 82,
            "score_reasons": ["niche_fit:76+9", "profit_category_bonus:storage+7"],
            "media": {"gallery_count": 1},
            "files": {"post_text": str(db_path.parent / "post.txt"), "image": str(image)},
        }]
    }
    AffiliPilotDB(db_path).save_batch("batch", "manual", manifest)


def _insert_order(db_path: Path):
    from affilipilot.accesstrade.reports import ensure_reporting_schema
    db = AffiliPilotDB(db_path)
    ensure_reporting_schema(db)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO accesstrade_orders(order_id, merchant, billing, pub_commission, status, is_confirmed, utm_content, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("order-1", "shopee", 250000, 18000, "approved", "confirmed", "post_20260521_1000_ke-bep_001", "{}"),
        )


def test_feedback_report_links_published_post_to_accesstrade_order(tmp_path):
    db = tmp_path / "affilipilot.db"
    _save_batch(db)
    record_publish_event(db, batch_key="batch", post_id="post_20260521_1000_ke-bep_001", state="published", facebook_post_id="fb_1", reason="test")
    _insert_order(db)

    report = build_feedback_report(db, batch_key="batch")

    assert report["summary"]["published_posts"] == 1
    assert report["summary"]["orders"] == 1
    assert report["summary"]["confirmed_orders"] == 1
    assert report["summary"]["commission_vnd"] == 18000
    item = report["items"][0]
    assert item["facebook_post_id"] == "fb_1"
    assert item["category"] == "storage"
    assert "has_confirmed_order" in item["signals"]
    rendered = render_feedback_report(report)
    assert "performance feedback loop" in rendered
    assert "Top posts:" in rendered


def test_performance_feedback_cli_writes_json(tmp_path, capsys):
    db = tmp_path / "affilipilot.db"
    _save_batch(db)
    record_publish_event(db, batch_key="batch", post_id="post_20260521_1000_ke-bep_001", state="published", facebook_post_id="fb_1")
    _insert_order(db)
    out = tmp_path / "feedback.json"

    code = main(["performance-feedback", "--db", str(db), "--batch-key", "batch", "--out", str(out)])

    stdout = capsys.readouterr().out
    assert code == 0
    assert "Published posts: 1" in stdout
    assert out.exists()
    assert "post_20260521_1000_ke-bep_001" in out.read_text(encoding="utf-8")


def test_score_product_accepts_feedback_category_bonus(monkeypatch):
    product = ProductCandidate(
        url="https://shopee.vn/p",
        title="Kệ để đồ nhà bếp chịu lực gọn góc bếp",
        category="storage",
        price_vnd=199000,
        image_url="https://example.com/p.jpg",
    )
    base = score_product(product)
    monkeypatch.setenv("AFFILIPILOT_FEEDBACK_CATEGORY_BONUS", "storage:6,electronics:-3")
    boosted = score_product(product)
    assert boosted["score"] >= base["score"]
    assert "performance_feedback_category:storage+6" in boosted["reasons"]
