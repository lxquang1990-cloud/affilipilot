from __future__ import annotations

from affilipilot.content.compliance import check_mom_baby_compliance, default_affiliate_disclosure
from affilipilot.models import ContentDraft, ProductCandidate


def _product_name(product: ProductCandidate) -> str:
    return product.title.strip() or "sản phẩm này"


def _price_hint(product: ProductCandidate) -> str:
    if product.price_vnd:
        price = f"{product.price_vnd:,}".replace(",", ".")
        return f"Giá tham khảo khoảng {price}đ, có thể thay đổi theo thời điểm."
    return "Giá/ưu đãi có thể thay đổi theo thời điểm, mẹ kiểm tra lại trước khi mua nhé."


def generate_safe_facebook_draft(product: ProductCandidate) -> ContentDraft:
    name = _product_name(product)
    category = product.category.lower()

    if category == "storage":
        hook = "Góc đồ của bé rất dễ bừa chỉ sau một buổi. Một món nhỏ nhưng giúp mẹ đỡ mất thời gian tìm đồ."
        body = f"Mẹ có thể tham khảo {name} nếu đang muốn sắp xếp bỉm, khăn, bình sữa hoặc đồ lặt vặt của bé gọn hơn. Điểm đáng chú ý là dùng cho việc tổ chức đồ trong nhà, không cần nói quá công dụng. {_price_hint(product)}"
    elif category == "feeding":
        hook = "Chuẩn bị đồ ăn dặm/bình sữa gọn hơn thì buổi sáng của mẹ cũng nhẹ hơn một chút."
        body = f"{name} phù hợp để mẹ tham khảo khi cần chia, cất hoặc mang theo đồ dùng ăn dặm/bỉm sữa. Nên kiểm tra kỹ chất liệu, dung tích và đánh giá shop trước khi mua. {_price_hint(product)}"
    elif category == "home_safety":
        hook = "Khi bé bắt đầu bò/đi men, những góc nhỏ trong nhà cũng đáng để để ý hơn."
        body = f"{name} là nhóm đồ hỗ trợ sắp xếp/an toàn sinh hoạt trong nhà. Mẹ nên xem kỹ kích thước, chất liệu và cách lắp trước khi chọn. {_price_hint(product)}"
    elif category == "toy":
        hook = "Một món đồ chơi tốt không cần quảng cáo quá đà — chỉ cần bé thích khám phá và mẹ thấy phù hợp."
        body = f"{name} có thể là lựa chọn để mẹ tham khảo cho giờ chơi của bé. Nên chọn theo độ tuổi, chất liệu và mức độ an toàn, không nên kỳ vọng hay cam kết tác dụng phát triển vượt trội. {_price_hint(product)}"
    else:
        hook = "Một gợi ý nhỏ cho mẹ đang tìm đồ tiện dùng trong sinh hoạt hằng ngày với bé."
        body = f"Mẹ có thể tham khảo {name}. Trước khi mua, nên kiểm tra kỹ thông tin shop, đánh giá, chất liệu và mức độ phù hợp với bé/nhà mình. {_price_hint(product)}"

    cta = "Nếu thấy hợp nhu cầu, mẹ xem chi tiết ở link nhé."
    disclosure = default_affiliate_disclosure()
    compliance = check_mom_baby_compliance("\n\n".join([hook, body, cta, disclosure]), category=product.category)
    return ContentDraft(product=product, hook=hook, body=body, cta=cta, disclosure=disclosure, compliance=compliance)
