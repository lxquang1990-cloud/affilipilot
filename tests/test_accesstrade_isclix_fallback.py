from affilipilot.accesstrade.client import AccesstradeConfig, AccesstradeCampaign, build_isclix_deep_link, create_tracking_link


def test_build_isclix_deep_link_contains_campaign_channel_and_encoded_url():
    link = build_isclix_deep_link(
        url="https://cellphones.com.vn/dien-thoai.html",
        campaign_id="campaign123",
        channel_id="channel456",
        utm={"sub1": "telegram", "sub4": "product"},
    )
    assert link.startswith("https://go.isclix.com/deep_link/v5/campaign123/channel456?")
    assert "url_enc=" in link
    assert "sub1=telegram" in link
    assert "sub4=product" in link


def test_create_tracking_link_fallbacks_on_campaign_not_running_response(monkeypatch):
    import affilipilot.accesstrade.client as client

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"message":"Campaign does not exists or not running","status":false,"status_code":"03"}'

    monkeypatch.setattr(client.urllib.request, "urlopen", lambda req, timeout=30: Resp())
    config = AccesstradeConfig(
        token=".token",
        campaigns={"CELLPHONES": AccesstradeCampaign(key="CELLPHONES", campaign_id="campaign123", channel_id="channel456", domains=("cellphones.com.vn",))},
    )
    res = create_tracking_link(url="https://cellphones.com.vn/dien-thoai.html", utm={"sub1":"telegram"}, config=config, dry_run=False, campaign_key="CELLPHONES")
    assert res.ok
    assert "go.isclix.com/deep_link/v5/campaign123/channel456" in res.affiliate_url
