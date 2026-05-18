import json

from affilipilot.accesstrade.client import AccesstradeConfig, build_tracking_payload, check_accesstrade_config
from affilipilot.cli import main
from affilipilot.publishing.facebook import FacebookConfig, check_facebook_config, dry_run_publish, publish_post
from affilipilot.publishing.gate import evaluate_publish_gate
from affilipilot.publishing.ready_package import build_ready_to_post_package
from affilipilot.workflows.approval import create_approval_batch, decide_post


def test_publish_gate_blocks_without_facebook(tmp_path):
    post_file = tmp_path / "post.txt"
    post_file.write_text("Caption\n\nBài viết có chứa link tiếp thị liên kết.", encoding="utf-8")
    post = {"compliance": {"status": "pass"}, "files": {"post_text": str(post_file)}}
    result = evaluate_publish_gate(post, approved=True, facebook_verified=False, dry_run_passed=False)
    assert not result.allowed
    assert "facebook_not_verified" in result.reasons


def test_publish_gate_allows_when_all_conditions_true(tmp_path):
    post_file = tmp_path / "post.txt"
    post_file.write_text("Caption\n\nBài viết có chứa link tiếp thị liên kết.", encoding="utf-8")
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    post = {
        "product": {"url": "https://go.isclix.com/deep_link/abc", "image_path": str(image_file)},
        "compliance": {"status": "pass"},
        "files": {"post_text": str(post_file)},
    }
    result = evaluate_publish_gate(post, approved=True, facebook_verified=True, dry_run_passed=True)
    assert result.allowed


def test_ready_package_for_approved_post_without_facebook(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000", encoding="utf-8")
    db_path = tmp_path / "affilipilot.db"
    out_dir = tmp_path / "drafts"
    create_approval_batch(input_file, out_dir, db_path, batch_key="batch", limit=1)
    decide_post(db_path, batch_key="batch", post_id="post_20260516_001", decision="approved")
    package = build_ready_to_post_package(db_path, batch_key="batch", out_dir=tmp_path / "ready")
    assert package["ready_count"] == 1
    assert package["ready"][0]["publish_gate"]["fallback_required"] is True


def test_approve_ready_cli_builds_ready_package_and_plan(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "token")
    input_file = tmp_path / "links.txt"
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={image_file}", encoding="utf-8")
    db_path = tmp_path / "affilipilot.db"
    create_approval_batch(input_file, tmp_path / "drafts", db_path, batch_key="batch", limit=1)
    decide_post(db_path, batch_key="batch", post_id="post_20260516_001", decision="approved")

    code = main(["approve-ready", "--db", str(db_path), "--batch-key", "batch", "--out-dir", str(tmp_path / "approved")])

    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot approve-ready: batch" in out
    assert "Ready package: 1 ready" in out
    assert (tmp_path / "approved" / "ready" / "ready_package.json").exists()
    plan = json.loads((tmp_path / "approved" / "facebook-plan.json").read_text(encoding="utf-8"))
    assert plan["publishable_count"] == 1


def test_facebook_config_health_and_dry_run():
    health = check_facebook_config(FacebookConfig(page_id="", page_access_token=""))
    assert not health.verified
    result = dry_run_publish("hello", FacebookConfig(page_id="page", page_access_token="token"))
    assert result["dry_run"] is True
    assert result["would_publish"] is True


def test_real_facebook_publish_requires_config():
    try:
        publish_post(post_text="hello", config=FacebookConfig(page_id="", page_access_token=""))
    except RuntimeError as exc:
        assert "Facebook config is not verified" in str(exc)
    else:
        raise AssertionError("publish_post should require verified config")


def test_accesstrade_payload_and_health():
    health = check_accesstrade_config(AccesstradeConfig(token=""))
    assert not health.configured
    assert "missing_ACCESSTRADE_CAMPAIGN_ID" in health.reasons
    ready = check_accesstrade_config(AccesstradeConfig(token="tok", campaign_id="123"))
    assert ready.configured
    payload = build_tracking_payload(campaign_id="123", urls=["https://shopee.vn/a"], utm={"sub1": "facebook", "utm_source": "facebook"})
    assert payload["campaign_id"] == "123"
    assert payload["sub1"] == "facebook"
    assert payload["url_enc"] is True
