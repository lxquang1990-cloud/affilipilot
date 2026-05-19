from pathlib import Path

import pytest

from affilipilot.content.page_fit import evaluate_page_audience_fit
from affilipilot.links.shortlink import visible_link_for_post
from affilipilot.publishing.facebook import _caption_link
from affilipilot.models import ProductCandidate
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.publishing.facebook_plan import build_graph_payload


def test_caption_link_requires_real_short_link(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_SHORT_BASE_URL", "https://snail.example")
    assert _caption_link("https://snail.example/go/toy-car") == "https://snail.example/go/toy-car"
    with pytest.raises(RuntimeError, match="raw affiliate URL"):
        _caption_link("https://go.isclix.com/deep_link/v5/campaign/channel?url_enc=abc")


def test_visible_link_uses_product_short_url_only():
    product = {
        "url": "https://go.isclix.com/deep_link/v5/raw",
        "tracking_url": "https://go.isclix.com/deep_link/v5/raw",
        "short_url": "https://snail.example/go/khan-sua",
    }
    assert visible_link_for_post(product) == "https://snail.example/go/khan-sua"


def test_page_audience_fit_blocks_baby_product_on_tech_page():
    result = evaluate_page_audience_fit({"category": "toy", "title": "Đồ chơi cho bé"}, page_audience="tech")
    assert not result.passed
    assert "page_audience_tech_product_mother_baby" in result.reasons

def test_page_audience_fit_infers_tech_from_page_name():
    result = evaluate_page_audience_fit({"category": "baby_play", "title": "Bể bơi cho bé"}, page_name="ITNews Vietnam")
    assert not result.passed
    assert "page_audience_tech_product_mother_baby" in result.reasons

def test_baby_pool_copy_is_specific_and_not_generic_template():
    draft = generate_safe_facebook_draft(ProductCandidate(title="Bể bơi xếp gọn PVC an toàn cho bé", category="baby_play", price_vnd=999000, url="https://lazada.vn/p"))
    text = draft.full_text
    assert "chỉ đáng mua nếu nó giải quyết đúng" not in text
    assert "Điểm nên kiểm tra trước" not in text
    assert "người lớn ngồi gần quan sát" in text
    assert "van xả nước" in text
    assert "#chobevui" in text

def test_baby_jumper_copy_is_specific_to_active_play():
    draft = generate_safe_facebook_draft(ProductCandidate(title="Nhà nhún nhảy cho bé lưới bảo hộ kép an toàn", category="baby_play", url="https://shopee.vn/p"))
    text = draft.full_text
    assert "nghịch nước" not in text
    assert "lưới bảo hộ" in text
    assert "tải trọng" in text
    assert "người lớn quan sát" in text


def test_multi_photo_plan_caps_at_four_images():
    graph = build_graph_payload(
        page_id="page",
        message="caption",
        link="https://snail.example/go/a",
        image_paths=["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg"],
    )
    assert graph["strategy"] == "multi_photo"
    assert graph["payload"]["local_image_paths"] == ["1.jpg", "2.jpg", "3.jpg", "4.jpg"]
