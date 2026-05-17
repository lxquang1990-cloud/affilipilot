from pathlib import Path

from affilipilot.quality import evaluate_quality_gate, is_product_detail_url


def test_product_detail_url_detection():
    assert is_product_detail_url("https://cellphones.com.vn/dien-thoai-itel-p55-plus-8gb-256gb.html")
    assert is_product_detail_url("https://www.lazada.vn/products/foo-i123-s456.html")
    assert not is_product_detail_url("https://www.lazada.vn/tag/binh-thia-an-dam/")


def test_quality_gate_blocks_tag_page_with_low_provenance(tmp_path):
    text = tmp_path / "post.txt"
    text.write_text("Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ. Nội dung đủ dài để qua check.", encoding="utf-8")
    post = {
        "product": {"url": "https://go.isclix.com/deep_link/v5/x/y", "original_url": "https://www.lazada.vn/tag/binh-thia/", "image_url": "https://img.example/product.jpg"},
        "files": {"post_text": str(text), "image": str(tmp_path / "img.jpg")},
        "media": {"ok": True, "local_path": str(tmp_path / "img.jpg"), "source": "tag_page_harvest", "confidence": "low"},
    }
    (tmp_path / "img.jpg").write_bytes(b"\xff\xd8\xff\x00")
    result = evaluate_quality_gate(post)
    assert not result.passed
    assert "source_not_product_detail" in result.reasons
    assert "untrusted_media_source:tag_page_harvest" in result.reasons


def test_quality_gate_passes_trusted_product_detail(tmp_path):
    text = tmp_path / "post.txt"
    text.write_text("Caption chuẩn có tiếp thị liên kết và thông tin kiểm tra trước khi mua. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.", encoding="utf-8")
    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8\xff\x00")
    post = {
        "product": {"url": "https://go.isclix.com/deep_link/v5/x/y", "original_url": "https://cellphones.com.vn/dien-thoai-itel-p55-plus-8gb-256gb.html", "image_url": "https://cdn2.cellphones.com.vn/media/catalog/product/a.jpg"},
        "files": {"post_text": str(text), "image": str(img)},
        "media": {"ok": True, "local_path": str(img), "source": "product_card_image", "confidence": "high"},
    }
    result = evaluate_quality_gate(post)
    assert result.passed
