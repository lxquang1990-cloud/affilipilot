from affilipilot.accesstrade.client import AccesstradeCampaign, AccesstradeConfig, build_response_audit, build_tracking_payload, classify_tracking_response, create_tracking_link, extract_affiliate_url, extract_short_url, load_campaigns_from_values
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input


def test_extract_affiliate_url_shapes():
    assert extract_affiliate_url({"data": {"short_link": "https://go.isclix.com/a"}}) == "https://go.isclix.com/a"
    assert extract_affiliate_url({"data": [{"affiliate_url": "https://pub.accesstrade.vn/b", "short_link": "https://short.ac/a"}]}) == "https://pub.accesstrade.vn/b"
    assert extract_short_url({"data": [{"affiliate_url": "https://pub.accesstrade.vn/b", "short_link": "https://short.ac/a"}]}) == "https://short.ac/a"
    official = {"data": {"success_link": [{"aff_link": "https://tracking.accesstrade.vn/deep_link/a", "short_link": "https://shorten.accesstrade.vn/abc", "url_origin": "https://shopee.vn"}]}}
    assert extract_affiliate_url(official) == "https://tracking.accesstrade.vn/deep_link/a"
    assert extract_short_url(official) == "https://shorten.accesstrade.vn/abc"
    assert extract_affiliate_url({}) == ""

def test_tracking_response_status_and_audit():
    success = {"data": {"success_link": [{"aff_link": "https://go.isclix.com/deep", "short_link": "https://shorten.ac/abc"}], "error_link": [], "suspend_url": []}}
    assert classify_tracking_response(success, affiliate_url=extract_affiliate_url(success), short_url=extract_short_url(success)) == "success_with_shortlink"
    audit = build_response_audit(success)
    assert audit["success_link_count"] == 1
    assert audit["has_short_url"] is True

    suspended = {"data": {"success_link": [], "error_link": [], "suspend_url": [{"url": "https://bad.example"}]}}
    assert classify_tracking_response(suspended) == "suspended"

    errored = {"data": {"success_link": [], "error_link": [{"url": "https://bad.example", "message": "invalid"}], "suspend_url": []}}
    assert classify_tracking_response(errored) == "error"


def test_create_tracking_link_dry_run_requires_config():
    result = create_tracking_link(url="https://shopee.vn/a", utm={}, config=AccesstradeConfig(token="", campaign_id=""), dry_run=True)
    assert not result.ok
    assert "missing_ACCESSTRADE_TOKEN" in result.error


def test_create_tracking_link_blocks_status_code_03_without_fallback(monkeypatch):
    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return b'{"message":"Campaign does not exists or not running","status":false,"status_code":"03"}'
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Resp())
    config = AccesstradeConfig(token="tok", campaigns={"LAZADA": AccesstradeCampaign(key="LAZADA", campaign_id="222", channel_id="chan", domains=("lazada.vn",))})
    result = create_tracking_link(url="https://www.lazada.vn/products/a.html", utm={}, config=config, dry_run=False, campaign_key="LAZADA")
    assert not result.ok
    assert result.affiliate_url == ""
    assert result.short_url == ""
    assert result.link_status == "missing_link"
    assert "Campaign does not exists or not running" in result.error


def test_create_tracking_link_dry_run_ok():
    result = create_tracking_link(url="https://shopee.vn/a", utm={}, config=AccesstradeConfig(token="tok", campaign_id="123"), dry_run=True)
    assert result.ok
    assert result.affiliate_url == "https://shopee.vn/a"


def test_multi_campaign_detection_and_override():
    config = AccesstradeConfig(
        token="tok",
        campaigns={
            "SHOPEE": AccesstradeCampaign(key="SHOPEE", campaign_id="111", domains=("shopee.vn",)),
            "LAZADA": AccesstradeCampaign(key="LAZADA", campaign_id="222", channel_id="chan", domains=("lazada.vn",)),
        },
    )
    lazada = create_tracking_link(url="https://www.lazada.vn/a", utm={}, config=config, dry_run=True)
    assert lazada.ok
    assert lazada.campaign_key == "LAZADA"
    assert lazada.payload["campaign_id"] == "222"
    assert lazada.payload["channel_id"] == "chan"

    forced = create_tracking_link(url="https://www.lazada.vn/a", utm={}, config=config, dry_run=True, campaign_key="shopee")
    assert forced.campaign_key == "SHOPEE"
    assert forced.payload["campaign_id"] == "111"


def test_load_campaigns_from_env_values_with_legacy():
    campaigns = load_campaigns_from_values({
        "ACCESSTRADE_CAMPAIGN_LAZADA": "222",
        "ACCESSTRADE_CAMPAIGN_LAZADA_CHANNEL_ID": "chan",
        "ACCESSTRADE_CAMPAIGN_LAZADA_DOMAINS": "lazada.vn,lazada.com",
        "ACCESSTRADE_SHOPEE_CAMPAIGN_ID": "111",
    })
    assert campaigns["LAZADA"].campaign_id == "222"
    assert campaigns["LAZADA"].channel_id == "chan"
    assert campaigns["SHOPEE"].campaign_id == "111"


def test_convert_and_write_input(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text("https://example.com/a?aff=1 | title=A | image_url=https://cdn.example/a.jpg", encoding="utf-8")
    out = tmp_path / "converted.json"
    summary = convert_input_links(f, out, dry_run=True)
    assert summary["total"] == 1
    converted = write_converted_input(out, tmp_path / "converted.txt")
    text = converted.read_text(encoding="utf-8")
    assert "title=A" in text
    assert "image_url=https://cdn.example/a.jpg" in text


def test_convert_blocks_lazada_channel_before_accesstrade(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text("https://www.lazada.vn/tag/khan-sua-em-be/ | title=Khăn sữa | category=baby_care", encoding="utf-8")
    out = tmp_path / "converted.json"
    summary = convert_input_links(f, out, dry_run=False, campaign_key="LAZADA")
    assert summary["ok_count"] == 0
    assert summary["failed_count"] == 1
    item = summary["items"][0]
    assert item["preflight"]["classification"]["kind"] == "tag"
    assert item["result"]["error"] == "marketplace_preflight_block:LAZADA:tag"
    converted = write_converted_input(out, tmp_path / "converted.txt")
    assert converted.read_text(encoding="utf-8") == ""


def test_convert_blocks_shopee_shortlink_until_resolved(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text("https://s.shopee.vn/abc123 | title=Short", encoding="utf-8")
    out = tmp_path / "converted.json"
    summary = convert_input_links(f, out, dry_run=False, campaign_key="SHOPEE")
    assert summary["failed_count"] == 1
    assert summary["items"][0]["preflight"]["classification"]["kind"] == "shortlink"
    assert summary["items"][0]["result"]["error"] == "marketplace_preflight_block:SHOPEE:shortlink"
