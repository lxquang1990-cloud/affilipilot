from pathlib import Path

from affilipilot.publishing.gate import evaluate_publish_gate
from affilipilot.publishing.requirements import check_affiliate_link, check_media, is_affiliate_link
from affilipilot.sources.manual_input import parse_link_lines


def test_affiliate_link_detection_blocks_plain_demo():
    assert not is_affiliate_link("https://shopee.vn/example-storage")
    assert not is_affiliate_link("https://shopee.vn/product-normal")
    assert is_affiliate_link("https://go.isclix.com/deep_link/abc")
    assert is_affiliate_link("https://s.shopee.vn/abc")


def test_parse_media_and_affiliate_metadata():
    products = parse_link_lines("https://shopee.vn/a | title=X | image_url=https://img.example/x.jpg | affiliate_url=https://go.isclix.com/a")
    p = products[0]
    assert p.image_url.startswith("https://img")
    assert p.affiliate_url.startswith("https://go.isclix")


def test_publish_gate_blocks_missing_affiliate_and_media(tmp_path):
    post_file = tmp_path / "post.txt"
    post_file.write_text("Caption\n\nBài viết có chứa link tiếp thị liên kết.", encoding="utf-8")
    post = {"product": {"url": "https://shopee.vn/example"}, "compliance": {"status": "pass"}, "files": {"post_text": str(post_file)}}
    result = evaluate_publish_gate(post, approved=True, facebook_verified=True, dry_run_passed=True)
    assert not result.allowed
    assert "link_not_affiliate_tracking" in result.reasons
    assert "missing_product_media" in result.reasons


def test_publish_gate_allows_affiliate_and_media(tmp_path):
    post_file = tmp_path / "post.txt"
    post_file.write_text("Caption\n\nBài viết có chứa link tiếp thị liên kết.", encoding="utf-8")
    post = {
        "product": {"url": "https://go.isclix.com/deep_link/abc", "image_url": "https://cdn.example/product.jpg"},
        "compliance": {"status": "pass"},
        "files": {"post_text": str(post_file)},
    }
    result = evaluate_publish_gate(post, approved=True, facebook_verified=True, dry_run_passed=True)
    assert result.allowed


def test_requirement_helpers():
    post = {"product": {"url": "https://go.isclix.com/a", "image_url": "https://img.example/a.jpg"}}
    assert check_affiliate_link(post).passed
    assert check_media(post).passed
