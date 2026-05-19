from pathlib import Path

from affilipilot.analytics.conversions import render_conversion_summary, summarize_conversions, upsert_conversion
from affilipilot.models import ProductCandidate
from affilipilot.observability.circuit_breaker import check_circuit, set_kill_switch
from affilipilot.observability.event_log import EventLog, read_events
from affilipilot.scoring.confidence import compute_confidence
from affilipilot.scoring.tier import Tier, TierConfig, classify_tier


def test_event_log_writes_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    EventLog(path).event("unit_test", batch_key="b1")
    events = read_events(path)
    assert events[-1]["event"] == "unit_test"
    assert events[-1]["batch_key"] == "b1"


def test_circuit_kill_switch(tmp_path):
    kill = tmp_path / "KILL"
    log = tmp_path / "events.jsonl"
    state = tmp_path / "state.json"
    state.write_text('{"enabled": true}\n')
    assert check_circuit(kill_path=kill, event_log_path=log, state_path=state).allowed
    status = set_kill_switch(True, kill_path=kill, event_log_path=log)
    assert not status.allowed
    assert status.reason == "manual_kill_switch"
    status = set_kill_switch(False, kill_path=kill, event_log_path=log)
    assert status.allowed


def test_confidence_and_tier_for_good_product():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Máy hút bụi cầm tay mini có bảo hành",
        category="home_appliance",
        price_vnd=299000,
        image_url="https://example.com/p.jpg",
        image_urls=["https://example.com/p1.jpg", "https://example.com/p2.jpg"],
        video_urls=["https://example.com/v.mp4"],
        notes="rating=4.8;sold=200;shopee_verified",
    )
    score, signals = compute_confidence(product)
    assert score >= 0.7
    assert classify_tier(score, signals, TierConfig(auto_threshold=0.8, soft_threshold=0.7)) in {Tier.AUTO, Tier.SOFT_GATE}


def test_conversion_summary(tmp_path):
    db = tmp_path / "a.db"
    upsert_conversion(db, {"sub_id": "ap_b1_d1", "order_id": "o1", "order_status": "approved", "commission_vnd": 12000, "order_value_vnd": 200000})
    summary = summarize_conversions(db)
    assert summary.total_orders == 1
    assert summary.commission_vnd == 12000
    assert "Commission" in render_conversion_summary(summary)
