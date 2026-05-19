import pytest

from affilipilot.publishing.facebook import _caption_link


def test_caption_link_requires_real_shortlink_not_raw_isclix(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_SHORT_BASE_URL", "https://snail.example")
    full = "https://go.isclix.com/deep_link/v5/abc/def?url_enc=xyz&sub1=facebook"
    with pytest.raises(RuntimeError, match="raw affiliate URL"):
        _caption_link(full)
    assert _caption_link("https://snail.example/go/product-a") == "https://snail.example/go/product-a"
    assert _caption_link("https://shorten.asia/mM5wrgby") == "https://shorten.asia/mM5wrgby"
    assert "..." not in _caption_link("https://snail.example/go/product-a")
