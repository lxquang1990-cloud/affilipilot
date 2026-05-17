from affilipilot.workflows.affiliate_ready import validate_affiliate_ready_input


def test_validate_affiliate_ready_input_blocks_plain_link(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text("https://shopee.vn/a | title=A", encoding="utf-8")
    result = validate_affiliate_ready_input(f)
    assert not result.passed
    assert result.failed_count == 1
    assert "link_not_affiliate_tracking" in result.items[0].reasons


def test_validate_affiliate_ready_input_passes_tracking_and_media(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text("https://go.isclix.com/a | title=A | image_url=https://cdn.example/a.jpg", encoding="utf-8")
    result = validate_affiliate_ready_input(f)
    assert result.passed
    assert result.passed_count == 1
