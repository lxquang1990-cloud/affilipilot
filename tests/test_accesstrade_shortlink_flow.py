from dataclasses import asdict

from affilipilot.accesstrade.client import AccesstradeLinkResult
from affilipilot.workflows.accesstrade_links import write_converted_input


def test_accesstrade_short_url_is_written_to_converted_input(tmp_path):
    summary = {
        "items": [
            {
                "result": asdict(AccesstradeLinkResult(
                    ok=True,
                    original_url="https://www.lazada.vn/products/pdp-i1.html",
                    affiliate_url="https://go.isclix.com/deep_link/v5/full",
                    short_url="https://short.ac/abc123",
                )),
                "product": {
                    "url": "https://www.lazada.vn/products/pdp-i1.html",
                    "title": "Đồ chơi cho bé",
                    "category": "toy",
                    "affiliate_url": "https://go.isclix.com/deep_link/v5/full",
                    "tracking_url": "https://go.isclix.com/deep_link/v5/full",
                    "short_url": "https://short.ac/abc123",
                },
            }
        ]
    }
    source = tmp_path / "converted.json"
    source.write_text(__import__("json").dumps(summary, ensure_ascii=False), encoding="utf-8")
    out = write_converted_input(source, tmp_path / "converted.txt")
    text = out.read_text(encoding="utf-8")
    assert "short_url=https://short.ac/abc123" in text
    assert "affiliate_url=https://go.isclix.com/deep_link/v5/full" in text
