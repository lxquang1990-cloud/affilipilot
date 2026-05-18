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
    text.write_text("Camera chụp con rõ hơn, pin dùng cả ngày, bộ nhớ rộng cho ảnh video gia đình. Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.", encoding="utf-8")
    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8\xff\x00")
    post = {
        "product": {"title": "Điện thoại Itel P55 Plus NFC 8GB 256GB", "category": "electronics", "url": "https://go.isclix.com/deep_link/v5/x/y", "original_url": "https://cellphones.com.vn/dien-thoai-itel-p55-plus-8gb-256gb.html", "image_url": "https://cdn2.cellphones.com.vn/media/catalog/product/a.jpg"},
        "files": {"post_text": str(text), "image": str(img)},
        "media": {"ok": True, "local_path": str(img), "source": "product_card_image", "confidence": "high"},
    }
    result = evaluate_quality_gate(post)
    assert result.passed

def test_quality_gate_blocks_electronics_mother_baby_template_mismatch(tmp_path):
    text = tmp_path / "post.txt"
    text.write_text("Một gợi ý nhỏ cho mẹ đang tìm đồ tiện dùng trong sinh hoạt hằng ngày với bé. Mẹ có thể tham khảo Samsung Galaxy S26 Ultra. Bài viết có chứa link tiếp thị liên kết. #CellphoneSAffiliate", encoding="utf-8")
    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8\xff\x00")
    post = {
        "product": {"title": "Samsung Galaxy S26 Ultra 12GB 256GB", "category": "electronics", "url": "https://go.isclix.com/deep_link/v5/x/y", "original_url": "https://cellphones.com.vn/dien-thoai-samsung-galaxy-s26-ultra.html", "image_url": "https://cdn2.cellphones.com.vn/media/catalog/product/a.jpg"},
        "files": {"post_text": str(text), "image": str(img)},
        "media": {"ok": True, "local_path": str(img), "source": "product_card_image", "confidence": "high"},
    }
    result = evaluate_quality_gate(post)
    assert not result.passed
    assert "audience_product_mismatch" in result.reasons
    assert "missing_electronics_benefit_angle" in result.reasons
    assert "internal_hashtag_primary" in result.reasons
