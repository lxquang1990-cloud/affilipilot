from __future__ import annotations

from affilipilot.content.compliance import check_mom_baby_compliance, default_affiliate_disclosure
from urllib.parse import urlparse

from affilipilot.models import ContentDraft, ProductCandidate


def _product_name(product: ProductCandidate) -> str:
    title = product.title.strip()
    if not title:
        return "sản phẩm này"
    separators = [" - ", " | ", "("]
    short = title
    for sep in separators:
        if sep in short:
            short = short.split(sep, 1)[0].strip()
    words = short.split()
    if len(words) > 12:
        short = " ".join(words[:12]).strip()
    return short or title[:90].strip()


def _price_hint(product: ProductCandidate) -> str:
    if product.price_vnd:
        price = f"{product.price_vnd:,}".replace(",", ".")
        return f"Giá tham khảo khoảng {price}đ, có thể thay đổi theo thời điểm."
    return "Giá/ưu đãi có thể thay đổi theo thời điểm, mẹ kiểm tra lại trước khi mua nhé."


def _interest_hashtags(product: ProductCandidate) -> str:
    link = product.tracking_url or product.affiliate_url or product.url
    host = urlparse(link).netloc.lower()
    text = f"{link} {product.notes} {product.title} {product.category}".lower()
    if "cellphones" in text or "cellphones" in host or product.category.lower() in {"electronics", "phone", "smartphone"}:
        return "#samsung #S26Ultra #reviewdienthoai #congnghe2025"
    if "khăn sữa" in text or "khan sua" in text or product.category.lower() == "baby_care":
        return "#khansua #mevabe #dodungchobe #mebim"
    if "feeding" in text or product.category.lower() == "feeding":
        return "#andam #mevabe #dodungchobe #mebim"
    if "storage" in text or product.category.lower() == "storage":
        return "#sapxepnhacua #dodungchobe #mebim #nhacuasachgon"
    if "lazada" in text or "lazada" in host:
        return "#mevabe #giadinh #muasamthongminh"
    if "shopee" in text or "shopee" in host:
        return "#mevabe #giadinh #muasamthongminh"
    return "#muasamthongminh #reviewsanpham"


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
    elif category in {"electronics", "phone", "smartphone"}:
        hook = "Mẹ hay chụp ảnh con mà ảnh mờ, thiếu sáng hoặc bé chạy quá nhanh?"
        body = f"{name} là nhóm điện thoại nên chỉ đáng cân nhắc nếu mẹ thật sự cần camera tốt để lưu khoảnh khắc của con, pin khỏe cho ngày dài và bộ nhớ rộng cho ảnh/video gia đình. Trước khi mua, nên so sánh camera, pin, dung lượng và chính sách bảo hành thay vì chỉ nhìn cấu hình. {_price_hint(product)}"
    elif category == "baby_care":
        title = name.lower()
        if "khăn" in title:
            hook = "Khăn sữa là món dùng liên tục mỗi ngày: lau mặt, lau sữa, lót vai, mang theo khi ra ngoài. Chọn sai thì rất nhanh xù, thô hoặc bí da bé."
            body = f"{name} đáng để mẹ xem nếu đang cần khăn mềm, dễ giặt và đủ dùng xoay vòng trong ngày. Nên ưu tiên chất liệu cotton/muslin/sợi tre, bề mặt mềm, ít bụi vải và kích thước phù hợp túi đồ của bé. {_price_hint(product)}"
        else:
            hook = "Đồ chăm bé nên bắt đầu từ việc dùng có thường xuyên không, có dễ vệ sinh không và có hợp da bé không."
            body = f"{name} là nhóm đồ mẹ nên xem kỹ chất liệu, kích thước, cách vệ sinh và đánh giá thật trước khi mua. Không cần mua vì quảng cáo hay giá rẻ nếu chưa khớp nhu cầu hằng ngày của bé. {_price_hint(product)}"
    else:
        hook = f"Nếu đang cân nhắc {name}, hãy xem nó có thật sự giải quyết một nhu cầu cụ thể trong nhà không."
        body = f"Nên kiểm tra kỹ chất liệu, kích thước, đánh giá shop và bối cảnh sử dụng trước khi mua. {_price_hint(product)}"

    cta = "Xem chi tiết sản phẩm, đánh giá shop và giá hiện tại ở link bên dưới nhé."
    disclosure = default_affiliate_disclosure() + "\n" + _interest_hashtags(product)
    compliance = check_mom_baby_compliance("\n\n".join([hook, body, cta, disclosure]), category=product.category)
    return ContentDraft(product=product, hook=hook, body=body, cta=cta, disclosure=disclosure, compliance=compliance)
