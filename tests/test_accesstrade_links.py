from affilipilot.accesstrade.client import AccesstradeConfig, build_tracking_payload, create_tracking_link, extract_affiliate_url
from affilipilot.workflows.accesstrade_links import convert_input_links, write_converted_input


def test_extract_affiliate_url_shapes():
    assert extract_affiliate_url({"data": {"short_link": "https://go.isclix.com/a"}}) == "https://go.isclix.com/a"
    assert extract_affiliate_url({"data": [{"affiliate_url": "https://pub.accesstrade.vn/b"}]}) == "https://pub.accesstrade.vn/b"
    assert extract_affiliate_url({}) == ""


def test_create_tracking_link_dry_run_requires_config():
    result = create_tracking_link(url="https://shopee.vn/a", utm={}, config=AccesstradeConfig(token="", campaign_id=""), dry_run=True)
    assert not result.ok
    assert "missing_ACCESSTRADE_TOKEN" in result.error


def test_create_tracking_link_dry_run_ok():
    result = create_tracking_link(url="https://shopee.vn/a", utm={}, config=AccesstradeConfig(token="tok", campaign_id="123"), dry_run=True)
    assert result.ok
    assert result.affiliate_url == "https://shopee.vn/a"


def test_convert_and_write_input(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text("https://shopee.vn/a | title=A | image_url=https://cdn.example/a.jpg", encoding="utf-8")
    out = tmp_path / "converted.json"
    summary = convert_input_links(f, out, dry_run=True)
    assert summary["total"] == 1
    converted = write_converted_input(out, tmp_path / "converted.txt")
    text = converted.read_text(encoding="utf-8")
    assert "title=A" in text
    assert "image_url=https://cdn.example/a.jpg" in text
