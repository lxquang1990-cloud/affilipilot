from pathlib import Path

from affilipilot.analytics.digest import build_daily_digest
from affilipilot.budget import record_spend
from affilipilot.config import load_config, render_config_status
from affilipilot.workflows.approval import create_approval_batch, decide_post


def test_load_config_without_secret(tmp_path):
    cfg = load_config(tmp_path / "missing.env")
    assert not cfg.accesstrade_token_present
    assert cfg.daily_budget_vnd == 30000
    assert "Accesstrade token: missing" in render_config_status(cfg)


def test_load_config_with_secret_markers(tmp_path):
    env = tmp_path / "affilipilot.env"
    env.write_text("ACCESSTRADE_TOKEN=abc\nACCESSTRADE_CAMPAIGN_LAZADA=222\nFACEBOOK_PAGE_ID=page\nFACEBOOK_PAGE_ACCESS_TOKEN=tok\n9ROUTER_API_KEY=router\n9ROUTER_API_ENDPOINT=http://127.0.0.1:20128/v1\nAFFILIPILOT_DAILY_BUDGET_VND=20000\n", encoding="utf-8")
    cfg = load_config(env)
    assert cfg.accesstrade_token_present
    assert cfg.accesstrade_campaign_present
    assert cfg.accesstrade_campaign_count == 1
    assert cfg.facebook_page_id_present
    assert cfg.router_key_present
    assert cfg.router_endpoint_present
    assert cfg.daily_budget_vnd == 20000


def test_budget_modes(tmp_path):
    path = tmp_path / "budget.json"
    status = record_spend(path, phase="draft", amount_vnd=10000, cap_vnd=30000)
    assert status.mode == "normal"
    status = record_spend(path, phase="judge", amount_vnd=15000, cap_vnd=30000)
    assert status.mode == "cheap_model_only"
    status = record_spend(path, phase="extra", amount_vnd=6000, cap_vnd=30000)
    assert status.mode == "hard_stop"


def test_daily_digest(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_url=https://cdn.example/test.jpg", encoding="utf-8")
    db_path = tmp_path / "affilipilot.db"
    create_approval_batch(input_file, tmp_path / "out", db_path, batch_key="batch", limit=1)
    decide_post(db_path, batch_key="batch", post_id="post_20260516_001", decision="approved")
    digest = build_daily_digest(db_path, batch_key="batch")
    assert "Approved: 1" in digest
    assert "Giỏ sắp xếp" in digest
