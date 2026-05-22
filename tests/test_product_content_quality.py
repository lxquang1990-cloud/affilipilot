from affilipilot.content.product_quality import evaluate_product_content


def test_product_content_blocks_generic_wrong_category_copy():
    product = {"title": "Set 5 khăn sữa trẻ em TILO", "category": "baby_care"}
    text = """
    Đang cân nhắc Set 5 khăn sữa trẻ em TILO? Đừng chỉ nhìn giá — hãy xem nó giải quyết nhu cầu nào của mình trước.
    Sản phẩm này phù hợp hơn khi nhu cầu, ngân sách và bối cảnh dùng thật sự rõ ràng.
    Xem chi tiết, so sánh cấu hình/màu và kiểm tra giá hiện tại ở link bên dưới nhé.
    #tiepthilienket
    """
    result = evaluate_product_content(product, text)
    assert not result.passed
    assert "generic_ai_affiliate_copy" in result.reasons
    assert "internal_affiliate_hashtag" in result.reasons
    assert "wrong_category_language:baby_care_tech_terms" in result.reasons


def test_product_content_passes_specific_khan_sua_copy():
    product = {"title": "Set 5 khăn sữa trẻ em TILO vải muslin cotton", "category": "baby_care"}
    text = """
    Khăn sữa là món dùng liên tục mỗi ngày: lau mặt, lau sữa, lót vai, mang theo khi ra ngoài.
    Set khăn muslin cotton này đáng xem nếu mẹ cần khăn mềm, dễ giặt, ít bụi vải và hợp da bé.
    Xem chi tiết sản phẩm, đánh giá shop và giá hiện tại ở link bên dưới nhé.
    Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.
    #khansua #dodungchobe #muasamthongminh
    """
    result = evaluate_product_content(product, text)
    assert result.passed, result.reasons
    assert result.score >= 75
